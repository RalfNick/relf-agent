"""Public entry preflight precedes admission or resource ownership changes."""

import asyncio

import pytest

import relf_agent as r
from relf_agent.errors import CloseIncomplete, RuntimeClosed, ValidationError
from relf_agent.runtime_builder import EchoProvider

from .helpers import ScriptedProvider
from .temporal_agent_fixture import engine as remote_engine
from .test_temporal_session_client import Transport
from .test_temporal_sessions import session as history_session

INVALID_WAIT = [
    pytest.param({"wait_timeout": 10**400}, id="oversized-timeout"),
    pytest.param({"wait_timeout": -1}, id="negative-timeout"),
    pytest.param({"terminal_only": "invalid"}, id="text-terminal-only"),
    pytest.param({"terminal_only": 1}, id="numeric-terminal-only"),
]


@pytest.mark.parametrize("options", INVALID_WAIT)
@pytest.mark.parametrize("session", [False, True], ids=["agent", "session"])
def test_invalid_run_options_never_accept_work_or_effects_and_same_command_can_retry(
    tmp_path, session, options
):
    async def scenario():
        effects, calls = {}, []

        class Provider:
            identity = {"kind": "preflight-test-provider", "version": "1"}

            async def complete(self, messages, tools):
                calls.append("model")
                if not any(m["role"] == "tool" for m in messages):
                    return r.ModelResponse(tool_calls=[r.ToolCall("apply", {})])
                return r.ModelResponse(output="done")

        async def apply(arguments, context):
            return effects.setdefault(context.effect_key, {"applied": True})

        async def reconcile(arguments, context):
            return effects.get(context.effect_key)

        tools = r.ToolRegistry()
        tools.register(
            r.ToolSpec("apply", "Apply", {"type": "object"}, effect="queryable_write"),
            apply,
            reconciler=reconcile,
        )
        async with r.Agent(
            model=Provider(), tools=tools, db_path=tmp_path / "runs.sqlite"
        ) as agent:
            entry = await agent.open_session("chat", command_id="open") if session else agent

            def counts():
                return tuple(
                    agent.runtime.engine.store.conn.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in ("runs", "commands", "events", "reservations")
                )

            before = counts()
            with pytest.raises(ValidationError):
                await entry.run("task", command_id="same", **options)
            assert counts() == before
            assert not calls and not effects and not agent.runtime._supervisor.refs
            if session:
                assert not (await entry.status()).busy and not await entry.turns()
            observed = await entry.run("task", command_id="same", wait_timeout=1)
            assert observed.snapshot.state == "succeeded" and observed.snapshot.result == "done"
            assert calls == ["model", "model"] and len(effects) == 1
            replay = await entry.run("task", command_id="same", wait_timeout=1)
            assert replay.ref == observed.ref and calls == ["model", "model"] and len(effects) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("options", INVALID_WAIT)
def test_remote_agent_run_rejects_before_registry_rpc_and_allows_original_approval_retry(
    monkeypatch, options
):
    async def scenario():
        raw = remote_engine(monkeypatch)
        async with r.Runtime.from_temporal(raw) as runtime:
            agent = runtime.create_agent(r.AgentSpec("a", "Answer", ("lookup",)))
            with pytest.raises(ValidationError):
                await agent.run("q", command_id="same", **options)
            assert (
                not raw.client.states and not raw.client.registries and raw.client.tool_calls == 0
            )
            observed = await agent.run("q", command_id="same", wait_timeout=1)
            assert observed.snapshot.state == "waiting_approval" and raw.client.tool_calls == 0
            handle = await runtime.aattach(observed.ref)
            (item,) = await handle.pending()
            await handle.approve(item["action_id"], item["digest"], command_id="approve")
            assert (await handle.wait(wait_timeout=1)).snapshot.state == "succeeded"
            assert raw.client.tool_calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("options", INVALID_WAIT)
def test_remote_session_run_rejects_before_original_history_turn_admission(monkeypatch, options):
    async def scenario():
        _, execution = history_session()
        transport = Transport(execution.manifest)
        engine = r.TemporalEngine(transport, task_queue="queue", release=execution.manifest)
        engine._guard, engine._handle = transport._guard, transport._handle

        async def diagnostics(run_id):
            from relf_agent.temporal_state import TemporalRunState
            from relf_agent.types import RunDiagnostics, RunSnapshot

            state = next(s for s in transport.states.values() if s.active["run_id"] == run_id)
            intent = state.active
            proof = TemporalRunState(
                run_id, state.scope, intent["command_id"], intent["request"], intent["manifest"]
            ).diagnostics()
            return RunDiagnostics(**{**proof, "snapshot": RunSnapshot(**proof["snapshot"])})

        async def namespace_id(client):
            return "namespace-uuid"

        engine.diagnostics = diagnostics
        monkeypatch.setattr("relf_agent.temporal_session_activities.namespace_id", namespace_id)
        async with r.Runtime.from_temporal(engine) as runtime:
            entry = await runtime.open_session(
                r.AgentSpec("a", "Answer"), "chat", command_id="open"
            )
            (state,) = transport.states.values()
            commands = dict(transport.registered)
            with pytest.raises(ValidationError):
                await entry.run("task", command_id="same", **options)
            assert state.active is None and not state.started_runs
            assert transport.registered == commands
            observed = await entry.run("task", command_id="same", wait_timeout=0)
            assert observed.snapshot.state == "queued"
            assert (await entry.submit("task", command_id="same")).ref == observed.ref
            assert state.started_runs == {observed.ref.run_id}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "options,error",
    [
        pytest.param({"close_timeout": 10**400}, ValidationError, id="oversized"),
        pytest.param({"close_timeout": True}, ValidationError, id="boolean"),
        pytest.param({"unsupported": 1}, TypeError, id="unknown-option"),
    ],
)
def test_rejected_owned_agent_close_keeps_entry_open_until_real_shutdown(tmp_path, options, error):
    async def scenario():
        provider = ScriptedProvider([r.ModelResponse(output="ok")])
        agent = r.Agent(model=provider, db_path=tmp_path / "close.sqlite")
        try:
            with pytest.raises(error):
                await agent.aclose(**options)
            assert not agent._closed and agent.runtime.state == "open"
            assert agent.runtime._close_task is None
            assert (
                await agent.run("q", command_id="valid", wait_timeout=1)
            ).snapshot.result == "ok"
        finally:
            await agent.aclose(close_timeout=1)
        assert agent._closed and agent.runtime.state == "closed"
        assert (await agent.aclose(close_timeout=10**400)).state == "closed"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "exit_context", [False, True, "body-error"], ids=["aclose", "context-exit", "body-error"]
)
def test_wrong_loop_close_does_not_detach_owned_agent(tmp_path, exit_context):
    loop = asyncio.new_event_loop()
    agent = r.Agent(model=EchoProvider("offline"), db_path=tmp_path / "loop.sqlite")
    try:
        loop.run_until_complete(agent.__aenter__())
        if exit_context == "body-error":
            original = ValueError("application failed")
            with pytest.raises(ValueError) as seen:
                asyncio.run(agent.__aexit__(ValueError, original, None))
            assert seen.value is original and isinstance(original.__cause__, ValidationError)
        else:
            close = agent.__aexit__(None, None, None) if exit_context else agent.aclose()
            with pytest.raises(ValidationError, match="event loop"):
                asyncio.run(close)
        assert not agent._closed and agent.runtime.state == "open"
        assert agent.runtime._close_task is None
    finally:
        loop.run_until_complete(agent.aclose(close_timeout=1))
        loop.close()


async def resource_runtime(tmp_path, resource):
    async def factory(config, context):
        context.own_async(resource)
        return EchoProvider("offline")

    registry = r.ComponentRegistry()
    registry.register_async("provider", "fixture", factory)
    return await r.Runtime.afrom_profile(
        r.RuntimeProfile("fixture", "1", {"default": {"adapter": "fixture"}}),
        tmp_path / "resource.sqlite",
        builder=r.RuntimeBuilder(registry),
    )


@pytest.mark.parametrize("handled", [False, True], ids=["retained-failure", "handled-rejection"])
def test_resource_callback_reentry_is_rejected_before_facade_self_wait(tmp_path, handled):
    async def scenario():
        errors = []
        runtime = None

        class Resource:
            reenter = True
            calls = 0

            async def aclose(self):
                self.calls += 1
                if self.reenter:
                    try:
                        await runtime.aclose(close_timeout=0.02)
                    except Exception as error:
                        errors.append(type(error))
                        if not handled:
                            raise

        resource = Resource()
        runtime = await resource_runtime(tmp_path, resource)
        try:
            if handled:
                await runtime.aclose(close_timeout=1)
                assert runtime.state == "closed"
            else:
                with pytest.raises(CloseIncomplete):
                    await runtime.aclose(close_timeout=1)
                assert runtime.state == "close_failed"
                assert len(runtime.engine._context._resources) == 1
            assert errors == [ValidationError]
        finally:
            resource.reenter = False
            await runtime.aclose(close_timeout=1)
        assert resource.calls == (1 if handled else 2) and runtime.state == "closed"

    asyncio.run(scenario())


def test_external_close_observers_still_share_original_resource_shutdown(tmp_path):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        class Resource:
            calls = 0

            async def aclose(self):
                self.calls += 1
                started.set()
                await release.wait()

        resource = Resource()
        runtime = await resource_runtime(tmp_path, resource)
        first = asyncio.create_task(runtime.aclose(close_timeout=1))
        await started.wait()
        second = asyncio.create_task(runtime.aclose(close_timeout=1))
        await asyncio.sleep(0)
        release.set()
        one, two = await asyncio.gather(first, second)
        assert one == two and one.state == "closed" and resource.calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_wait", [False, True])
def test_real_owned_shutdown_still_detaches_entry_and_retains_work_for_retry(tmp_path, cancel_wait):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        effects = []

        async def handler(arguments, context):
            started.set()
            await release.wait()
            effects.append(context.effect_key)
            return {"finished": True}

        tools = r.ToolRegistry()
        tools.register(r.ToolSpec("block", "Block", {"type": "object"}), handler)
        provider = ScriptedProvider(
            [r.ModelResponse(tool_calls=[r.ToolCall("block", {})]), r.ModelResponse(output="ok")]
        )
        agent = r.Agent(model=provider, tools=tools, db_path=tmp_path / "drain.sqlite")
        await agent.submit("q", command_id="original")
        await started.wait()
        try:
            if cancel_wait:
                closer = asyncio.create_task(agent.aclose(close_timeout=1))
                await asyncio.sleep(0)
                closer.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await closer
            else:
                with pytest.raises(CloseIncomplete):
                    await agent.aclose(close_timeout=0.01)
            assert agent._closed and agent.runtime.state != "open" and not effects
            assert not agent.runtime._close_task.done()
            with pytest.raises(RuntimeClosed):
                await agent.submit("q", command_id="new")
        finally:
            release.set()
            await agent.aclose(close_timeout=1)
        assert agent.runtime.state == "closed" and len(effects) == 1 and provider.calls == 2

    asyncio.run(scenario())
