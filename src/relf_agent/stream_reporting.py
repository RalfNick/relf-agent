"""Explicit bounded reporting in an authority-owned async Attempt."""

import asyncio
import json
from contextlib import contextmanager
from contextvars import ContextVar

from .errors import ValidationError
from .ports import _complete_sync_none
from .stream_updates import StreamUpdatePolicy, update_value
from .types import canonical

_ACTIVE = ContextVar("relf_stream_attempt", default=None)


class StreamAttempt:
    def __init__(self, identity, operation, action_id, attempt_id, publisher):
        self.policy = StreamUpdatePolicy.from_identity(identity)
        self.operation, self.action_id, self.attempt_id = operation, action_id, attempt_id
        self.publisher, self.loop = publisher, asyncio.get_running_loop()
        self.lock = asyncio.Lock()
        self.closed, self.disabled = False, False
        self.count = self.size = self.sequence = self.published = 0
        self.reason = None

    @property
    def summary(self):
        return {
            "published": self.published,
            "truncated": self.reason is not None,
            "reason": self.reason,
        }

    async def _publish(self, kind, payload):
        self.sequence += 1
        value = update_value(
            {
                "version": 1,
                "action_id": self.action_id,
                "attempt_id": self.attempt_id,
                "operation": self.operation,
                "sequence": self.sequence,
                "kind": kind,
                "payload": payload,
            },
            self.policy,
        )
        try:
            result = await asyncio.wait_for(self.publisher(value), self.policy.publish_timeout)
            _complete_sync_none(result, "Stream observation publication")
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            self.disabled, self.reason = True, "publisher_error"
            return False
        except Exception:
            self.disabled, self.reason = True, "publisher_error"
            return False
        self.published += kind != "gap"
        return True

    async def emit(self, payload):
        if self.closed or self.disabled or asyncio.get_running_loop() is not self.loop:
            return False
        async with self.lock:
            if self.closed or self.disabled or self.reason is not None:
                return False
            try:
                if type(payload) is not dict:
                    raise ValidationError("Progress requires a JSON object")
                encoded = canonical(payload)
                size = len(encoded.encode("utf-8"))
                payload = json.loads(encoded)
            except (ValidationError, UnicodeError, RecursionError, OverflowError):
                self.reason = "invalid_payload"
            else:
                if size > self.policy.max_payload_bytes:
                    self.reason = "payload_limit"
                elif (
                    self.count >= self.policy.max_deltas or self.size + size > self.policy.max_bytes
                ):
                    self.reason = "capacity"
            if self.reason is not None:
                await self._publish("gap", {"reason": self.reason})
                return False
            self.count += 1
            self.size += size
            return await self._publish(self.operation + "_delta", payload)


@contextmanager
def attempt_scope(identity, operation, action_id, attempt_id, publisher):
    value = (
        None
        if identity is None
        else StreamAttempt(identity, operation, action_id, attempt_id, publisher)
    )
    token = _ACTIVE.set(value)
    try:
        yield value
    finally:
        if value is not None:
            value.closed = True
        _ACTIVE.reset(token)


async def emit_tool_delta(payload):
    """Report JSON from a managed async tool; False is not an effect failure."""
    current = _ACTIVE.get()
    if current is None or current.operation != "tool":
        return False
    return await current.emit(payload)


async def emit_model_delta(text):
    current = _ACTIVE.get()
    if current is None or current.operation != "model":
        return False
    return await current.emit({"text": text})


def current_end(operation, action_id, attempt_id):
    current = _ACTIVE.get()
    if current is None or (current.operation, current.action_id, current.attempt_id) != (
        operation,
        action_id,
        attempt_id,
    ):
        return {}
    return {
        "stream_end": {
            "operation": operation,
            "action_id": action_id,
            "attempt_id": attempt_id,
            "observation": current.summary,
        }
    }
