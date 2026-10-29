import asyncio
from contextlib import aclosing

import pytest

import relf_agent as r
from relf_agent.errors import DefinitionMismatch, ValidationError


def api(name):
    assert hasattr(r, name), f"Missing stream API: {name}"
    return getattr(r, name)


@pytest.mark.parametrize(
    "options",
    [
        {"max_deltas": True},
        {"max_deltas": 0},
        {"max_deltas": 1025},
        {"max_bytes": 0},
        {"max_payload_bytes": 0},
        {"max_bytes": 256, "max_payload_bytes": 512},
        {"publish_timeout": float("nan")},
        {"publish_timeout": True},
        {"publish_timeout": 10**400},
        {"publish_timeout": -(10**400)},
    ],
)
def test_policy_refuses_invalid_limits(options):
    with pytest.raises(ValidationError):
        api("StreamUpdatePolicy")(**options)


def test_policy_roundtrip_and_detached_identity():
    policy = api("StreamUpdatePolicy")()
    identity = policy.identity
    assert type(policy).from_identity(identity) == policy
    identity["max_deltas"] = 0
    assert policy.identity["max_deltas"] == 64
    with pytest.raises(ValidationError):
        type(policy).from_identity({**policy.identity, "extra": True})


class Provider:
    identity = {"kind": "stream-contract", "version": "1"}

    def __init__(self, mode="ok"):
        self.mode, self.calls, self.closed = mode, 0, False

    async def complete(self, messages, tools):
        pytest.fail("Stream adapter must make exactly one stream call")

    async def stream(self, messages, tools):
        self.calls += 1
        try:
            yield r.ModelStreamEvent("text", text="hello ")
            yield r.ModelStreamEvent("text", text="world")
            if self.mode == "failure":
                raise RuntimeError("source failed")
            if self.mode != "missing":
                yield r.ModelStreamEvent("response", response=r.ModelResponse("hello world"))
            if self.mode == "extra":
                yield r.ModelStreamEvent("text", text="late")
        finally:
            self.closed = True


@pytest.mark.parametrize("mode", ["missing", "extra", "failure"])
def test_incomplete_or_invalid_stream_never_returns_partial_decision(mode):
    provider = Provider(mode)
    wrapped = api("StreamedModelProvider")(provider)
    with pytest.raises((ValidationError, RuntimeError)):
        asyncio.run(wrapped.complete([], []))
    assert provider.calls == 1 and provider.closed


def test_stream_adapter_returns_completed_response_and_borrows_provider():
    async def run():
        provider = Provider()
        wrapped = api("StreamedModelProvider")(provider)
        assert await wrapped.complete([], []) == r.ModelResponse("hello world")
        assert provider.calls == 1 and provider.closed
        assert not hasattr(wrapped, "aclose")
        provider.identity = {"kind": "stream-contract", "version": "2"}
        with pytest.raises(DefinitionMismatch):
            await wrapped.complete([], [])
        assert provider.calls == 1
        assert await api("emit_tool_delta")({"message": "no active attempt"}) is False

    asyncio.run(run())


def test_stream_adapter_cancellation_closes_source():
    async def run():
        entered = asyncio.Event()

        class Waiting(Provider):
            async def stream(self, messages, tools):
                try:
                    yield r.ModelStreamEvent("text", text="prefix")
                    entered.set()
                    await asyncio.Event().wait()
                finally:
                    self.closed = True

        provider = Waiting()
        wrapped = api("StreamedModelProvider")(provider)
        task = asyncio.create_task(wrapped.complete([], []))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert provider.closed

    asyncio.run(run())


def test_typed_delta_and_run_fact_have_distinct_semantics():
    value = {
        "version": 1,
        "action_id": "action",
        "attempt_id": "action:1",
        "operation": "model",
        "sequence": 1,
        "kind": "model_delta",
        "payload": {"text": "prefix"},
    }
    envelope = r.EventEnvelope(r.Scope(), r.RunEvent("run", 1, "agent_update", value))
    event = api("AgentStreamEvent")(envelope)
    assert event.kind == "model_delta" and event.authoritative is False
    event.data["text"] = "changed"
    assert event.data == {"text": "prefix"} and event.cursor == envelope.cursor
    fact = api("AgentStreamEvent")(
        r.EventEnvelope(r.Scope(), r.RunEvent("run", 2, "run_succeeded", {}))
    )
    assert fact.kind == "run" and fact.authoritative is True
    assert fact.source_kind == "run_succeeded"


def test_projected_subscription_keeps_last_valid_cursor_on_invalid_protocol():
    class Reader:
        scope = r.Scope()

        def status(self, run_id):
            return r.RunSnapshot(run_id, "succeeded", 1, "ok", None, (), ())

        def events(self, run_id, *, after=0, limit=1000):
            return [r.RunEvent(run_id, 1, "agent_update", {"version": 99})] if after == 0 else []

    async def run():
        from relf_agent.stream_updates import AgentStreamSubscription

        raw = r.RunEventSubscription(Reader(), "run", follow=False)
        async with aclosing(AgentStreamSubscription(raw)) as stream:
            with pytest.raises(ValidationError):
                await anext(stream)
            assert stream.cursor.after == 0

    asyncio.run(run())


def test_malformed_capabilities_are_typed_configuration_error():
    provider = Provider()
    provider.capabilities = {"streaming": True}
    with pytest.raises(ValidationError):
        api("StreamedModelProvider")(provider)


def test_active_stream_uses_frozen_chunk_configuration():
    async def run():
        from relf_agent.stream_reporting import attempt_scope

        updates = []

        async def publish(value):
            updates.append(value)

        class Changing(Provider):
            async def stream(self, messages, tools):
                wrapper.chunk_chars = 1
                yield r.ModelStreamEvent("text", text="longer than one character")
                yield r.ModelStreamEvent("response", response=r.ModelResponse("done"))

        wrapper = api("StreamedModelProvider")(Changing(), chunk_chars=128)
        with attempt_scope(api("StreamUpdatePolicy")().identity, "model", "a", "a:1", publish):
            assert (await wrapper.complete([], [])).output == "done"
        assert len(updates) == 1
        with pytest.raises(DefinitionMismatch):
            await wrapper.complete([], [])

    asyncio.run(run())


def test_stream_adapter_keeps_continuation_type_owner_and_payload():
    from relf_agent.model_continuation import decode_received_response
    from relf_agent.model_evidence import snapshot_model_response
    from tests.test_model_continuation import received

    original = received()

    class Continued(Provider):
        continuation_identity = {"protocol": "fixture-functions-1", "owner_digest": "a" * 64}

        async def stream(self, messages, tools):
            yield r.ModelStreamEvent("response", response=decode_received_response(original))

    wrapped = api("StreamedModelProvider")(Continued())
    result = asyncio.run(wrapped.complete([], []))
    assert snapshot_model_response(result) == original
    assert wrapped.continuation_identity == Continued.continuation_identity
