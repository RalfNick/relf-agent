import asyncio
import copy
from dataclasses import asdict
from types import SimpleNamespace

import pytest

import relf_agent as r
from relf_agent.errors import DefinitionMismatch
from relf_agent.temporal_activities import TemporalRuntime
from relf_agent.temporal_state import TemporalRunState
from relf_agent.types import submission_request

from .test_local_stream_updates import Provider


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
def test_stream_policy_does_not_replace_custom_authorization_identity(enabled, explicit):
    def policy(*args):
        return None

    expected = {"kind": "custom-authorization", "version": "1"}
    policy.identity = expected
    runtime = TemporalRuntime(
        providers={"default": r.StreamedModelProvider(Provider())},
        tools=r.ToolRegistry(),
        policy=policy,
        policy_identity=dict(expected) if explicit else None,
        stream_updates=r.StreamUpdatePolicy() if enabled else None,
    )
    assert runtime.policy_identity == expected
    assert runtime.manifest["policy"] == expected
    assert ("stream_updates" in runtime.manifest) is enabled


def make(policy=None, tools=None):
    runtime = TemporalRuntime(
        providers={"default": r.StreamedModelProvider(Provider(), chunk_chars=1)},
        tools=r.ToolRegistry() if tools is None else tools,
        stream_updates=policy,
    )
    state = TemporalRunState(
        "run",
        asdict(r.Scope()),
        "s",
        submission_request(r.AgentSpec("a", "Answer", tuple(runtime.tools._tools)), "q"),
        runtime.manifest,
        execution_epoch="epoch",
    )
    return runtime, state


def payload(state, action, sequence=1):
    return {
        "scope": state.scope,
        "run_id": state.run_id,
        "release_digest": state.release_digest,
        "execution_epoch": state.epoch,
        "update": {
            "version": 1,
            "action_id": action["id"],
            "attempt_id": action["attempts"][0]["id"],
            "operation": action["kind"],
            "sequence": sequence,
            "kind": action["kind"] + "_delta",
            "payload": {"text": "prefix"},
        },
    }


@pytest.mark.parametrize(
    "field", ["scope", "run_id", "release_digest", "execution_epoch", "attempt_id", "action_id"]
)
def test_original_history_refuses_foreign_progress_without_advancing_business(field):
    from relf_agent.temporal_stream_updates import accept_update

    _, state = make(r.StreamUpdatePolicy())
    action, _ = state.next_operation()
    value = payload(state, action)
    if field in {"attempt_id", "action_id"}:
        value["update"][field] = "foreign"
    else:
        value[field] = (
            {"workspace": "foreign", "principal": "owner"} if field == "scope" else "foreign"
        )
    before = state.diagnostics()
    with pytest.raises(DefinitionMismatch):
        accept_update(state, value)
    assert state.diagnostics() == before


def test_history_deduplicates_progress_detects_gap_and_retains_limits():
    from relf_agent.temporal_stream_updates import accept_update

    _, state = make(r.StreamUpdatePolicy(max_deltas=2))
    action, _ = state.next_operation()
    revision, budget, count = state.revision, state.budget, len(state.event_log)
    assert accept_update(state, payload(state, action)) is True
    assert accept_update(state, payload(state, action)) is False
    assert accept_update(state, payload(state, action, 3)) is True
    assert accept_update(state, payload(state, action, 4)) is False
    assert state.revision == revision and state.budget == budget
    rows = [e for e in state.event_log[count:] if e["kind"] == "agent_update"]
    assert sum(e["data"]["kind"] == "gap" for e in rows) == 1
    assert sum(e["data"]["kind"] == "model_delta" for e in rows) == 2


def test_worker_activity_projection_uses_same_model_tool_protocol_and_end_facts():
    from relf_agent.temporal_stream_updates import accept_update, observe_activity

    async def run():
        tools, calls = r.ToolRegistry(), []

        @tools.tool(effect="read_only", context_parameter="context")
        async def change(*, context):
            calls.append(context.effect_key)
            assert await r.emit_tool_delta({"progress": "read"})
            return {"found": True}

        runtime, state = make(r.StreamUpdatePolicy(), tools)
        for _ in range(6):
            work = state.next_operation()
            if work is None:
                break
            action, request = work

            async def publish(update, request=request):
                assert accept_update(
                    state,
                    {
                        name: request[name]
                        for name in ("scope", "run_id", "release_digest", "execution_epoch")
                    }
                    | {"update": update},
                )

            if action["kind"] == "model":
                result = await observe_activity(
                    request,
                    "model",
                    lambda request=request: runtime.complete_model(request),
                    publish,
                )
                state.accept_model(action["id"], result)
            else:
                result = await observe_activity(
                    request, "tool", lambda request=request: runtime.execute_tool(request), publish
                )
                state.accept_tool(action["id"], result)
        assert state.state == "succeeded" and state.result == "done" and len(calls) == 1
        rows = [
            r.AgentStreamEvent(r.EventEnvelope(r.Scope(), r.RunEvent(**e))) for e in state.event_log
        ]
        assert {e.kind for e in rows} >= {"model_delta", "tool_delta", "model_end", "tool_end"}
        assert sum(e.kind in {"model_end", "tool_end"} for e in rows) == 3
        assert all(e.attempt_id for e in rows if e.kind != "run")

    asyncio.run(run())


def test_callback_pins_actual_epoch_and_borrows_original_client():
    from relf_agent.temporal_stream_updates import callbacks

    async def run():
        _, state = make(r.StreamUpdatePolicy())
        action, request = state.next_operation()
        seen = []

        class Client:
            namespace = "ns"

            def get_workflow_handle(self, workflow_id, *, run_id):
                assert (workflow_id, run_id) == ("run", "epoch")
                return self

            async def signal(self, name, value):
                seen.append((name, value))

        client = Client()
        send = callbacks(
            client,
            request,
            SimpleNamespace(workflow_id="run", workflow_run_id="epoch", workflow_namespace="ns"),
        )
        original_scope = copy.deepcopy(request["scope"])
        request["scope"]["principal"] = "caller mutation"
        await send(payload(state, action)["update"])
        assert seen[0][0] == "agent_update" and seen[0][1]["execution_epoch"] == "epoch"
        assert seen[0][1]["scope"] == original_scope
        client.namespace = "other"
        with pytest.raises(DefinitionMismatch):
            await send(payload(state, action)["update"])
        assert len(seen) == 1 and not hasattr(client, "close")

    asyncio.run(run())
