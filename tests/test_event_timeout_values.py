"""Event timeout validation is bounded and never converts huge integers first."""

import asyncio

import pytest

from relf_agent import RunEventSubscription
from relf_agent.errors import ValidationError

from .test_run_event_subscription import Reader


@pytest.mark.parametrize("field", ["read_timeout", "poll_interval"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(10**400, id="oversized-positive"),
        pytest.param(-(10**400), id="oversized-negative"),
        pytest.param(True, id="boolean"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
    ],
)
def test_invalid_event_timeouts_raise_validation_without_source_calls(field, value):
    reader = Reader()
    with pytest.raises(ValidationError, match="finite supported range"):
        RunEventSubscription(reader, "r", **{field: value})
    assert reader.calls == 0 and not reader.closed


@pytest.mark.parametrize(
    "field,value",
    [
        ("read_timeout", 0.001),
        ("read_timeout", 300),
        ("poll_interval", 0.01),
        ("poll_interval", 60),
    ],
)
def test_event_timeout_inclusive_bounds_are_preserved(field, value):
    reader = Reader()
    stream = RunEventSubscription(reader, "r", **{field: value})
    assert getattr(stream, field) is value and reader.calls == 0
    asyncio.run(stream.aclose())
    assert not reader.closed
