"""Actual Temporal evidence for bounded fan-out; never real model quality."""

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

from .fan_out_worker import Ledger, close_temporal_runtime, definition, temporal_runtime
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
            RELF_FAN_OUT_QUEUE=self.queue,
        )
        args = [
            sys.executable,
            "-u",
            "-m",
            "tests.fan_out_worker",
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
            raise BaseExceptionGroup("Owned fan-out Worker cleanup", errors)


@asynccontextmanager
async def system(root, *, approval=False):
    from temporalio.client import Client, WorkflowExecutionStatus
    from temporalio.service import RPCError, RPCStatusCode

    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    runtime = temporal_runtime(root, approval=approval)
    queue = "fan-out-" + uuid.uuid4().hex
    engine = TemporalEngine(
        client,
        task_queue=queue,
        release=runtime.orchestration_release,
        scope=r.Scope("fan-out-service", queue),
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
                    await handle.terminate("Owned fan-out test cleanup")
            except RPCError as error:
                if error.status != RPCStatusCode.NOT_FOUND:
                    errors.append(error)
        if errors:
            raise BaseExceptionGroup(
                "Fan-out test/cleanup failures", ([failure] if failure else []) + errors
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


def test_actual_temporal_batch_uses_original_children_and_stable_result(tmp_path):
    async def exercise():
        async with system(tmp_path) as (engine, _, owned):
            handle = await engine.submit(definition(), [3, 1, 2], command_id="same", budget=4)
            owned.add(handle.run_id)
            done = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state in {"succeeded", "failed"}
            )
            assert done.state == "succeeded" and done.result == {
                "keys": ["map-0000", "map-0001", "map-0002"],
                "values": [9, 1, 4],
                "total": 14,
            }, done
            ledger = Ledger(tmp_path)
            assert len(ledger.rows("plan")) == 1
            assert len(ledger.rows("map")) == 3 and len(ledger.rows("reduce")) == 1
            assert (
                await engine.submit(definition(), [3, 1, 2], command_id="same", budget=4) == handle
            )
            assert (await engine.diagnostics(handle.run_id)).budget["spent"] == 4
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(exercise(), 120))


def test_actual_temporal_approval_restart_preserves_plan_and_original_commands(tmp_path):
    async def exercise():
        async with system(tmp_path, approval=True) as (engine, peers, owned):
            handle = await engine.submit(definition(), [3, 1, 2], command_id="same", budget=4)
            owned.add(handle.run_id)
            waiting = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state == "waiting_approval"
            )
            before = tuple(waiting.pending)
            assert before and Ledger(tmp_path).rows("map") == []
            await peers.kill(peers.processes[0][1])
            await peers.start("replacement")
            commands = {}
            for _ in range(4):
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
                for pending in snapshot.pending:
                    key = pending["action_id"]
                    receipt = await engine.approve(
                        pending["run_id"], key, pending["digest"], command_id="approve-" + key
                    )
                    assert (
                        await engine.approve(
                            pending["run_id"], key, pending["digest"], command_id="approve-" + key
                        )
                        == receipt
                    )
                    commands[key] = receipt
                await engine.drive(handle.run_id)
            done = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state in {"succeeded", "failed"}
            )
            assert done.state == "succeeded" and done.result["total"] == 14, done
            assert all(p["action_id"] in commands for p in before)
            ledger = Ledger(tmp_path)
            assert len(ledger.rows("plan")) == 1
            assert len(ledger.rows("map")) == 3 and len(ledger.rows("reduce")) == 1
            assert len(commands) == 3
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(exercise(), 120))
