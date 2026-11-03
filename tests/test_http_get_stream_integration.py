"""Configured GET and presentation share the original approval/receipt log."""

import asyncio
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from relf_agent import (
    GraphNode,
    GraphWorkflowSpec,
    RuntimeBuilder,
    RuntimeProfile,
    ValueRef,
)


@contextmanager
def business_lookup():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append((self.path, int(self.headers.get("Content-Length", "0"))))
            data = json.dumps(
                {"order": parse_qs(urlsplit(self.path).query)["id"][0], "status": "ready"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/orders", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_configured_get_approval_reopen_and_stream_end_do_not_redispatch(tmp_path):
    with business_lookup() as (url, requests):
        profile = RuntimeProfile(
            "get-stream",
            "1",
            {},
            {
                "stream_updates": {"adapter": "bounded", "config": {"max_deltas": 2}},
                "tools": {
                    "adapter": "http-json",
                    "config": {
                        "tools": [
                            {
                                "descriptor": {
                                    "name": "lookup",
                                    "description": "Read an order",
                                    "input_schema": {
                                        "type": "object",
                                        "properties": {"order_id": {"type": "string"}},
                                        "required": ["order_id"],
                                        "additionalProperties": False,
                                    },
                                    "output_schema": {"type": "object"},
                                },
                                "url": url,
                                "version": "1",
                                "method": "GET",
                                "query_parameters": {"order_id": "id"},
                                "policy": {
                                    "version": "1",
                                    "effect": "read_only",
                                    "requires_approval": True,
                                },
                            }
                        ]
                    },
                },
            },
        )
        flow = GraphWorkflowSpec(
            "get-stream", [GraphNode("lookup", tool="lookup")], output=ValueRef("lookup")
        )
        database = tmp_path / "runs.sqlite"

        async def run():
            async with await RuntimeBuilder().abuild(profile, database) as runtime:
                original = runtime.submit(flow, {"order_id": "单号 & #/?"}, command_id="submit")
                paused = await runtime.drive(original.run_id)
                assert paused.state == "waiting_approval" and requests == []
                pending = paused.pending[0]

            async with await RuntimeBuilder().abuild(profile, database) as runtime:
                assert (
                    runtime.submit(flow, {"order_id": "单号 & #/?"}, command_id="submit")
                    == original
                )
                approved = runtime.approve(
                    original.run_id, pending["action_id"], pending["digest"], command_id="approve"
                )
                done = await runtime.drive(original.run_id)
                assert done.state == "succeeded"
                assert done.result == {"order": "单号 & #/?", "status": "ready"}
                events = runtime.events(original.run_id)
                ends = [event.data["stream_end"] for event in events if "stream_end" in event.data]
                assert len(ends) == 1 and ends[0]["operation"] == "tool"
                assert not any(event.kind == "agent_update" for event in events)

            async with await RuntimeBuilder().abuild(profile, database) as runtime:
                assert (
                    runtime.submit(flow, {"order_id": "单号 & #/?"}, command_id="submit")
                    == original
                )
                assert (
                    runtime.approve(
                        original.run_id,
                        pending["action_id"],
                        pending["digest"],
                        command_id="approve",
                    )
                    == approved
                )
                assert (await runtime.drive(original.run_id)).result == done.result
                assert runtime.events(original.run_id) == events

        asyncio.run(run())
        assert len(requests) == 1 and requests[0][1] == 0
        assert urlsplit(requests[0][0]).path == "/orders"
