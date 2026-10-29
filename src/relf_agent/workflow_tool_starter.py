"""Optional editable Tool-only application for the existing graph starter."""

TOOL_GRAPH_FILES = {
    "agent_app/tool_runtime.py": '''"""Sync registration factory, async business handlers, original ProfiledEngine."""

import asyncio
from pathlib import Path

from relf_agent import ComponentRegistry, ProfiledEngine, RuntimeBuilder, ToolRegistry, load_catalog
from relf_agent.errors import ValidationError


async def lookup_order(order_id: str):
    # Replace this fixture with an awaited read-only business API.
    await asyncio.sleep(0)
    return {"order_id": order_id, "sku": "SKU-1", "quantity": 2}


async def check_stock(order_id: str, sku: str, quantity: int):
    await asyncio.sleep(0)
    return {"order_id": order_id, "sku": sku, "available": quantity <= 4}


def register_tools(config, context):
    if set(config) - {"requires_approval"} or type(config.get("requires_approval", False)) is not bool:
        raise ValidationError("Tool fixture accepts only a boolean requires_approval")
    tools = ToolRegistry()
    for handler in (lookup_order, check_stock):
        tools.register_function(handler, effect="read_only", version="1",
                                requires_approval=config.get("requires_approval", False))
    return tools


def create_engine(db_path=".ralf/tool-graph.sqlite"):
    root = Path(__file__).resolve().parents[1]
    registry = ComponentRegistry()
    registry.register("tools", "order-fixture", register_tools)
    # Factory construction is synchronous; async handlers run only on dispatch.
    # Keep original profile versions/code when changing the catalog default.
    return ProfiledEngine(load_catalog(root / "tool-runtime.toml"), db_path,
                          builder=RuntimeBuilder(registry, base_dir=root))
''',
    "agent_app/tool_graph.py": '''"""Two existing Local Tool nodes; no model configuration or model calls."""

import argparse
import asyncio
import json
from pathlib import Path

from relf_agent import load_spec
from relf_agent.errors import RalfError
from .tool_runtime import create_engine


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=".ralf/tool-graph.sqlite")
    parser.add_argument("--order-id", default="ORD-1")
    parser.add_argument("--command-id", default="order-check-1")
    parser.add_argument("--budget", type=int, default=2)
    parser.add_argument("--submit-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        with create_engine(args.db) as engine:
            spec = load_spec(Path(__file__).resolve().parents[1] / "tool-graph.json")
            handle = engine.submit(spec, {"order_id": args.order_id},
                                   command_id=args.command_id, budget=args.budget)
            snapshot = engine.status(handle.run_id) if args.submit_only else asyncio.run(engine.drive(handle.run_id))
            info = engine.diagnostics(handle.run_id)
            print(json.dumps({"run_id": snapshot.run_id, "state": snapshot.state,
                              "pending": snapshot.pending, "result": snapshot.result,
                              "model_actions": sum(a["kind"] == "model" for a in snapshot.actions),
                              "tool_actions": sum(a["kind"] == "tool" for a in snapshot.actions),
                              "credits_spent": info.budget["spent"]}, ensure_ascii=False))
            return 1 if snapshot.state == "failed" else 0
    except RalfError as error:
        print(json.dumps({"error": error.code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "tool-runtime.toml": """schema_version = 1
[default]
name = "async-tool-orders"
version = "1"
[[profiles]]
name = "async-tool-orders"
version = "1"
providers = {}
[profiles.components.tools]
adapter = "order-fixture"
[profiles.components.tools.config]
requires_approval = false
""",
    "tool-graph.json": """{
  "kind": "graph", "name": "async-order-check",
  "nodes": [
    {"id": "lookup", "tool": "lookup_order", "output_schema": {"type": "object"}},
    {"id": "stock", "tool": "check_stock", "depends_on": ["lookup"],
     "input": {"kind": "object", "fields": {
       "order_id": {"kind": "ref", "source": "lookup", "path": ["order_id"]},
       "sku": {"kind": "ref", "source": "lookup", "path": ["sku"]},
       "quantity": {"kind": "ref", "source": "lookup", "path": ["quantity"]}
     }}, "output_schema": {"type": "object"}}
  ],
  "output": {"kind": "ref", "source": "stock"}
}
""",
}
