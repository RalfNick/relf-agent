"""Actual close attempts keep their work while adding safe retry diagnostics."""

import asyncio
import threading
from types import SimpleNamespace

import pytest

import relf_agent as r
from relf_agent.agent_runtime import CloseReport
from relf_agent.errors import CloseIncomplete, CoordinatorBusy
from relf_agent.runtime_builder import EchoProvider
from relf_agent.runtime_lifecycle import BuildContext
from relf_agent.temporal_builder import _ConstructionCleanup

from .helpers import ScriptedProvider
from .test_agent_runtime import engine


@pytest.mark.parametrize("cancel_first", [False, True])
@pytest.mark.parametrize(("owned", "ownership"), [(True, "owned"), (False, "borrowed")])
def test_local_thread_close_diagnostics_preserve_original_handler_and_retry(
    tmp_path, cancel_first, owned, ownership
):
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        effects = []

        def operation(arguments, context):
            entered.set()
            assert release.wait(3)
            effects.append(context.effect_key)
            return {"done": True}

        tools = r.ToolRegistry()
        tools.register(
            r.ToolSpec("read", "Read", {"type": "object"}, effect="read_only"), operation
        )
        path = tmp_path / "runtime.sqlite"
        raw = engine(
            path,
            ScriptedProvider(
                [
                    r.ModelResponse(tool_calls=[r.ToolCall("read", {})]),
                    r.ModelResponse(output="done"),
                ]
            ),
            tools=tools,
        )
        runtime = r.Runtime(raw, owned=owned)
        run = await runtime.create_agent(r.AgentSpec("agent", "Read", ("read",))).submit(
            "q", command_id="once"
        )
        assert await asyncio.to_thread(entered.wait, 1)
        try:
            if cancel_first:
                closer = asyncio.create_task(runtime.aclose())
                await asyncio.sleep(0.01)
                closer.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await closer
            with pytest.raises(CloseIncomplete) as caught:
                await runtime.aclose(close_timeout=0.01)
            assert isinstance(caught.value.report, CloseReport)
            assert caught.value.diagnostics["authority"] == "local"
            assert caught.value.diagnostics["stage"] == "run_drain"
            assert caught.value.diagnostics["ownership"] == ownership
            assert {"kind": "run", "count": 1} in caught.value.diagnostics["blockers"]
            assert raw.status(run.ref.run_id).state == "running"
            with pytest.raises(CoordinatorBusy):
                with engine(path, ScriptedProvider([])):
                    pass
        finally:
            release.set()
            await runtime.aclose(close_timeout=2)
            raw.close()
        assert len(effects) == 1

    asyncio.run(scenario())


def test_local_authority_close_failure_is_identified_without_losing_report(tmp_path):
    async def scenario():
        class Store(r.SQLiteStore):
            failures = 0

            def close(self):
                self.failures += 1
                if self.failures == 1:
                    raise OSError("secret-store-name")
                super().close()

        raw = r.LocalEngine(
            Store(tmp_path / "authority.sqlite"), providers={}, tools=r.ToolRegistry()
        )
        runtime = r.Runtime(raw, owned=True)
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await runtime.aclose()
            assert caught.value.diagnostics["stage"] == "authority_close"
            assert caught.value.diagnostics["authority"] == "local"
            assert "secret-store-name" not in str(caught.value.diagnostics)
        finally:
            await runtime.aclose()

    asyncio.run(scenario())


def test_local_owned_resource_failure_is_separated_from_closed_execution_authority(tmp_path):
    from relf_agent.runtime_lifecycle import RuntimeInstance

    async def scenario():
        path = tmp_path / "resource.sqlite"
        raw = engine(path, ScriptedProvider([]))
        context = BuildContext(raw.store, path, raw.scope, tmp_path)
        attempts = []

        class Resource:
            def close(self):
                attempts.append("close")
                if len(attempts) == 1:
                    raise OSError("secret-resource-address")

        context.own(Resource())
        managed = RuntimeInstance(raw, context)
        runtime = r.Runtime(managed, owned=True)
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await runtime.aclose()
            assert caught.value.diagnostics["stage"] == "resource_close"
            assert caught.value.diagnostics["blockers"] == [{"kind": "resource", "count": 1}]
            assert "secret-resource-address" not in str(caught.value.diagnostics)
            assert managed._engine_closed and len(context._resources) == 1
        finally:
            await runtime.aclose()
        assert attempts == ["close", "close"] and context._resources == []

    asyncio.run(scenario())


def test_temporal_rpc_close_diagnostics_keep_borrowed_client_and_original_submit(monkeypatch):
    from .temporal_agent_fixture import engine as remote_engine

    async def scenario():
        raw = remote_engine(monkeypatch)
        raw.client.start_gate.clear()
        runtime = r.Runtime.from_temporal(raw, owned=True)
        submit = asyncio.create_task(
            runtime.create_agent(r.AgentSpec("agent", "Reply")).submit("q", command_id="once")
        )
        await raw.client.start_entered.wait()
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await runtime.aclose(close_timeout=0.01)
            assert caught.value.diagnostics["authority"] == "temporal"
            assert caught.value.diagnostics["stage"] == "rpc_drain"
            assert caught.value.diagnostics["blockers"] == [{"kind": "rpc", "count": 1}]
            assert not raw._closed and not raw.client.closed
        finally:
            raw.client.start_gate.set()
            run = await submit
            await runtime.aclose(close_timeout=2)
        assert run.ref.run_id in raw.client.states
        assert len(raw.client.states) == 1 and not raw.client.closed

    asyncio.run(scenario())


def test_construction_task_timeout_does_not_close_its_owned_resource(tmp_path):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        closes = []

        class Resource:
            async def aclose(self):
                closes.append("closed")

        context = BuildContext(
            None, tmp_path / "none.sqlite", r.Scope(), tmp_path, allow_async=True
        )
        context.own_async(Resource())
        cleanup = _ConstructionCleanup(context)

        async def operation():
            entered.set()
            await release.wait()

        task = asyncio.create_task(cleanup.execute(operation))
        await entered.wait()
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await cleanup.aclose(wait_timeout=0)
            assert caught.value.diagnostics["stage"] == "construction"
            assert caught.value.diagnostics["blockers"] == [{"kind": "construction", "count": 1}]
            assert closes == [] and not task.done()
        finally:
            release.set()
            await task
            await cleanup.aclose()
        assert closes == ["closed"]

    asyncio.run(scenario())


def test_construction_thread_timeout_keeps_real_bridge_and_original_cleanup(tmp_path):
    from relf_agent.tools import current_thread_tracker

    async def scenario():
        entered, release = threading.Event(), threading.Event()
        completed = []
        context = BuildContext(
            None, tmp_path / "none.sqlite", r.Scope(), tmp_path, allow_async=True
        )
        cleanup = _ConstructionCleanup(context)

        def handler():
            entered.set()
            assert release.wait(3)
            completed.append("done")

        async def operation():
            await current_thread_tracker.get().run(handler)

        task = asyncio.create_task(cleanup.execute(operation))
        assert await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await cleanup.aclose(wait_timeout=0.01)
            assert caught.value.diagnostics["stage"] == "construction"
            assert caught.value.diagnostics["blockers"] == [{"kind": "thread", "count": 1}]
            assert completed == []
        finally:
            release.set()
            await cleanup.aclose(wait_timeout=2)
        assert completed == ["done"]

    asyncio.run(scenario())


def test_assembly_resource_close_adds_stage_and_keeps_original_error_for_retry(tmp_path):
    from .test_temporal_assembly_cleanup import builder, profile

    async def scenario():
        report = {"private": "resource-name"}
        failure = CloseIncomplete(report)
        attempts = []

        class Resource:
            async def aclose(self):
                attempts.append("close")
                if len(attempts) == 1:
                    raise failure

        async def factory(config, context):
            context.own_async(Resource())
            return EchoProvider("owned")

        assembly = await builder(factory, tmp_path).abuild(profile("managed"))
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await assembly.aclose()
            assert caught.value is failure and caught.value.report is report
            assert caught.value.diagnostics["authority"] == "temporal"
            assert caught.value.diagnostics["stage"] == "resource_close"
            assert caught.value.diagnostics["blockers"] == [{"kind": "resource", "count": 1}]
        finally:
            await assembly.aclose()
        assert attempts == ["close", "close"] and assembly._closed

    asyncio.run(scenario())


def test_assembly_worker_stop_timeout_keeps_one_original_stop_after_cancel(tmp_path, monkeypatch):
    import relf_agent.temporal

    from .test_temporal_assembly_cleanup import builder, profile

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        events = []

        class Resource:
            async def aclose(self):
                events.append("resource")

        async def factory(config, context):
            context.own_async(Resource())
            return EchoProvider("owned")

        class Worker:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append("worker")
                entered.set()
                await release.wait()

        monkeypatch.setattr(relf_agent.temporal, "build_temporal_worker", lambda *a, **kw: Worker())
        assembly = await builder(factory, tmp_path).abuild(profile("managed"))
        await assembly.start_worker(SimpleNamespace(namespace="original"), task_queue="queue")
        closer = asyncio.create_task(assembly.aclose())
        await entered.wait()
        closer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closer
        try:
            with pytest.raises(CloseIncomplete) as caught:
                await assembly.aclose(wait_timeout=0.01)
            assert caught.value.diagnostics["stage"] == "worker_stop"
            assert caught.value.diagnostics["blockers"] == [{"kind": "worker", "count": 1}]
            assert events == ["worker"]
        finally:
            release.set()
            await assembly.aclose()
        assert events == ["worker", "resource"]

    asyncio.run(scenario())
