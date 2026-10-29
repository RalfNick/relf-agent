"""Typed, resumable presentation over the original authority's event log."""

import json
import math
from dataclasses import asdict, dataclass, field

from .errors import ValidationError
from .event_records import EventEnvelope
from .types import canonical


@dataclass(frozen=True)
class StreamUpdatePolicy:
    max_deltas: int = 64
    max_bytes: int = 65536
    max_payload_bytes: int = 4096
    publish_timeout: float = 0.25

    def __post_init__(self):
        if (
            type(self.max_deltas) is not int
            or not 1 <= self.max_deltas <= 1024
            or type(self.max_bytes) is not int
            or not 256 <= self.max_bytes <= 1048576
            or type(self.max_payload_bytes) is not int
            or not 256 <= self.max_payload_bytes <= min(65536, self.max_bytes)
            or type(self.publish_timeout) not in (int, float)
            or not 0 < self.publish_timeout <= 2
            or not math.isfinite(self.publish_timeout)
        ):
            raise ValidationError("Invalid stream update limits")

    @property
    def identity(self):
        return {"version": 1, **asdict(self)}

    @classmethod
    def from_identity(cls, value):
        if (
            type(value) is not dict
            or set(value)
            != {"version", "max_deltas", "max_bytes", "max_payload_bytes", "publish_timeout"}
            or type(value["version"]) is not int
            or value["version"] != 1
        ):
            raise ValidationError("Unsupported stream update policy")
        return cls(**{name: value[name] for name in value if name != "version"})


def policy_identity(value):
    if value is None:
        return None
    if type(value) is not StreamUpdatePolicy:
        raise ValidationError("Stream updates require an explicit StreamUpdatePolicy")
    return value.identity


def update_value(value, policy=None):
    if type(value) is not dict or set(value) != {
        "version",
        "action_id",
        "attempt_id",
        "operation",
        "sequence",
        "kind",
        "payload",
    }:
        raise ValidationError("Invalid Agent update fields")
    if (
        type(value["version"]) is not int
        or value["version"] != 1
        or any(
            type(value[n]) is not str or not value[n] or len(value[n]) > 1024
            for n in ("action_id", "attempt_id")
        )
        or type(value["sequence"]) is not int
        or not 1 <= value["sequence"] <= 2**63 - 1
        or type(value["operation"]) is not str
        or value["operation"] not in {"model", "tool"}
        or type(value["kind"]) is not str
        or value["kind"] not in {value["operation"] + "_delta", "gap"}
        or type(value["payload"]) is not dict
    ):
        raise ValidationError("Invalid Agent update identity or payload")
    if value["kind"] == "model_delta" and (
        set(value["payload"]) != {"text"} or type(value["payload"]["text"]) is not str
    ):
        raise ValidationError("Model delta requires text")
    try:
        encoded = canonical(value)
        payload_bytes = len(canonical(value["payload"]).encode("utf-8"))
        if payload_bytes > (65536 if policy is None else policy.max_payload_bytes):
            raise ValidationError("Stream update payload exceeds allowance")
        return json.loads(encoded)
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValidationError("Stream update requires finite UTF-8 JSON") from exc


@dataclass(frozen=True, init=False)
class AgentStreamEvent:
    envelope: EventEnvelope
    kind: str
    authoritative: bool
    action_id: str | None
    attempt_id: str | None
    sequence: int | None
    _data_json: str = field(repr=False)

    def __init__(self, envelope):
        if not isinstance(envelope, EventEnvelope):
            raise ValidationError("Agent stream requires an original EventEnvelope")
        event = envelope.event
        if event.kind == "agent_update":
            value = update_value(event.data)
            kind, authoritative, data = value["kind"], False, value["payload"]
        elif "stream_end" in event.data:
            value = event.data["stream_end"]
            if (
                type(value) is not dict
                or value.get("operation") not in ("model", "tool")
                or type(value.get("action_id")) is not str
                or type(value.get("attempt_id")) is not str
            ):
                raise ValidationError("Invalid stream end observation")
            kind, authoritative, data = value["operation"] + "_end", True, event.data
        else:
            value, kind, authoritative, data = {}, "run", True, event.data
        for key, item in {
            "envelope": envelope,
            "kind": kind,
            "authoritative": authoritative,
            "action_id": value.get("action_id"),
            "attempt_id": value.get("attempt_id"),
            "sequence": value.get("sequence"),
            "_data_json": canonical(data),
        }.items():
            object.__setattr__(self, key, item)

    @property
    def data(self):
        return json.loads(self._data_json)

    @property
    def cursor(self):
        return self.envelope.cursor

    @property
    def source_kind(self):
        return self.envelope.event.kind

    def to_dict(self):
        return {
            "kind": self.kind,
            "authoritative": self.authoritative,
            "action_id": self.action_id,
            "attempt_id": self.attempt_id,
            "sequence": self.sequence,
            "data": self.data,
            "source": self.envelope.to_dict(),
        }


class AgentStreamSubscription:
    def __init__(self, subscription):
        self._source, self._cursor = subscription, subscription.cursor

    @property
    def cursor(self):
        return self._cursor

    def __aiter__(self):
        return self

    async def __anext__(self):
        # The source owns read admission and its cancellation/cleanup. A rejected
        # concurrent or foreign-loop read must not close its active consumer.
        envelope = await anext(self._source)
        try:
            value = AgentStreamEvent(envelope)
        except BaseException:
            await self.aclose()
            raise
        self._cursor = value.cursor
        return value

    async def aclose(self):
        await self._source.aclose()
