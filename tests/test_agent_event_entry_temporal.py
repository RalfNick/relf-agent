import asyncio
from contextlib import aclosing

import relf_agent as r

from .temporal_agent_fixture import engine


def test_temporal_handle_observes_original_events_without_owning_worker(monkeypatch):
    async def run():
        raw = engine(monkeypatch)
        async with r.Runtime.from_temporal(raw) as runtime:
            handle = await runtime.create_agent(r.AgentSpec("a", "Answer", ("lookup",))).submit(
                "task", command_id="s"
            )
            paused = await handle.wait(wait_timeout=1)
            assert paused.snapshot.state == "waiting_approval"
            before = await handle.events()
            async with aclosing(handle.subscribe_events(follow=False, page_size=2)) as events:
                assert [row.event async for row in events] == before
            assert raw.client.tool_calls == 0
            assert (await handle.status()).state == "waiting_approval"
        assert not raw._closed and not raw.client.closed

    asyncio.run(run())
