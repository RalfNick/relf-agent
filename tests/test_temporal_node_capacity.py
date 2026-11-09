"""Original History fences capacity-only refusals without a new business attempt."""

import copy
import json
from dataclasses import asdict

import pytest

import relf_agent as r
from relf_agent import temporal_node_capacity as capacity
from relf_agent.errors import DefinitionMismatch
from relf_agent.temporal_activities import TemporalRuntime
from relf_agent.temporal_parent_state import TemporalParentState
from relf_agent.temporal_state import TemporalRunState
from relf_agent.types import canonical, digest, submission_request

from .test_temporal_workflow_nodes_state import Echo, acknowledge


def make_state():
    registry = r.NodeExecutorRegistry()
    registry.register(r.NodeExecutorSpec("echo", "Echo", "read_only", cost=2), Echo())
    runtime = TemporalRuntime(providers={}, tools=r.ToolRegistry(), workflow_executors=registry)
    manifest = json.loads(canonical(runtime.orchestration_release))
    parent = TemporalParentState(
        "capacity-parent",
        asdict(r.Scope()),
        "submit",
        submission_request(
            r.GraphWorkflowSpec("capacity", [r.GraphNode("one", executor="echo")]),
            [False, 0, None],
            budget=4,
        ),
        manifest,
        "parent-epoch",
    )
    (call,) = parent.next_calls()
    state = TemporalRunState(
        call["run_id"], parent.scope, call["command_id"], call["request"], manifest, "child-epoch"
    )
    return runtime, state


def waiting_state():
    runtime, state = make_state()
    action, request = state.next_operation()
    capacity.begin_window(state, action, now=100.0, total_seconds=15.0)
    response = capacity.refusal(request)
    state.accept_tool(action["id"], response)
    capacity.delay(state, now=100.0)
    return runtime, state, action, request, response


def guard(state, request, invocation="a" * 32):
    return state.admit_tool_dispatch(
        {
            name: request[name]
            for name in ("scope", "run_id", "action_id", "release_digest", "execution_epoch")
        }
        | {"request_digest": digest(request), "invocation_id": invocation}
    )


def test_capacity_refusal_keeps_one_reserved_action_and_no_history_claim():
    _, state, action, request, _ = waiting_state()
    assert state.state == "running" and state.error is None
    assert state.budget["reserved"] == 2 and state.budget["spent"] == 0
    assert len(state.actions) == len(action["attempts"]) == 1
    assert state.active_action is None and state.next_operation() is None
    assert capacity.waiting(state) is action
    assert "invocation_id" not in state.tool_executions[action["id"]]
    assert request["node_capacity_ordinal"] == 0


def test_history_retry_keeps_effect_attempt_and_budget_but_fences_old_transport():
    _, state, action, request, response = waiting_state()
    fixed = (action["id"], action["effect_key"], copy.deepcopy(action["attempts"]), state.budget)
    state.accept_tool(action["id"], response)  # duplicate observation is not a second refusal
    denied = guard(state, request)
    assert denied["allowed"] is denied["claimed"] is False
    assert capacity.resume(state, now=100.2)
    next_action, next_request = state.next_operation()
    assert next_action is action and next_request["node_capacity_ordinal"] == 1
    assert capacity.transport_id(action).endswith(":capacity:1")
    assert (action["id"], action["effect_key"], action["attempts"], state.budget) == fixed
    with pytest.raises(DefinitionMismatch):
        guard(state, request)
    assert guard(state, next_request)["allowed"] is True
    ended = {
        name: next_request[name]
        for name in ("scope", "action_id", "release_digest", "execution_epoch")
    }
    state.tool_execution_ended(
        ended | {"request_digest": digest(next_request), "invocation_id": "a" * 32}
    )
    state.accept_tool(action["id"], {"ok": True, "result": [False, 0, None]})
    acknowledge(state)
    state.next_operation()
    assert state.state == "succeeded" and state.budget["spent"] == 2


@pytest.mark.parametrize("terminal", ["cancel", "timeout"])
def test_wait_cancel_or_expiry_finishes_only_original_unstarted_attempt(terminal):
    _, state, action, request, _ = waiting_state()
    if terminal == "cancel":
        state.command("cancel", {"kind": "cancel", "scope": state.scope})
        assert state.state == "cancelled"
    else:
        assert not capacity.resume(state, now=115.0)
        assert state.state == "failed" and state.error["code"] == "node_capacity_timeout"
    assert state.budget["reserved"] == state.budget["unknown"] == state.budget["spent"] == 0
    assert state.quiescent and state.next_operation() is None
    assert action["attempts"][0]["status"] == "not_dispatched"
    denied = guard(state, request)
    assert denied["allowed"] is denied["claimed"] is False


@pytest.mark.parametrize("field", ["scope", "request_digest", "ordinal", "execution_epoch"])
def test_invalid_capacity_proof_cannot_release_or_retry_unknown_work(field):
    _, state = make_state()
    action, request = state.next_operation()
    capacity.begin_window(state, action, now=100.0, total_seconds=15.0)
    response = capacity.refusal(request)
    response["node_capacity"][field] = "wrong"
    state.accept_tool(action["id"], response)
    assert state.state == "waiting_reconciliation"
    assert state.budget["unknown"] == 2 and capacity.waiting(state) is None
    assert state.next_operation() is None


def test_already_claimed_invocation_cannot_be_retried_as_capacity():
    _, state = make_state()
    action, request = state.next_operation()
    capacity.begin_window(state, action, now=100.0, total_seconds=15.0)
    assert guard(state, request)["allowed"]
    state.accept_tool(action["id"], capacity.refusal(request))
    assert state.state == "waiting_reconciliation" and state.budget["unknown"] == 2
    assert capacity.waiting(state) is None


def test_history_reconstruction_keeps_timer_window_and_original_budget():
    _, state, action, request, _ = waiting_state()
    restored = copy.deepcopy(state)
    assert capacity.waiting(restored)["id"] == action["id"]
    assert capacity.delay(restored, now=100.0) == pytest.approx(0.1)
    assert capacity.resume(restored, now=100.1)
    resumed, envelope = restored.next_operation()
    assert resumed["effect_key"] == request["effect_key"]
    assert envelope["node_capacity_ordinal"] == 1 and restored.budget["reserved"] == 2


@pytest.mark.parametrize("field,value", [("ok", 0), ("dispatched", 0), ("handler_not_started", 1)])
def test_capacity_flags_are_exact_booleans_not_python_numeric_equals(field, value):
    _, state = make_state()
    action, request = state.next_operation()
    capacity.begin_window(state, action, now=100.0, total_seconds=15.0)
    response = capacity.refusal(request)
    response[field] = value
    state.accept_tool(action["id"], response)
    assert state.state == "waiting_reconciliation" and state.budget["unknown"] == 2


@pytest.mark.parametrize("kind", ["nan", "object", "cycle", "depth"])
def test_non_json_capacity_proof_retains_unknown_without_native_exception(kind):
    _, state = make_state()
    action, request = state.next_operation()
    response = capacity.refusal(request)
    bad = {"nan": float("nan"), "object": object(), "cycle": {}, "depth": {}}[kind]
    if kind == "cycle":
        bad["self"] = bad
    elif kind == "depth":
        for _ in range(1200):
            bad = {"next": bad}
    response["node_capacity"]["bad"] = bad
    state.accept_tool(action["id"], response)
    assert state.state == "waiting_reconciliation" and state.budget["unknown"] == 2


def test_ack_transport_identity_uses_original_action_not_end_callback_order():
    _, state = make_state()
    action, request = state.next_operation()
    assert guard(state, request)["allowed"]
    early, late = copy.deepcopy(state), copy.deepcopy(state)
    proof = {
        name: request[name] for name in ("scope", "action_id", "release_digest", "execution_epoch")
    }
    proof |= {"request_digest": digest(request), "invocation_id": "a" * 32}
    early.tool_execution_ended(proof)
    early.accept_tool(action["id"], {"ok": True, "result": 7})
    late.accept_tool(action["id"], {"ok": True, "result": 7})
    assert len(early.event_log) != len(late.event_log)
    first = capacity.ack_transport_id(early, early.pending_acks[0])
    assert capacity.ack_transport_id(late, late.pending_acks[0]) == first
    assert first == "ack:" + action["id"] + ":capacity:1"
    assert capacity.ack_transport_id(early, early.pending_acks[0]).endswith(":capacity:2")
