"""SDK Workflow timer projection; actual Service recovery is separately exercised."""

import asyncio
from datetime import UTC, datetime

import pytest

from relf_agent.temporal_workflow import TemporalRunWorkflow, workflow

from .test_temporal_node_capacity import waiting_state


@pytest.mark.parametrize("mode", ["timer", "timer-clock-batch", "early-wake", "cancel", "expired"])
def test_original_workflow_waits_with_its_history_clock_and_cancel_semantics(monkeypatch, mode):
    _, state, action, _, _ = waiting_state()
    host = object.__new__(TemporalRunWorkflow)
    host.state, host.wake_revision = state, 0
    clock = [115.0 if mode == "expired" else 100.0]
    waits = []
    monkeypatch.setattr(workflow, "now", lambda: datetime.fromtimestamp(clock[0], UTC))

    async def sleep(seconds):
        waits.append(seconds)
        if mode == "early-wake":
            clock[0] += 0.01
            host.wake_revision += 1
            await asyncio.sleep(0)
            assert action["node_capacity"]["phase"] == "waiting"
        if mode == "cancel":
            await asyncio.Event().wait()
        if mode != "timer-clock-batch":
            clock[0] += seconds

    async def wait_condition(predicate):
        while not predicate():
            if mode == "cancel" and waits:
                state.command("cancel", {"kind": "cancel", "scope": state.scope})
                host.wake_revision += 1
            await asyncio.sleep(0)

    monkeypatch.setattr(workflow, "wait_condition", wait_condition)
    monkeypatch.setattr(workflow, "sleep", sleep)

    async def run():
        assert await host._wait_node_capacity()
        assert action["node_capacity"]["phase"] == (
            "closed" if mode in {"cancel", "expired"} else "retry_ready"
        )
        if mode in {"cancel", "expired"}:
            assert state.budget["reserved"] == 0 and state.quiescent
        else:
            assert state.budget["reserved"] == 2 and action["node_capacity"]["ordinal"] == 1
        assert all(0 < value <= 0.1 for value in waits)
        assert len(waits) == (0 if mode == "expired" else 1)

    asyncio.run(run())
