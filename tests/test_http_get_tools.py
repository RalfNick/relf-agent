"""Fixed GET queries over actual loopback HTTP and original managed Actions."""

import asyncio
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest

from relf_agent import (
    ComponentRegistry,
    GraphNode,
    GraphWorkflowSpec,
    HTTPToolSource,
    InvocationContext,
    RuntimeBuilder,
    RuntimeProfile,
    Scope,
    ToolDescriptor,
    ToolSourceError,
    ValueRef,
    load_catalog,
)
from relf_agent.errors import DefinitionMismatch, ValidationError
from relf_agent.tools import ThreadExecutionTracker, current_thread_group, current_thread_tracker
from relf_agent.types import digest


@contextmanager
def endpoint():
    calls, started, release, effects = [], threading.Event(), threading.Event(), {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            calls.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body,
                }
            )
            started.set()
            parsed = urlsplit(self.path)
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            result = {"query": pairs} if self.command == "GET" else json.loads(body)
            if parsed.path == "/hang":
                release.wait(5)
            if parsed.path == "/write":
                arguments = dict(pairs)
                key = arguments["effect_key"]
                effects.setdefault(key, {"value": arguments["value"], "effect_key": key})
                result = effects[key]
            status, content, extra = 200, json.dumps(result).encode(), {}
            if parsed.path == "/redirect":
                status, content, extra = 307, b"", {"Location": "/followed"}
            elif parsed.path == "/error":
                status, content = 503, b"private-server-diagnostic"
            elif parsed.path == "/invalid":
                content = b"private-invalid-json"
            elif parsed.path == "/oversized":
                content = b"x" * 65536
            self.send_response(status)
            self.send_header("Content-Length", str(len(content)))
            for key, value in extra.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls, started, release, effects
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join()


def descriptor():
    return ToolDescriptor("lookup", "Fixed query", {"type": "object"}, {"type": "object"})


def context():
    return InvocationContext(Scope(), "run", "action", "attempt", "stable-key", "epoch")


def source(url, **options):
    return HTTPToolSource(descriptor(), url, version="get-v1", method="GET", **options)


def test_actual_get_encodes_sorted_mapped_scalar_and_repeated_values_without_body():
    with endpoint() as (url, calls, _, _, _):

        async def run():
            mapping = {"z": "tag", "a": "q", "flag": "enabled", "optional": "unused"}
            remote = source(url + "/fixed/path", query_parameters=mapping)
            original = remote.identity
            mapping["a"] = "changed"
            values = {"z": ["a&b", 0, False, 1.5], "flag": True, "a": "中文 +/?#=&%\r\n"}
            try:
                assert await remote.list_tools() == (descriptor(),) and not calls
                assert await remote.call_tool(descriptor(), values, context()) == {
                    "query": [
                        ["q", values["a"]],
                        ["enabled", "true"],
                        ["tag", "a&b"],
                        ["tag", "0"],
                        ["tag", "false"],
                        ["tag", "1.5"],
                    ]
                }
                assert remote.identity == original
                assert original["query_parameters"] == {
                    "z": "tag",
                    "a": "q",
                    "flag": "enabled",
                    "optional": "unused",
                }
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert len(calls) == 1
        request = calls[0]
        assert request["method"] == "GET" and not request["body"]
        assert request["path"] == (
            "/fixed/path?q=%E4%B8%AD%E6%96%87+%2B%2F%3F%23%3D%26%25%0D%0A"
            "&enabled=true&tag=a%26b&tag=0&tag=false&tag=1.5"
        )
        headers = {key.lower(): value for key, value in request["headers"].items()}
        assert "content-type" not in headers and headers["accept-encoding"] == "identity"
        assert headers["host"] == url.removeprefix("http://")


def test_default_get_names_and_empty_arguments_are_sent_without_query_body():
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/fixed")
            try:
                assert await remote.call_tool(descriptor(), {"z": "", "a": False}, context()) == {
                    "query": [["a", "false"], ["z", ""]]
                }
                assert await remote.call_tool(descriptor(), {}, context()) == {"query": []}
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert [call["path"] for call in calls] == ["/fixed?a=false&z=", "/fixed"]


@pytest.mark.parametrize(
    "value", [None, {}, [], [None], [{}], [[]], [[1]], float("nan"), float("inf"), "\ud800"]
)
def test_unsupported_get_values_refuse_before_any_request(value):
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/fixed")
            try:
                with pytest.raises(ValidationError):
                    await remote.call_tool(descriptor(), {"q": value}, context())
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert not calls


@pytest.mark.parametrize("arguments", [{"missing": "x"}, {"q": "x", "missing": 1}])
def test_partial_explicit_mapping_never_silently_drops_actual_arguments(arguments):
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/fixed", query_parameters={"q": "query"})
            try:
                with pytest.raises(ValidationError):
                    await remote.call_tool(descriptor(), arguments, context())
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert not calls


@pytest.mark.parametrize("name", ["", "bad name", "q\n", "q\x7f", "q\x85", "\ud800"])
def test_default_argument_names_are_checked_before_dispatch(name):
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/fixed")
            try:
                with pytest.raises(ValidationError):
                    await remote.call_tool(descriptor(), {name: "x"}, context())
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert not calls


@pytest.mark.parametrize(
    "arguments,limit,mapping",
    [
        ({"q": "中文"}, 12, None),
        ({"q": "中文"}, 18, None),
        ({"q": "x"}, 12, {"q": "long-query-name"}),
        ({"q": ["中", "中"]}, 22, None),
    ],
)
def test_json_and_encoded_query_each_have_the_original_input_byte_limit(arguments, limit, mapping):
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/fixed", max_input_bytes=limit, query_parameters=mapping)
            try:
                with pytest.raises(ValidationError):
                    await remote.call_tool(descriptor(), arguments, context())
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert not calls


@pytest.mark.parametrize("mode", ["redirect", "error", "invalid", "oversized"])
def test_get_failures_never_retry_redirect_or_expose_queries(mode):
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/" + mode, max_output_bytes=256)
            try:
                with pytest.raises(ToolSourceError) as error:
                    await remote.call_tool(descriptor(), {"q": "private-query-secret"}, context())
                assert "private-" not in str(error.value) and url not in str(error.value)
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert len(calls) == 1


@pytest.mark.parametrize(
    "options",
    [
        {"method": "get"},
        {"method": "PUT"},
        {"method": None},
        {"method": "POST", "query_parameters": {}},
        {"method": "GET", "query_parameters": []},
        {"method": "GET", "query_parameters": {"a": "same", "b": "same"}},
        {"method": "GET", "query_parameters": {"bad name": "q"}},
        {"method": "GET", "query_parameters": {"q": "bad\nname"}},
        {"method": "GET", "query_parameters": {"q": ""}},
        {"method": "GET", "query_parameters": {"q": True}},
    ],
)
def test_invalid_get_configuration_is_pure_before_database_or_client(
    tmp_path, monkeypatch, options
):
    def forbidden_client(*args, **kwargs):
        pytest.fail("Invalid declaration allocated an HTTP client")

    monkeypatch.setattr(httpx, "Client", forbidden_client)
    declared = {
        "tools": [
            {
                "descriptor": descriptor().to_dict(),
                "url": "http://127.0.0.1/fixed",
                "version": "1",
                "policy": {"version": "1", "effect": "read_only", "requires_approval": False},
                **options,
            }
        ]
    }
    with pytest.raises(ValidationError):
        ComponentRegistry().prepare("tools", {"adapter": "http-json", "config": declared})
    selected = RuntimeProfile(
        "invalid-get", "1", {}, {"tools": {"adapter": "http-json", "config": declared}}
    )

    async def run():
        with pytest.raises(ValidationError):
            await RuntimeBuilder().abuild(selected, tmp_path / "runs.sqlite")

    asyncio.run(run())
    assert not (tmp_path / "runs.sqlite").exists()


def test_sdk_rejects_non_string_mapping_keys_before_json_profile_normalization():
    with pytest.raises(ValidationError):
        source("http://127.0.0.1/fixed", query_parameters={1: "q"})


def test_get_cancelled_wait_and_close_retry_keep_actual_thread_ownership():
    with endpoint() as (url, calls, started, release, _):

        async def run():
            remote, tracker = source(url + "/hang", timeout=2), ThreadExecutionTracker()
            token = current_thread_tracker.set(tracker)
            group = current_thread_group.set("get-run")
            try:
                task = asyncio.create_task(remote.call_tool(descriptor(), {"q": "x"}, context()))
            finally:
                current_thread_tracker.reset(token)
                current_thread_group.reset(group)
            try:
                assert await asyncio.to_thread(started.wait, 2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                closing = asyncio.create_task(remote.aclose())
                await asyncio.sleep(0.03)
                assert not closing.done() and tracker.has_active_for("get-run")
                closing.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await closing
                retry = asyncio.create_task(remote.aclose())
                await asyncio.sleep(0.03)
                assert not retry.done() and tracker.has_active_for("get-run")
                with pytest.raises(ToolSourceError):
                    await remote.list_tools()
            finally:
                release.set()
            await asyncio.wait_for(retry, 3)
            await tracker.drain("get-run")
            assert not tracker.has_active

        asyncio.run(run())
        assert len(calls) == 1


def write_profile(root, url, extension):
    tool = {
        "descriptor": {
            "name": "write",
            "description": "Explicitly approved GET write",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}, "effect_key": {"type": "string"}},
                "required": ["value", "effect_key"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object"},
        },
        "url": url + "/write",
        "version": "get-write-v1",
        "method": "GET",
        "query_parameters": {"value": "value", "effect_key": "effect_key"},
        "policy": {
            "version": "1",
            "effect": "idempotent_write",
            "requires_approval": True,
            "effect_key_argument": "effect_key",
        },
    }
    path = root / ("runtime." + extension)
    if extension == "json":
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "default": {"name": "get", "version": "1"},
                    "profiles": [
                        {
                            "name": "get",
                            "version": "1",
                            "providers": {},
                            "components": {
                                "tools": {"adapter": "http-json", "config": {"tools": [tool]}}
                            },
                        }
                    ],
                }
            )
        )
    else:
        path.write_text(f'''schema_version = 1
[default]
name = "get"
version = "1"
[[profiles]]
name = "get"
version = "1"
providers = {{}}
[profiles.components.tools]
adapter = "http-json"
[[profiles.components.tools.config.tools]]
url = "{url}/write"
version = "get-write-v1"
method = "GET"
[profiles.components.tools.config.tools.query_parameters]
value = "value"
effect_key = "effect_key"
[profiles.components.tools.config.tools.descriptor]
name = "write"
description = "Explicitly approved GET write"
[profiles.components.tools.config.tools.descriptor.input_schema]
type = "object"
required = ["value", "effect_key"]
additionalProperties = false
[profiles.components.tools.config.tools.descriptor.input_schema.properties.value]
type = "string"
[profiles.components.tools.config.tools.descriptor.input_schema.properties.effect_key]
type = "string"
[profiles.components.tools.config.tools.descriptor.output_schema]
type = "object"
[profiles.components.tools.config.tools.policy]
version = "1"
effect = "idempotent_write"
requires_approval = true
effect_key_argument = "effect_key"
''')
    return load_catalog(path).default


@pytest.mark.parametrize("extension", ["json", "toml"])
def test_declared_get_keeps_original_approval_reopen_and_duplicate_receipts(tmp_path, extension):
    with endpoint() as (url, calls, _, _, effects):
        selected = write_profile(tmp_path, url, extension)
        flow = GraphWorkflowSpec(
            "approved-get", [GraphNode("write", tool="write")], output=ValueRef("write")
        )

        async def run():
            database = tmp_path / "runs.sqlite"
            async with await RuntimeBuilder().abuild(selected, database) as runtime:
                handle = runtime.submit(flow, {"value": "7"}, command_id="submit")
                status = await runtime.drive(handle.run_id)
                assert status.state == "waiting_approval" and not calls
                pending = status.pending[0]
            async with await RuntimeBuilder().abuild(
                load_catalog(tmp_path / ("runtime." + extension)).default, database
            ) as runtime:
                assert runtime.submit(flow, {"value": "7"}, command_id="submit") == handle
                approval = runtime.approve(
                    handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
                )
                done = await runtime.drive(handle.run_id)
                assert done.state == "succeeded" and done.result["value"] == "7"
                assert (
                    runtime.approve(
                        handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
                    )
                    == approval
                )
                assert len(calls) == len(effects) == 1
            async with await RuntimeBuilder().abuild(selected, database) as runtime:
                assert runtime.submit(flow, {"value": "7"}, command_id="submit") == handle
                assert (await runtime.drive(handle.run_id)).result == done.result
                assert len(calls) == len(effects) == 1

        asyncio.run(run())
        assert calls[0]["method"] == "GET" and not calls[0]["body"]


def test_post_identity_and_legacy_transport_invocation_are_unchanged(monkeypatch):
    from relf_agent import http_tool_transport

    observed = []

    def original_call(*args, **kwargs):
        observed.append((args, kwargs))
        return {"value": 1}

    monkeypatch.setattr(http_tool_transport, "execute", original_call)

    async def run():
        remote = HTTPToolSource(descriptor(), "http://127.0.0.1/fixed", version="post-v1")
        assert remote.identity == {
            "kind": "http-json-tool-source",
            "version": "1",
            "behavior_version": "post-v1",
            "url": "http://127.0.0.1/fixed",
            "method": "POST",
            "header_names": [],
            "header_fingerprint": digest({}),
            "timeout": 30,
            "max_input_bytes": 1048576,
            "max_output_bytes": 1048576,
            "tool": descriptor().to_dict(),
        }
        try:
            assert await remote.call_tool(descriptor(), {"value": 1}, context()) == {"value": 1}
        finally:
            await remote.aclose()

    asyncio.run(run())
    assert len(observed) == 1 and not observed[0][1]
    args = observed[0][0]
    assert args[:5] == ("http://127.0.0.1/fixed", {}, b'{"value":1}', 30, 1048576)
    assert len(args) == 6 and isinstance(args[-1], threading.Event)


def test_get_fixed_mapping_drift_refuses_before_request():
    with endpoint() as (url, calls, _, _, _):

        async def run():
            remote = source(url + "/fixed", query_parameters={"q": "query"})
            remote._query_parameters["q"] = "changed"
            try:
                with pytest.raises(DefinitionMismatch):
                    await remote.call_tool(descriptor(), {"q": "x"}, context())
            finally:
                await remote.aclose()

        asyncio.run(run())
        assert not calls
