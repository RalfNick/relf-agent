"""A node child uses the original History ToolAction, never a model decision."""

from dataclasses import asdict

import pytest

from relf_agent import (
    GraphNode,
    GraphWorkflowSpec,
    NodeExecutorRegistry,
    NodeExecutorSpec,
    Scope,
    ToolExecutionOwner,
    ToolRegistry,
    ValueRef,
)
from relf_agent.errors import DefinitionMismatch, ValidationError
from relf_agent.temporal_activities import TemporalRuntime
from relf_agent.temporal_parent_state import TemporalParentState
from relf_agent.temporal_state import TemporalRunState
from relf_agent.types import digest, submission_request


class UnusedProvider:
    identity = {"kind": "node-tests-unused-model", "version": "1"}

    async def complete(self, messages, tools):
        raise AssertionError("A declared node never calls a model")


class Echo:
    identity = {"kind": "temporal-node-state-echo", "version": "1"}

    async def execute(self, input, config, context):
        return input


def node_manifest(*, approval=False, output_schema=None, cost=2):
    registry = NodeExecutorRegistry()
    registry.register(
        NodeExecutorSpec(
            "echo",
            "Echo complete JSON",
            "read_only",
            cost=cost,
            requires_approval=approval,
            output_schema=output_schema,
        ),
        Echo(),
    )
    runtime = TemporalRuntime(
        providers={"default": UnusedProvider()},
        tools=ToolRegistry(),
        tool_execution=ToolExecutionOwner(version="node-state-tests-1"),
    )
    manifest = runtime.orchestration_release
    alias = "__relf_node__:echo"
    manifest.update(workflow_node_protocol=1, workflow_nodes=registry.manifest([alias]))
    manifest["tools"].update(registry.manifests([alias]))
    return manifest


def request(value, *, output_schema=None):
    scope = asdict(Scope())
    parent_id, parent_epoch, node_id = "parent-run", "parent-epoch", "echo"
    command = "ralf-child:" + digest([scope, parent_id, "0:echo"])
    run_id = "ralf-temporal-" + digest([scope, command])
    body = {
        "definition": {
            "kind": "executor",
            "name": node_id,
            "version": "1",
            "steps": [{"tool": "__relf_node__:echo", "output_schema": output_schema}],
        },
        "input": {"input": value, "config": {}},
        "budget": 8,
        "session_id": None,
        "workflow_node": {
            "version": 1,
            "scope": scope,
            "parent_run_id": parent_id,
            "parent_execution_epoch": parent_epoch,
            "parent_release_digest": "d" * 64,
            "node_id": node_id,
            "planning_revision": 0,
            "run_id": run_id,
            "command_id": command,
        },
    }
    return run_id, command, body


def make_state(value, **options):
    run_id, command, body = request(value)
    return TemporalRunState(
        run_id, asdict(Scope()), command, body, node_manifest(**options), "epoch"
    )


def admit(state, envelope):
    proof = {
        name: envelope[name]
        for name in ("scope", "run_id", "action_id", "release_digest", "execution_epoch")
    }
    proof.update(request_digest=digest(envelope), invocation_id="1" * 32)
    result = state.admit_tool_dispatch(proof)
    assert result["allowed"] and result["claimed"]
    return {k: v for k, v in proof.items() if k != "run_id"}


def acknowledge(state):
    # Model the existing Workflow ACK Activity loop after its completed reply.
    while state.pending_acks:
        evidence = state.pending_acks.pop(0)
        state.active_evidence_ack = evidence["action_id"]
        state._emit("effect_journal_acknowledged", {"action_id": evidence["action_id"], "ok": True})
        state.active_evidence_ack = None


@pytest.mark.parametrize("value", [None, False, 0, "", [1, None], {"value": 7}])
def test_pure_node_result_waits_for_actual_end_and_ack_without_model(value):
    state = make_state(value)
    action, envelope = state.next_operation()
    assert action["kind"] == "tool" and action["arguments"] == {"input": value, "config": {}}
    assert envelope["node_request"] == state.request
    assert state.budget["reserved"] == 2 and state.decisions == 0
    ended = admit(state, envelope)
    state.accept_tool(action["id"], {"ok": True, "result": value, "source": "node-executor"})
    assert state.state == "running" and state.result is None
    assert state.next_operation() is None and not state.quiescent
    state.tool_execution_ended(ended)
    assert state.next_operation() is None and state.state == "running"
    acknowledge(state)
    assert state.next_operation() is None
    assert state.state == "succeeded" and state.result == value and state.budget["spent"] == 2
    assert [a["kind"] for a in state.actions] == ["tool"] and state.messages == []


def test_approval_replay_keeps_one_action_and_original_effect_key():
    state = make_state({"value": 7}, approval=True)
    assert state.next_operation() is None and state.state == "waiting_approval"
    (pending,) = state.snapshot()["pending"]
    assert state.budget["spent"] == state.budget["reserved"] == 0
    payload = {
        "kind": "approve",
        "scope": state.scope,
        "action_id": pending["action_id"],
        "digest": pending["digest"],
        "approved": True,
    }
    first = state.command("approve", payload)
    assert state.command("approve", payload) == first
    action, envelope = state.next_operation()
    effect_key = action["effect_key"]
    ended = admit(state, envelope)
    state.accept_tool(action["id"], {"ok": True, "result": 7})
    state.tool_execution_ended(ended)
    acknowledge(state)
    state.next_operation()
    assert state.state == "succeeded" and len(state.actions) == 1
    assert state.actions[0]["effect_key"] == effect_key and state.budget["spent"] == 2


def test_unknown_receipt_never_redispatches_after_manual_effect_confirmation():
    state = make_state(None)
    action, envelope = state.next_operation()
    ended = admit(state, envelope)
    state.operation_unknown(action["id"], "worker-lost")
    assert state.next_operation() is None and state.budget["unknown"] == 2
    state.accept_tool(
        action["id"], {"ok": True, "result": None, "source": "operator"}, reconciled=True
    )
    acknowledge(state)
    assert state.next_operation() is None and not state.quiescent
    state.tool_execution_ended(ended)
    state.next_operation()
    assert state.state == "succeeded" and state.budget["spent"] == 2 and len(state.actions) == 1


def test_cancelled_node_does_not_become_successful_after_late_receipt():
    state = make_state(7)
    action, envelope = state.next_operation()
    ended = admit(state, envelope)
    state.command("cancel", {"kind": "cancel", "scope": state.scope})
    assert not state.quiescent
    state.accept_tool(action["id"], {"ok": True, "result": 7})
    state.tool_execution_ended(ended)
    acknowledge(state)
    state.next_operation()
    assert state.state == "cancelled" and state.result is None and state.quiescent


def test_output_schema_failure_keeps_confirmed_receipt_and_never_repeats_tool():
    state = make_state(7, output_schema={"type": "integer"})
    action, envelope = state.next_operation()
    ended = admit(state, envelope)
    state.accept_tool(action["id"], {"ok": True, "result": "wrong"})
    state.tool_execution_ended(ended)
    acknowledge(state)
    state.next_operation()
    assert state.state == "failed" and state.error["code"] == "validation_error"
    assert state.actions[0]["status"] == "completed" and state.actions[0]["result"] == "wrong"
    assert state.next_operation() is None and len(state.actions) == 1


def test_graph_projects_private_child_and_keeps_original_parent_capacity():
    graph = GraphWorkflowSpec(
        "nodes", [GraphNode("echo", executor="echo")], output=ValueRef("echo")
    )
    manifest = node_manifest()
    parent = TemporalParentState(
        "parent-run",
        asdict(Scope()),
        "submit",
        submission_request(graph, [1, None], budget=16),
        manifest,
        "parent-epoch",
    )
    (call,) = parent.next_calls()
    assert call["request"]["definition"]["kind"] == "executor"
    assert call["request"]["input"] == {"input": [1, None], "config": {}}
    assert parent.budget["reserved"] == 2
    parent.mark_started(call["run_id"])
    child = TemporalRunState(
        call["run_id"], parent.scope, call["command_id"], call["request"], manifest, "child-epoch"
    )
    action, envelope = child.next_operation()
    ended = admit(child, envelope)
    child.accept_tool(action["id"], {"ok": True, "result": [1, None]})
    parent.observe(call["run_id"], {"scope": child.scope, **child.diagnostics()})
    assert parent.budget["reserved"] == 2 and parent.next_calls() == []
    child.tool_execution_ended(ended)
    acknowledge(child)
    child.next_operation()
    parent.observe(call["run_id"], {"scope": child.scope, **child.diagnostics()})
    parent.next_calls()
    assert parent.state == "succeeded" and parent.result == [1, None]
    assert parent.budget["spent"] == 2 and parent.budget["reserved"] == 0


@pytest.mark.parametrize("cost", [0, 1, 9])
def test_parent_reserves_exact_node_cost_in_original_child_escrow(cost):
    graph = GraphWorkflowSpec(
        "parallel",
        [GraphNode("one", executor="echo"), GraphNode("two", executor="echo")],
        max_concurrency=2,
    )
    parent = TemporalParentState(
        "parent-run",
        asdict(Scope()),
        "submit",
        submission_request(graph, 7, budget=cost * 2),
        node_manifest(cost=cost),
        "parent-epoch",
    )
    calls = parent.next_calls()
    assert len(calls) == 2 and [c["cap"] for c in calls] == [cost, cost]
    assert [c["request"]["budget"] for c in calls] == [cost, cost]
    assert parent.budget["reserved"] == cost * 2 and parent.budget["spent"] == 0


def test_insufficient_node_budget_never_creates_child_intent():
    graph = GraphWorkflowSpec("one", [GraphNode("one", executor="echo")])
    parent = TemporalParentState(
        "parent-run",
        asdict(Scope()),
        "submit",
        submission_request(graph, 7, budget=1),
        node_manifest(cost=2),
        "parent-epoch",
    )
    with pytest.raises(ValidationError, match="budget"):
        parent.next_calls()
    assert parent.children == [] and parent.budget["spent"] == parent.budget["reserved"] == 0


@pytest.mark.parametrize(
    "change", ["run", "scope", "parent", "command", "arguments", "tool", "effect", "release"]
)
def test_activity_envelope_requires_original_node_identity(change):
    from copy import deepcopy

    from relf_agent.temporal_node_protocol import validate_node_envelope

    state = make_state(7)
    _, envelope = state.next_operation()
    validate_node_envelope(envelope, state.manifest)
    bad = deepcopy(envelope)
    if change == "run":
        bad["run_id"] = "another-run"
    elif change == "scope":
        bad["scope"]["principal"] = "another-principal"
    elif change == "parent":
        bad["node_request"]["workflow_node"]["parent_run_id"] = "another-parent"
    elif change == "command":
        bad["node_request"]["workflow_node"]["command_id"] = "another-command"
    elif change == "arguments":
        bad["arguments"] = {"input": 9, "config": {}}
    elif change == "tool":
        bad["tool"] = "__relf_node__:other"
    elif change == "effect":
        bad["effect_key"] = "another-effect"
    else:
        bad["release_digest"] = "0" * 64
    with pytest.raises((DefinitionMismatch, ValidationError)):
        validate_node_envelope(bad, state.manifest)


@pytest.mark.parametrize(
    "parent", [None, ("another-parent", "parent-epoch"), ("parent-run", "another-epoch")]
)
def test_actual_workflow_parent_must_match_original_node_origin(monkeypatch, parent):
    from types import SimpleNamespace

    from temporalio.exceptions import ApplicationError

    from relf_agent.temporal_workflow import TemporalRunWorkflow, workflow

    run_id, command, body = request(7)
    actual = None if parent is None else SimpleNamespace(workflow_id=parent[0], run_id=parent[1])
    monkeypatch.setattr(
        workflow, "info", lambda: SimpleNamespace(workflow_id=run_id, run_id="epoch", parent=actual)
    )
    with pytest.raises(ApplicationError, match="actual parent"):
        TemporalRunWorkflow(
            {
                "scope": asdict(Scope()),
                "command_id": command,
                "request": body,
                "manifest": node_manifest(),
                "activity_timeout": 3,
            }
        )


def test_actual_workflow_parent_accepts_one_original_node_child(monkeypatch):
    from types import SimpleNamespace

    from relf_agent.temporal_workflow import TemporalRunWorkflow, workflow

    run_id, command, body = request(7)
    actual = SimpleNamespace(workflow_id="parent-run", run_id="parent-epoch")
    monkeypatch.setattr(
        workflow, "info", lambda: SimpleNamespace(workflow_id=run_id, run_id="epoch", parent=actual)
    )
    child = TemporalRunWorkflow(
        {
            "scope": asdict(Scope()),
            "command_id": command,
            "request": body,
            "manifest": node_manifest(),
            "activity_timeout": 3,
        }
    )
    assert child.state.request == body and child.state.messages == []


def test_deferred_node_ack_blocks_success_until_original_ack_retry():
    state = make_state(7)
    action, envelope = state.next_operation()
    ended = admit(state, envelope)
    state.accept_tool(action["id"], {"ok": True, "result": 7})
    state.tool_execution_ended(ended)
    original = state.pending_acks.pop(0)
    state.deferred_acks.append(original)
    assert state.next_operation() is None and state.state == "running"
    assert state.diagnostics()["workflow"]["evidence_ack_pending"] is True
    state.command("drive", {"kind": "drive", "scope": state.scope})
    state.retry_blocked()
    assert state.pending_acks == [original] and state.deferred_acks == []
    acknowledge(state)
    state.next_operation()
    assert state.state == "succeeded" and state.result == 7
    assert len(state.actions) == 1 and state.budget["spent"] == 2


async def legacy_tool(arguments, context):
    return arguments


def test_unmarked_legacy_release_keeps_same_prefix_ordinary_tool_behavior():
    from relf_agent import AgentSpec, ToolSpec

    alias = "__relf_node__:legacy"
    tools = ToolRegistry()
    tools.register(ToolSpec(alias, "Legacy ordinary tool", {"type": "object"}), legacy_tool)
    runtime = TemporalRuntime(providers={"default": UnusedProvider()}, tools=tools)
    state = TemporalRunState(
        "legacy",
        asdict(Scope()),
        "submit",
        submission_request(AgentSpec("old", "Read", tools=(alias,)), "task", budget=8),
        runtime.manifest,
    )
    model, _ = state.next_operation()
    state.accept_model(
        model["id"],
        {
            "ok": True,
            "output": None,
            "tool_calls": [{"name": alias, "arguments": {}, "call_id": "call"}],
            "usage": None,
        },
    )
    action, envelope = state.next_operation()
    assert action["kind"] == "tool" and action["tool"] == alias
    assert "node_request" not in envelope and "workflow_node_protocol" not in runtime.manifest


@pytest.mark.parametrize("nested", [False, True])
def test_graph_host_tool_allowlist_refuses_node_before_child_admission(nested):
    from relf_agent import AgentSpec, TeamSpec, TemporalExecutionPolicy
    from relf_agent.temporal_state import validate_request

    manifest = node_manifest()
    manifest["execution_policy"] = TemporalExecutionPolicy(allowed_tools=("ordinary",)).identity
    graph = GraphWorkflowSpec("restricted", [GraphNode("echo", executor="echo")])
    definition = TeamSpec("team", {"nested": graph}) if nested else graph
    body = submission_request(definition, 7, budget=2)
    with pytest.raises(ValidationError, match="forbidden"):
        validate_request(body, manifest)
    parent = TemporalParentState.__new__(TemporalParentState)
    with pytest.raises(ValidationError, match="forbidden"):
        parent.__init__("parent-run", asdict(Scope()), "submit", body, manifest, "parent-epoch")
    assert getattr(parent, "children", []) == []
    validate_request(submission_request(AgentSpec("ordinary", "Answer"), 7), manifest)
