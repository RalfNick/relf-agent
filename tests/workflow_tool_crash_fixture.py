import asyncio
import json
import os
import sys
from pathlib import Path

from relf_agent import (
    GraphNode,
    GraphWorkflowSpec,
    LocalEngine,
    SQLiteStore,
    ToolRegistry,
    ToolSpec,
    ValueRef,
)

root, mode = Path(sys.argv[1]), sys.argv[2]
handler_kind = sys.argv[3] if len(sys.argv) > 3 else "sync"


def handler(arguments, context):
    path = root / "business-count"
    path.write_text(str(int(path.read_text()) + 1) if path.exists() else "1")
    return arguments


async def async_handler(arguments, context):
    await asyncio.sleep(0)
    return handler(arguments, context)


def identity(action):
    return {
        **{key: action[key] for key in ("id", "effect_key", "digest")},
        "attempt_ids": [attempt["id"] for attempt in action["attempts"]],
    }


class CrashEngine(LocalEngine):
    def _record_tool_observation(self, *args):
        result = super()._record_tool_observation(*args)
        if mode == "crash":
            action = self.store.run(args[0])["actions"][0]
            (root / "identity.json").write_text(json.dumps(identity(action)))
            os._exit(77)
        return result


registry = ToolRegistry()
registry.register(
    ToolSpec("business", "Write", {"type": "object"}, effect="unqueryable_write"),
    async_handler if handler_kind == "async" else handler,
)
with CrashEngine(SQLiteStore(root / "run.sqlite"), providers={}, tools=registry) as engine:
    spec = GraphWorkflowSpec(
        "tool", [GraphNode("write", tool="business")], output=ValueRef("write")
    )
    handle = engine.submit(spec, {"value": 3}, command_id="same")
    result = asyncio.run(engine.drive(handle.run_id))
    action = engine.store.run(handle.run_id)["actions"][0]
    assert identity(action) == json.loads((root / "identity.json").read_text())
    print(
        json.dumps(
            {
                "state": result.state,
                "result": result.result,
                "calls": int((root / "business-count").read_text()),
            }
        )
    )
