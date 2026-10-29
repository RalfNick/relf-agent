import asyncio

import pytest

import relf_agent as r
from relf_agent.errors import ValidationError
from relf_agent.stream_updates import AgentStreamSubscription


def test_rejected_concurrent_read_does_not_close_original_observer():
    async def run():
        entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class Reader:
            scope = r.Scope()

            async def events(self, run_id, *, after=0, limit=1000):
                if after:
                    return []
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
                return [r.RunEvent(run_id, 1, "run_succeeded", {})]

            async def status(self, run_id):
                return r.RunSnapshot(run_id, "succeeded", 1, "done", None, (), ())

        stream = AgentStreamSubscription(r.RunEventSubscription(Reader(), "run", follow=False))
        first = asyncio.create_task(anext(stream))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            with pytest.raises(ValidationError, match="one consumer"):
                await anext(stream)
            assert not cancelled.is_set()
            release.set()
            event = await asyncio.wait_for(first, 1)
            assert event.source_kind == "run_succeeded" and stream.cursor.after == 1
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
        finally:
            release.set()
            if not first.done():
                first.cancel()
            await asyncio.gather(first, return_exceptions=True)
            await stream.aclose()

    asyncio.run(run())
