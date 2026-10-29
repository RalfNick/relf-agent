"""Actual stream Worker fixture; audit writes are not business effects."""

import asyncio
import json
import os
from pathlib import Path

import relf_agent as r
from relf_agent.temporal import build_temporal_worker
from relf_agent.temporal_activities import TemporalRuntime


def audit(root, kind):
    with (root / "calls.jsonl").open("a") as output:
        output.write(json.dumps({"kind": kind, "pid": os.getpid()}) + "\n")
        output.flush()
        os.fsync(output.fileno())


class StreamSource:
    identity = {"kind": "actual-service-stream-fixture", "version": "1"}

    def __init__(self, root):
        self.root = root

    async def complete(self, messages, tools):
        raise AssertionError("The explicit wrapper must consume stream only")

    async def stream(self, messages, tools):
        audit(self.root, "model")
        yield r.ModelStreamEvent("text", text="prefix")
        if any(message["role"] == "tool" for message in messages):
            response = r.ModelResponse("done")
        else:
            (self.root / "prefix-held").touch()
            while not (self.root / "release-model").exists():  # noqa: ASYNC110 -- subprocess fence
                await asyncio.sleep(0.02)
            response = r.ModelResponse(tool_calls=[r.ToolCall("lookup", {}, "lookup-call")])
        yield r.ModelStreamEvent("response", response=response)

    async def lookup(self, arguments, context):
        await r.emit_tool_delta({"message": "lookup-start"})
        audit(self.root, "tool")
        await r.emit_tool_delta({"message": "lookup-finished"})
        return {"found": True}


def definition():
    return r.AgentSpec("stream-reader", "Use lookup, then answer", ("lookup",))


def stream_runtime(root, *, limited=False):
    source, tools = StreamSource(root), r.ToolRegistry()
    tools.register(
        r.ToolSpec(
            "lookup",
            "Approved read-only lookup",
            {"type": "object", "additionalProperties": False},
            effect="read_only",
            requires_approval=True,
        ),
        source.lookup,
    )
    return TemporalRuntime(
        providers={"default": r.StreamedModelProvider(source, chunk_chars=1)},
        tools=tools,
        stream_updates=r.StreamUpdatePolicy(max_deltas=2) if limited else r.StreamUpdatePolicy(),
    )


async def worker_main(root, address, queue):
    from temporalio.client import Client

    client = await Client.connect(address)
    async with build_temporal_worker(client, task_queue=queue, runtime=stream_runtime(root)):
        print("TEMPORAL_STREAM_READY", flush=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    # The client imports this factory by its stable module name. A -m entry
    # point must use the same declarations, not register __main__ methods.
    from tests.temporal_stream_worker import worker_main as imported_worker_main

    asyncio.run(
        imported_worker_main(
            Path(os.environ["RALF_STREAM_ROOT"]),
            os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
            os.environ["RALF_STREAM_QUEUE"],
        )
    )
