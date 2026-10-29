"""The high-level handle observes its original authority without owning it."""

import asyncio
from contextlib import aclosing

import pytest

import relf_agent as r
from relf_agent.errors import AuthorizationDenied, RuntimeClosed

from .helpers import ScriptedProvider
from .test_agent_runtime import engine


@pytest.mark.parametrize("kind", ["agent", "sequence", "graph", "team", "dynamic"])
def test_common_handle_streams_committed_events_for_existing_compositions(tmp_path, kind):
    async def run():
        spec = r.AgentSpec("a", "Answer")
        definition = {
            "agent": spec,
            "sequence": r.WorkflowSpec("sequence", [spec]),
            "graph": r.GraphWorkflowSpec("graph", [r.GraphNode("a", agent=spec)]),
            "team": r.TeamSpec("team", {"a": spec}),
            "dynamic": r.DynamicWorkflowSpec("dynamic", {"a": spec}),
        }[kind]
        provider = ScriptedProvider([r.ModelResponse("done")])
        raw = engine(tmp_path / "runs.sqlite", provider)
        async with r.Runtime(raw, owned=True) as runtime:
            handle = await runtime.create_agent(definition).submit("task", command_id="s")
            assert (await handle.wait(wait_timeout=2)).snapshot.state == "succeeded"
            before, calls = raw.events(handle.ref.run_id), provider.calls
            async with aclosing(handle.subscribe_events(page_size=2)) as events:
                rows = [row async for row in events]
            assert [row.event for row in rows] == before
            assert raw.events(handle.ref.run_id) == before and provider.calls == calls
            assert events.cursor == rows[-1].cursor

    asyncio.run(run())


@pytest.mark.parametrize("cancel", [False, True])
def test_disconnect_or_observer_cancellation_does_not_cancel_business(tmp_path, cancel):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class Provider:
            identity = {"kind": "event-entry-waiting", "version": "1"}

            async def complete(self, messages, tools):
                entered.set()
                await release.wait()
                return r.ModelResponse("done")

        raw = engine(tmp_path / "running.sqlite", Provider())
        async with r.Runtime(raw, owned=True) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "task", command_id="s"
            )
            await asyncio.wait_for(entered.wait(), 1)
            before = raw.events(handle.ref.run_id)
            events = waiter = None
            try:
                events = handle.subscribe_events(after=before[-1].seq, poll_interval=0.01)
                waiter = asyncio.create_task(anext(events))
                await asyncio.sleep(0.02)
                assert not waiter.done()
                if cancel:
                    waiter.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await waiter
                else:
                    await events.aclose()
                    with pytest.raises(StopAsyncIteration):
                        await waiter
                assert (await handle.status()).state == "running"
                assert raw.events(handle.ref.run_id) == before
            finally:
                release.set()
                if events is not None:
                    await events.aclose()
                if waiter is not None:
                    await asyncio.gather(waiter, return_exceptions=True)
            assert (await handle.wait(wait_timeout=2)).snapshot.result == "done"
            assert not any(e.kind == "run_cancelled" for e in await handle.events())

    asyncio.run(run())


def test_buffered_events_refuse_after_runtime_close(tmp_path):
    async def run():
        raw = engine(tmp_path / "closed.sqlite", ScriptedProvider([r.ModelResponse("done")]))
        runtime = r.Runtime(raw, owned=True)
        events = None
        try:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "task", command_id="s"
            )
            await handle.wait(wait_timeout=2)
            events = handle.subscribe_events(page_size=100)
            first = await anext(events)
            assert len(raw.events(handle.ref.run_id)) > 1
            await runtime.aclose()
            with pytest.raises(RuntimeClosed):
                await anext(events)
            assert events.cursor == first.cursor
            with pytest.raises(RuntimeClosed):
                handle.subscribe_events()
        finally:
            if events is not None:
                await events.aclose()
            await runtime.aclose()

    asyncio.run(run())


def test_event_cursor_reconnects_after_approval_restart_without_duplicate_effect(tmp_path):
    async def run():
        writes = []
        tools = r.ToolRegistry()
        tools.register(
            r.ToolSpec("write", "Write", {"type": "object"}, requires_approval=True),
            lambda args, ctx: writes.append(ctx.effect_key) or {"written": True},
        )
        path = tmp_path / "approval.sqlite"
        async with r.Runtime(
            engine(
                path,
                ScriptedProvider([r.ModelResponse(tool_calls=[r.ToolCall("write", {})])]),
                tools=tools,
            ),
            owned=True,
        ) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer", ("write",))).submit(
                "task", command_id="s"
            )
            paused = await handle.wait(wait_timeout=2)
            assert paused.snapshot.state == "waiting_approval"
            ref, pending = handle.ref, paused.snapshot.pending[0]
            async with aclosing(handle.subscribe_events(page_size=2)) as events:
                first = await anext(events)
                cursor = r.EventCursor.from_token(events.cursor.token)
            assert cursor == first.cursor and not writes

        raw = engine(path, ScriptedProvider([r.ModelResponse("done")]), tools=tools)
        async with r.Runtime(raw, owned=True) as runtime:
            handle = runtime.attach(r.RunRef.from_dict(ref.to_dict()))
            async with aclosing(handle.subscribe_events(after=cursor, page_size=2)) as events:
                receipt = await handle.approve(
                    pending["action_id"], pending["digest"], command_id="a"
                )
                assert (
                    await handle.approve(pending["action_id"], pending["digest"], command_id="a")
                    == receipt
                )
                rows = [row.event async for row in events]
            assert rows == raw.events(ref.run_id, after=cursor.after)
            assert len({row.seq for row in rows}) == len(rows)
            assert len(writes) == 1 and (await handle.status()).state == "succeeded"

    asyncio.run(run())


def test_handle_refuses_cursor_from_another_scope(tmp_path):
    async def run():
        async with r.Runtime(
            engine(tmp_path / "scope.sqlite", ScriptedProvider([r.ModelResponse("done")])),
            owned=True,
        ) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "task", command_id="s"
            )
            foreign = r.EventCursor(r.Scope("other", "owner"), handle.ref.run_id)
            with pytest.raises(AuthorizationDenied):
                handle.subscribe_events(after=foreign)
            assert (await handle.wait(wait_timeout=2)).snapshot.result == "done"

    asyncio.run(run())


def test_failed_resource_close_refuses_buffered_events_and_allows_cleanup_retry(tmp_path):
    async def run():
        raw = engine(tmp_path / "close-failure.sqlite", ScriptedProvider([r.ModelResponse("done")]))
        original_close = raw.close
        refuse = True

        def close():
            if refuse:
                raise RuntimeError("resource still busy")
            original_close()

        raw.close = close
        runtime = r.Runtime(raw, owned=True)
        events = None
        try:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "task", command_id="s"
            )
            await handle.wait(wait_timeout=2)
            events = handle.subscribe_events(page_size=100)
            first = await anext(events)
            assert len(raw.events(handle.ref.run_id)) > 1
            with pytest.raises(r.CloseIncomplete):
                await runtime.aclose()
            assert runtime.state == "close_failed" and runtime._drained
            with pytest.raises(RuntimeClosed):
                await handle.events()
            with pytest.raises(RuntimeClosed):
                await anext(events)
            assert events.cursor == first.cursor
            with pytest.raises(RuntimeClosed):
                handle.subscribe_events()
        finally:
            if events is not None:
                await events.aclose()
            refuse = False
            await runtime.aclose()
        assert runtime.state == "closed"

    asyncio.run(run())
