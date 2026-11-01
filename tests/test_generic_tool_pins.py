"""Generic entry drift must not execute or adopt a different implementation."""

import asyncio
from functools import partial

import pytest

from relf_agent import (
    AgentSpec,
    LocalEngine,
    ModelResponse,
    Runtime,
    Scope,
    SQLiteStore,
    ToolCall,
    ToolRegistry,
    ToolSpec,
)
from relf_agent.errors import (
    CloseIncomplete,
    CoordinatorBusy,
    DefinitionMismatch,
    ExecutionHostFailed,
)
from relf_agent.executors import DispatchEnvelope, PythonToolExecutor
from relf_agent.types import InvocationContext, digest

FORMS = ["plain", "async", "bound", "partial", "callable", "async-callable"]


def callable_pair(form, calls):
    # Independent code bodies, with no captured state; mutations leave source
    # provenance unchanged, as in the original in-place __code__ reproducer.
    prefix = "async " if form in {"async", "async-callable"} else ""
    receiver = "self, " if form in {"bound", "callable", "async-callable"} else ""
    namespace = {"__name__": __name__, "calls": calls}
    exec(
        f"{prefix}def original({receiver}arguments, context):\n"
        "    calls.append('original')\n"
        "    return {'implementation': 'original'}\n"
        f"{prefix}def replacement({receiver}arguments, context):\n"
        "    calls.append('replacement')\n"
        "    return {'implementation': 'replacement'}\n",
        namespace,
    )
    original, replacement = namespace["original"], namespace["replacement"]
    if form == "bound":
        handler = type("Owner", (), {"run": original})().run
    elif form in {"callable", "async-callable"}:
        handler = type("Owner", (), {"__call__": original})()
    elif form == "partial":
        handler = partial(original)
    else:
        handler = original

    def mutate():
        original.__code__ = replacement.__code__

    return handler, mutate


def registry_with(handler, reconciler=None):
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "change",
            "Change",
            {"type": "object"},
            effect="unqueryable_write",
            requires_approval=True,
        ),
        handler,
        reconciler=reconciler,
    )
    return registry


def envelope_for(registry):
    return DispatchEnvelope(
        InvocationContext(Scope(), "run", "action", "attempt", "effect", "epoch"),
        registry.get("change").manifest,
        {},
        "operation",
    )


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_direct_entry_drift_is_rejected_before_dispatch(form, operation):
    calls = []
    handler, mutate = callable_pair(form, calls)
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    mutate()
    with pytest.raises(DefinitionMismatch):
        asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert calls == []


@pytest.mark.parametrize("form", FORMS)
def test_registry_rejects_changed_entry_before_approval_or_manifest_use(form):
    handler, mutate = callable_pair(form, [])
    registry = registry_with(handler)
    mutate()
    with pytest.raises(DefinitionMismatch):
        registry.manifests(["change"])


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
@pytest.mark.parametrize("result", [None, {"committed": True}])
def test_inflight_entry_drift_cannot_be_adopted_as_observation(operation, result):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def original(arguments, context):
            started.set()
            await release.wait()
            return result

        async def replacement(arguments, context):
            started.set()
            await release.wait()
            return result

        registry = registry_with(original, original if operation == "reconcile" else None)
        envelope = envelope_for(registry)
        task = asyncio.create_task(getattr(PythonToolExecutor(registry), operation)(envelope))
        await asyncio.wait_for(started.wait(), 2)
        original.__code__ = replacement.__code__
        release.set()
        with pytest.raises(DefinitionMismatch):
            await task

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_callable_entry_rebinding_cannot_dispatch(operation):
    class Handler:
        def __call__(self, arguments, context):
            calls.append("original")
            return {}

    def replacement(self, arguments, context):
        calls.append("replacement")
        return {}

    calls = []
    handler = Handler()
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    Handler.__call__ = replacement
    with pytest.raises(DefinitionMismatch):
        asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert calls == []


class Provider:
    identity = {"kind": "generic-tool-pin-fixture", "version": "1"}

    async def complete(self, messages, tools):
        if any(message["role"] == "tool" for message in messages):
            return ModelResponse(output="done")
        return ModelResponse(tool_calls=[ToolCall("change", {})])


def test_unchanged_original_manifest_approval_and_restart_remain_compatible(tmp_path):
    async def scenario():
        calls = []
        handler, _ = callable_pair("plain", calls)
        registry = registry_with(handler)
        # This is the pre-fix persisted manifest, with no transient pins added.
        manifest = {
            "name": "change",
            "description": "Change",
            "input_schema": {"type": "object"},
            "version": "1",
            "effect": "unqueryable_write",
            "requires_approval": True,
            "cost": 1,
            "config": {},
            "implementation_digest": digest(
                [
                    {"module": __name__, "name": "original", "source": None},
                    None,
                ]
            ),
        }
        assert registry.get("change").manifest == manifest
        path = tmp_path / "run.sqlite"
        with LocalEngine(
            SQLiteStore(path), providers={"default": Provider()}, tools=registry
        ) as engine:
            handle = engine.submit(AgentSpec("a", "A", ("change",)), "change", command_id="s")
            waiting = await engine.drive(handle.run_id)
            assert waiting.state == "waiting_approval" and calls == []
            pending = waiting.pending[0]
            engine.approve(handle.run_id, pending["action_id"], pending["digest"], command_id="a")
        # A fresh registry must accept the old stored release, without added pins
        # changing approval digests or effect identity.
        registry = registry_with(handler)
        with LocalEngine(
            SQLiteStore(path), providers={"default": Provider()}, tools=registry
        ) as engine:
            done = await engine.drive(handle.run_id)
            assert done.state == "succeeded" and done.result == "done"
            assert calls == ["original"]
            assert (await engine.drive(handle.run_id)).state == "succeeded"
            assert calls == ["original"]

    asyncio.run(scenario())


def test_approval_of_original_action_cannot_execute_drifted_entry(tmp_path):
    async def scenario():
        calls = []
        handler, mutate = callable_pair("plain", calls)
        registry = registry_with(handler)
        with LocalEngine(
            SQLiteStore(tmp_path / "run.sqlite"), providers={"default": Provider()}, tools=registry
        ) as engine:
            handle = engine.submit(AgentSpec("a", "A", ("change",)), "change", command_id="s")
            waiting = await engine.drive(handle.run_id)
            pending = waiting.pending[0]
            mutate()
            try:
                engine.approve(
                    handle.run_id, pending["action_id"], pending["digest"], command_id="a"
                )
                await engine.drive(handle.run_id)
            except DefinitionMismatch:
                pass
            assert calls == []
            assert engine.status(handle.run_id).state != "succeeded"

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_queued_sync_entry_is_rechecked_inside_worker_before_any_write(operation):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    async def scenario():
        calls = []
        handler, mutate = callable_pair("plain", calls)
        registry = registry_with(handler, handler if operation == "reconcile" else None)
        envelope = envelope_for(registry)
        loop = asyncio.get_running_loop()
        release = threading.Event()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        blocker = loop.run_in_executor(None, release.wait)
        task = asyncio.create_task(getattr(PythonToolExecutor(registry), operation)(envelope))
        try:
            # The synchronous entry is queued behind a real occupied worker.
            await asyncio.sleep(0)
            mutate()
        finally:
            release.set()
        await blocker
        with pytest.raises(DefinitionMismatch):
            await task
        assert calls == []

    asyncio.run(scenario())


def test_inflight_run_drift_preserves_unknown_write_outcome(tmp_path):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def original(arguments, context):
            calls.append("original")
            started.set()
            await release.wait()
            return {"committed": True}

        async def replacement(arguments, context):
            calls.append("replacement")
            started.set()
            await release.wait()
            return {"committed": True}

        registry = registry_with(original)
        with LocalEngine(
            SQLiteStore(tmp_path / "run.sqlite"), providers={"default": Provider()}, tools=registry
        ) as engine:
            handle = engine.submit(AgentSpec("a", "A", ("change",)), "change", command_id="s")
            waiting = await engine.drive(handle.run_id)
            pending = waiting.pending[0]
            engine.approve(handle.run_id, pending["action_id"], pending["digest"], command_id="a")
            task = asyncio.create_task(engine.drive(handle.run_id))
            await asyncio.wait_for(started.wait(), 2)
            original.__code__ = replacement.__code__
            release.set()
            try:
                await task
            except DefinitionMismatch:
                pass
            snapshot = engine.status(handle.run_id)
            assert snapshot.state != "succeeded"
            tool_action = next(action for action in snapshot.actions if action["kind"] == "tool")
            assert tool_action["status"] == "outcome_unknown"
            assert "result" not in tool_action
            assert calls == ["original"]

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_result_serialization_cannot_change_entry_before_observation_return(operation):
    def original(arguments, context):
        return Receipt(committed=True)

    def replacement(arguments, context):
        return Receipt(committed=False)

    class Receipt(dict):
        def items(self):
            original.__code__ = replacement.__code__
            return super().items()

    registry = registry_with(original, original if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    with pytest.raises(DefinitionMismatch):
        asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))


def test_hosted_drift_retains_original_run_and_lease_until_restored_resume_and_close(tmp_path):
    async def scenario():
        calls = []
        handler, mutate = callable_pair("plain", calls)
        original_code = handler.__code__
        registry = registry_with(handler)
        path = tmp_path / "hosted.sqlite"
        runtime = Runtime(
            LocalEngine(SQLiteStore(path), providers={"default": Provider()}, tools=registry),
            owned=True,
        )
        run = await runtime.create_agent(AgentSpec("a", "A", ("change",))).submit(
            "change", command_id="s"
        )
        waiting = await run.wait(wait_timeout=2)
        assert waiting.snapshot.state == "waiting_approval"
        ref = run.ref
        pending = waiting.snapshot.pending[0]
        original_action = next(
            action for action in waiting.snapshot.actions if action["kind"] == "tool"
        )
        mutate()
        await run.approve(pending["action_id"], pending["digest"], command_id="a")
        with pytest.raises(ExecutionHostFailed):
            await run.wait(wait_timeout=2)
        rejected = await run.status()
        rejected_action = next(action for action in rejected.actions if action["kind"] == "tool")
        assert rejected.state != "succeeded" and calls == []
        assert rejected_action["id"] == original_action["id"]
        assert rejected_action["digest"] == original_action["digest"]
        assert rejected_action["effect_key"] == original_action["effect_key"]
        assert rejected_action["approved"] is True
        assert rejected_action["attempts"] == [] and "result" not in rejected_action
        assert (await run.diagnostics()).release_digest == ref.release_digest

        with pytest.raises(CloseIncomplete) as failed_close:
            await runtime.aclose(close_timeout=2)
        assert runtime.state == "close_failed"
        assert ref in failed_close.value.report.parked
        # Failed hosted work still belongs to the original authority. Closing
        # incompletely must neither release its lease nor replace its Run.
        with SQLiteStore(path) as observer:
            with pytest.raises(CoordinatorBusy):
                observer.create_coordinator().acquire()

        handler.__code__ = original_code
        resumed = await run.resume()
        assert resumed.ref == ref and runtime.state == "close_failed"
        done = await resumed.wait(wait_timeout=2)
        assert done.snapshot.state == "succeeded" and done.snapshot.result == "done"
        assert calls == ["original"]
        completed = next(action for action in done.snapshot.actions if action["kind"] == "tool")
        assert completed["id"] == original_action["id"]
        assert completed["digest"] == original_action["digest"]
        assert completed["effect_key"] == original_action["effect_key"]
        assert len(completed["attempts"]) == 1
        with SQLiteStore(path) as observer:
            with pytest.raises(CoordinatorBusy):
                observer.create_coordinator().acquire()
        closed = await runtime.aclose(close_timeout=2)
        assert closed.state == runtime.state == "closed"
        assert await runtime.aclose(close_timeout=2) == closed
        with SQLiteStore(path) as observer:
            coordinator = observer.create_coordinator()
            coordinator.acquire()
            coordinator.release()

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
@pytest.mark.parametrize("mutation", ["replacement", "code"])
def test_partial_subclass_entry_drift_is_rejected_before_dispatch(operation, mutation):
    calls = []

    def wrapped(arguments, context):
        calls.append("wrapped")
        return {"implementation": "wrapped"}

    class Handler(partial):
        def __call__(self, arguments, context):
            calls.append("original")
            return self.func(arguments, context)

    class Replacement(Handler):
        def __call__(self, arguments, context):
            calls.append("replacement")
            return self.func(arguments, context)

    handler = Handler(wrapped)
    registry = registry_with(handler, handler if operation == "reconcile" else None)
    envelope = envelope_for(registry)
    if mutation == "replacement":
        Handler.__call__ = Replacement.__call__
    else:
        Handler.__call__.__code__ = Replacement.__call__.__code__
    with pytest.raises(DefinitionMismatch):
        asyncio.run(getattr(PythonToolExecutor(registry), operation)(envelope))
    assert calls == []
