"""Actual native Agent stream/effect recovery; original namespace is required."""

import asyncio
import json
import os
import uuid
from contextlib import aclosing

import pytest

import relf_agent as r
from relf_agent.temporal import TemporalEngine, build_temporal_worker, replay_temporal_history

from .temporal_stream_recovery_worker import CallingProvider, tools

pytestmark = pytest.mark.skipif(
    not os.getenv("RALF_TEST_TEMPORAL_ADDRESS"), reason="requires actual owned Temporal Service"
)


def test_actual_streaming_agent_unknown_receipt_replays_in_original_namespace(tmp_path):
    async def run():
        from temporalio.client import Client

        from relf_agent.temporal_activities import TemporalRuntime

        from .test_temporal_stream_service import approval, until

        client = await Client.connect(os.environ["RALF_TEST_TEMPORAL_ADDRESS"])
        queue = "agent-unknown-" + uuid.uuid4().hex
        execution = TemporalRuntime(
            providers={"default": CallingProvider(tmp_path)},
            tools=tools(tmp_path, mode="unknown"),
            stream_updates=r.StreamUpdatePolicy(),
            tool_execution=r.ToolExecutionOwner(version="1"),
        )
        engine = TemporalEngine(
            client,
            task_queue=queue,
            release=execution.manifest,
            scope=r.Scope("agent-unknown", queue),
            activity_timeout=10,
            drive_timeout=30,
        )
        host = r.Runtime.from_temporal(engine)
        try:
            async with build_temporal_worker(client, task_queue=queue, runtime=execution):
                handle = await host.create_agent(
                    r.AgentSpec("reader", "Read", tools=("lookup",))
                ).submit("lookup", command_id="s", budget=3)
                waiting = await approval(handle)
                await handle.approve(waiting["action_id"], waiting["digest"], command_id="approve")

                async def uncertain():
                    return (await handle.status()).state == "waiting_reconciliation"

                await until(uncertain)
                info = await handle.diagnostics()
                assert info.budget["unknown"] == 1 and info.budget["spent"] == 1
                async with aclosing(handle.stream_updates(follow=False)) as progress:
                    rows = [row async for row in progress]
                assert any(row.kind == "tool_delta" for row in rows)
                assert any(row.source_kind == "action_outcome_unknown" for row in rows)
                assert [
                    json.loads(row)["kind"]
                    for row in (tmp_path / "calls.jsonl").read_bytes().splitlines()
                ] == ["dispatch"]
                await engine.reconcile(
                    handle.ref.run_id, waiting["action_id"], command_id="query", query=True
                )
                done = await handle.wait(wait_timeout=30, terminal_only=True)
                assert done.snapshot.state == "succeeded" and done.snapshot.result == "done"
                assert (await handle.diagnostics()).budget["spent"] == 3

                async def quiescent():
                    return (await handle.diagnostics()).workflow["quiescent"]

                await until(quiescent)
                before = (tmp_path / "calls.jsonl").read_bytes()
                assert [json.loads(row)["kind"] for row in before.splitlines()] == [
                    "dispatch",
                    "query",
                ]
                assert len((tmp_path / "model-calls.jsonl").read_text().splitlines()) == 2
                history = await client.get_workflow_handle(handle.ref.run_id).fetch_history()
                (tmp_path / "history.json").write_text(history.to_json())
                await replay_temporal_history(history, namespace=client.namespace)
                assert (tmp_path / "calls.jsonl").read_bytes() == before
        finally:
            await host.aclose()
            await engine.aclose()

    asyncio.run(asyncio.wait_for(run(), 120))
