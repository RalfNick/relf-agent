"""Offline bounded batch: square each number, approve, then sum adopted results.

Only local execution and audit SQLite files are written. No model or network is
used. The math operations are read-only; their independent ledger records calls
and receipts, not a guarantee about arbitrary external write effects.
"""

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from relf_agent import (
    DynamicWorkflowSpec,
    FanOutDAGPlanner,
    GraphNode,
    GraphWorkflowSpec,
    LocalEngine,
    NodeExecutorRegistry,
    NodeExecutorSpec,
    SQLiteStore,
    ToolRegistry,
    ValueRef,
)

ITEMS = [3, 1, 2]


class ReceiptLedger:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.connection = sqlite3.connect(self.path)
        with self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS calls (seq INTEGER PRIMARY KEY,effect_key TEXT)"
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS receipts (effect_key TEXT PRIMARY KEY,"
                "operation TEXT,result TEXT)"
            )

    def record(self, kind, value, result, effect_key):
        operation = json.dumps({"kind": kind, "input": value}, sort_keys=True)
        with self.connection:
            self.connection.execute("INSERT INTO calls(effect_key) VALUES (?)", (effect_key,))
            previous = self.connection.execute(
                "SELECT operation,result FROM receipts WHERE effect_key=?", (effect_key,)
            ).fetchone()
            if previous is not None:
                if previous[0] != operation:
                    raise ValueError("Effect key does not match its original operation")
                return json.loads(previous[1])
            self.connection.execute(
                "INSERT INTO receipts VALUES (?,?,?)", (effect_key, operation, json.dumps(result))
            )
            return result

    def counts(self):
        return (
            self.connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0],
            self.connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],
        )

    def close(self):
        self.connection.close()


class BatchNode:
    """Ordinary structural async component; replace it with your own client."""

    def __init__(self, client, kind):
        self.client, self.kind = client, kind

    @property
    def identity(self):
        return {
            "kind": "example-batch-node",
            "version": "1",
            "ledger": str(self.client.path),
            "operation": self.kind,
        }

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        result = (
            input * input
            if self.kind == "square"
            else {"keys": list(input), "values": list(input.values()), "total": sum(input.values())}
        )
        return self.client.record(self.kind, input, result, context.effect_key)


def make_registry(client):
    nodes = NodeExecutorRegistry()
    nodes.register(
        NodeExecutorSpec(
            "square",
            "Square one approved item",
            effect="read_only",
            requires_approval=True,
            input_schema={"type": "integer"},
            output_schema={"type": "integer"},
        ),
        BatchNode(client, "square"),
    )
    nodes.register(
        NodeExecutorSpec(
            "sum",
            "Sum the adopted item results",
            effect="read_only",
            input_schema={"type": "object"},
        ),
        BatchNode(client, "sum"),
    )
    return nodes


def workflow():
    return DynamicWorkflowSpec(
        "batch-example",
        {
            "worker": GraphWorkflowSpec(
                "square", [GraphNode("square", executor="square")], output=ValueRef("square")
            ),
            "sum": GraphWorkflowSpec(
                "sum", [GraphNode("sum", executor="sum")], output=ValueRef("sum")
            ),
        },
        planner="fan-out",
        plan_mode="dag",
        child_budget=1,
        max_steps=4,
        max_revisions=1,
        max_concurrency=2,
        max_depth=3,
    )


def create_engine(db_path, client):
    store = SQLiteStore(db_path)
    try:
        return LocalEngine(
            store,
            providers={},
            tools=ToolRegistry(),
            workflow_executors=make_registry(client),
            planners={"fan-out": FanOutDAGPlanner("worker", reducer="sum")},
        )
    except BaseException:
        store.close()
        raise


def child_pending(engine, root_id):
    return [
        {"child_run_id": child["run_id"], **pending}
        for child in engine.diagnostics(root_id).workflow["children"]
        for pending in engine.status(child["run_id"]).pending
    ]


async def run_demo(db_path, client, command_id, *, pause_before_approval=False):
    before, _ = client.counts()
    with create_engine(db_path, client) as engine:
        handle = engine.submit(workflow(), ITEMS, command_id=command_id, budget=4)
        repeated = engine.submit(workflow(), ITEMS, command_id=command_id, budget=4)
        initial = await engine.drive(handle.run_id)
        if initial.state not in {"waiting_approval", "succeeded"}:
            raise RuntimeError(f"Unexpected batch state: {initial.state}: {initial.error}")
        if pause_before_approval and initial.state == "waiting_approval":
            requests, receipts = client.counts()
            return {
                "run_id": handle.run_id,
                "state": initial.state,
                "pending": child_pending(engine, handle.run_id),
                "requests_total": requests,
                "receipts_total": receipts,
            }

    # Reopen the original authority before approving any item.
    with create_engine(db_path, client) as engine:
        for _ in range(len(ITEMS) + 2):
            done = await engine.drive(handle.run_id)
            if done.state == "succeeded":
                break
            if done.state != "waiting_approval":
                raise RuntimeError(f"Unexpected batch state: {done.state}: {done.error}")
            for pending in child_pending(engine, handle.run_id):
                options = {"command_id": command_id + ":approve:" + pending["action_id"]}
                receipt = engine.approve(
                    pending["child_run_id"], pending["action_id"], pending["digest"], **options
                )
                assert (
                    engine.approve(
                        pending["child_run_id"], pending["action_id"], pending["digest"], **options
                    )
                    == receipt
                )
        if done.state != "succeeded":
            raise RuntimeError("Batch did not complete within its bounded approval rounds")
        spent = engine.diagnostics(handle.run_id).budget["spent"]

    with create_engine(db_path, client) as engine:
        replay = engine.submit(workflow(), ITEMS, command_id=command_id, budget=4)
        final = await engine.drive(replay.run_id)
        assert final.state == "succeeded" and final.result == done.result
        # Completed approvals retain their original command receipts as well.
        replayed = 0
        for child in engine.diagnostics(handle.run_id).workflow["children"]:
            if child["member"] != "worker":
                continue
            action = engine.status(child["run_id"]).actions[0]
            options = {"command_id": command_id + ":approve:" + action["id"]}
            first = engine.approve(child["run_id"], action["id"], action["digest"], **options)
            assert first == engine.approve(
                child["run_id"], action["id"], action["digest"], **options
            )
            replayed += 1
    requests, receipts = client.counts()
    return {
        "run_id": handle.run_id,
        "initial_state": initial.state,
        "state": final.state,
        "result": final.result,
        "spent": spent,
        "receipt_replay_matches": handle == repeated == replay and replayed == len(ITEMS),
        "requests_this_process": requests - before,
        "requests_total": requests,
        "receipts_total": receipts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", help="Execution SQLite file; audit receipts use PATH.business.sqlite"
    )
    parser.add_argument("--command-id", default="fan-out-demo")
    parser.add_argument("--pause-before-approval", action="store_true")
    args = parser.parse_args()

    def run(path):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        client = ReceiptLedger(str(path) + ".business.sqlite")
        try:
            result = asyncio.run(
                run_demo(
                    path, client, args.command_id, pause_before_approval=args.pause_before_approval
                )
            )
        finally:
            client.close()
        print(json.dumps(result, sort_keys=True))

    if args.db:
        run(args.db)
    else:
        with TemporaryDirectory(prefix="relf-fan-out-") as directory:
            run(Path(directory) / "runs.sqlite")


if __name__ == "__main__":
    # Preserve the same application module identity in every independent process.
    from fan_out_workflow import main as run_example

    run_example()
