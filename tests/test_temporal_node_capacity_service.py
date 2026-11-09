"""Actual Service capacity waiting, cancellation, replay and original ACK debt."""

import asyncio
import json
import os
import sys
import uuid
from collections import Counter
from contextlib import asynccontextmanager

import pytest

import relf_agent as r
from relf_agent.errors import CloseIncomplete, NotFound
from relf_agent.temporal import TemporalEngine, build_temporal_worker
from relf_agent.types import canonical, digest

from .temporal_node_capacity_worker import close_runtime, make_runtime
from .test_temporal_scoped_capacity_service import discover_owned_descendants
from .test_temporal_workflow_nodes_service import calls, replay_all, until

pytestmark = pytest.mark.skipif(
    not os.getenv("RALF_TEST_TEMPORAL_ADDRESS"), reason="requires actual owned Temporal Service"
)


class HistoryProcesses:
    def __init__(self, client, queue, root, mode, release):
        self.client, self.queue, self.root, self.mode, self.release = (
            client,
            queue,
            root,
            mode,
            release,
        )
        self.processes = []

    async def start(self, label):
        environment = {
            key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ
        }
        environment.update(
            RALF_TEST_TEMPORAL_ADDRESS=os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
            RALF_TEST_TEMPORAL_NAMESPACE=self.client.namespace,
            RALF_NODE_CAPACITY_QUEUE=self.queue,
            RALF_NODE_CAPACITY_ROOT=str(self.root),
            RALF_NODE_CAPACITY_MODE=self.mode,
            RALF_NODE_CAPACITY_LABEL=label,
        )
        with (self.root / (label + ".log")).open("w") as output:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-m",
                "tests.temporal_node_capacity_worker",
                env=environment,
                stdout=output,
                stderr=output,
            )
        self.processes.append((label, process))
        async with asyncio.timeout(20):
            while not (self.root / ("ready-" + label + ".json")).exists():  # noqa: ASYNC110 -- actual readiness
                assert process.returncode is None, (self.root / (label + ".log")).read_text()
                await asyncio.sleep(0.02)
        ready = json.loads((self.root / ("ready-" + label + ".json")).read_text())
        assert ready["workflow_only"] is True
        assert ready["release"] == json.loads(canonical(self.release))
        assert ready["package"] == r.__file__
        return process

    async def kill(self, process):
        process.kill()
        await asyncio.wait_for(process.wait(), 10)

    async def close(self):
        for label, process in self.processes:
            if process.returncode is not None:
                continue
            (self.root / ("stop-" + label)).touch()
            try:
                assert await asyncio.wait_for(process.wait(), 15) == 0, (
                    self.root / (label + ".log")
                ).read_text()
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()


@asynccontextmanager
async def system(root, *, mode="hold", process_history=False):
    from temporalio.client import Client, WorkflowExecutionStatus
    from temporalio.service import RPCError, RPCStatusCode
    from temporalio.worker import Worker

    from relf_agent.temporal_activities import registered_activities
    from relf_agent.temporal_control_activities import registered_parent_activities
    from relf_agent.temporal_session_activities import registered_session_activities

    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    runtime = make_runtime(root, mode)
    assert runtime.tool_execution.identity["max_calls"] == 16
    assert runtime.tool_execution.identity["kind"] == "workflow-node-capacity-owner"
    (root / "actual-service.json").write_text(
        json.dumps(
            {
                "namespace": client.namespace,
                "connected": True,
                "package": r.__file__,
                "owner": runtime.tool_execution.identity,
                "activity_timeout": 10,
                "drive_timeout": 30,
                "history_worker_process": process_history,
                "separate_original_activity_worker": True,
            }
        )
    )
    queue = "node-capacity-" + uuid.uuid4().hex
    engine = TemporalEngine(
        client,
        task_queue=queue,
        release=runtime.orchestration_release,
        scope=r.Scope("node-capacity-service", queue),
        activity_timeout=10,
        drive_timeout=30,
    )
    processes = HistoryProcesses(client, queue, root, mode, runtime.orchestration_release)
    activity_worker = Worker(
        client,
        task_queue=queue,
        activities=registered_activities(runtime, client)
        + registered_parent_activities(runtime, client)
        + registered_session_activities(runtime, client),
        workflows=[],
        identity="node-capacity-activity:" + digest(runtime.orchestration_release),
        build_id=digest(runtime.orchestration_release),
        disable_eager_activity_execution=True,
    )
    history_worker = None
    owned, failure = set(), None
    try:
        await activity_worker.__aenter__()
        if process_history:
            await processes.start("initial")
        else:
            history_worker = build_temporal_worker(
                client, task_queue=queue, runtime=runtime, no_remote_activities=True
            )
            await history_worker.__aenter__()
        yield engine, runtime, processes, owned
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = []
        (root / "release-handler").touch()
        (root / "release-ack").touch()

        async def clean(operation):
            try:
                await operation
            except BaseException as error:
                errors.append(error)

        await clean(close_runtime(runtime))
        await clean(activity_worker.__aexit__(None, None, None))
        if history_worker is not None:
            await clean(history_worker.__aexit__(None, None, None))
        await clean(processes.close())
        owned.add(engine.command_registry_id)
        await clean(discover_owned_descendants(client, owned))
        for target in sorted(owned):
            try:
                handle = client.get_workflow_handle(target)
                if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                    await handle.terminate(reason="owned node-capacity test cleanup")
            except RPCError as error:
                if error.status != RPCStatusCode.NOT_FOUND:
                    errors.append(error)
            except BaseException as error:
                errors.append(error)
        await clean(engine.aclose())
        (root / "cleanup.json").write_text(
            json.dumps(
                {
                    "owned_histories": sorted(owned),
                    "activity_owner_preserved_on_history_restart": True,
                    "cleanup_errors": [type(error).__name__ for error in errors],
                }
            )
        )
        if errors:
            raise BaseExceptionGroup(
                "Capacity service and original cleanup failures",
                ([failure] if failure is not None else []) + errors,
            )


def graph(count, *, hold):
    names = ["slot-" + str(index) for index in range(count)]
    return r.GraphWorkflowSpec(
        "capacity-" + str(count),
        [r.GraphNode(name, executor="step", config={"slot": name, "hold": hold}) for name in names],
        output=r.InputMap({name: r.ValueRef(name) for name in names}),
        max_concurrency=count,
    )


async def fill_then_wait(engine, root, owned):
    fill = await engine.submit(graph(16, hold=True), {"value": 16}, command_id="fill", budget=32)
    owned.add(fill.run_id)

    async def entered():
        return len(list(root.glob("entered-slot-*")))

    await until(entered, lambda count: count == 16)
    wait = await engine.submit(graph(1, hold=False), {"value": 17}, command_id="wait", budget=4)
    owned.add(wait.run_id)
    parent = await until(
        lambda: engine.diagnostics(wait.run_id), lambda info: len(info.workflow["children"]) == 1
    )
    child = parent.workflow["children"][0]["run_id"]
    owned.add(child)
    waiting = await until(
        lambda: child_snapshot(engine, child),
        lambda snapshot: (
            snapshot is not None
            and any(
                action.get("node_capacity", {}).get("phase") == "waiting"
                for action in snapshot.actions
            )
        ),
    )
    action = next(action for action in waiting.actions if action["kind"] == "tool")
    assert len(action["attempts"]) == 1
    assert sum(row["kind"] == "execute" for row in calls(root)) == 16
    info = await engine.diagnostics(child)
    assert info.budget["spent"] == info.budget["unknown"] == 0 and info.budget["reserved"] == 1
    (root / "waiting.json").write_text(
        json.dumps({"child": child, "action": action, "budget": info.budget})
    )
    return fill, wait, child, action


async def child_snapshot(engine, child):
    # A parent durably records the child intent before SDK start completes.
    # Retain the original until() deadline and wait for the actual child.
    try:
        return await engine.status(child)
    except NotFound:
        return None


async def final_success(engine, run_id):
    await engine.drive(run_id)
    return await until(
        lambda: engine.diagnostics(run_id),
        lambda info: (
            info.snapshot.state in {"succeeded", "failed", "cancelled"}
            and info.workflow["quiescent"]
        ),
    )


def assert_identity(original, current):
    assert current["id"] == original["id"]
    assert current["digest"] == original["digest"]
    assert current["effect_key"] == original["effect_key"]
    assert len(current["attempts"]) == 1
    assert current["attempts"][0]["id"] == original["attempts"][0]["id"]


def test_actual_single_parallel_graph_waits_after_sixteen_real_handlers(tmp_path):
    async def run():
        async with system(tmp_path) as (engine, _, _, owned):
            handle = await engine.submit(
                graph(17, hold=True), {"value": 17}, command_id="seventeen", budget=34
            )
            owned.add(handle.run_id)

            async def entered():
                return len(list(tmp_path.glob("entered-slot-*")))

            await until(entered, lambda count: count == 16)
            parent = await until(
                lambda: engine.diagnostics(handle.run_id),
                lambda info: len(info.workflow["children"]) == 17,
            )
            children = [entry["run_id"] for entry in parent.workflow["children"]]
            owned.update(children)

            async def waiting_child():
                snapshots = await asyncio.gather(
                    *(child_snapshot(engine, child) for child in children)
                )
                for snapshot in snapshots:
                    if snapshot is None:
                        continue
                    for action in snapshot.actions:
                        if action.get("node_capacity", {}).get("phase") == "waiting":
                            return snapshot.run_id, action
                return None

            child, original = await until(waiting_child, lambda value: value is not None)
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 16
            before = await engine.diagnostics(child)
            assert before.budget["spent"] == before.budget["unknown"] == 0
            assert before.budget["reserved"] == 1
            (tmp_path / "waiting.json").write_text(
                json.dumps({"child": child, "action": original, "budget": before.budget})
            )
            (tmp_path / "release-handler").touch()
            done = await final_success(engine, handle.run_id)
            assert done.snapshot.state == "succeeded"
            assert done.snapshot.result == {
                "slot-" + str(index): {"value": 17} for index in range(17)
            }
            assert done.budget["spent"] == 17
            assert done.budget["reserved"] == done.budget["unknown"] == 0
            current = next(
                action
                for action in (await engine.status(child)).actions
                if action["kind"] == "tool"
            )
            assert_identity(original, current)
            executions = [row for row in calls(tmp_path) if row["kind"] == "execute"]
            assert len(executions) == 17
            assert len({row["effect_key"] for row in executions}) == 17
            assert sum(row["kind"] == "ended" for row in calls(tmp_path)) == 17
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


@pytest.mark.parametrize("restart_history", [False, True])
def test_actual_default_capacity_two_runs_resume_original_action_once(tmp_path, restart_history):
    async def run():
        async with system(tmp_path, process_history=restart_history) as (
            engine,
            _,
            processes,
            owned,
        ):
            fill, waiting, child, original = await fill_then_wait(engine, tmp_path, owned)
            if restart_history:
                # Stop the only History poller before starting its replacement;
                # actual handlers remain in the independent Activity Worker.
                await processes.kill(processes.processes[0][1])
                await processes.start("replacement")
            (tmp_path / "release-handler").touch()
            filled, resumed = await asyncio.gather(
                final_success(engine, fill.run_id), final_success(engine, waiting.run_id)
            )
            assert filled.snapshot.state == resumed.snapshot.state == "succeeded"
            assert filled.snapshot.result == {
                "slot-" + str(index): {"value": 16} for index in range(16)
            }
            assert resumed.snapshot.result == {"slot-0": {"value": 17}}
            assert filled.budget["spent"] == 16 and resumed.budget["spent"] == 1
            assert filled.budget["reserved"] == resumed.budget["reserved"] == 0
            assert filled.budget["unknown"] == resumed.budget["unknown"] == 0
            current = next(
                action
                for action in (await engine.status(child)).actions
                if action["kind"] == "tool"
            )
            assert_identity(original, current)
            executions = [row for row in calls(tmp_path) if row["kind"] == "execute"]
            assert len(executions) == 17
            assert all(
                count == 1 for count in Counter(row["effect_key"] for row in executions).values()
            )
            assert sum(row["kind"] == "ended" for row in calls(tmp_path)) == 17
            assert next(row for row in executions if row["effect_key"] == original["effect_key"])[
                "input"
            ] == {"value": 17}
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


def test_actual_waiting_cancel_has_no_handler_or_consumption_and_close_retries(tmp_path):
    async def run():
        async with system(tmp_path) as (engine, runtime, _, owned):
            fill, waiting, child, original = await fill_then_wait(engine, tmp_path, owned)
            receipt = await engine.cancel(waiting.run_id, command_id="cancel-waiter")
            assert await engine.cancel(waiting.run_id, command_id="cancel-waiter") == receipt
            cancelled = await until(
                lambda: engine.diagnostics(waiting.run_id),
                lambda info: info.snapshot.state == "cancelled" and info.workflow["quiescent"],
            )
            assert (
                cancelled.budget["spent"]
                == cancelled.budget["reserved"]
                == cancelled.budget["unknown"]
                == 0
            )
            current = next(
                action
                for action in (await engine.status(child)).actions
                if action["kind"] == "tool"
            )
            assert_identity(original, current)
            child_info = await engine.diagnostics(child)
            assert (
                child_info.budget["spent"]
                == child_info.budget["reserved"]
                == child_info.budget["unknown"]
                == 0
            )
            with pytest.raises(CloseIncomplete) as caught:
                await runtime.close_context_execution(wait_timeout=0.02)
            assert caught.value.diagnostics["stage"] == "handler_drain"
            assert {"kind": "handler", "count": 16} in caught.value.diagnostics["blockers"]
            assert len([row for row in calls(tmp_path) if row["kind"] == "execute"]) == 16
            (tmp_path / "release-handler").touch()
            assert (await final_success(engine, fill.run_id)).snapshot.state == "succeeded"
            assert await runtime.wait_context_executions(wait_timeout=10)
            await runtime.close_context_execution(wait_timeout=10)
            assert all(row.get("effect_key") != original["effect_key"] for row in calls(tmp_path))
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


def test_actual_handler_end_does_not_hide_original_pending_ack_on_close(tmp_path):
    async def run():
        async with system(tmp_path, mode="delay-ack") as (engine, runtime, _, owned):
            handle = await engine.submit(graph(1, hold=False), None, command_id="ack", budget=4)
            owned.add(handle.run_id)

            async def ack_entered():
                return (tmp_path / "ack-entered").exists()

            await until(ack_entered, bool)
            assert sum(row["kind"] == "ended" for row in calls(tmp_path)) == 1
            with pytest.raises(CloseIncomplete) as caught:
                await runtime.close_context_execution(wait_timeout=0.02)
            assert caught.value.diagnostics["stage"] == "end_ack"
            assert {"kind": "end_ack", "count": 1} in caught.value.diagnostics["blockers"]
            assert not any(row["kind"] == "ack-forwarded" for row in calls(tmp_path))
            closer = asyncio.create_task(runtime.close_context_execution(wait_timeout=10))
            await asyncio.sleep(0.01)
            closer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closer
            assert not await runtime.wait_context_executions(wait_timeout=0.02)
            (tmp_path / "release-ack").touch()
            assert await runtime.wait_context_executions(wait_timeout=10)
            await runtime.close_context_execution(wait_timeout=10)
            info = await final_success(engine, handle.run_id)
            assert info.snapshot.state == "succeeded" and info.budget["spent"] == 1
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 1
            assert sum(row["kind"] == "ack-forwarded" for row in calls(tmp_path)) == 1
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))
