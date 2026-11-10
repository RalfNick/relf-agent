"""Fixed write verbs keep original Local approval, receipts and real ownership."""

import asyncio
import json

import pytest

import relf_agent as r
from relf_agent.tools import ThreadExecutionTracker, current_thread_group, current_thread_tracker

from .http_write_fixture import effects, write_endpoint


def descriptor(*, output_schema=None):
    return r.ToolDescriptor(
        "write",
        "Write the fixed business resource",
        {
            "type": "object",
            "properties": {"value": {"type": "integer"}, "effect_key": {"type": "string"}},
            "required": ["value", "effect_key"],
            "additionalProperties": False,
        },
        {"type": "object"} if output_schema is None else output_schema,
    )


def profile(url, method, *, effect="idempotent_write", allow_empty_204=None, output_schema=None):
    tool = {
        "descriptor": descriptor(output_schema=output_schema).to_dict(),
        "url": url,
        "version": "write-fixture-v1",
        "method": method,
        "policy": {
            "version": "1",
            "effect": effect,
            "requires_approval": True,
            "effect_key_argument": "effect_key",
        },
    }
    if allow_empty_204 is not None:
        tool["allow_empty_204"] = allow_empty_204
    return r.RuntimeProfile(
        "http-write-recovery",
        "1",
        {},
        {"tools": {"adapter": "http-json", "config": {"tools": [tool]}}},
    )


def flow():
    return r.GraphWorkflowSpec(
        "fixed-write", [r.GraphNode("write", tool="write")], output=r.ValueRef("write")
    )


def approve(runtime, handle, pending):
    value = runtime.approve(
        handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
    )
    assert (
        runtime.approve(
            handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
        )
        == value
    )
    return value


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_approved_write_close_reopen_and_duplicate_commands_keep_original_effect(tmp_path, method):
    with write_endpoint(tmp_path) as (url, calls, _, _, _):
        selected = profile(url + "/write", method)
        database = tmp_path / "runs.sqlite"

        async def run():
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                handle = runtime.submit(flow(), {"value": 7}, command_id="same", budget=1)
                waiting = await runtime.drive(handle.run_id)
                assert (
                    waiting.state == "waiting_approval" and calls == [] and effects(tmp_path) == []
                )
                pending = waiting.pending[0]
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                assert runtime.submit(flow(), {"value": 7}, command_id="same", budget=1) == handle
                receipt = approve(runtime, handle, pending)
                done = await runtime.drive(handle.run_id)
                assert done.state == "succeeded" and done.result["value"] == 7
                original_events = runtime.events(handle.run_id)
                assert runtime.diagnostics(handle.run_id).budget == {
                    "limit": 1,
                    "spent": 1,
                    "held": 0,
                }
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                assert runtime.submit(flow(), {"value": 7}, command_id="same", budget=1) == handle
                assert approve(runtime, handle, pending) == receipt
                assert (await runtime.drive(handle.run_id)).result == done.result
                assert runtime.events(handle.run_id) == original_events

        asyncio.run(run())
        assert len(calls) == 1 and calls[0]["method"] == method and calls[0]["path"] == "/write"
        sent = json.loads(calls[0]["body"])
        assert sent["value"] == 7 and effects(tmp_path) == [(sent["effect_key"], sent)]
        assert calls[0]["headers"]["Content-Type"] == "application/json"


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
@pytest.mark.parametrize("effect", ["idempotent_write", "unqueryable_write"])
def test_lost_response_reopen_retains_original_effect_key_and_unknown_policy(
    tmp_path, method, effect
):
    with write_endpoint(tmp_path) as (url, calls, _, _, _):
        selected = profile(url + "/lost", method, effect=effect)
        database = tmp_path / "runs.sqlite"

        async def run():
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                handle = runtime.submit(flow(), {"value": 7}, command_id="same", budget=3)
                waiting = await runtime.drive(handle.run_id)
                original_approval = waiting.pending[0]
                receipt = approve(runtime, handle, original_approval)
                assert (await runtime.drive(handle.run_id)).state == "waiting_reconciliation"
                assert len(calls) == 1 and len(effects(tmp_path)) == 1
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                assert runtime.submit(flow(), {"value": 7}, command_id="same", budget=3) == handle
                assert approve(runtime, handle, original_approval) == receipt
                done = await runtime.drive(handle.run_id)
                if effect == "idempotent_write":
                    assert done.state == "succeeded" and done.result["value"] == 7
                    assert len(calls) == 2
                    assert calls[0]["body"] == calls[1]["body"]
                    assert done.result["effect_key"] == json.loads(calls[0]["body"])["effect_key"]
                else:
                    assert done.state == "waiting_reconciliation" and len(calls) == 1
                    for _ in range(2):
                        assert (
                            await runtime.drive(handle.run_id)
                        ).state == "waiting_reconciliation"
                    assert len(calls) == 1
                assert len(effects(tmp_path)) == 1
                assert all(call["method"] == method and call["path"] == "/lost" for call in calls)
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                before = len(calls)
                assert runtime.submit(flow(), {"value": 7}, command_id="same", budget=3) == handle
                assert (await runtime.drive(handle.run_id)).state == done.state
                assert len(calls) == before

        asyncio.run(run())


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
@pytest.mark.parametrize("mode", ["allow_null", "default_refusal", "schema_refusal"])
def test_empty204_managed_result_needs_explicit_option_and_nullable_schema(tmp_path, method, mode):
    with write_endpoint(tmp_path) as (url, calls, _, _, _):
        selected = profile(
            url + "/empty",
            method,
            effect="unqueryable_write",
            allow_empty_204=None if mode == "default_refusal" else True,
            output_schema={"type": "object"} if mode == "schema_refusal" else {"type": "null"},
        )
        database = tmp_path / "runs.sqlite"

        async def run():
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                handle = runtime.submit(flow(), {"value": 7}, command_id="same", budget=1)
                paused = await runtime.drive(handle.run_id)
                assert paused.state == "waiting_approval" and calls == []
                pending = paused.pending[0]
                receipt = approve(runtime, handle, pending)
                done = await runtime.drive(handle.run_id)
                if mode == "allow_null":
                    assert done.state == "succeeded" and done.result is None
                    assert runtime.diagnostics(handle.run_id).budget == {
                        "limit": 1,
                        "held": 0,
                        "spent": 1,
                    }
                    assert any(
                        event.kind == "tool_result_committed"
                        for event in runtime.events(handle.run_id)
                    )
                else:
                    assert done.state == "waiting_reconciliation"
                    assert runtime.diagnostics(handle.run_id).budget == {
                        "limit": 1,
                        "held": 1,
                        "spent": 0,
                    }
            async with await r.RuntimeBuilder().abuild(selected, database) as runtime:
                assert runtime.submit(flow(), {"value": 7}, command_id="same", budget=1) == handle
                assert approve(runtime, handle, pending) == receipt
                repeated = await runtime.drive(handle.run_id)
                assert repeated.state == done.state and repeated.result == done.result
                assert len(calls) == len(effects(tmp_path)) == 1

        asyncio.run(run())


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_cancelled_write_and_cancelled_close_retry_retain_actual_http_handler(tmp_path, method):
    with write_endpoint(tmp_path) as (url, calls, started, release, ended):

        async def run():
            remote = r.HTTPToolSource(
                descriptor(), url + "/hang", method=method, version="write-v1", timeout=2
            )
            tracker = ThreadExecutionTracker()
            owner = current_thread_tracker.set(tracker)
            group = current_thread_group.set("http-write")
            try:
                calling = asyncio.create_task(
                    remote.call_tool(
                        descriptor(),
                        {"value": 7, "effect_key": "fixture-stable-key"},
                        r.InvocationContext(
                            r.Scope(), "run", "action", "attempt", "fixture-stable-key", "epoch"
                        ),
                    )
                )
            finally:
                current_thread_tracker.reset(owner)
                current_thread_group.reset(group)
            retry = None
            try:
                assert await asyncio.to_thread(started.wait, 2)
                assert len(effects(tmp_path)) == 1 and not ended.is_set()
                calling.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await calling
                closing = asyncio.create_task(remote.aclose())
                await asyncio.sleep(0.03)
                assert not closing.done() and tracker.has_active_for("http-write")
                assert not ended.is_set()
                closing.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await closing
                retry = asyncio.create_task(remote.aclose())
                await asyncio.sleep(0.03)
                assert not retry.done() and tracker.has_active_for("http-write")
                assert not ended.is_set()
                with pytest.raises(r.ToolSourceError):
                    await remote.list_tools()
            finally:
                release.set()
                if not calling.done():
                    calling.cancel()
                    await asyncio.gather(calling, return_exceptions=True)
                if retry is None:
                    retry = asyncio.create_task(remote.aclose())
                await asyncio.wait_for(retry, 3)
                await tracker.drain("http-write")
            assert not tracker.has_active and ended.is_set()
            await remote.aclose()

        asyncio.run(run())
        assert len(calls) == len(effects(tmp_path)) == 1 and calls[0]["method"] == method
