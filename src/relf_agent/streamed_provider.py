"""Borrow a text stream; only EOF-complete responses reach the authority."""

import asyncio
import copy
import inspect
import logging

from ._dto_json import canonical_dto
from .errors import DefinitionMismatch, ValidationError
from .middleware import _entry, _identity
from .model_protocol import ModelCapabilities, ModelStreamEvent
from .ports import _complete_sync_none, is_async_callable, is_sync_callable
from .stream_reporting import emit_model_delta
from .types import ModelResponse, canonical

_LOG = logging.getLogger("relf_agent.stream")


class StreamedModelProvider:
    def __init__(self, provider, *, chunk_chars=128):
        if type(chunk_chars) is not int or not 1 <= chunk_chars <= 256:
            raise ValidationError("Stream chunk_chars must be from 1 to 256")
        self.provider, self.chunk_chars = provider, chunk_chars
        self._pending_closes, self._active = {}, {}
        self._retrying = False
        self._pinned = canonical(self.identity)

    @property
    def identity(self):
        method = getattr(self.provider, "stream", None)
        if not (inspect.isasyncgenfunction(method) or is_sync_callable(method)):
            raise ValidationError("Streamed provider requires an async iterator port")
        capabilities = self.capabilities
        if capabilities is not None and (
            not isinstance(capabilities, ModelCapabilities) or capabilities.streaming is not True
        ):
            raise ValidationError("Provider disables streaming")
        validate = getattr(self.provider, "validate_request", None)
        if validate is not None and not is_sync_callable(validate):
            raise ValidationError("Provider preflight must be synchronous")
        return {
            "kind": "streamed-model-provider",
            "version": "1",
            "chunk_chars": self.chunk_chars,
            "provider": _identity(self.provider, ("complete",), is_async_callable),
            "stream": _entry(method),
            "preflight": None if validate is None else _entry(validate),
            "implementation": {
                n: _entry(getattr(self, n)) for n in ("complete", "stream", "validate_request")
            },
        }

    @property
    def capabilities(self):
        return getattr(self.provider, "capabilities", None)

    @property
    def continuation_identity(self):
        from .model_continuation import provider_continuation_identity

        return provider_continuation_identity(self.provider)

    def _verify(self):
        if self._pending_closes or self._retrying:
            raise ValidationError("Retry pending stream iterator cleanup before dispatch")
        if canonical(self.identity) != self._pinned:
            raise DefinitionMismatch("Streamed Provider registration changed")

    @property
    def pending_stream_closes(self):
        return len(self._pending_closes)

    async def _close(self, source):
        try:
            close = getattr(source, "aclose", None)
            if not callable(close):
                if inspect.iscoroutine(source) or inspect.isgenerator(source):
                    source.close()
                return True
            value = close()
            if inspect.isawaitable(value):
                value = await value
            _complete_sync_none(value, "Stream iterator close")
        except asyncio.CancelledError:
            self._pending_closes[id(source)] = source
            if asyncio.current_task().cancelling():
                raise
        except Exception:
            self._pending_closes[id(source)] = source
        else:
            self._pending_closes.pop(id(source), None)
            return True
        try:
            _LOG.warning("Stream iterator cleanup pending code=stream_close_failed")
        except (Exception, asyncio.CancelledError):
            pass
        return False

    async def retry_stream_closes(self):
        """Close retained iterators only; the underlying Provider stays borrowed."""
        if self._active or self._retrying:
            raise ValidationError("Drain active streams before retrying cleanup")
        self._retrying = True
        try:
            for source in list(self._pending_closes.values()):
                await self._close(source)
            if self._pending_closes:
                raise ValidationError("Stream iterator cleanup remains pending")
        finally:
            self._retrying = False

    def validate_request(self, messages, tools):
        self._verify()
        validate = getattr(self.provider, "validate_request", None)
        if validate is not None:
            _complete_sync_none(validate(messages, tools), "Provider preflight")
        self._verify()

    def stream(self, messages, tools):
        self._verify()
        return self.provider.stream(messages, tools)

    async def complete(self, messages, tools):
        self.validate_request(messages, tools)
        chunk_chars = self.chunk_chars
        source = self.provider.stream(messages, tools)
        self._active[id(source)] = source
        final, buffer, size, reporting = None, "", 0, True
        try:
            if (
                not callable(getattr(source, "aclose", None))
                or not callable(getattr(source, "__anext__", None))
                or not callable(getattr(source, "__aiter__", None))
            ):
                raise ValidationError("Provider stream must be a closable async iterator")
            iterator = source.__aiter__()
            if iterator is not source:
                await self._close(iterator)
                raise ValidationError("Provider stream must return its actual async iterator")
            while True:
                try:
                    event = await anext(source)
                except StopAsyncIteration:
                    break
                if not isinstance(event, ModelStreamEvent) or final is not None:
                    raise ValidationError("Malformed or extra complete stream event")
                encoded = canonical_dto(event)
                size += len(encoded.encode("utf-8"))
                if size > 4_000_000:
                    raise ValidationError("Model stream exceeds its response allowance")
                if event.kind == "text" and type(event.text) is str and event.response is None:
                    if reporting:
                        buffer += event.text
                        ready = len(buffer) - len(buffer) % chunk_chars
                        for offset in range(0, ready, chunk_chars):
                            if not await emit_model_delta(buffer[offset : offset + chunk_chars]):
                                reporting = False
                                break
                        buffer = buffer[ready:] if reporting else ""
                elif (
                    event.kind == "response"
                    and not event.text
                    and isinstance(event.response, ModelResponse)
                ):
                    final = copy.deepcopy(event.response)
                    if buffer and reporting:
                        await emit_model_delta(buffer)
                        buffer = ""
                else:
                    raise ValidationError("Invalid model stream event")
            if final is None:
                raise ValidationError("Model stream has no complete response")
        finally:
            try:
                await self._close(source)
            finally:
                self._active.pop(id(source), None)
        return final
