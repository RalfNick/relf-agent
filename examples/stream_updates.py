"""Copy outside checkout and run with the maintenance SDK; no live model needed."""

import argparse
import asyncio
import json
from contextlib import aclosing

from relf_agent import (
    AgentSpec,
    LocalEngine,
    ModelResponse,
    ModelStreamEvent,
    Runtime,
    SQLiteStore,
    StreamedModelProvider,
    StreamUpdatePolicy,
    ToolCall,
    ToolRegistry,
    emit_tool_delta,
)


class OfflineStream:
    identity = {"kind": "stream-updates-example", "version": "1"}

    def __init__(self):
        self.calls = 0

    async def complete(self, messages, tools):
        raise AssertionError("The explicit adapter consumes stream only")

    async def stream(self, messages, tools):
        self.calls += 1
        yield ModelStreamEvent("text", text="Checking the local example. ")
        await asyncio.sleep(0)
        response = (
            ModelResponse("Example completed.")
            if any(m["role"] == "tool" for m in messages)
            else ModelResponse(tool_calls=[ToolCall("lookup", {}, "lookup-call")])
        )
        yield ModelStreamEvent("response", response=response)


async def run(path, command_id):
    tools, calls, base = ToolRegistry(), [], OfflineStream()

    @tools.tool(effect="read_only")
    async def lookup():
        await emit_tool_delta({"message": "Reading the local fixture"})
        calls.append(True)
        return {"found": True}

    engine = LocalEngine(
        SQLiteStore(path),
        providers={"default": StreamedModelProvider(base, chunk_chars=8)},
        tools=tools,
        stream_updates=StreamUpdatePolicy(),
    )
    async with Runtime(engine, owned=True) as runtime:
        handle = await runtime.create_agent(
            AgentSpec("example", "Use lookup then answer", ("lookup",))
        ).submit("Run the offline example", command_id=command_id)
        async with aclosing(handle.stream_updates()) as updates:
            async for event in updates:
                print(
                    json.dumps(
                        {
                            "kind": event.kind,
                            "authoritative": event.authoritative,
                            "data": event.data,
                            "cursor": event.cursor.token,
                        },
                        ensure_ascii=False,
                    )
                )
        snapshot = await handle.status()
        print(
            json.dumps(
                {
                    "state": snapshot.state,
                    "result": snapshot.result,
                    "run_id": handle.ref.run_id,
                    "model_calls": base.calls,
                    "tool_calls": len(calls),
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=".ralf/stream-example.sqlite")
    parser.add_argument("--command-id", default="stream-example-1")
    args = parser.parse_args()
    asyncio.run(run(args.db, args.command_id))
