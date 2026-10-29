"""Cancelled close observers must not leak a late failure to the event loop."""

import asyncio
import gc

from relf_agent import AgentSpec, LocalEngine, Scope, SQLiteStore, ToolRegistry
from relf_agent.handoff import SQLiteInbox
from relf_agent.runtime_builder import EchoProvider
from relf_agent.service_lifecycle import LocalA2AService


def test_late_service_close_failure_is_observed_before_explicit_retry(tmp_path):
    async def scenario():
        entered, release, ended = asyncio.Event(), asyncio.Event(), asyncio.Event()
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        unhandled = []
        loop.set_exception_handler(lambda loop, context: unhandled.append(context))

        class Inbox:
            attempts = 0

            def __init__(self):
                self.store = SQLiteInbox(tmp_path / "inbox.sqlite")

            async def accept(self, *args, **kwargs):
                return self.store.accept(*args, **kwargs)

            async def complete(self, *args, **kwargs):
                return self.store.complete(*args, **kwargs)

            async def result(self, *args, **kwargs):
                return self.store.result(*args, **kwargs)

            async def pending(self, *args, **kwargs):
                return self.store.pending(*args, **kwargs)

            async def aclose(self):
                self.attempts += 1
                if self.attempts == 1:
                    entered.set()
                    await release.wait()
                    raise RuntimeError("fixture-private-close-failure")
                self.store.close()

        inbox = Inbox()
        engine = LocalEngine(
            SQLiteStore(tmp_path / "runs.sqlite"),
            providers={"default": EchoProvider("close")},
            tools=ToolRegistry(),
        )

        async def authenticate(headers):
            return Scope()

        service = LocalA2AService(
            engine=engine,
            inbox=inbox,
            authenticate=authenticate,
            spec=AgentSpec("a", "Answer"),
            url="http://test/rpc",
        )
        closing = asyncio.create_task(service.aclose())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            service._close_task.add_done_callback(lambda task: ended.set())
            closing.cancel()
            try:
                await closing
            except asyncio.CancelledError:
                pass
            release.set()
            await asyncio.wait_for(ended.wait(), 2)
            assert not service.closed and inbox.attempts == 1
            await service.aclose()
            assert service.closed and inbox.attempts == 2
            gc.collect()
            await asyncio.sleep(0)
            assert unhandled == []
        finally:
            release.set()
            await service.aclose()
            inbox.store.close()
            engine.close()
            loop.set_exception_handler(previous_handler)

    asyncio.run(scenario())
