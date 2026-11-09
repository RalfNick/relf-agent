"""Local node registrations retain their original six public call entries."""

import asyncio
import copy

import pytest

import relf_agent as r
from relf_agent.errors import DefinitionMismatch

PORTS = ("manifest", "manifests", "tool", "get", "check", "validate_output")


class Echo:
    identity = {"kind": "registry-entry-echo", "version": "1"}

    def __init__(self, *, held=False):
        self.calls = []
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        if not held:
            self.release.set()

    async def execute(self, input, config, context):
        self.calls.append((input, context.effect_key, context.attempt_id))
        self.entered.set()
        await self.release.wait()
        return input


def nodes(component, registry_type=r.NodeExecutorRegistry):
    registry = registry_type()
    registry.register(
        r.NodeExecutorSpec(
            "echo", "Complete JSON echo", "read_only", output_schema={"type": "integer"}
        ),
        component,
    )
    return registry


def engine(path, registry):
    return r.LocalEngine(
        r.SQLiteStore(path), providers={}, tools=r.ToolRegistry(), workflow_executors=registry
    )


def graph(concurrency=1):
    return r.GraphWorkflowSpec(
        "pinned-registry",
        [r.GraphNode("echo", executor="echo")],
        output=r.ValueRef("echo"),
        max_concurrency=concurrency,
    )


def replace_port(registry, port):
    original, calls = getattr(registry, port), []

    def replacement(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    setattr(registry, port, replacement)
    return original, calls


@pytest.mark.parametrize("port", PORTS)
def test_public_registry_entry_drift_after_submit_refuses_before_business(tmp_path, port):
    component = Echo()
    registry = nodes(component)
    with engine(tmp_path / "run.sqlite", registry) as runtime:
        accepted = runtime.submit(graph(), 7, command_id="submit", budget=5)
        original, replacements = replace_port(registry, port)
        try:
            with pytest.raises(DefinitionMismatch):
                asyncio.run(runtime.drive(accepted.run_id))
            assert replacements == [] and component.calls == []
            assert runtime.store.run(accepted.run_id)["actions"] == []
            assert runtime.store.budget(accepted.run_id) == {"limit": 5, "held": 0, "spent": 0}
        finally:
            setattr(registry, port, original)
        assert asyncio.run(runtime.drive(accepted.run_id)).result == 7
        assert len(component.calls) == 1


@pytest.mark.parametrize("port", PORTS)
@pytest.mark.parametrize("concurrency", [1, 2])
def test_entry_drift_during_await_preserves_sqlite_receipt_and_recovers_once(
    tmp_path, port, concurrency
):
    async def exercise():
        component = Echo(held=True)
        registry, path = nodes(component), tmp_path / "run.sqlite"
        runtime = engine(path, registry)
        accepted = runtime.submit(graph(concurrency), 11, command_id="submit", budget=5)
        release = copy.deepcopy(runtime.store.run(accepted.run_id)["manifest"])
        drive = asyncio.create_task(runtime.drive(accepted.run_id))
        original = None
        try:
            await asyncio.wait_for(component.entered.wait(), 5)
            original, _ = replace_port(registry, port)
            component.release.set()
            failed = await asyncio.wait_for(drive, 5)
            assert failed.state == "failed" and failed.error["code"] == "definition_mismatch"
            assert len(component.calls) == 1
            before = runtime.store.run(accepted.run_id)
            action = before["actions"][0]
            assert action["status"] == "receipt_received"
            assert action["effect_observation"]["result"] == 11
            assert action["attempts"][0]["status"] == "receipt_received"
            assert before["manifest"] == release and before["state"] != "succeeded"
        finally:
            component.release.set()
            await asyncio.gather(drive, return_exceptions=True)
            if original is not None:
                setattr(registry, port, original)
            runtime.close()

        fresh_component = Echo()
        with engine(path, nodes(fresh_component)) as reopened:
            done = await reopened.drive(accepted.run_id)
            assert done.state == "failed" and done.error["code"] == "definition_mismatch"
            assert done.result is None
            after = reopened.store.run(accepted.run_id)
            restored = after["actions"][0]
            assert after["manifest"] == release and len(after["actions"]) == 1
            for key in ("id", "digest", "effect_key", "arguments", "effect_observation"):
                assert restored[key] == action[key]
            assert len(restored["attempts"]) == 1 and restored["status"] == "completed"
            assert reopened.store.budget(accepted.run_id) == {"limit": 5, "held": 0, "spent": 1}
            assert len(component.calls) == 1 and fresh_component.calls == []
            events = reopened.events(accepted.run_id)
            assert (await reopened.drive(accepted.run_id)).state == "failed"
            assert reopened.events(accepted.run_id) == events

    asyncio.run(exercise())


@pytest.mark.parametrize("concurrency", [1, 2])
def test_replacing_output_validation_cannot_accept_invalid_fixed_output(tmp_path, concurrency):
    component = Echo()
    registry = nodes(component)
    with engine(tmp_path / "run.sqlite", registry) as runtime:
        accepted = runtime.submit(graph(concurrency), "not-an-integer", command_id="submit")
        original = registry.validate_output
        registry.validate_output = lambda alias, result: result
        try:
            with pytest.raises(DefinitionMismatch):
                asyncio.run(runtime.drive(accepted.run_id))
            assert component.calls == []
        finally:
            registry.validate_output = original
        done = asyncio.run(runtime.drive(accepted.run_id))
        assert done.state == "failed" and done.error["code"] == "validation_error"
        assert len(component.calls) == 1


def test_initial_custom_public_ports_keep_normal_extension_and_unused_registrations(tmp_path):
    class Custom(r.NodeExecutorRegistry):
        def manifest(self, aliases):
            return super().manifest(aliases)

        def manifests(self, aliases):
            return super().manifests(aliases)

        def tool(self, alias):
            return super().tool(alias)

        def get(self, name):
            return super().get(name)

        def check(self, aliases=()):
            return super().check(aliases)

        def validate_output(self, alias, result):
            return super().validate_output(alias, result)

    component, unused = Echo(), Echo()
    registry = nodes(component, Custom)
    with engine(tmp_path / "run.sqlite", registry) as runtime:
        accepted = runtime.submit(graph(), 13, command_id="submit")
        manifest = runtime.store.run(accepted.run_id)["manifest"]
        registry.register(r.NodeExecutorSpec("unused", "Unused", "read_only"), unused)
        unused.identity = {"kind": "changed-unused", "version": "2"}
        assert asyncio.run(runtime.drive(accepted.run_id)).result == 13
        assert runtime.store.run(accepted.run_id)["manifest"] == manifest
    assert len(component.calls) == 1 and unused.calls == []


def test_plain_agent_does_not_select_or_validate_unused_node_ports(tmp_path):
    class Provider:
        identity = {"kind": "registry-pin-plain-agent", "version": "1"}

        async def complete(self, messages, tools):
            return r.ModelResponse("complete")

    component = Echo()
    registry = nodes(component)
    with r.LocalEngine(
        r.SQLiteStore(tmp_path / "run.sqlite"),
        providers={"default": Provider()},
        tools=r.ToolRegistry(),
        workflow_executors=registry,
    ) as runtime:
        accepted = runtime.submit(r.AgentSpec("ordinary", "Answer"), "q", command_id="submit")
        original, replacements = replace_port(registry, "validate_output")
        try:
            done = asyncio.run(runtime.drive(accepted.run_id))
            assert done.state == "succeeded" and done.result == "complete"
            assert replacements == [] and component.calls == []
        finally:
            registry.validate_output = original
