"""Only a proven original-node owner capacity refusal is retryable by History."""

import asyncio
import importlib

import pytest

from relf_agent.errors import CloseIncomplete, ValidationError
from relf_agent.temporal_context_execution import ContextExecutionRejected
from relf_agent.tool_execution import ToolExecutionOwner
from relf_agent.types import digest


def api():
    try:
        module = importlib.import_module("relf_agent.temporal_node_capacity_owner")
    except ModuleNotFoundError as exc:
        assert exc.name != "relf_agent.temporal_node_capacity_owner", (
            "The node-only, capacity-specific owner must exist"
        )
        raise
    return module


def proof(action="first"):
    return {
        "scope": {"workspace": "local", "principal": "local-user"},
        "action_id": action,
        "release_digest": digest({"release": "node"}),
        "request_digest": digest({"request": action}),
        "execution_epoch": "original-node-epoch",
    }


def owner(module, kind, *, max_calls=1):
    cls = module.NodeCapacityOwner if kind == "tool" else module.NodeNotificationOwner
    return cls(max_calls=max_calls)


def test_node_specific_defaults_keep_bounded_original_owner_metadata():
    module = api()
    tool = module.NodeCapacityOwner()
    assert isinstance(tool, ToolExecutionOwner)
    assert module.NODE_OWNER_KIND == "workflow-node-capacity-owner"
    assert tool.identity == {
        "kind": module.NODE_OWNER_KIND,
        "version": "1",
        "behavior_version": "workflow-node-capacity-1",
        "max_calls": 16,
    }
    assert module.NodeNotificationOwner().identity == {
        "kind": "context-execution-owner",
        "version": "1",
        "max_calls": 256,
    }
    tool.identity["max_calls"] = 2
    assert tool.identity["max_calls"] == 16


@pytest.mark.parametrize("kind", ["tool", "notification"])
@pytest.mark.parametrize("value", [True, 0, -1, 257, "16", None])
def test_node_owner_keeps_original_capacity_validation(kind, value):
    module = api()
    with pytest.raises(ValidationError):
        owner(module, kind, max_calls=value)


@pytest.mark.parametrize("kind", ["tool", "notification"])
def test_full_distinct_action_is_capacity_only_without_scheduling_or_dispatch(kind):
    module = api()

    async def run():
        component = owner(module, kind)
        entered, release = asyncio.Event(), asyncio.Event()
        calls, ends = [], []

        async def operation():
            calls.append("first")
            entered.set()
            await release.wait()
            return {"value": None}

        async def second():
            calls.append("second")
            return False

        async def ended(value):
            ends.append(value)

        active = asyncio.create_task(component.execute(operation, proof=proof(), on_end=ended))
        await asyncio.wait_for(entered.wait(), 5)
        try:
            tasks = set(asyncio.all_tasks())
            with pytest.raises(module.NodeCapacityUnavailable) as caught:
                await component.execute(second, proof=proof("second"), on_end=ended)
            assert type(caught.value) is module.NodeCapacityUnavailable
            assert isinstance(caught.value, ContextExecutionRejected)
            assert caught.value.handler_not_started is True
            assert caught.value.code == ContextExecutionRejected(handler_not_started=True).code
            assert set(asyncio.all_tasks()) == tasks
            assert calls == ["first"] and ends == []
            assert await component.wait(wait_timeout=0) is False
        finally:
            release.set()
            assert await active == {"value": None}
            assert await component.wait(wait_timeout=5)
        assert await component.execute(second, proof=proof("second"), on_end=ended) is False
        assert await component.wait(wait_timeout=5)
        await component.aclose()
        assert calls == ["first", "second"]
        assert ends == [proof(), proof("second")]

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["tool", "notification"])
@pytest.mark.parametrize("changed_request", [False, True])
def test_full_original_action_is_duplicate_not_capacity(kind, changed_request):
    module = api()

    async def run():
        component = owner(module, kind)
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def operation():
            calls.append(True)
            entered.set()
            await release.wait()

        active = asyncio.create_task(component.execute(operation, proof=proof()))
        await asyncio.wait_for(entered.wait(), 5)
        duplicate = proof()
        if changed_request:
            duplicate["request_digest"] = digest({"changed": True})
        try:
            with pytest.raises(ContextExecutionRejected) as caught:
                await component.execute(operation, proof=duplicate)
            assert type(caught.value) is ContextExecutionRejected
            assert caught.value.handler_not_started is False
            assert calls == [True]
        finally:
            release.set()
            await active
            await component.aclose(wait_timeout=5)

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["tool", "notification"])
@pytest.mark.parametrize("bad", ["proof", "operation", "callback"])
def test_invalid_call_on_full_owner_preserves_original_validation(kind, bad):
    module = api()

    async def run():
        component = owner(module, kind)
        entered, release = asyncio.Event(), asyncio.Event()

        async def operation():
            entered.set()
            await release.wait()

        active = asyncio.create_task(component.execute(operation, proof=proof()))
        await asyncio.wait_for(entered.wait(), 5)
        options = {"proof": proof("second")}
        method = operation
        if bad == "proof":
            options["proof"]["execution_epoch"] = None
        elif bad == "operation":

            def method():
                return None

        else:
            options["on_end"] = 0
        try:
            with pytest.raises(ValidationError):
                await component.execute(method, **options)
        finally:
            release.set()
            await active
            await component.aclose(wait_timeout=5)

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["tool", "notification"])
def test_closed_owner_refusal_is_not_capacity(kind):
    module = api()

    async def run():
        component = owner(module, kind)
        await component.aclose()
        calls = []

        async def operation():
            calls.append(True)

        with pytest.raises(ContextExecutionRejected) as caught:
            await component.execute(operation, proof=proof())
        assert type(caught.value) is ContextExecutionRejected
        assert caught.value.handler_not_started is True
        assert calls == []

    asyncio.run(run())


def test_closing_full_tool_owner_refusal_is_not_capacity():
    module = api()

    async def run():
        component = module.NodeCapacityOwner(max_calls=1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def operation():
            entered.set()
            await release.wait()

        active = asyncio.create_task(component.execute(operation, proof=proof()))
        await asyncio.wait_for(entered.wait(), 5)
        try:
            with pytest.raises(CloseIncomplete):
                await component.aclose(wait_timeout=0)
            with pytest.raises(ContextExecutionRejected) as caught:
                await component.execute(operation, proof=proof("second"))
            assert type(caught.value) is ContextExecutionRejected
        finally:
            release.set()
            await active
            await component.aclose(wait_timeout=5)

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["tool", "notification"])
def test_business_refusal_after_other_slot_fills_is_not_capacity(kind):
    module = api()

    async def run():
        component = owner(module, kind, max_calls=2)
        entered, release, other_entered, other_release = (asyncio.Event() for _ in range(4))
        original = ContextExecutionRejected(handler_not_started=True)

        async def operation():
            entered.set()
            await release.wait()
            raise original

        async def other():
            other_entered.set()
            await other_release.wait()

        first = asyncio.create_task(component.execute(operation, proof=proof()))
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(component.execute(other, proof=proof("other")))
        await asyncio.wait_for(other_entered.wait(), 5)
        try:
            release.set()
            with pytest.raises(ContextExecutionRejected) as caught:
                await first
            assert caught.value is original
            assert type(caught.value) is ContextExecutionRejected
        finally:
            release.set()
            other_release.set()
            await asyncio.gather(first, second, return_exceptions=True)
            await component.aclose(wait_timeout=5)

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["tool", "notification"])
def test_pending_end_ack_retains_capacity_and_original_close_retry(kind):
    module = api()

    async def run():
        component = owner(module, kind)
        acknowledge, entered = asyncio.Event(), asyncio.Event()
        effects, ends = [], []

        async def operation():
            effects.append("effect")
            return 0

        async def ended(value):
            ends.append(value)
            entered.set()
            await acknowledge.wait()

        assert await component.execute(operation, proof=proof(), on_end=ended) == 0
        await asyncio.wait_for(entered.wait(), 5)
        try:
            with pytest.raises(module.NodeCapacityUnavailable):
                await component.execute(operation, proof=proof("second"))
            with pytest.raises(CloseIncomplete):
                await component.aclose(wait_timeout=0)
            assert effects == ["effect"]
        finally:
            acknowledge.set()
            await component.aclose(wait_timeout=5)
        assert ends == [proof()]

    asyncio.run(run())


def test_original_tool_owner_capacity_refusal_remains_general():
    module = api()

    async def run():
        component = ToolExecutionOwner(version="original", max_calls=1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def operation():
            entered.set()
            await release.wait()

        active = asyncio.create_task(component.execute(operation, proof=proof()))
        await asyncio.wait_for(entered.wait(), 5)
        try:
            with pytest.raises(ContextExecutionRejected) as caught:
                await component.execute(operation, proof=proof("second"))
            assert type(caught.value) is ContextExecutionRejected
            assert not isinstance(caught.value, module.NodeCapacityUnavailable)
        finally:
            release.set()
            await active
            await component.aclose(wait_timeout=5)

    asyncio.run(run())
