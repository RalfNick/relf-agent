"""Invalid observation timeouts never start cleanup or cancel accepted work."""

import asyncio

import pytest

import relf_agent as r
from relf_agent.agent_runtime import seconds
from relf_agent.errors import ValidationError

from .helpers import ScriptedProvider
from .temporal_agent_fixture import engine as temporal_engine
from .test_agent_runtime import engine


@pytest.mark.parametrize(
    "value", [10**400, -(10**400), True, False, None, "1", -1, float("nan"), float("inf")]
)
def test_seconds_rejects_unrepresentable_and_invalid_values(value):
    with pytest.raises(ValidationError, match="Wait timeout must be finite non-negative seconds"):
        seconds(value, "Wait timeout")


@pytest.mark.parametrize("value", [0, 1, 0.25, 10**300])
def test_seconds_preserves_original_finite_values_and_types(value):
    assert seconds(value, "Wait timeout") is value


@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_local_runtime_constructor_refuses_huge_timeout_without_taking_ownership(tmp_path, value):
    with engine(tmp_path / "local.sqlite", ScriptedProvider([])) as raw:
        with pytest.raises(ValidationError, match="Close timeout"):
            r.Runtime(raw, owned=True, close_timeout=value)
        # Failed facade construction does not close the borrowed authority.
        handle = raw.submit(r.AgentSpec("a", "Answer"), "q", command_id="original")
        assert raw.status(handle.run_id).state == "queued"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_profile_timeout_rejected_before_builder_or_database(tmp_path, asynchronous):
    calls = []

    class Builder:
        def build(self, *args, **kwargs):
            calls.append("build")
            raise AssertionError("Invalid timeout must precede resource creation")

        async def abuild(self, *args, **kwargs):
            calls.append("abuild")
            raise AssertionError("Invalid timeout must precede resource creation")

    path = tmp_path / "not-created.sqlite"
    with pytest.raises(ValidationError, match="Close timeout"):
        if asynchronous:
            asyncio.run(
                r.Runtime.afrom_profile(
                    r.RuntimeProfile("test", "1", {}),
                    path,
                    builder=Builder(),
                    close_timeout=10**400,
                )
            )
        else:
            r.Runtime.from_profile(
                r.RuntimeProfile("test", "1", {}), path, builder=Builder(), close_timeout=10**400
            )
    assert not calls and not path.exists()


def test_invalid_wait_does_not_cancel_or_advance_live_local_run(tmp_path):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        class Provider:
            identity = {"kind": "timeout-validation-fixture", "version": "1"}

            async def complete(self, messages, tools):
                calls.append("model")
                started.set()
                await release.wait()
                return r.ModelResponse(output="done")

        async with r.Runtime(engine(tmp_path / "wait.sqlite", Provider()), owned=True) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer")).submit(
                "q", command_id="once"
            )
            await started.wait()
            before = await handle.status()
            events = await handle.events()
            try:
                with pytest.raises(ValidationError, match="Wait timeout"):
                    await handle.wait(wait_timeout=10**400)
                after = await handle.status()
                assert after.state == before.state == "running"
                assert after.state_revision == before.state_revision
                assert await handle.events() == events
                assert calls == ["model"]
            finally:
                release.set()
            assert (await handle.wait(wait_timeout=1)).snapshot.result == "done"
            assert calls == ["model"]

    asyncio.run(scenario())


def test_invalid_close_override_leaves_local_runtime_open_for_safe_retry(tmp_path):
    async def scenario():
        runtime = r.Runtime(engine(tmp_path / "close.sqlite", ScriptedProvider([])), owned=True)
        try:
            with pytest.raises(ValidationError, match="Close timeout"):
                await runtime.aclose(close_timeout=10**400)
            assert runtime.state == "open" and runtime._close_task is None
        finally:
            await runtime.aclose(close_timeout=1)
        assert runtime.state == "closed"

    asyncio.run(scenario())


def test_temporal_runtime_timeout_constructor_rejects_before_rpc(monkeypatch):
    async def scenario():
        raw = temporal_engine(monkeypatch)
        with pytest.raises(ValidationError, match="Close timeout"):
            r.Runtime.from_temporal(raw, close_timeout=10**400)
        assert not raw.client.states and not raw._closed

    asyncio.run(scenario())


def test_invalid_remote_wait_preserves_original_approval_and_business_receipt(monkeypatch):
    async def scenario():
        raw = temporal_engine(monkeypatch)
        async with r.Runtime.from_temporal(raw) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer", ("lookup",))).submit(
                "q", command_id="once"
            )
            assert (await handle.wait(wait_timeout=1)).snapshot.state == "waiting_approval"
            before = await handle.status()
            with pytest.raises(ValidationError, match="Wait timeout"):
                await handle.wait(wait_timeout=10**400)
            after = await handle.status()
            assert after.state == before.state == "waiting_approval"
            assert after.state_revision == before.state_revision and raw.client.tool_calls == 0
            (item,) = await handle.pending()
            await handle.approve(item["action_id"], item["digest"], command_id="approve")
            assert (await handle.wait(wait_timeout=1)).snapshot.result == "done"
            assert raw.client.tool_calls == 1

    asyncio.run(scenario())
