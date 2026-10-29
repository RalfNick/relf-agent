"""Actual Service evidence; no online model or business-write quality claim."""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from contextlib import aclosing
from pathlib import Path

import pytest

import relf_agent as r
from relf_agent.temporal import TemporalEngine, build_temporal_worker, replay_temporal_history

from .temporal_stream_worker import definition, stream_runtime

pytestmark = pytest.mark.skipif(
    not os.getenv("RALF_TEST_TEMPORAL_ADDRESS"), reason="requires actual owned Temporal Service"
)


def calls(root):
    path = root / "calls.jsonl"
    return [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines()]


async def until(predicate):
    async with asyncio.timeout(30):
        while True:
            value = await predicate()
            if value:
                return value
            await asyncio.sleep(0.02)


async def approval(handle):
    async def pending():
        item = next((item for item in await handle.pending() if item["kind"] == "approval"), None)
        if item is None:
            snapshot = await handle.status()
            assert snapshot.state not in {"failed", "cancelled", "succeeded"}, snapshot
        return item

    return await until(pending)


def engine_for(client, queue, execution):
    return TemporalEngine(
        client,
        task_queue=queue,
        release=execution.manifest,
        scope=r.Scope("stream-service", queue),
        activity_timeout=10,
        drive_timeout=30,
    )


async def verify_result(client, handle, root):
    done = await handle.wait(wait_timeout=30, terminal_only=True)
    assert done.snapshot.state == "succeeded" and done.snapshot.result == "done"
    async with aclosing(handle.stream_updates(follow=False)) as stream:
        rows = [event async for event in stream]
    assert sum(row["kind"] == "model" for row in calls(root)) == 2
    assert sum(row["kind"] == "tool" for row in calls(root)) == 1
    assert [event.data["message"] for event in rows if event.kind == "tool_delta"] == [
        "lookup-start",
        "lookup-finished",
    ]
    assert len([event for event in rows if event.kind == "model_end"]) == 2
    assert len([event for event in rows if event.kind == "tool_end"]) == 1
    assert all(not event.authoritative for event in rows if event.kind.endswith("_delta"))
    raw = await handle.diagnostics()
    assert raw.budget["spent"] == 3
    assert raw.budget["unknown"] == raw.budget["reserved"] == 0
    history = await client.get_workflow_handle(handle.ref.run_id).fetch_history()
    (root / "history.json").write_text(history.to_json())
    before = calls(root)
    await replay_temporal_history(history)
    assert calls(root) == before
    return rows


@pytest.mark.parametrize("limited", [False, True])
def test_actual_prefix_observer_cancel_approval_and_history(tmp_path, limited):
    async def run():
        from temporalio.client import Client

        client = await Client.connect(os.environ["RALF_TEST_TEMPORAL_ADDRESS"])
        queue = "stream-live-" + uuid.uuid4().hex
        execution = stream_runtime(tmp_path, limited=limited)
        engine = engine_for(client, queue, execution)
        host = r.Runtime.from_temporal(engine)
        try:
            async with build_temporal_worker(client, task_queue=queue, runtime=execution):
                handle = await host.create_agent(definition()).submit("lookup", command_id="s")

                async def held():
                    return (tmp_path / "prefix-held").exists()

                await until(held)
                async with aclosing(handle.stream_updates(follow=False)) as stream:
                    prefix = [event async for event in stream]
                    cursor = stream.cursor
                assert any(event.kind == "model_delta" for event in prefix)
                assert not any(event.kind.endswith("_end") for event in prefix)
                observer = handle.stream_updates(after=cursor, poll_interval=0.01)
                reading = asyncio.create_task(anext(observer))
                try:
                    await asyncio.sleep(0.03)
                    reading.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await reading
                    assert (await handle.status()).state == "running"
                    assert [row["kind"] for row in calls(tmp_path)] == ["model"]
                finally:
                    await observer.aclose()
                (tmp_path / "release-model").touch()
                pending = await approval(handle)
                assert [row["kind"] for row in calls(tmp_path)] == ["model"]
                receipt = await handle.approve(
                    pending["action_id"], pending["digest"], command_id="approve"
                )
                assert receipt == await handle.approve(
                    pending["action_id"], pending["digest"], command_id="approve"
                )
                rows = await verify_result(client, handle, tmp_path)
                if limited:
                    assert len([event for event in rows if event.kind == "model_delta"]) == 4
                    assert len([event for event in rows if event.kind == "gap"]) == 2
                    assert all(
                        event.data["stream_end"]["observation"]["truncated"]
                        for event in rows
                        if event.kind == "model_end"
                    )
                else:
                    assert not any(event.kind == "gap" for event in rows)
                    assert all(
                        not event.data["stream_end"]["observation"]["truncated"]
                        for event in rows
                        if event.kind in {"model_end", "tool_end"}
                    )
        finally:
            (tmp_path / "release-model").touch()
            await host.aclose()
            await engine.aclose()

    asyncio.run(asyncio.wait_for(run(), 120))


def test_actual_approval_survives_worker_kill_without_repeating_accepted_model(tmp_path):
    async def run():
        from temporalio.client import Client

        address = os.environ["RALF_TEST_TEMPORAL_ADDRESS"]
        client = await Client.connect(address)
        queue = "stream-restart-" + uuid.uuid4().hex
        execution = stream_runtime(tmp_path)
        engine = engine_for(client, queue, execution)
        host, processes = r.Runtime.from_temporal(engine), []
        (tmp_path / "release-model").touch()

        async def start(label):
            log = tmp_path / (label + ".log")
            with log.open("w") as output:
                process = await asyncio.to_thread(
                    subprocess.Popen,
                    [sys.executable, "-u", "-m", "tests.temporal_stream_worker"],
                    env={
                        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                        "PYTHONPATH": os.pathsep.join(
                            [str(Path(r.__file__).parents[1]), str(Path(__file__).parents[1])]
                        ),
                        "RALF_TEST_TEMPORAL_ADDRESS": address,
                        "RALF_STREAM_ROOT": str(tmp_path),
                        "RALF_STREAM_QUEUE": queue,
                    },
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            processes.append(process)

            async def ready():
                assert process.poll() is None, log.read_text()
                return "TEMPORAL_STREAM_READY" in log.read_text()

            await until(ready)
            return process

        try:
            first = await start("original")
            handle = await host.create_agent(definition()).submit("lookup", command_id="s")
            pending = await approval(handle)
            before = [
                r.AgentStreamEvent(r.EventEnvelope(engine.scope, e)).to_dict()
                for e in await handle.events()
            ]
            first.kill()
            await asyncio.to_thread(first.wait, 10)
            await host.aclose()
            assert [row["kind"] for row in calls(tmp_path)] == ["model"]
            await start("restored")
            host = r.Runtime.from_temporal(engine)
            attached = await host.aattach(handle.ref)
            async with aclosing(attached.stream_updates(follow=False)) as stream:
                assert [event.to_dict() async for event in stream] == before
            receipt = await attached.approve(
                pending["action_id"], pending["digest"], command_id="approve"
            )
            assert receipt == await attached.approve(
                pending["action_id"], pending["digest"], command_id="approve"
            )
            await verify_result(client, attached, tmp_path)
            (tmp_path / "worker-restart.json").write_text(
                json.dumps(
                    {
                        "original_pid": first.pid,
                        "original_returncode": first.returncode,
                        "restored_pid": processes[-1].pid,
                    }
                )
            )
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                try:
                    await asyncio.to_thread(process.wait, 10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, 10)
            assert all(process.poll() is not None for process in processes)
            (tmp_path / "worker-shutdown.json").write_text(
                json.dumps([{"pid": p.pid, "returncode": p.returncode} for p in processes])
            )
            await host.aclose()
            await engine.aclose()

    asyncio.run(asyncio.wait_for(run(), 120))
