"""Cached optional operations and cleanup callbacks keep runtime ownership."""

import asyncio
import threading

import pytest

from relf_agent import (
    AgentSpec,
    ComponentRegistry,
    DynamicWorkflowSpec,
    ModelResponse,
    RuntimeBuilder,
    RuntimeProfile,
    SQLiteStore,
    ToolCall,
    ToolRegistry,
    ToolSpec,
)
from relf_agent.dag_planning import DAGProposal
from relf_agent.errors import CoordinatorBusy, ValidationError
from relf_agent.runtime_builder import EchoProvider
from relf_agent.user_input import register_user_input


@pytest.mark.parametrize(
    "name",
    [
        "send_input",
        "compact_messages",
        "patch_plan",
        "parent_run_id",
        "context_stages",
        "memory_stages",
        "context_artifacts",
    ],
)
def test_cached_optional_operation_cannot_bypass_async_shutdown(tmp_path, name):
    async def scenario():
        started, finish = threading.Event(), threading.Event()
        path = tmp_path / "input.sqlite"
        retained = []

        def work(arguments, invocation):
            started.set()
            assert finish.wait(5)
            return "finished"

        class Provider:
            identity = {"kind": "cleanup-boundary", "version": "1"}

            async def complete(self, messages, tools):
                if any(message["role"] == "tool" for message in messages):
                    return ModelResponse(output="done")
                if messages[1]["content"] == "completed":
                    return ModelResponse(output="done")
                if messages[1]["content"] == "question":
                    return ModelResponse(
                        tool_calls=(ToolCall("request_input", {"prompt": "Which target?"}),)
                    )
                return ModelResponse(tool_calls=(ToolCall("work", {}),))

        def provider_factory(config, context):
            retained.append(context)
            return Provider()

        def tools_factory(config, context):
            tools = ToolRegistry()
            register_user_input(tools)
            tools.register(ToolSpec("work", "Block until released", {"type": "object"}), work)
            return tools

        registry = ComponentRegistry()
        registry.register("provider", "cleanup-boundary", provider_factory)
        registry.register("tools", "cleanup-boundary", tools_factory)
        profile = RuntimeProfile(
            "cleanup-boundary",
            "1",
            {"default": {"adapter": "cleanup-boundary"}},
            {"tools": {"adapter": "cleanup-boundary"}},
        )
        runtime = await RuntimeBuilder(registry).abuild(profile, path)
        driving = closing = None
        try:
            question = runtime.submit(
                AgentSpec("ask", "Ask", ("request_input",)), "question", command_id="question"
            )
            assert (await runtime.drive(question.run_id)).state == "waiting_input"
            store = retained[0].store
            pending = next(iter(store.run(question.run_id)["input_requests"].values()))["request"]
            target = question.run_id
            args, options = (target,), {}
            if name == "send_input":
                args = (target, pending["pending_id"], pending["target_digest"], "production")
                options = {"command_id": "late-control"}
            elif name == "compact_messages":
                completed = runtime.submit(
                    AgentSpec("done", "Answer"), "completed", command_id="done"
                )
                assert (await runtime.drive(completed.run_id)).state == "succeeded"
                target, args = completed.run_id, (completed.run_id,)
                options = {"command_id": "late-control"}
            elif name == "patch_plan":
                dag = runtime.submit(
                    DynamicWorkflowSpec(
                        "dag",
                        {"ask": AgentSpec("ask", "Ask", ("request_input",))},
                        planner="dag-rule",
                        plan_mode="dag",
                    ),
                    "question",
                    command_id="dag",
                )
                assert (await runtime.drive(dag.run_id)).state == "waiting_input"
                target = dag.run_id
                proposal = DAGProposal.from_dict(
                    store.run(target)["orchestration"]["dag"]["proposal"]
                )
                args = (target, proposal)
                options = {"expected_plan_revision": 0, "command_id": "late-control"}
            original = store.run(target)
            operation = getattr(runtime, name)
            slow = runtime.submit(AgentSpec("slow", "Work", ("work",)), "slow", command_id="slow")
            driving = asyncio.create_task(runtime.drive(slow.run_id))
            assert await asyncio.to_thread(started.wait, 2)
            closing = asyncio.create_task(runtime.aclose())
            await asyncio.sleep(0)
            assert not closing.done()
            with pytest.raises(ValidationError, match="closing"):
                operation(*args, **options)
            assert store.run(target) == original
            assert (
                store.conn.execute(
                    "SELECT count(*) FROM commands WHERE id='late-control'"
                ).fetchone()[0]
                == 0
            )
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            with pytest.raises(ValidationError, match="closing"):
                operation(*args, **options)
            assert store.run(target) == original
            closing = asyncio.create_task(runtime.aclose())
            await asyncio.sleep(0)
            assert not closing.done()
            with SQLiteStore(path) as other:
                with pytest.raises(CoordinatorBusy):
                    other.create_coordinator().acquire()
        finally:
            finish.set()
            if driving is not None:
                await driving
            if closing is not None:
                await asyncio.gather(closing, return_exceptions=True)
            await runtime.aclose()

        async with await RuntimeBuilder(registry).abuild(profile, path) as restored:
            result = getattr(restored, name)(*args, **options)
            if name in {"send_input", "compact_messages", "patch_plan"}:
                assert result.apply_state == "applied"
                assert getattr(restored, name)(*args, **options) == result
            else:
                assert result == (None if name == "parent_run_id" else [])
            if name == "send_input":
                assert (await restored.drive(question.run_id)).result == "done"

    asyncio.run(scenario())


@pytest.mark.parametrize("entry", ["runtime", "context"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_sync_resource_callback_cannot_reenter_the_cleanup_ledger(tmp_path, entry, asynchronous):
    first = (tmp_path / "first.txt").open("w")
    last = (tmp_path / "last.txt").open("w")
    calls, rejected = [], []
    context = None

    class Client:
        reentered = False

        def close(self):
            calls.append("last")
            if not self.reentered:
                self.reentered = True
                with pytest.raises(ValidationError) as failure:
                    if entry == "runtime":
                        runtime.close()
                    else:
                        context.cleanup()
                rejected.append(failure.value)
            last.close()

    class First:
        def close(self):
            calls.append("first")
            first.close()

    def factory(config, selected):
        nonlocal context
        context = selected
        selected.own(First())
        selected.own(Client())
        return EchoProvider("cleanup")

    registry = ComponentRegistry()
    registry.register("provider", "cleanup-boundary", factory)
    profile = RuntimeProfile("cleanup-boundary", "1", {"default": {"adapter": "cleanup-boundary"}})
    runtime = RuntimeBuilder(registry).build(profile, tmp_path / "resources.sqlite")
    try:
        if asynchronous:
            asyncio.run(runtime.aclose())
        else:
            runtime.close()
        assert calls == ["last", "first"]
        assert len(rejected) == 1
        assert first.closed and last.closed
        runtime.close()
        assert calls == ["last", "first"]
    finally:
        first.close()
        last.close()
        context.store.close()


def test_concurrent_context_cleanup_cannot_pop_another_callers_resources(tmp_path):
    async def scenario():
        entered, finish = asyncio.Event(), asyncio.Event()
        closes = []
        retained = []

        class Client:
            async def aclose(self):
                closes.append("client")
                entered.set()
                await finish.wait()

        async def factory(config, context):
            retained.append(context)
            context.own_async(Client())
            return EchoProvider("cleanup")

        registry = ComponentRegistry()
        registry.register_async("provider", "cleanup-boundary", factory)
        profile = RuntimeProfile(
            "cleanup-boundary", "1", {"default": {"adapter": "cleanup-boundary"}}
        )
        runtime = await RuntimeBuilder(registry).abuild(profile, tmp_path / "concurrent.sqlite")
        closing = asyncio.create_task(runtime.aclose())
        retry = None
        try:
            await asyncio.wait_for(entered.wait(), 2)
            for _ in range(2):
                with pytest.raises(ValidationError):
                    await asyncio.wait_for(retained[0].cleanup_async(), 0.2)
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            assert closes == ["client"]
            retry = asyncio.create_task(runtime.aclose())
            await asyncio.sleep(0)
            assert not retry.done()
            with pytest.raises(ValidationError):
                await asyncio.wait_for(retained[0].cleanup_async(), 0.2)
            assert closes == ["client"]
        finally:
            finish.set()
            await asyncio.gather(closing, return_exceptions=True)
            if retry is not None:
                await retry
            await runtime.aclose()
        assert closes == ["client"]

    asyncio.run(scenario())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_uncaught_cleanup_reentry_keeps_resources_for_an_explicit_retry(tmp_path, asynchronous):
    first = (tmp_path / "first.txt").open("w")
    last = (tmp_path / "last.txt").open("w")
    context = None
    calls = []

    class First:
        def close(self):
            calls.append("first")
            first.close()

    class Client:
        reenter = True

        def close(self):
            calls.append("last")
            if self.reenter:
                self.reenter = False
                context.cleanup()
            last.close()

    def factory(config, selected):
        nonlocal context
        context = selected
        context.own(First())
        context.own(Client())
        return EchoProvider("cleanup")

    registry = ComponentRegistry()
    registry.register("provider", "cleanup-boundary", factory)
    profile = RuntimeProfile("cleanup-boundary", "1", {"default": {"adapter": "cleanup-boundary"}})
    runtime = RuntimeBuilder(registry).build(profile, tmp_path / "retry.sqlite")
    try:
        with pytest.raises(ValidationError, match="cleanup"):
            if asynchronous:
                asyncio.run(runtime.aclose())
            else:
                runtime.close()
        assert calls == ["last"]
        assert not first.closed and not last.closed
        with pytest.raises(ValidationError):
            runtime.submit(AgentSpec("closed", "Answer"), "q", command_id="must-not-accept")
        if asynchronous:
            asyncio.run(runtime.aclose())
        else:
            runtime.close()
        assert calls == ["last", "last", "first"]
        assert first.closed and last.closed
        runtime.close()
        assert calls == ["last", "last", "first"]
    finally:
        first.close()
        last.close()
        context.store.close()
