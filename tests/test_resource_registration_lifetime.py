"""Resource acceptance cannot change a ledger while its owners close it."""

import asyncio

import pytest

from relf_agent import ComponentRegistry, RuntimeBuilder, RuntimeProfile, Scope
from relf_agent.errors import ValidationError
from relf_agent.runtime_builder import EchoProvider
from relf_agent.runtime_lifecycle import BuildContext


@pytest.mark.parametrize("asynchronous", [False, True])
def test_close_callback_cannot_register_another_owned_resource(tmp_path, asynchronous):
    first = (tmp_path / "first.txt").open("w")
    late = (tmp_path / "late.txt").open("w")
    context = None
    closed = []

    class Client:
        def close(self):
            closed.append("client")
            with pytest.raises(ValidationError, match="cleanup"):
                context.own(late)

    def factory(config, selected):
        nonlocal context
        context = selected
        selected.own(first)
        selected.own(Client())
        return EchoProvider("lifetime")

    registry = ComponentRegistry()
    registry.register("provider", "resource-lifetime", factory)
    profile = RuntimeProfile("lifetime", "1", {"default": {"adapter": "resource-lifetime"}})
    runtime = RuntimeBuilder(registry).build(profile, tmp_path / "runtime.sqlite")
    try:
        if asynchronous:
            asyncio.run(runtime.aclose())
        else:
            runtime.close()
        assert first.closed and not late.closed
        assert closed == ["client"]
        runtime.close()
        assert closed == ["client"]
    finally:
        first.close()
        late.close()
        context.store.close()


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_completed_cleanup_refuses_late_ownership_through_all_context_views(tmp_path, shared, mode):
    async def scenario():
        owner = BuildContext(None, tmp_path / "unused", Scope(), tmp_path, allow_async=True)
        context = (
            BuildContext(
                None, tmp_path / "unused", Scope(), tmp_path, allow_async=True, resource_owner=owner
            )
            if shared
            else owner
        )
        await owner.cleanup_async()
        late = (tmp_path / "late.txt").open("w")

        class Client:
            calls = 0

            async def aclose(self):
                self.calls += 1

        client = Client()
        try:
            with pytest.raises(ValidationError, match="cleanup"):
                context.own(late) if mode == "sync" else context.own_async(client)
            assert not late.closed and client.calls == 0
            await owner.cleanup_async()
            assert not late.closed and client.calls == 0
        finally:
            late.close()
            await client.aclose()

    asyncio.run(scenario())


def test_cancelled_cleanup_still_refuses_new_ownership_and_can_retry(tmp_path):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        context = BuildContext(None, tmp_path / "unused", Scope(), tmp_path, allow_async=True)
        closed = []

        class Client:
            async def aclose(self):
                closed.append("client")
                entered.set()
                await release.wait()

        context.own_async(Client())
        late = (tmp_path / "late.txt").open("w")
        closing = asyncio.create_task(context.cleanup_async())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            with pytest.raises(ValidationError, match="cleanup"):
                context.own(late)
            assert not late.closed
        finally:
            release.set()
            await context.cleanup_async()
            late.close()
        assert closed == ["client"]

    asyncio.run(scenario())


def test_failed_cleanup_keeps_admission_closed_until_the_original_retry_finishes(tmp_path):
    context = BuildContext(None, tmp_path / "unused", Scope(), tmp_path)
    original = (tmp_path / "original.txt").open("w")
    late = (tmp_path / "late.txt").open("w")

    class Client:
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("retry original cleanup")
            original.close()

    client = context.own(Client())
    try:
        with pytest.raises(RuntimeError):
            context.cleanup()
        with pytest.raises(ValidationError, match="cleanup"):
            context.own(late)
        assert not original.closed and not late.closed
        context.cleanup()
        assert original.closed and not late.closed
        assert client.attempts == 2
        context.cleanup()
        assert client.attempts == 2
    finally:
        original.close()
        late.close()


def test_refused_sync_cleanup_leaves_resource_admission_open(tmp_path):
    async def scenario():
        context = BuildContext(None, tmp_path / "unused", Scope(), tmp_path, allow_async=True)
        closed = []

        class Client:
            async def aclose(self):
                closed.append("client")

        context.own_async(Client())
        with pytest.raises(ValidationError, match="aclose"):
            context.cleanup()
        late = (tmp_path / "late.txt").open("w")
        try:
            assert context.own(late) is late
            await context.cleanup_async()
            assert late.closed and closed == ["client"]
        finally:
            late.close()
            await context.cleanup_async()

    asyncio.run(scenario())
