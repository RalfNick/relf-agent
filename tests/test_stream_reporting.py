import asyncio

import pytest

from relf_agent import StreamUpdatePolicy, emit_tool_delta
from relf_agent.stream_reporting import attempt_scope


@pytest.mark.parametrize("failure", ["error", "cancelled", "timeout", "value"])
def test_observation_failure_disables_progress_without_failing_business(failure):
    async def run():
        calls = []

        async def publish(value):
            calls.append(value)
            if failure == "error":
                raise RuntimeError("private observer error")
            if failure == "cancelled":
                raise asyncio.CancelledError
            if failure == "timeout":
                await asyncio.sleep(1)
            return True

        policy = StreamUpdatePolicy(publish_timeout=0.01)
        with attempt_scope(policy.identity, "tool", "a", "a:1", publish) as scope:
            assert await emit_tool_delta({"progress": 1}) is False
            assert await emit_tool_delta({"progress": 2}) is False
            result = "business result"
        assert result == "business result" and len(calls) == 1
        assert scope.summary["reason"] == "publisher_error"

    asyncio.run(run())


def test_real_source_cancellation_drains_publication_and_propagates():
    async def run():
        entered, exited = asyncio.Event(), asyncio.Event()

        async def publish(value):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()

        async def source():
            with attempt_scope(StreamUpdatePolicy().identity, "tool", "a", "a:1", publish):
                await emit_tool_delta({"progress": 1})

        task = asyncio.create_task(source())
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert exited.is_set()

    asyncio.run(run())


def test_child_task_cannot_emit_after_original_attempt_scope_ends():
    async def run():
        release, seen = asyncio.Event(), []

        async def publish(value):
            seen.append(value)

        async def delayed():
            await release.wait()
            return await emit_tool_delta({"progress": "late"})

        with attempt_scope(StreamUpdatePolicy().identity, "tool", "a", "a:1", publish):
            task = asyncio.create_task(delayed())
        release.set()
        assert await task is False and seen == []

    asyncio.run(run())


def test_disabled_local_reporting_has_no_store_read_and_shadows_parent_attempt():
    async def run():
        from types import SimpleNamespace

        from relf_agent.local_stream_updates import reporting

        seen = []

        async def publish(value):
            seen.append(value)

        def forbidden(*args):
            raise AssertionError("Disabled observation must not reread execution state")

        engine = SimpleNamespace(stream_updates=None, _authorized=forbidden)
        with attempt_scope(StreamUpdatePolicy().identity, "tool", "parent", "parent:1", publish):
            with reporting(engine, "run", "child", "child:1", "tool"):
                assert await emit_tool_delta({"message": "child"}) is False
            assert await emit_tool_delta({"message": "parent"}) is True
        assert [value["action_id"] for value in seen] == ["parent"]

    asyncio.run(run())
