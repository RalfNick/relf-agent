import asyncio

import pytest

import relf_agent as r
from relf_agent.errors import ValidationError


class Iterator:
    def __init__(self):
        self.index, self.closes, self.fail = 0, 0, True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index:
            raise StopAsyncIteration
        self.index += 1
        return r.ModelStreamEvent("response", response=r.ModelResponse("known"))

    async def aclose(self):
        self.closes += 1
        if self.fail:
            raise OSError("private iterator close failure")


class Provider:
    identity = {"kind": "owned-stream-iterator", "version": "1"}

    def __init__(self, source):
        self.source, self.calls = source, 0

    async def complete(self, *args):
        pytest.fail("Stream only")

    def stream(self, *args):
        self.calls += 1
        return self.source


def test_eof_completed_response_is_recorded_and_close_debt_is_retryable(tmp_path):
    async def run():
        iterator = Iterator()
        provider = Provider(iterator)
        wrapped = r.StreamedModelProvider(provider)
        with r.LocalEngine(
            r.SQLiteStore(tmp_path / "received.sqlite"),
            providers={"default": wrapped},
            tools=r.ToolRegistry(),
            stream_updates=r.StreamUpdatePolicy(),
        ) as engine:
            handle = engine.submit(r.AgentSpec("a", "Answer"), "q", command_id="s")
            assert (await engine.drive(handle.run_id)).result == "known"
            assert (
                sum(e.kind == "model_response_recorded" for e in engine.events(handle.run_id)) == 1
            )
            assert wrapped.pending_stream_closes == 1 and iterator.closes == 1
            with pytest.raises(ValidationError):
                await wrapped.complete([], [])
            assert provider.calls == 1
            iterator.fail = False
            await wrapped.retry_stream_closes()
            assert wrapped.pending_stream_closes == 0 and iterator.closes == 2
            await wrapped.retry_stream_closes()
            assert iterator.closes == 2

    asyncio.run(run())


def test_async_iterable_container_is_refused_before_inner_iteration():
    async def run():
        entered, finished = [], []

        async def inner():
            try:
                entered.append(True)
                yield r.ModelStreamEvent("response", response=r.ModelResponse("known"))
                yield r.ModelStreamEvent("text", text="late")
            finally:
                finished.append(True)

        actual = inner()

        class Container:
            closed = False

            def __aiter__(self):
                return actual

            async def aclose(self):
                self.closed = True

        container = Container()
        wrapped = r.StreamedModelProvider(Provider(container))
        try:
            with pytest.raises(ValidationError):
                await wrapped.complete([], [])
            assert container.closed and not entered
        finally:
            await actual.aclose()

    asyncio.run(run())


def test_disabled_reporting_stops_splitting_large_valid_chunks(monkeypatch):
    async def run():
        from relf_agent import streamed_provider

        attempts = []

        async def disabled(text):
            attempts.append(len(text))
            return False

        monkeypatch.setattr(streamed_provider, "emit_model_delta", disabled)

        class Large(Provider):
            async def stream(self, *args):
                yield r.ModelStreamEvent("text", text="x" * 500000)
                yield r.ModelStreamEvent("response", response=r.ModelResponse("known"))

        wrapped = r.StreamedModelProvider(Large(None), chunk_chars=1)
        assert (await wrapped.complete([], [])).output == "known"
        assert attempts == [1]

    asyncio.run(run())


def test_close_attribute_failure_after_eof_keeps_response_and_retry_handle():
    async def run():
        class ChangingClose(Iterator):
            broken = False

            async def __anext__(self):
                if self.index:
                    self.broken = True
                    raise StopAsyncIteration
                return await super().__anext__()

            @property
            def aclose(self):
                if self.broken:
                    raise OSError("private close lookup")
                return self.cleanup

            async def cleanup(self):
                self.closes += 1

        iterator = ChangingClose()
        wrapped = r.StreamedModelProvider(Provider(iterator))
        assert (await wrapped.complete([], [])).output == "known"
        assert wrapped.pending_stream_closes == 1
        iterator.broken = False
        await wrapped.retry_stream_closes()
        assert iterator.closes == 1 and wrapped.pending_stream_closes == 0

    asyncio.run(run())


def test_cancellation_during_iterator_close_retains_cleanup_for_safe_retry():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class Closing(Iterator):
            async def aclose(self):
                self.closes += 1
                entered.set()
                await release.wait()

        iterator = Closing()
        provider = Provider(iterator)
        wrapped = r.StreamedModelProvider(provider)
        task = asyncio.create_task(wrapped.complete([], []))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            with pytest.raises(ValidationError, match="active streams"):
                await wrapped.retry_stream_closes()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert wrapped.pending_stream_closes == 1
            with pytest.raises(ValidationError, match="pending stream"):
                await wrapped.complete([], [])
            assert provider.calls == 1 and iterator.closes == 1
            release.set()
            await wrapped.retry_stream_closes()
            assert wrapped.pending_stream_closes == 0 and iterator.closes == 2
            await wrapped.retry_stream_closes()
            assert iterator.closes == 2
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await wrapped.retry_stream_closes()

    asyncio.run(run())
