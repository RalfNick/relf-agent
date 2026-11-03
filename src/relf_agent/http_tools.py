"""Fixed JSON HTTP tools through the original ToolSource execution contract."""

import copy
import re
import threading
import unicodedata
from urllib.parse import urlencode, urlsplit

import httpx
from jsonschema import Draft202012Validator

from . import http_tool_transport
from .errors import DefinitionMismatch, ValidationError
from .tool_sources import ToolDescriptor, ToolSourceError
from .tools import ThreadExecutionTracker, current_thread_group, current_thread_tracker
from .types import canonical, digest


def _configuration(url, version, headers, timeout, input_limit, output_limit):
    if (
        type(url) is not str
        or not url
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url)
    ):
        raise ValidationError("HTTP tool URL requires fixed HTTP(S) text")
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid endpoint")
        _ = parsed.port
        httpx.URL(url)
    except (ValueError, httpx.InvalidURL):
        raise ValidationError("HTTP tool URL requires a valid fixed HTTP(S) endpoint") from None
    if type(version) is not str or not version.strip():
        raise ValidationError("HTTP source requires an explicit behavior version")
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValidationError("HTTP timeout must be finite seconds in (0,300]")
    for value in (input_limit, output_limit):
        if type(value) is not int or not 1 <= value <= 16777216:
            raise ValidationError("HTTP byte limits require integers in [1,16777216]")
    if headers is not None and type(headers) is not dict:
        raise ValidationError("HTTP headers require an explicit dictionary")
    result = {}
    for key, value in (headers or {}).items():
        if (
            type(key) is not str
            or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)
            or type(value) is not str
            or any(ord(char) < 32 or ord(char) >= 127 for char in value)
            or key.lower() in result
            or key.lower()
            in {"host", "content-length", "transfer-encoding", "content-type", "accept-encoding"}
        ):
            raise ValidationError("HTTP header names or values conflict with fixed JSON framing")
        result[key.lower()] = value
    return result


def _query_name(value):
    if (
        type(value) is not str
        or not value
        or any(char.isspace() or unicodedata.category(char) == "Cc" for char in value)
    ):
        raise ValidationError(
            "HTTP query names require non-empty text without whitespace or controls"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValidationError("HTTP query names require valid UTF-8") from None
    return value


def _query_configuration(method, parameters):
    if type(method) is not str or method not in {"POST", "GET"}:
        raise ValidationError("HTTP tool method must be POST or GET")
    if method == "POST" and parameters is not None:
        raise ValidationError("HTTP POST tools cannot configure query parameters")
    if parameters is None:
        return None
    if type(parameters) is not dict:
        raise ValidationError("HTTP query parameters require an explicit dictionary")
    result = {_query_name(key): _query_name(value) for key, value in parameters.items()}
    if len(set(result.values())) != len(result):
        raise ValidationError("HTTP query parameter targets must be unique")
    return result


def _query(arguments, parameters, max_bytes):
    encoded, size = [], 0
    for key in sorted(arguments):
        _query_name(key)
        if parameters is not None and key not in parameters:
            raise ValidationError("HTTP argument has no fixed query parameter mapping")
        name = key if parameters is None else parameters[key]
        value = arguments[key]
        values = value if type(value) is list else [value]
        if not values:
            raise ValidationError("HTTP query values require scalars or non-empty scalar lists")
        for item in values:
            if type(item) not in (str, int, float, bool):
                raise ValidationError(
                    "HTTP query values require strings, finite numbers or booleans"
                )
            try:
                part = urlencode(
                    [(name, item if type(item) is str else canonical(item))],
                    encoding="utf-8",
                    errors="strict",
                )
            except UnicodeEncodeError:
                raise ValidationError("HTTP query values require valid UTF-8") from None
            size += len(part) + bool(encoded)
            if size > max_bytes:
                raise ValidationError("HTTP query exceeds its byte limit")
            encoded.append(part)
    return "&".join(encoded)


class HTTPToolSource:
    def __init__(
        self,
        descriptor,
        url,
        *,
        version,
        headers=None,
        timeout=30,
        max_input_bytes=1048576,
        max_output_bytes=1048576,
        method="POST",
        query_parameters=None,
    ):
        if not isinstance(descriptor, ToolDescriptor):
            raise ValidationError("HTTP source requires one explicit ToolDescriptor")
        self._headers = _configuration(
            url, version, headers, timeout, max_input_bytes, max_output_bytes
        )
        self._query_parameters = _query_configuration(method, query_parameters)
        if method == "GET" and any(delimiter in url for delimiter in ("?", "#")):
            raise ValidationError("HTTP GET endpoint cannot contain query or fragment delimiters")
        self._method = method
        self._descriptor = ToolDescriptor(**descriptor.to_dict())
        self._url, self._version = url, version
        self._timeout, self._input_limit, self._output_limit = (
            timeout,
            max_input_bytes,
            max_output_bytes,
        )
        self._lock, self._stops, self._closing = threading.Lock(), set(), False
        self._tracker = ThreadExecutionTracker()
        self._identity = canonical(self.identity)

    @property
    def identity(self):
        result = {
            "kind": "http-json-tool-source",
            "version": "1",
            "behavior_version": self._version,
            "url": self._url,
            "method": self._method,
            "header_names": sorted(self._headers),
            "header_fingerprint": digest(self._headers),
            "timeout": self._timeout,
            "max_input_bytes": self._input_limit,
            "max_output_bytes": self._output_limit,
            "tool": self._descriptor.to_dict(),
        }
        if self._method == "GET":
            result["query_parameters"] = copy.deepcopy(self._query_parameters)
        return result

    def _check(self):
        if canonical(self.identity) != self._identity:
            raise DefinitionMismatch("Original HTTP tool configuration changed")
        if self._closing:
            raise ToolSourceError("HTTP tool source is closing or closed")

    async def list_tools(self):
        with self._lock:
            self._check()
            return (ToolDescriptor(**self._descriptor.to_dict()),)

    def _execute(self, token, payload, stopped):
        if token is not None and not self._tracker._begin(token):
            return None
        try:
            if self._method == "POST":
                result = http_tool_transport.execute(
                    self._url, self._headers, payload, self._timeout, self._output_limit, stopped
                )
            else:
                result = http_tool_transport.execute(
                    self._url,
                    self._headers,
                    None,
                    self._timeout,
                    self._output_limit,
                    stopped,
                    method="GET",
                    query=payload,
                )
            if self._descriptor.output_schema is not None and not Draft202012Validator(
                self._descriptor.output_schema
            ).is_valid(result):
                raise ToolSourceError("HTTP output differs from the pinned Schema")
            return result
        finally:
            if token is not None:
                self._tracker._finish(token)

    async def call_tool(self, descriptor, arguments, context):
        if (
            not isinstance(descriptor, ToolDescriptor)
            or descriptor.to_dict() != self._descriptor.to_dict()
        ):
            raise DefinitionMismatch("HTTP invocation differs from its pinned descriptor")
        if not isinstance(arguments, dict) or not Draft202012Validator(
            self._descriptor.input_schema
        ).is_valid(arguments):
            raise ValidationError("HTTP arguments differ from the pinned Schema")
        try:
            values = copy.deepcopy(arguments)
            payload = canonical(values).encode("utf-8")
        except (ValueError, RecursionError):
            raise ValidationError("HTTP input requires finite UTF-8 JSON") from None
        if len(payload) > self._input_limit:
            raise ValidationError("HTTP input exceeds its byte limit")
        if self._method == "GET":
            payload = _query(values, self._query_parameters, self._input_limit)
        stopped = threading.Event()
        ambient = current_thread_tracker.get()
        tracker = ambient or self._tracker
        with self._lock:
            self._check()
            self._stops.add(stopped)
            token = (
                self._tracker._register(current_thread_group.get()) if ambient is not None else None
            )
        try:
            result = await tracker.run(
                self._execute, token, payload, stopped, group=current_thread_group.get()
            )
            self._check()
            return copy.deepcopy(result)
        except BaseException:
            stopped.set()
            if token is not None:
                self._tracker._withdraw_pending(token)
            raise
        finally:
            with self._lock:
                self._stops.discard(stopped)

    async def wait_for_calls(self):
        await self._tracker.drain()

    async def aclose(self):
        with self._lock:
            self._closing = True
            for stopped in self._stops:
                stopped.set()
        await self.wait_for_calls()
