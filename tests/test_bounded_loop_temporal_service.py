"""Actual bounded-loop History and approval-quiescent restart evidence only."""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

import relf_agent as r
from relf_agent.temporal import TemporalEngine, replay_temporal_history
from relf_agent.types import canonical

from .bounded_loop_worker import Ledger, close_temporal_runtime, definition, temporal_runtime
from .test_temporal_scoped_capacity_service import discover_owned_descendants

TEST_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not os.getenv("RALF_TEST_TEMPORAL_ADDRESS"), reason="requires actual owned Temporal Service"
)


async def until(operation, predicate):
    async with asyncio.timeout(30):
        while True:
            value = await operation()
            if predicate(value):
                return value
            await asyncio.sleep(0.02)


class Peers:
    def __init__(self, root, client, queue, release, approval):
        self.root, self.client, self.queue, self.release, self.approval = (
            root,
            client,
            queue,
            release,
            approval,
        )
        self.processes = []

    async def start(self, label):
        env = {
            k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"}
        }
        env.update(
            RALF_TEST_TEMPORAL_ADDRESS=os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
            RALF_TEST_TEMPORAL_NAMESPACE=self.client.namespace,
            RELF_BOUNDED_LOOP_QUEUE=self.queue,
        )
        args = [
            sys.executable,
            "-u",
            "-m",
            "tests.bounded_loop_worker",
            str(self.root),
            "--temporal",
            "--label",
            label,
        ]
        if self.approval:
            args.append("--approval")
        with (self.root / (label + ".log")).open("w") as output:
            process = await asyncio.create_subprocess_exec(
                *args,
                env=env,
                cwd=TEST_ROOT,
                stdout=output,
                stderr=output,
            )
        self.processes.append((label, process))
        async with asyncio.timeout(20):
            while not (self.root / ("ready-" + label + ".json")).exists():  # noqa: ASYNC110 -- actual Worker readiness
                assert process.returncode is None, (self.root / (label + ".log")).read_text()
                await asyncio.sleep(0.02)
        ready = json.loads((self.root / ("ready-" + label + ".json")).read_text())
        assert ready["package"] == r.__file__ and ready["release"] == json.loads(
            canonical(self.release)
        )
        return process

    async def kill(self, process):
        process.kill()
        await asyncio.wait_for(process.wait(), 10)

    async def close(self):
        errors = []
        for label, process in self.processes:
            if process.returncode is not None:
                continue
            (self.root / ("stop-" + label)).touch()
            try:
                assert await asyncio.wait_for(process.wait(), 15) == 0, (
                    self.root / (label + ".log")
                ).read_text()
                assert (self.root / ("closed-" + label)).exists()
            except BaseException as error:
                errors.append(error)
                if process.returncode is None:
                    process.kill()
                    await process.wait()
        (self.root / "worker-cleanup.json").write_text(
            json.dumps(
                {
                    "processes": [
                        {"label": label, "pid": p.pid, "exit_code": p.returncode}
                        for label, p in self.processes
                    ],
                    "all_waited": True,
                    "errors": [type(e).__name__ for e in errors],
                }
            )
        )
        if errors:
            raise BaseExceptionGroup("Owned bounded-loop Worker cleanup", errors)


@asynccontextmanager
async def system(root, *, approval=False):
    from temporalio.client import Client, WorkflowExecutionStatus
    from temporalio.service import RPCError, RPCStatusCode

    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    runtime = temporal_runtime(root, approval=approval)
    queue = "bounded-loop-" + uuid.uuid4().hex
    engine = TemporalEngine(
        client,
        task_queue=queue,
        release=runtime.orchestration_release,
        scope=r.Scope("bounded-loop-service", queue),
        activity_timeout=10,
        drive_timeout=30,
    )
    peers = Peers(root, client, queue, runtime.orchestration_release, approval)
    owned, failure = set(), None
    try:
        await peers.start("initial")
        yield engine, peers, owned
    except BaseException as error:
        failure = error
        raise
    finally:
        errors = []

        async def clean(operation):
            try:
                await operation
            except BaseException as error:
                errors.append(error)

        await clean(peers.close())
        await clean(close_temporal_runtime(runtime))
        await clean(engine.aclose())
        owned.add(engine.command_registry_id)
        await clean(discover_owned_descendants(client, owned))
        for run_id in owned:
            try:
                handle = client.get_workflow_handle(run_id)
                if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                    await handle.terminate("Owned bounded-loop test cleanup")
            except RPCError as error:
                if error.status != RPCStatusCode.NOT_FOUND:
                    errors.append(error)
        if errors:
            raise BaseExceptionGroup(
                "Bounded-loop test/cleanup failures", ([failure] if failure else []) + errors
            )


async def replay_all(engine, owned, root):
    owned.add(engine.command_registry_id)
    await discover_owned_descendants(engine.client, owned)
    before = Ledger(root).rows()
    for n, run_id in enumerate(sorted(owned)):
        history = await engine.client.get_workflow_handle(run_id).fetch_history()
        (root / ("history-" + str(n) + ".json")).write_text(history.to_json())
        await replay_temporal_history(history, namespace=engine.client.namespace)
    assert Ledger(root).rows() == before


async def assert_three_original_rounds(engine, root_id, root):
    ledger = Ledger(root)
    assert len(ledger.rows("plan")) == len(ledger.rows("verify")) == 3
    assert len(ledger.rows("work")) == 3
    assert len({row["effect_key"] for row in ledger.rows("work")}) == 3
    assert [json.loads(row["input"])["revision"] for row in ledger.rows("plan")] == [0, 1, 2]
    assert [json.loads(row["input"]) for row in ledger.rows("work")] == [
        {"task": {"target": 3}, "previous": None, "iteration": 1},
        {
            "task": {"target": 3},
            "previous": {"done": False, "value": 1, "iteration": 1},
            "iteration": 2,
        },
        {
            "task": {"target": 3},
            "previous": {"done": False, "value": 2, "iteration": 2},
            "iteration": 3,
        },
    ]
    diagnostics = await engine.diagnostics(root_id)
    children = diagnostics.workflow["children"]
    assert [c["id"] for c in children] == ["0:iteration", "1:iteration", "2:iteration"]
    assert len({c["run_id"] for c in children}) == 3
    assert diagnostics.budget["allowance"] == diagnostics.budget["spent"] == 3
    assert (
        diagnostics.budget["reserved"]
        == diagnostics.budget["unknown"]
        == diagnostics.budget["remaining"]
        == 0
    )
    assert len(diagnostics.budget["reservations"]) == 3
    assert all(
        reservation["status"] == "settled" and reservation["actual"] == reservation["amount"] == 1
        for reservation in diagnostics.budget["reservations"]
    )
    assert diagnostics.workflow["quiescent"] is True
    assert diagnostics.workflow["remote_stop_confirmed"] is True
    assert all(
        child["settled"] is True
        and child["observed_flow"]["quiescent"] is True
        and child["observed_flow"]["remote_stop_confirmed"] is True
        for child in children
    )


def test_actual_temporal_loop_retains_three_adopted_rounds_and_replays_history(tmp_path):
    async def exercise():
        async with system(tmp_path) as (engine, _, owned):
            handle = await engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
            owned.add(handle.run_id)
            done = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state in {"succeeded", "failed"}
            )
            assert done.state == "succeeded" and done.result == {
                "done": True,
                "value": 3,
                "iteration": 3,
            }, done
            before = Ledger(tmp_path).rows()
            assert (
                await engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
                == handle
            )
            assert Ledger(tmp_path).rows() == before
            await assert_three_original_rounds(engine, handle.run_id, tmp_path)
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(exercise(), 120))


def test_actual_temporal_second_round_approval_worker_restart_keeps_original_previous(tmp_path):
    async def exercise():
        async with system(tmp_path, approval=True) as (engine, peers, owned):
            handle = await engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
            owned.add(handle.run_id)
            waiting = await until(
                lambda: engine.status(handle.run_id),
                lambda s: s.state == "waiting_approval" and bool(s.pending),
            )
            first = waiting.pending[0]
            assert Ledger(tmp_path).rows("work") == []
            command = "approve-" + first["action_id"]
            receipt = await engine.approve(
                first["run_id"], first["action_id"], first["digest"], command_id=command
            )
            assert (
                await engine.approve(
                    first["run_id"], first["action_id"], first["digest"], command_id=command
                )
                == receipt
            )
            waiting = await until(
                lambda: engine.status(handle.run_id),
                lambda s: (
                    s.state == "waiting_approval"
                    and any(p["action_id"] != first["action_id"] for p in s.pending)
                ),
            )
            second = next(p for p in waiting.pending if p["action_id"] != first["action_id"])
            assert len(Ledger(tmp_path).rows("work")) == 1
            assert [
                json.loads(row["input"])["revision"] for row in Ledger(tmp_path).rows("plan")
            ] == [0, 1]
            assert (await engine.diagnostics(handle.run_id)).workflow["planning_revision"] == 1
            await peers.kill(peers.processes[0][1])
            await peers.start("replacement")
            assert (
                await engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
                == handle
            )
            commands = {first["action_id"]: receipt}
            for _ in range(3):
                snapshot = await until(
                    lambda: engine.status(handle.run_id),
                    lambda s: (
                        s.state in {"succeeded", "failed"}
                        or s.state == "waiting_approval"
                        and any(p["action_id"] not in commands for p in s.pending)
                    ),
                )
                if snapshot.state == "succeeded":
                    break
                assert snapshot.state == "waiting_approval", snapshot
                for p in snapshot.pending:
                    key = p["action_id"]
                    if key in commands:
                        continue
                    approved = await engine.approve(
                        p["run_id"], key, p["digest"], command_id="approve-" + key
                    )
                    assert (
                        await engine.approve(
                            p["run_id"], key, p["digest"], command_id="approve-" + key
                        )
                        == approved
                    )
                    commands[key] = approved
                await engine.drive(handle.run_id)
            done = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state in {"succeeded", "failed"}
            )
            assert done.state == "succeeded" and done.result == {
                "done": True,
                "value": 3,
                "iteration": 3,
            }, done
            assert len(commands) == 3 and second["action_id"] in commands
            await assert_three_original_rounds(engine, handle.run_id, tmp_path)
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(exercise(), 120))
