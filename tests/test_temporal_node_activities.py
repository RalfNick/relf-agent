"""Fixed private async nodes execute through the original Temporal Tool protocol."""

import asyncio
import copy
import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from relf_agent import (
    GraphNode,
    NodeExecutorRegistry,
    NodeExecutorSpec,
    Scope,
    ToolRegistry,
    ToolSpec,
)
from relf_agent.errors import (
    AuthorizationDenied,
    CloseIncomplete,
    DefinitionMismatch,
    ValidationError,
)
from relf_agent.executors import EffectObservation
from relf_agent.temporal_activities import TemporalRuntime
from relf_agent.types import canonical, digest

from .test_temporal_engine import Provider


class Node:
    identity = {"kind": "temporal-business-node", "version": "1"}

    def __init__(self):
        self.calls = []

    async def execute(self, input, config, context):
        self.calls.append((input, config, context.effect_key))
        return {"value": input, "config": config}


def nodes(component=None, *, effect="read_only", **options):
    registry = NodeExecutorRegistry()
    registry.register(
        NodeExecutorSpec("business", "Business", effect, **options),
        Node() if component is None else component,
    )
    return registry


def runtime(registry=None, **options):
    return TemporalRuntime(
        providers={},
        tools=ToolRegistry(),
        workflow_executors=nodes() if registry is None else registry,
        **options,
    )


def test_provider_free_node_release_pins_private_tools_without_publishing_them_to_agents():
    component = Node()
    registered = nodes(component)
    worker = runtime(registered)
    manifest = worker.manifest
    assert manifest["providers"] == {}
    assert manifest["workflow_node_protocol"] == 1
    assert manifest["workflow_nodes"] == registered.manifest(["__relf_node__:business"])
    assert (
        manifest["tools"]["__relf_node__:business"]
        == registered.tool("__relf_node__:business").manifest
    )
    assert worker.tools._tools == {}
    assert (
        manifest["tool_execution_protocol"]["owner"]["behavior_version"]
        == "workflow-node-default-1"
    )
    assert component.calls == []
    asyncio.run(worker.close_context_execution())


def test_omitted_node_selection_preserves_original_release():
    old = TemporalRuntime(providers={"default": Provider()}, tools=ToolRegistry())
    unchanged = TemporalRuntime(
        providers={"default": Provider()},
        tools=ToolRegistry(),
        workflow_executors=None,
    )
    assert unchanged.manifest == old.manifest
    assert not any(key.startswith("workflow_node") for key in old.manifest)
    with pytest.raises(ValidationError, match="providers"):
        TemporalRuntime(providers={}, tools=ToolRegistry())


@pytest.mark.parametrize("value", [False, {}, object()])
def test_node_registration_rejects_non_registry_objects(value):
    with pytest.raises(ValidationError):
        runtime(value)


def test_private_node_writes_require_the_original_durable_journal():
    with pytest.raises(ValidationError, match="Journal"):
        runtime(nodes(effect="unqueryable_write"))


def test_public_tools_cannot_collide_with_private_node_namespace():
    tools = ToolRegistry()

    async def read(arguments, context):
        return arguments

    tools.register(ToolSpec("__relf_node__:foreign", "Read", {"type": "object"}), read)
    with pytest.raises(ValidationError):
        TemporalRuntime(providers={}, tools=tools, workflow_executors=nodes())


@pytest.mark.parametrize("drift", ["registry", "adapter", "identity", "method", "registration"])
def test_node_release_drift_is_refused_without_any_business_call(drift):
    component = Node()
    registered = nodes(component)
    worker = runtime(registered)
    if drift == "registry":
        worker.workflow_executors = nodes()
    elif drift == "adapter":
        registered._executor = nodes().executor
    elif drift == "identity":
        component.identity = {"kind": "temporal-business-node", "version": "changed"}
    elif drift == "method":

        async def replacement(input, config, context):
            return "changed"

        component.execute = replacement
    else:
        registered.register(NodeExecutorSpec("later", "Later", "read_only"), Node())
    try:
        with pytest.raises(DefinitionMismatch):
            worker.validate_release()
        assert component.calls == []
    finally:
        asyncio.run(worker.close_context_execution())


class Journal:
    identity = {"kind": "offline-node-journal", "version": "1"}

    def __init__(self):
        self.records = {}
        self.events = []

    async def begin(self, envelope):
        key = envelope.context.effect_key
        self.events.append(("begin", key))
        if key in self.records:
            return {"execute": False, "observation": self.records[key]}
        self.records[key] = None
        return {"execute": True}

    async def received(self, envelope, observation):
        self.events.append(("received", envelope.context.effect_key))
        self.records[envelope.context.effect_key] = observation

    async def observation(self, envelope):
        self.events.append(("query", envelope.context.effect_key))
        return self.records.get(envelope.context.effect_key)

    async def acknowledge(self, envelope, observation):
        self.events.append(("ack", envelope.context.effect_key))


def node_envelope(worker, *, orchestration=False):
    from relf_agent.temporal_bindings import request_release_digest
    from relf_agent.temporal_node_protocol import action_id, child_request
    from relf_agent.workflow import lower_node

    # Real Activity payloads cross the SDK JSON converter; tuple-valued
    # dataclass metadata in default planners is represented as JSON arrays.
    manifest = json.loads(
        canonical(worker.orchestration_release if orchestration else worker.manifest)
    )
    scope = asdict(Scope())
    parent = SimpleNamespace(
        scope=scope,
        run_id="parent",
        epoch="parent-epoch",
        release_digest=digest(["parent-release", manifest]),
        planning_revision=0,
        manifest=manifest,
    )
    lowered = lower_node(GraphNode("business", executor="business", config={"mode": "fixed"}))
    body = child_request(parent, lowered, {"input": 7, "config": {"mode": "fixed"}}, 8)
    action = action_id(body)
    run = body["workflow_node"]["run_id"]
    tool = manifest["tools"]["__relf_node__:business"]
    return {
        "runtime_manifest": manifest,
        "scope": scope,
        "run_id": run,
        "action_id": action,
        "attempt_id": action + ":attempt:1",
        "effect_key": "ralf-temporal:" + digest([scope, run, action]),
        "execution_epoch": "child-epoch",
        "tool": tool["name"],
        "tool_manifest": tool,
        "arguments": body["input"],
        "operation_digest": digest(
            {
                "run_id": run,
                "action_id": action,
                "scope": scope,
                "tool": tool,
                "arguments": body["input"],
            }
        ),
        "release_digest": request_release_digest(body, manifest),
        "node_request": body,
    }


def callbacks(request, ends):
    async def guard(fixed, *, invocation_id):
        assert fixed == request
        return {name: fixed[name] for name in ("run_id", "action_id", "release_digest")} | {
            "invocation_id": invocation_id,
            "allowed": True,
            "claimed": True,
        }

    async def ended(proof):
        assert proof["request_digest"] == digest(request)
        assert proof["scope"] == request["scope"]
        assert proof["action_id"] == request["action_id"]
        ends.append(proof)

    return guard, ended


@pytest.mark.parametrize("orchestration", [False, True])
def test_node_execute_uses_original_tool_owner_and_preserves_raw_journal_observation(orchestration):
    async def run():
        component, journal = Node(), Journal()
        worker = runtime(
            nodes(component, effect="unqueryable_write", output_schema=False), journal=journal
        )
        request, ends = node_envelope(worker, orchestration=orchestration), []
        guard, ended = callbacks(request, ends)
        try:
            result = await worker.execute_tool(request, dispatch_guard=guard, on_end=ended)
            assert result == {
                "ok": True,
                "result": {"value": 7, "config": {"mode": "fixed"}},
                "source": "node-executor",
            }
            assert component.calls == [(7, {"mode": "fixed"}, request["effect_key"])]
            assert [event for event, _ in journal.events] == ["begin", "received"]
            assert journal.records[request["effect_key"]].result == result["result"]
            assert await worker.wait_context_executions(wait_timeout=2)
            assert len(ends) == 1
        finally:
            await worker.close_context_execution()

    asyncio.run(run())


@pytest.mark.parametrize("orchestration", [False, True])
def test_node_journal_recovery_never_reexecutes_original_handler(orchestration):
    async def run():
        component, journal = Node(), Journal()
        worker = runtime(nodes(component, effect="unqueryable_write"), journal=journal)
        request = node_envelope(worker, orchestration=orchestration)
        journal.records[request["effect_key"]] = EffectObservation(
            {"saved": True}, "retained-journal"
        )
        ends = []
        guard, ended = callbacks(request, ends)
        try:
            response = await worker.execute_tool(request, dispatch_guard=guard, on_end=ended)
            assert response == {"ok": True, "result": {"saved": True}, "source": "retained-journal"}
            assert component.calls == []
            queried = await worker.reconcile_tool(request)
            assert queried == response and component.calls == []
            assert await worker.acknowledge_evidence(
                {**request, "result": {"saved": True}, "source": "retained-journal"}
            ) == {"ok": True}
            assert [event for event, _ in journal.events] == ["begin", "query", "received", "ack"]
        finally:
            await worker.close_context_execution()

    asyncio.run(run())


@pytest.mark.parametrize(
    "mutation", ["missing", "parent", "scope", "arguments", "action", "release", "orchestration"]
)
@pytest.mark.parametrize("operation", ["execute", "reconcile", "acknowledge"])
def test_foreign_node_envelope_cannot_dispatch_query_or_acknowledge(mutation, operation):
    async def run():
        component, journal = Node(), Journal()
        worker = runtime(nodes(component, effect="unqueryable_write"), journal=journal)
        request = node_envelope(worker)
        forged = copy.deepcopy(request)
        if mutation == "missing":
            forged.pop("node_request")
        elif mutation == "parent":
            forged["node_request"]["workflow_node"]["parent_run_id"] = "foreign"
        elif mutation == "scope":
            forged["scope"]["principal"] = "foreign"
        elif mutation == "arguments":
            forged["arguments"]["input"] = 8
        elif mutation == "action":
            forged["action_id"] = "foreign"
        elif mutation == "orchestration":
            forged["runtime_manifest"]["orchestration"] = {"foreign": True}
        else:
            forged["release_digest"] = "f" * 64
        try:
            if operation == "execute":
                response = await worker._execute_tool(forged)
            elif operation == "reconcile":
                response = await worker.reconcile_tool(forged)
            else:
                response = await worker.acknowledge_evidence(
                    {**forged, "result": "forged", "source": "operator"}
                )
            assert response["ok"] is False
            assert component.calls == [] and journal.events == []
        finally:
            await worker.close_context_execution()

    asyncio.run(run())


def test_unknown_node_effect_is_queried_without_dispatching_original_handler():
    class Queryable(Node):
        def __init__(self):
            super().__init__()
            self.queries = []

        async def reconcile(self, input, config, context):
            self.queries.append((input, config, context.effect_key))
            return EffectObservation({"receipt": True}, "business-query")

    async def run():
        component, journal = Queryable(), Journal()
        worker = runtime(nodes(component, effect="queryable_write"), journal=journal)
        request, ends = node_envelope(worker), []
        journal.records[request["effect_key"]] = None
        guard, ended = callbacks(request, ends)
        try:
            response = await worker.execute_tool(request, dispatch_guard=guard, on_end=ended)
            assert response == {"ok": False, "code": "effect_outcome_unknown", "dispatched": True}
            assert component.calls == component.queries == []
            assert await worker.reconcile_tool(request) == {
                "ok": True,
                "result": {"receipt": True},
                "source": "business-query",
            }
            assert component.calls == []
            assert component.queries == [(7, {"mode": "fixed"}, request["effect_key"])]
            assert [event for event, _ in journal.events] == ["begin", "query", "received"]
        finally:
            await worker.close_context_execution()

    asyncio.run(run())


def test_observer_cancel_keeps_actual_node_owned_until_handler_and_end_ack_finish():
    class Blocking(Node):
        def __init__(self):
            super().__init__()
            self.entered, self.release, self.stopped = (
                asyncio.Event(),
                asyncio.Event(),
                asyncio.Event(),
            )

        async def execute(self, input, config, context):
            self.calls.append((input, config, context.effect_key))
            self.entered.set()
            try:
                await self.release.wait()
                return {"stopped": True}
            finally:
                self.stopped.set()

    async def run():
        component, journal = Blocking(), Journal()
        worker = runtime(nodes(component, effect="unqueryable_write"), journal=journal)
        request, ends = node_envelope(worker), []
        guard, ended = callbacks(request, ends)
        observer = asyncio.create_task(
            worker.execute_tool(request, dispatch_guard=guard, on_end=ended)
        )
        try:
            await asyncio.wait_for(component.entered.wait(), 2)
            observer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observer
            assert not component.stopped.is_set() and ends == []
            assert not await worker.wait_context_executions(wait_timeout=0)
            with pytest.raises(CloseIncomplete):
                await worker.close_context_execution(wait_timeout=0)
            assert not component.stopped.is_set() and ends == []
        finally:
            component.release.set()
            await worker.close_context_execution(wait_timeout=2)
        assert component.stopped.is_set() and len(ends) == 1
        assert component.calls == [(7, {"mode": "fixed"}, request["effect_key"])]
        assert journal.records[request["effect_key"]].result == {"stopped": True}
        await worker.close_context_execution(wait_timeout=0)

    asyncio.run(run())


@pytest.mark.parametrize("method", ["manifest", "tool"])
def test_direct_registry_method_drift_is_refused_even_if_it_returns_original_data(method):
    registered = nodes()
    worker = runtime(registered)
    original = getattr(registered, method)

    def replacement(*args):
        return original(*args)

    setattr(registered, method, replacement)
    try:
        with pytest.raises(DefinitionMismatch):
            worker.validate_release()
    finally:
        asyncio.run(worker.close_context_execution())


def test_node_publication_composes_with_original_context_execution_owner():
    worker = runtime(context_reads=True)
    assert worker.manifest["workflow_node_protocol"] == 1
    assert (
        "context_read_protocol" in worker.manifest and "tool_execution_protocol" in worker.manifest
    )
    asyncio.run(worker.close_context_execution())


def test_private_node_applies_host_authorization_before_journal_or_handler():
    checked = []

    def policy(scope, spec, arguments):
        checked.append((scope.principal, spec.name, arguments))
        raise AuthorizationDenied("Denied")

    async def run():
        component, journal = Node(), Journal()
        worker = runtime(
            nodes(component, effect="unqueryable_write"),
            journal=journal,
            policy=policy,
            policy_identity={"kind": "deny-node", "version": "1"},
        )
        request = node_envelope(worker)
        try:
            assert await worker._execute_tool(request) == {
                "ok": False,
                "code": "authorization_denied",
                "dispatched": False,
            }
            assert component.calls == [] and journal.events == []
            assert checked == [
                ("local-owner", "__relf_node__:business", {"input": 7, "config": {"mode": "fixed"}})
            ]
        finally:
            await worker.close_context_execution()

    asyncio.run(run())


def test_public_tools_in_node_release_keep_the_original_executor():
    async def run():
        calls = []

        async def public(arguments, context):
            calls.append(arguments)
            return "public-result"

        tools = ToolRegistry()
        tools.register(ToolSpec("public", "Public", {"type": "object"}), public)
        component = Node()
        worker = TemporalRuntime(providers={}, tools=tools, workflow_executors=nodes(component))
        request = node_envelope(worker)
        request.pop("node_request")
        request.update(
            tool="public", tool_manifest=tools.get("public").manifest, arguments={"value": 7}
        )
        ends = []
        guard, ended = callbacks(request, ends)
        try:
            assert await worker.execute_tool(request, dispatch_guard=guard, on_end=ended) == {
                "ok": True,
                "result": "public-result",
                "source": "tool-handler",
            }
            assert calls == [{"value": 7}] and component.calls == []
        finally:
            await worker.close_context_execution()

    asyncio.run(run())
