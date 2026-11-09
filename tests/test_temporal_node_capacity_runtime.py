"""Real handlers and original History guards over a shared bounded Worker owner."""

import asyncio
import json
from dataclasses import asdict

import pytest

import relf_agent as r
from relf_agent import temporal_node_capacity as capacity
from relf_agent.errors import CloseIncomplete
from relf_agent.temporal_activities import TemporalRuntime
from relf_agent.temporal_parent_state import TemporalParentState
from relf_agent.temporal_state import TemporalRunState
from relf_agent.types import canonical, digest, submission_request


class Held:
    identity = {"kind": "capacity-actual-handlers", "version": "1"}

    def __init__(self):
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.calls, self.active, self.peak = [], 0, 0

    async def execute(self, input, config, context):
        self.calls.append(context.effect_key)
        self.active += 1
        self.peak = max(self.peak, self.active)
        if self.active == 16:
            self.entered.set()
        try:
            await self.release.wait()
            return input
        finally:
            self.active -= 1


def system():
    component = Held()
    registry = r.NodeExecutorRegistry()
    registry.register(r.NodeExecutorSpec("held", "Actual held call", "read_only"), component)
    runtime = TemporalRuntime(providers={}, tools=r.ToolRegistry(), workflow_executors=registry)
    manifest = json.loads(canonical(runtime.orchestration_release))
    parents = [
        TemporalParentState(
            "parent-" + str(index),
            asdict(r.Scope()),
            "submit-" + str(index),
            submission_request(
                r.GraphWorkflowSpec(
                    "capacity",
                    [r.GraphNode("node" + str(i), executor="held") for i in range(count)],
                    max_concurrency=count,
                ),
                [False, 0, None],
                budget=count,
            ),
            manifest,
            "parent-epoch-" + str(index),
        )
        for index, count in enumerate([16, 1])
    ]
    states = [
        TemporalRunState(
            call["run_id"],
            parent.scope,
            call["command_id"],
            call["request"],
            manifest,
            "epoch-" + str(i),
        )
        for parent in parents
        for i, call in enumerate(parent.next_calls())
    ]
    return runtime, component, states


async def execute(runtime, state, *, ack=None):
    action, request = state.next_operation()
    capacity.begin_window(state, action, now=100.0, total_seconds=15.0)

    async def guard(value, *, invocation_id):
        return state.admit_tool_dispatch(
            {
                name: value[name]
                for name in ("scope", "run_id", "action_id", "release_digest", "execution_epoch")
            }
            | {"request_digest": digest(value), "invocation_id": invocation_id}
        )

    async def ended(value):
        if ack is not None:
            await ack.wait()
        state.tool_execution_ended(value)

    response = await runtime.execute_tool(request, dispatch_guard=guard, on_end=ended)
    state.accept_tool(action["id"], response)
    return response


def test_seventeen_nodes_across_two_runs_share_sixteen_slots_and_execute_once():
    async def run():
        runtime, component, states = system()
        tasks = [asyncio.create_task(execute(runtime, state)) for state in states[:16]]
        try:
            await asyncio.wait_for(component.entered.wait(), 5)
            response = await execute(runtime, states[16])
            assert response["code"] == capacity.WAIT_CODE and states[16].state == "running"
            assert states[16].budget["reserved"] == 1 and component.active == 16
            assert "invocation_id" not in next(iter(states[16].tool_executions.values()))
            component.release.set()
            assert all(result["ok"] for result in await asyncio.gather(*tasks))
            assert await runtime.wait_context_executions(wait_timeout=5)
            assert capacity.resume(states[16], now=100.2)
            assert (await execute(runtime, states[16]))["ok"] is True
            assert await runtime.wait_context_executions(wait_timeout=5)
            assert component.peak == 16 and len(component.calls) == len(set(component.calls)) == 17
            assert all(state.budget["spent"] == 1 for state in states)
        finally:
            component.release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)

    asyncio.run(run())


@pytest.mark.parametrize("blocker", ["handler", "end_ack"])
def test_waiting_cancel_and_incomplete_close_report_real_owner_obligations(blocker):
    async def run():
        runtime, component, states = system()
        ack = asyncio.Event()
        tasks = [asyncio.create_task(execute(runtime, state, ack=ack)) for state in states[:16]]
        try:
            await asyncio.wait_for(component.entered.wait(), 5)
            assert (await execute(runtime, states[16]))["code"] == capacity.WAIT_CODE
            states[16].command("cancel", {"kind": "cancel", "scope": states[16].scope})
            assert states[16].state == "cancelled" and states[16].quiescent
            assert states[16].budget["reserved"] == states[16].budget["spent"] == 0
            if blocker == "end_ack":
                component.release.set()
                await asyncio.gather(*tasks)
                await asyncio.sleep(0)
            with pytest.raises(CloseIncomplete) as pending:
                await runtime.close_context_execution(wait_timeout=0)
            diagnostic = pending.value.diagnostics
            assert diagnostic["authority"] == "temporal"
            assert diagnostic["stage"] == ("handler_drain" if blocker == "handler" else "end_ack")
            assert {item["kind"]: item["count"] for item in diagnostic["blockers"]}[blocker] == 16
            assert pending.value.report == {"tool_execution": "pending"}
        finally:
            component.release.set()
            ack.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await runtime.close_context_execution(wait_timeout=5)
            await runtime.tool_execution.aclose(wait_timeout=5)
        assert len(component.calls) == 16 and component.active == 0

    asyncio.run(run())
