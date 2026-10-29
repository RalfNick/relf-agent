import asyncio
from contextlib import aclosing

import pytest

import relf_agent as r


class Provider:
    identity = {"kind": "managed-stream-local", "version": "1"}

    def __init__(self):
        self.calls = self.closed = 0

    async def complete(self, messages, tools):
        pytest.fail("Only the explicit stream adapter dispatches this provider")

    async def stream(self, messages, tools):
        self.calls += 1
        try:
            yield r.ModelStreamEvent("text", text="prefix")
            result = (
                r.ModelResponse(tool_calls=[r.ToolCall("change", {}, "call")])
                if tools and not any(m["role"] == "tool" for m in messages)
                else r.ModelResponse("done")
            )
            yield r.ModelStreamEvent("response", response=result)
        finally:
            self.closed += 1


def make(path, provider, *, tools=None, policy=None):
    store = r.SQLiteStore(path)
    try:
        return r.LocalEngine(
            store,
            providers={"default": r.StreamedModelProvider(provider, chunk_chars=1)},
            tools=r.ToolRegistry() if tools is None else tools,
            stream_updates=policy,
        )
    except BaseException:
        store.close()
        raise


def test_default_policy_does_not_emit_or_change_release(tmp_path):
    async def run():
        with make(tmp_path / "default.sqlite", Provider()) as raw:
            handle = raw.submit(r.AgentSpec("a", "Answer"), "q", command_id="s")
            assert "stream_updates" not in raw.diagnostics(handle.run_id).manifest
            assert (await raw.drive(handle.run_id)).result == "done"
            assert not any(e.kind == "agent_update" for e in raw.events(handle.run_id))

    asyncio.run(run())


def test_models_and_approved_async_tool_share_typed_durable_stream(tmp_path):
    async def run():
        writes, reports = [], []
        tools = r.ToolRegistry()

        @tools.tool(effect="idempotent_write", requires_approval=True, context_parameter="context")
        async def change(*, context):
            reports.append(await r.emit_tool_delta({"message": "checking"}))
            writes.append(context.effect_key)
            reports.append(await r.emit_tool_delta({"message": "written"}))
            return {"applied": True}

        provider = Provider()
        raw = make(tmp_path / "chain.sqlite", provider, tools=tools, policy=r.StreamUpdatePolicy())
        async with r.Runtime(raw, owned=True) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer", ("change",))).submit(
                "q", command_id="s"
            )
            paused = await handle.wait(wait_timeout=2)
            assert paused.snapshot.state == "waiting_approval" and not writes
            async with aclosing(handle.stream_updates(follow=False)) as updates:
                prefix = [e async for e in updates]
                cursor = updates.cursor
            assert any(e.kind == "model_delta" for e in prefix)
            assert not any(e.kind == "tool_delta" for e in prefix)
            pending = paused.snapshot.pending[0]
            approval = await handle.approve(pending["action_id"], pending["digest"], command_id="a")
            assert (
                await handle.approve(pending["action_id"], pending["digest"], command_id="a")
                == approval
            )
            async with aclosing(handle.stream_updates(after=cursor)) as updates:
                rest = [e async for e in updates]
            assert reports == [True, True] and len(writes) == 1
            assert (await handle.status()).result == "done" and provider.calls == 2
            assert [e.data["message"] for e in rest if e.kind == "tool_delta"] == [
                "checking",
                "written",
            ]
            deltas = [e for e in prefix + rest if e.kind.endswith("_delta")]
            ends = [e for e in prefix + rest if e.kind in {"model_end", "tool_end"}]
            assert len(ends) == 3 and all(e.authoritative for e in ends)
            assert all(not e.authoritative and e.action_id and e.attempt_id for e in deltas)
            assert all(e.action_id and e.attempt_id for e in ends)
            assert raw.store.budget(handle.ref.run_id)["spent"] == 3
            assert [e.envelope.event for e in prefix + rest] == await handle.events()

    asyncio.run(run())


def test_live_prefix_is_visible_and_consumer_cancel_preserves_source(tmp_path):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class Waiting(Provider):
            async def stream(self, messages, tools):
                self.calls += 1
                try:
                    yield r.ModelStreamEvent("text", text="live")
                    entered.set()
                    await release.wait()
                    yield r.ModelStreamEvent("response", response=r.ModelResponse("done"))
                finally:
                    self.closed += 1

        provider = Waiting()
        async with r.Runtime(
            make(tmp_path / "live.sqlite", provider, policy=r.StreamUpdatePolicy()), owned=True
        ) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "q", command_id="s"
            )
            try:
                await asyncio.wait_for(entered.wait(), 1)
                async with aclosing(handle.stream_updates(follow=False)) as updates:
                    rows = [e async for e in updates]
                    cursor = updates.cursor
                assert "".join(e.data["text"] for e in rows if e.kind == "model_delta") == "live"
                assert (await handle.status()).state == "running" and provider.closed == 0
                updates = handle.stream_updates(after=cursor, poll_interval=0.01)
                reader = asyncio.create_task(anext(updates))
                await asyncio.sleep(0.02)
                reader.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await reader
                await updates.aclose()
                assert (await handle.status()).state == "running" and provider.closed == 0
            finally:
                release.set()
            assert (await handle.wait(wait_timeout=2)).snapshot.result == "done"
            assert provider.calls == provider.closed == 1

    asyncio.run(run())


def test_overflow_emits_one_gap_and_keeps_full_final_result(tmp_path):
    async def run():
        policy = r.StreamUpdatePolicy(max_deltas=2)
        async with r.Runtime(
            make(tmp_path / "overflow.sqlite", Provider(), policy=policy), owned=True
        ) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "q", command_id="s"
            )
            assert (await handle.wait(wait_timeout=2)).snapshot.result == "done"
            async with aclosing(handle.stream_updates()) as updates:
                rows = [e async for e in updates]
            assert len([e for e in rows if e.kind == "model_delta"]) == 2
            assert [e.data for e in rows if e.kind == "gap"] == [{"reason": "capacity"}]
            (end,) = [e for e in rows if e.kind == "model_end"]
            assert end.data["stream_end"]["observation"]["truncated"] is True

    asyncio.run(run())


def test_idle_slow_consumer_does_not_hold_business_and_reconnects_exact_cursor(tmp_path):
    async def run():
        calls, tools = [], r.ToolRegistry()

        async def change(arguments, context):
            calls.append(context.effect_key)
            return {"applied": True}

        tools.register(
            r.ToolSpec("change", "Read", {"type": "object"}, requires_approval=True), change
        )
        provider = Provider()
        raw = make(
            tmp_path / "slow.sqlite",
            provider,
            tools=tools,
            policy=r.StreamUpdatePolicy(max_deltas=2),
        )
        async with r.Runtime(raw, owned=True) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer", ("change",))).submit(
                "q", command_id="s"
            )
            paused = await handle.wait(wait_timeout=2)
            assert paused.snapshot.state == "waiting_approval"
            observer = handle.stream_updates(page_size=1)
            try:
                first = await anext(observer)
                cursor = r.EventCursor.from_token(observer.cursor.token)
                assert first.cursor == cursor
                pending = paused.snapshot.pending[0]
                await handle.approve(pending["action_id"], pending["digest"], command_id="approve")
                # Intentionally stop consuming while the independently hosted Run
                # completes; the assertion does not depend on a timing sleep.
                done = await handle.wait(wait_timeout=2, terminal_only=True)
                assert done.snapshot.result == "done" and len(calls) == 1
                assert observer.cursor == cursor and provider.calls == provider.closed == 2
            finally:
                await observer.aclose()
            async with aclosing(handle.stream_updates(after=cursor, page_size=1)) as resumed:
                rows = [row async for row in resumed]
            assert [row.envelope.event for row in rows] == raw.events(
                handle.ref.run_id, after=cursor.after
            )
            assert len({row.envelope.event.seq for row in rows}) == len(rows)
            assert any(row.source_kind == "run_succeeded" for row in rows)
            assert len([row for row in rows if row.kind == "gap"]) == 2
            assert len(calls) == 1

    asyncio.run(run())


@pytest.mark.parametrize("phase", ["model", "tool"])
def test_received_evidence_restart_does_not_repeat_source_or_write(tmp_path, phase):
    async def run():
        path, writes, tools, provider = (
            tmp_path / "receipt.sqlite",
            [],
            r.ToolRegistry(),
            Provider(),
        )

        @tools.tool(effect="idempotent_write", context_parameter="context")
        async def change(*, context):
            await r.emit_tool_delta({"message": "one write"})
            writes.append(context.effect_key)
            return {"applied": True}

        selected = tools if phase == "tool" else r.ToolRegistry()
        spec = r.AgentSpec("a", "Answer", ("change",) if phase == "tool" else ())
        with make(path, provider, tools=selected, policy=r.StreamUpdatePolicy()) as raw:
            handle = raw.submit(spec, "q", command_id="s")

            def crash(*args):
                raise RuntimeError("after durable evidence")

            setattr(
                raw,
                "_adopt_model_response" if phase == "model" else "_adopt_tool_observation",
                crash,
            )
            with pytest.raises(RuntimeError, match="after durable"):
                await raw.drive(handle.run_id)
            before = raw.events(handle.run_id)
            calls = provider.calls
        with make(path, provider, tools=selected, policy=r.StreamUpdatePolicy()) as raw:
            assert raw.submit(spec, "q", command_id="s") == handle
            assert (await raw.drive(handle.run_id)).result == "done"
            assert provider.calls == calls + (1 if phase == "tool" else 0)
            assert len(writes) == (1 if phase == "tool" else 0)
            assert raw.events(handle.run_id)[: len(before)] == before
            assert len(
                [
                    e
                    for e in raw.events(handle.run_id)
                    if e.kind == "agent_update" and e.data["operation"] == "tool"
                ]
            ) == (1 if phase == "tool" else 0)

    asyncio.run(run())


def test_standalone_agent_can_select_policy_without_constructing_an_engine(tmp_path):
    async def run():
        model = r.StreamedModelProvider(Provider(), chunk_chars=1)
        async with r.Agent(
            model=model,
            db_path=tmp_path / "standalone.sqlite",
            stream_updates=r.StreamUpdatePolicy(),
        ) as agent:
            handle = await agent.submit("q", command_id="s")
            async with aclosing(handle.stream_updates()) as updates:
                rows = [row async for row in updates]
            assert any(row.kind == "model_delta" for row in rows)
            assert (await handle.status()).result == "done"

    asyncio.run(run())


def test_shared_agent_cannot_override_host_stream_policy(tmp_path):
    async def run():
        from relf_agent.errors import ValidationError

        async with r.Runtime(make(tmp_path / "shared.sqlite", Provider()), owned=True) as runtime:
            with pytest.raises(ValidationError):
                r.Agent(runtime=runtime, stream_updates=r.StreamUpdatePolicy())
            result = await runtime.create_agent(r.AgentSpec("a", "Answer")).run(
                "q", command_id="s", wait_timeout=2
            )
            assert result.snapshot.state == "succeeded"

    asyncio.run(run())
