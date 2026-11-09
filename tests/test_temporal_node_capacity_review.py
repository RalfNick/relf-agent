"""Late no-start evidence cannot undo an accepted end or repair unknown work."""

import asyncio
import copy

import pytest

from relf_agent import temporal_node_capacity as capacity
from relf_agent.errors import CloseIncomplete
from relf_agent.types import digest

from .test_temporal_node_capacity import guard, make_state
from .test_temporal_workflow_nodes_state import acknowledge


def dispatch():
    runtime, state = make_state()
    action, request = state.next_operation()
    capacity.begin_window(state, action, now=100.0, total_seconds=15.0)
    return runtime, state, action, request


def test_duplicate_completed_unstarted_reply_preserves_zero_consumption_and_quiescence():
    _, state, action, request = dispatch()
    response = capacity.unstarted(request, "validation_error")
    state.accept_tool(action["id"], response)
    assert state.state == "failed" and state.quiescent
    before = copy.deepcopy(state.budget)
    state.accept_tool(action["id"], copy.deepcopy(response))
    assert state.state == "failed" and state.quiescent
    assert state.budget == before
    assert action["attempts"][0]["status"] == "not_dispatched"
    assert action["status"] == "failed"


@pytest.mark.parametrize("kind", ["capacity", "unstarted", "generic-undispatched"])
def test_rejected_capacity_proof_cannot_be_repaired_by_later_no_start_response(kind):
    _, state, action, request = dispatch()
    invalid = capacity.refusal(request)
    invalid["node_capacity"]["request_digest"] = "0" * 64
    state.accept_tool(action["id"], invalid)
    assert state.state == "waiting_reconciliation" and state.budget["unknown"] == 2
    before = copy.deepcopy(state.budget)
    response = (
        capacity.refusal(request)
        if kind == "capacity"
        else capacity.unstarted(request, "validation_error")
        if kind == "unstarted"
        else {"ok": False, "code": "validation_error", "dispatched": False}
    )
    state.accept_tool(action["id"], response)
    assert state.state == "waiting_reconciliation"
    assert state.budget == before
    assert action["status"] == "outcome_unknown"
    assert capacity.waiting(state) is None
    assert not capacity.resume(state, now=100.5)
    assert state.next_operation() is None


def terminal_state(outcome):
    runtime, state, action, request = dispatch()
    if outcome == "failed":
        state.accept_tool(action["id"], capacity.unstarted(request, "validation_error"))
    elif outcome == "cancelled":
        state.accept_tool(action["id"], capacity.refusal(request))
        state.command("cancel-original", {"kind": "cancel", "scope": state.scope})
    else:
        assert guard(state, request)["allowed"] is True
        state.tool_execution_ended(
            {
                name: request[name]
                for name in ("scope", "action_id", "release_digest", "execution_epoch")
            }
            | {"request_digest": digest(request), "invocation_id": "a" * 32}
        )
        state.accept_tool(action["id"], {"ok": True, "result": [False, 0, None]})
        acknowledge(state)
        state.next_operation()
    assert state.state == outcome and state.quiescent
    return runtime, state, action, request


@pytest.mark.parametrize("outcome", ["failed", "cancelled", "succeeded"])
@pytest.mark.parametrize("kind", ["capacity", "unstarted"])
def test_late_foreign_no_start_reply_cannot_reopen_committed_terminal_work(outcome, kind):
    _, state, action, request = terminal_state(outcome)
    response = (
        capacity.refusal(request)
        if kind == "capacity"
        else capacity.unstarted(request, "validation_error")
    )
    response["node_capacity" if kind == "capacity" else "node_not_started"]["request_digest"] = (
        "0" * 64
    )
    before = (copy.deepcopy(state.budget), action["status"], copy.deepcopy(state.result))
    state.accept_tool(action["id"], response)
    assert state.state == outcome and state.quiescent
    assert (state.budget, action["status"], state.result) == before
    assert state.next_operation() is None


def test_closing_malformed_capacity_request_returns_structured_failure_without_raising():
    runtime, state, _, request = dispatch()
    malformed = copy.deepcopy(request)
    malformed.pop("node_capacity_ordinal")
    runtime._tool_execution_closing = True
    callbacks = []

    async def admission(value, *, invocation_id):
        callbacks.append("admission")
        return guard(state, value, invocation_id)

    async def ended(value):
        callbacks.append("end")

    async def run():
        try:
            response = await runtime.execute_tool(malformed, dispatch_guard=admission, on_end=ended)
            assert type(response) is dict and response["ok"] is False
            assert response["dispatched"] is False
            assert "node_capacity" not in response and "node_not_started" not in response
            assert callbacks == []
        finally:
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)

    asyncio.run(run())


@pytest.mark.parametrize("timing", ["before-guard", "during-guard"])
def test_original_guard_denial_after_cancel_settles_no_effect_without_unknown(timing):
    runtime, state, action, request = dispatch()

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        grants, ends = [], []

        async def admission(value, *, invocation_id):
            entered.set()
            if timing == "during-guard":
                await release.wait()
            result = guard(state, value, invocation_id)
            grants.append(result)
            return result

        async def ended(value):
            ends.append(value)
            state.tool_execution_ended(value)

        if timing == "before-guard":
            state.command("cancel-original", {"kind": "cancel", "scope": state.scope})
        execution = asyncio.create_task(
            runtime.execute_tool(request, dispatch_guard=admission, on_end=ended)
        )
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if timing == "during-guard":
                state.command("cancel-original", {"kind": "cancel", "scope": state.scope})
                release.set()
            response = await execution
            assert await runtime.wait_context_executions(wait_timeout=5)
            state.accept_tool(action["id"], response)
            assert len(grants) == len(ends) == 1
            assert grants[0]["claimed"] is True and grants[0]["allowed"] is False
            assert response["dispatched"] is False
            assert state.state == "cancelled" and state.quiescent
            assert state.budget["unknown"] == state.budget["reserved"] == 0
            assert state.budget["spent"] == 0
        finally:
            release.set()
            await asyncio.gather(execution, return_exceptions=True)
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)

    asyncio.run(run())


def test_host_closes_after_guard_allowed_before_handler_settles_known_no_start():
    runtime, state, action, request = dispatch()

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        grants, ends = [], []

        async def admission(value, *, invocation_id):
            result = guard(state, value, invocation_id)
            grants.append(result)
            entered.set()
            await release.wait()
            return result

        async def ended(value):
            ends.append(value)
            state.tool_execution_ended(value)

        execution = asyncio.create_task(
            runtime.execute_tool(request, dispatch_guard=admission, on_end=ended)
        )
        try:
            await asyncio.wait_for(entered.wait(), 5)
            assert grants[0]["claimed"] is True and grants[0]["allowed"] is True
            with pytest.raises(CloseIncomplete):
                await runtime.close_context_execution(wait_timeout=0)
            release.set()
            response = await execution
            assert await runtime.wait_context_executions(wait_timeout=5)
            state.accept_tool(action["id"], response)
            assert len(ends) == 1
            assert response["ok"] is False and response["dispatched"] is False
            assert state.state == "failed" and state.quiescent
            assert state.budget["unknown"] == state.budget["reserved"] == 0
            assert state.budget["spent"] == 0
        finally:
            release.set()
            await asyncio.gather(execution, return_exceptions=True)
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)

    asyncio.run(run())


def test_foreign_claim_denial_never_confirms_original_invocation_stopped():
    runtime, state, action, request = dispatch()
    assert guard(state, request, "b" * 32)["allowed"] is True

    async def run():
        ends = []

        async def admission(value, *, invocation_id):
            return guard(state, value, invocation_id)

        async def ended(value):
            ends.append(value)
            state.tool_execution_ended(value)

        try:
            response = await runtime.execute_tool(request, dispatch_guard=admission, on_end=ended)
            assert await runtime.wait_context_executions(wait_timeout=5)
            state.accept_tool(action["id"], response)
            assert response["dispatched"] is True
            assert ends == []
            assert state.state == "waiting_reconciliation" and state.budget["unknown"] == 2
            assert not state.quiescent
        finally:
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)

    asyncio.run(run())


def test_uncertain_action_after_fenced_wait_cannot_schedule_another_capacity_transport():
    _, state, action, request = dispatch()
    state.accept_tool(action["id"], capacity.refusal(request))
    capacity.delay(state, now=100.0)
    invalid = capacity.refusal(request)
    invalid["node_capacity"]["request_digest"] = "0" * 64
    state.accept_tool(action["id"], invalid)
    # A foreign reply can be ignored after the accepted fence. If it instead
    # makes the action uncertain, it must not leave a live capacity retry path.
    assert action["status"] != "outcome_unknown" or capacity.waiting(state) is None
    if action["status"] == "outcome_unknown":
        assert not capacity.resume(state, now=100.5)
        assert state.next_operation() is None
        assert state.budget["unknown"] == 2


def test_cancel_after_timer_ready_before_transport_releases_original_unstarted_reservation():
    _, state, action, request = dispatch()
    state.accept_tool(action["id"], capacity.refusal(request))
    capacity.delay(state, now=100.0)
    assert capacity.resume(state, now=100.2)
    assert action["node_capacity"]["phase"] == "retry_ready" and state.active_action is None
    state.command("cancel-ready", {"kind": "cancel", "scope": state.scope})
    assert state.state == "cancelled" and state.quiescent
    assert state.budget["reserved"] == state.budget["unknown"] == state.budget["spent"] == 0
    assert state.next_operation() is None


def test_outer_notification_saturation_is_unclaimed_capacity_and_can_resume_original_action():
    from .test_temporal_node_capacity_runtime import system

    async def run():
        runtime, component, states = system()
        state = states[-1]
        action, request = state.next_operation()
        capacity.begin_window(state, action, now=100.0, total_seconds=15.0)
        entered, release = asyncio.Event(), asyncio.Event()
        count, grants = 0, []

        async def held():
            nonlocal count
            count += 1
            if count == 256:
                entered.set()
            await release.wait()

        async def admission(value, *, invocation_id):
            result = guard(state, value, invocation_id)
            grants.append(result)
            return result

        async def ended(value):
            state.tool_execution_ended(value)

        held_tasks = []
        try:
            for index in range(256):
                value = {
                    name: request[name] for name in ("scope", "release_digest", "execution_epoch")
                } | {
                    "action_id": "notification-filler-" + str(index),
                    "request_digest": digest({"notification-filler": index}),
                }
                held_tasks.append(
                    asyncio.create_task(runtime._tool_notifications.execute(held, proof=value))
                )
            await asyncio.wait_for(entered.wait(), 5)
            response = await runtime.execute_tool(request, dispatch_guard=admission, on_end=ended)
            state.accept_tool(action["id"], response)
            assert response["code"] == capacity.WAIT_CODE and grants == []
            assert component.calls == [] and state.budget["reserved"] == 1
            assert "invocation_id" not in state.tool_executions[action["id"]]
            release.set()
            await asyncio.gather(*held_tasks)
            assert await runtime.wait_context_executions(wait_timeout=5)
            assert capacity.resume(state, now=100.2)
            same_action, next_request = state.next_operation()
            assert same_action is action
            component.release.set()
            result = await runtime.execute_tool(
                next_request, dispatch_guard=admission, on_end=ended
            )
            state.accept_tool(action["id"], result)
            assert await runtime.wait_context_executions(wait_timeout=5)
            assert result["ok"] is True and len(component.calls) == 1
            assert len(grants) == 1 and grants[0]["allowed"] is True
            assert state.budget["spent"] == 1
        finally:
            release.set()
            component.release.set()
            await asyncio.gather(*held_tasks, return_exceptions=True)
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)

    asyncio.run(run())
