import asyncio
import inspect
import threading

import pytest

from relf_agent import EventEnvelope, RunEvent, RunEventSubscription, RunSnapshot, Scope
from relf_agent.errors import ValidationError


class Reader:
    scope = Scope()

    def __init__(self, events, state):
        self.records, self.snapshot = events, state
        self.closed = False

    def events(self, run_id, **options):
        return self.records

    def status(self, run_id):
        return self.snapshot


class AsyncReader(Reader):
    async def events(self, *args, **options):
        return super().events(*args, **options)

    async def status(self, *args, **options):
        return super().status(*args, **options)


@pytest.mark.parametrize("reader_type", [Reader, AsyncReader])
@pytest.mark.parametrize("phase", ["event", "status"])
@pytest.mark.parametrize("shape", ["lock", "coroutine", "cycle"])
def test_invalid_json_refuses_whole_page_without_advancing_cursor(reader_type, phase, shape):
    entered = []

    async def later():
        entered.append(True)

    bad = later() if shape == "coroutine" else threading.Lock() if shape == "lock" else {}
    if shape == "cycle":
        bad["self"] = bad
    records = [RunEvent("r", 1, "step", {}), RunEvent("r", 2, "step", {"value": bad})]
    status = RunSnapshot("r", "running", 1, {"value": bad}, None, (), ())
    reader = reader_type(records if phase == "event" else [], status)

    async def run():
        stream = RunEventSubscription(reader, "r")
        try:
            with pytest.raises(ValidationError):
                await anext(stream)
            assert stream.cursor.after == 0 and entered == [] and not reader.closed
        finally:
            await stream.aclose()

    try:
        asyncio.run(run())
        if phase == "event":
            with pytest.raises(ValidationError):
                EventEnvelope(reader.scope, records[-1])
    finally:
        if inspect.iscoroutine(bad):
            bad.close()


@pytest.mark.parametrize("reader_type", [Reader, AsyncReader])
@pytest.mark.parametrize("state", [[], {}], ids=["list", "dict"])
def test_invalid_state_raises_typed_error(reader_type, state):
    async def run():
        reader = reader_type([], RunSnapshot("r", state, 0, None, None, (), ()))
        stream = RunEventSubscription(reader, "r")
        try:
            with pytest.raises(ValidationError):
                await anext(stream)
            assert stream.cursor.after == 0
        finally:
            await stream.aclose()

    asyncio.run(run())
