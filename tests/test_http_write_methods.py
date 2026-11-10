"""Fixed write verbs and explicit empty acknowledgements over the original source."""

import asyncio
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

import relf_agent as r
from relf_agent import http_tool_transport
from relf_agent.errors import DefinitionMismatch, ValidationError


def descriptor(output_schema=None):
    return r.ToolDescriptor(
        "update", "Update a fixed business resource", {"type": "object"}, output_schema
    )


def context():
    return r.InvocationContext(r.Scope(), "run", "action", "attempt", "stable-key", "epoch")


@contextmanager
def endpoint():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.respond()

        def do_GET(self):
            self.respond()

        def do_PUT(self):
            self.respond()

        def do_PATCH(self):
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
            status, content, extra = 200, body, {}
            if self.path.startswith("/empty204"):
                status, content = 204, b""
            if self.path == "/empty204-positive":
                extra["Content-Length"], content = "1", b"x"
            elif self.path == "/empty204-transfer":
                extra["Transfer-Encoding"], content = "chunked", b"0\r\n\r\n"
            elif self.path == "/empty204-transfer-empty":
                extra["Transfer-Encoding"] = ""
            elif self.path == "/empty204-compressed":
                extra["Content-Encoding"] = "gzip"
            elif self.path == "/empty200":
                content = b""
            elif self.path == "/whitespace":
                content = b" \n "
            elif self.path == "/invalid":
                content = b"private-invalid-json"
            elif self.path == "/null":
                content = b"null"
            elif self.path == "/oversized":
                content = b'"' + b"x" * 128 + b'"'
            elif self.path == "/redirect":
                status, content, extra = 307, b"", {"Location": "/echo"}
            elif self.path == "/error":
                status, content = 503, b"private-business-diagnostic"
            self.send_response(status)
            if self.path == "/empty204-zero":
                self.send_header("Content-Length", "0")
            elif status != 204:
                self.send_header("Content-Length", str(len(content)))
            for key, value in extra.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_actual_write_verb_uses_canonical_json_body_and_fixed_headers(method):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor({"type": "object"})
            source = r.HTTPToolSource(declared, url + "/echo", version="write-1", method=method)
            try:
                assert await source.list_tools() == (declared,) and calls == []
                value = {"value": {"z": None, "a": "中文"}}
                assert await source.call_tool(declared, value, context()) == value
                assert source.identity["method"] == method
            finally:
                await source.aclose()

        asyncio.run(run())
        assert len(calls) == 1
        assert calls[0]["method"] == method and calls[0]["path"] == "/echo"
        assert calls[0]["body"] == '{"value":{"a":"中文","z":null}}'.encode()
        assert calls[0]["headers"]["Content-Type"] == "application/json"
        assert calls[0]["headers"]["Accept-Encoding"] == "identity"


@pytest.mark.parametrize("method", ["POST", "GET", "PUT", "PATCH"])
@pytest.mark.parametrize("path", ["/empty204", "/empty204-zero"])
def test_opt_in_accepts_only_empty_204_as_schema_validated_json_null(method, path):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor({"type": "null"})
            source = r.HTTPToolSource(
                declared, url + path, version="empty-1", method=method, allow_empty_204=True
            )
            try:
                assert await source.call_tool(declared, {}, context()) is None
                assert source.identity["allow_empty_204"] is True
            finally:
                await source.aclose()

        asyncio.run(run())
        assert len(calls) == 1 and calls[0]["method"] == method


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_original_default_still_rejects_empty_204(method):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor({"type": "null"})
            source = r.HTTPToolSource(declared, url + "/empty204", version="old", method=method)
            try:
                with pytest.raises(r.ToolSourceError):
                    await source.call_tool(declared, {}, context())
            finally:
                await source.aclose()

        asyncio.run(run())
        assert len(calls) == 1


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_acknowledged_null_is_rejected_when_original_output_schema_requires_object(method):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor({"type": "object"})
            source = r.HTTPToolSource(
                declared, url + "/empty204", version="empty-1", method=method, allow_empty_204=True
            )
            try:
                with pytest.raises(r.ToolSourceError, match="Schema"):
                    await source.call_tool(declared, {}, context())
            finally:
                await source.aclose()

        asyncio.run(run())
        assert len(calls) == 1


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
@pytest.mark.parametrize(
    "path",
    [
        "/empty200",
        "/whitespace",
        "/invalid",
        "/oversized",
        "/redirect",
        "/error",
        "/empty204-positive",
        "/empty204-transfer",
        "/empty204-transfer-empty",
        "/empty204-compressed",
    ],
)
def test_empty_ack_option_does_not_relax_status_json_framing_encoding_or_bytes(method, path):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor()
            source = r.HTTPToolSource(
                declared,
                url + path,
                version="strict-1",
                method=method,
                allow_empty_204=True,
                max_output_bytes=64,
            )
            try:
                with pytest.raises(r.ToolSourceError) as caught:
                    await source.call_tool(declared, {}, context())
                assert "private" not in str(caught.value) and url not in str(caught.value)
            finally:
                await source.aclose()

        asyncio.run(run())
        assert len(calls) == 1 and calls[0]["path"] == path


@pytest.mark.parametrize("body", [b"x", b"null", b" ", b"x" * 65])
def test_nonempty_observed_204_body_is_never_json_or_an_empty_ack(monkeypatch, body):
    # HTTP/1.1 parsers suppress illegal 204 bodies. The native HTTPX transport
    # exercises our observed-body boundary without faking the Client lifecycle.
    original_client = httpx.Client

    def client(**options):
        return original_client(
            **options,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(204, stream=httpx.ByteStream(body))
            ),
        )

    monkeypatch.setattr(http_tool_transport.httpx, "Client", client)

    async def run():
        declared = descriptor()
        source = r.HTTPToolSource(
            declared,
            "http://127.0.0.1/fixed",
            version="observed-1",
            method="PUT",
            allow_empty_204=True,
            max_output_bytes=64,
        )
        try:
            with pytest.raises(r.ToolSourceError):
                await source.call_tool(declared, {}, context())
        finally:
            await source.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Length": "not-an-integer"},
        {"Content-Length": "-0"},
        {"Content-Length": "1"},
        {"Transfer-Encoding": ""},
    ],
)
def test_204_invalid_header_framing_is_sanitized_before_acceptance(monkeypatch, headers):
    original_client = httpx.Client

    def client(**options):
        return original_client(
            **options,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(204, headers=headers, stream=httpx.ByteStream(b""))
            ),
        )

    monkeypatch.setattr(http_tool_transport.httpx, "Client", client)

    async def run():
        declared = descriptor({"type": "null"})
        source = r.HTTPToolSource(
            declared,
            "http://127.0.0.1/fixed",
            version="framing-1",
            method="PATCH",
            allow_empty_204=True,
        )
        try:
            with pytest.raises(r.ToolSourceError) as caught:
                await source.call_tool(declared, {}, context())
            assert "not-an-integer" not in str(caught.value)
        finally:
            await source.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_json_null_response_does_not_require_the_empty_204_option(method):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor({"type": "null"})
            source = r.HTTPToolSource(declared, url + "/null", version="json-null-1", method=method)
            try:
                assert await source.call_tool(declared, {}, context()) is None
                assert "allow_empty_204" not in source.identity
            finally:
                await source.aclose()

        asyncio.run(run())
        assert len(calls) == 1


@pytest.mark.parametrize("option", [None, 0, 1, 0.0, "true", [], {}])
def test_empty_ack_option_is_a_strict_boolean_at_sdk_construction(option):
    with pytest.raises(ValidationError):
        r.HTTPToolSource(
            descriptor(), "http://127.0.0.1/fixed", version="bad", allow_empty_204=option
        )


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_json_write_methods_cannot_use_get_query_mappings(method):
    with pytest.raises(ValidationError):
        r.HTTPToolSource(
            descriptor(),
            "http://127.0.0.1/fixed",
            version="bad",
            method=method,
            query_parameters={},
        )


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
@pytest.mark.parametrize("option", [False, True])
def test_declared_write_and_empty_ack_are_admitted_without_connecting(method, option):
    declaration = {
        "tools": [
            {
                "descriptor": descriptor({"type": "null"}).to_dict(),
                "url": "http://127.0.0.1:1/fixed",
                "version": "declared-1",
                "method": method,
                "allow_empty_204": option,
                "policy": {"version": "1", "effect": "read_only", "requires_approval": False},
            }
        ]
    }
    factory, prepared = r.ComponentRegistry().prepare(
        "tools", {"adapter": "http-json", "config": declaration}
    )
    assert asyncio.iscoroutinefunction(factory)
    assert prepared["tools"][0]["method"] == method
    assert prepared["tools"][0]["allow_empty_204"] is option


@pytest.mark.parametrize("construction", ["build", "abuild", "temporal-abuild"])
@pytest.mark.parametrize("option", [None, 0, "true"])
def test_bad_empty_ack_option_refuses_before_any_resource_is_allocated(
    tmp_path, construction, option
):
    registrations, allocated = r.ComponentRegistry(), []

    def provider(config, context):
        allocated.append("provider")
        pytest.fail("Invalid HTTP option allocated a provider")

    def store(*args, **kwargs):
        allocated.append("store")
        pytest.fail("Invalid HTTP option allocated an execution store")

    registrations.register("provider", "must-not-construct", provider)
    providers = {"default": {"adapter": "must-not-construct"}}
    components = {
        "tools": {
            "adapter": "http-json",
            "config": {
                "tools": [
                    {
                        "descriptor": descriptor().to_dict(),
                        "url": "http://127.0.0.1/fixed",
                        "version": "bad",
                        "method": "PUT",
                        "allow_empty_204": option,
                        "policy": {
                            "version": "1",
                            "effect": "read_only",
                            "requires_approval": False,
                        },
                    }
                ]
            },
        }
    }
    path = tmp_path / "never.sqlite"
    if construction == "temporal-abuild":
        from relf_agent.temporal_builder import TemporalRuntimeBuilder
        from relf_agent.temporal_profile import TemporalProfile

        async def run():
            with pytest.raises(ValidationError):
                await TemporalRuntimeBuilder(registrations).abuild(
                    TemporalProfile("bad", "1", providers, components), data_path=path
                )

        asyncio.run(run())
    else:
        builder = r.RuntimeBuilder(registrations, store_factory=store)
        profile = r.RuntimeProfile("bad", "1", providers, components)
        if construction == "build":
            with pytest.raises(ValidationError):
                builder.build(profile, path)
        else:

            async def run():
                with pytest.raises(ValidationError):
                    await builder.abuild(profile, path)

            asyncio.run(run())
    assert allocated == [] and not path.exists()


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_false_option_keeps_original_identity_and_transport_arguments(monkeypatch, method):
    observed = []

    def transport(*args, **kwargs):
        observed.append((args, kwargs))
        return {"ok": True}

    monkeypatch.setattr(http_tool_transport, "execute", transport)

    async def run():
        declared = descriptor()
        implicit = r.HTTPToolSource(
            declared, "http://127.0.0.1/fixed", version="old", method=method
        )
        explicit = r.HTTPToolSource(
            declared, "http://127.0.0.1/fixed", version="old", method=method, allow_empty_204=False
        )
        try:
            assert implicit.identity == explicit.identity
            assert "allow_empty_204" not in explicit.identity
            for source in (implicit, explicit):
                assert await source.call_tool(declared, {"value": 1}, context()) == {"ok": True}
        finally:
            await implicit.aclose()
            await explicit.aclose()

    asyncio.run(run())
    assert len(observed) == 2
    for args, kwargs in observed:
        assert len(args) == 6 and isinstance(args[-1], threading.Event)
        if method == "POST":
            assert args[:5] == ("http://127.0.0.1/fixed", {}, b'{"value":1}', 30, 1048576)
            assert kwargs == {}
        else:
            assert args[:5] == ("http://127.0.0.1/fixed", {}, None, 30, 1048576)
            assert kwargs == {"method": "GET", "query": "value=1"}


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
def test_opt_in_flag_drift_refuses_before_any_request(method):
    with endpoint() as (url, calls):

        async def run():
            declared = descriptor()
            source = r.HTTPToolSource(
                declared, url + "/empty204", version="drift-1", method=method, allow_empty_204=True
            )
            source._allow_empty_204 = False
            try:
                with pytest.raises(DefinitionMismatch):
                    await source.call_tool(declared, {}, context())
            finally:
                await source.aclose()

        asyncio.run(run())
        assert calls == []
