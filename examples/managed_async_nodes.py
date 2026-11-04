"""Offline async node: approve a sample receipt, reopen, then replay commands.

Only the two local SQLite files are written. No model, key or network is used.
Pass --db to retain the example between processes; omission uses a temporary directory.
"""

import argparse
import asyncio
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from relf_agent import (
    EffectObservation,
    GraphNode,
    GraphWorkflowSpec,
    LocalEngine,
    NodeExecutorRegistry,
    NodeExecutorSpec,
    SQLiteStore,
    ToolRegistry,
    ValueRef,
)

ITEMS = [{"sku": "demo-desk", "units": 2}, {"sku": "demo-lamp", "units": 1}]
NODE_CONFIG = {"warehouse": "offline-demo", "reason": "example-only"}


class ReceiptLedger:
    """A sample business system, separate from the framework's execution log."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.connection = sqlite3.connect(self.path)
        with self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS requests (effect_key TEXT NOT NULL)"
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS receipts ("
                "effect_key TEXT PRIMARY KEY, operation TEXT NOT NULL, result TEXT NOT NULL)"
            )

    def record(self, items, config, effect_key):
        operation = json.dumps({"input": items, "config": config}, sort_keys=True)
        with self.connection:
            self.connection.execute("INSERT INTO requests VALUES (?)", (effect_key,))
            previous = self.connection.execute(
                "SELECT operation, result FROM receipts WHERE effect_key = ?", (effect_key,)
            ).fetchone()
            if previous is not None:
                if previous[0] != operation:
                    raise ValueError("An effect key cannot name two different operations")
                return json.loads(previous[1])
            result = {
                "effect_key": effect_key,
                "items": items,
                "config": config,
                "total_units": sum(item["units"] for item in items),
            }
            self.connection.execute(
                "INSERT INTO receipts VALUES (?, ?, ?)",
                (effect_key, operation, json.dumps(result, sort_keys=True)),
            )
            return result

    def receipt(self, effect_key):
        row = self.connection.execute(
            "SELECT result FROM receipts WHERE effect_key = ?", (effect_key,)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def counts(self):
        requests = self.connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        effects = self.connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
        return requests, effects

    def close(self):
        self.connection.close()


class RecordReceipt:
    """A structural third-party node; no framework base class is required."""

    def __init__(self, client):
        self.client = client

    @property
    def identity(self):
        return {"kind": "example-receipt-node", "version": "1", "ledger": str(self.client.path)}

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        return self.client.record(input, config, context.effect_key)

    async def reconcile(self, input, config, context):
        await asyncio.sleep(0)
        receipt = self.client.receipt(context.effect_key)
        return None if receipt is None else EffectObservation(receipt, "offline-ledger")


def make_registry(client):
    nodes = NodeExecutorRegistry()
    nodes.register(
        NodeExecutorSpec(
            "receipt",
            "Record an approved receipt in the offline example ledger",
            effect="idempotent_write",
            requires_approval=True,
            cost=2,
            input_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"sku": {"type": "string"}, "units": {"type": "integer"}},
                    "required": ["sku", "units"],
                    "additionalProperties": False,
                },
            },
            config_schema={
                "type": "object",
                "properties": {"warehouse": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["warehouse", "reason"],
                "additionalProperties": False,
            },
            output_schema={"type": "object", "required": ["effect_key", "items", "config"]},
        ),
        RecordReceipt(client),
    )
    return nodes


def workflow():
    return GraphWorkflowSpec(
        "offline-receipt",
        [
            GraphNode(
                "record",
                executor="receipt",
                config=NODE_CONFIG,
                output_schema={"type": "object", "required": ["effect_key", "total_units"]},
            )
        ],
        output=ValueRef("record"),
    )


def create_engine(db_path, client):
    store = SQLiteStore(db_path)
    try:
        return LocalEngine(
            store, providers={}, tools=ToolRegistry(), workflow_executors=make_registry(client)
        )
    except BaseException:
        store.close()
        raise


async def run_demo(db_path, client, command_id, *, pause_before_approval=False):
    before, _ = client.counts()
    with create_engine(db_path, client) as engine:
        handle = engine.submit(workflow(), ITEMS, command_id=command_id, budget=4)
        repeated = engine.submit(workflow(), ITEMS, command_id=command_id, budget=4)
        initial = await engine.drive(handle.run_id)
        if initial.state not in {"waiting_approval", "succeeded"}:
            raise RuntimeError(f"Unexpected node state: {initial.state}: {initial.error}")
        action = initial.actions[0]
    if pause_before_approval and initial.state == "waiting_approval":
        requests, effects = client.counts()
        return {
            "run_id": handle.run_id,
            "state": initial.state,
            "requests_total": requests,
            "effects_total": effects,
            "submission": asdict(handle.receipt),
            "pending": initial.pending[0],
        }

    # The first Engine is closed before the original Action is approved.
    approval_id = command_id + ":approve"
    with create_engine(db_path, client) as engine:
        approved = engine.approve(
            handle.run_id, action["id"], action["digest"], command_id=approval_id
        )
        done = await engine.drive(handle.run_id)
        if done.state != "succeeded":
            raise RuntimeError(f"Unexpected node state: {done.state}: {done.error}")
        spent = engine.diagnostics(handle.run_id).budget["spent"]

    # Replaying both commands also works after the original Run completed.
    with create_engine(db_path, client) as engine:
        replay = engine.submit(workflow(), ITEMS, command_id=command_id, budget=4)
        approval_replay = engine.approve(
            replay.run_id, action["id"], action["digest"], command_id=approval_id
        )
        final = await engine.drive(replay.run_id)
        committed = final.actions[0]
    requests, effects = client.counts()
    return {
        "run_id": handle.run_id,
        "initial_state": initial.state,
        "state": final.state,
        "effect_key": committed["effect_key"],
        "action_id": committed["id"],
        "action_count": len(final.actions),
        "submission": asdict(handle.receipt),
        "approval": asdict(approved),
        "receipt_replay_matches": handle == repeated == replay and approved == approval_replay,
        "requests_this_process": requests - before,
        "requests_total": requests,
        "effects_total": effects,
        "spent": spent,
        "result": final.result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", help="Execution SQLite path; business ledger uses PATH.business.sqlite"
    )
    parser.add_argument("--command-id", default="managed-node-demo")
    parser.add_argument("--pause-before-approval", action="store_true")
    args = parser.parse_args()

    def run(db_path):
        db_path = Path(db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        client = ReceiptLedger(str(db_path) + ".business.sqlite")
        try:
            result = asyncio.run(
                run_demo(
                    db_path,
                    client,
                    args.command_id,
                    pause_before_approval=args.pause_before_approval,
                )
            )
        finally:
            client.close()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))

    if args.db:
        run(args.db)
    else:
        with TemporaryDirectory(prefix="relf-managed-node-") as directory:
            run(Path(directory) / "runs.sqlite")


if __name__ == "__main__":
    # Direct script execution always imports the same application module, even
    # outside the checkout. Keep this filename when copying the example.
    from managed_async_nodes import main as run_example

    run_example()
