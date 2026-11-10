"""Offline approved iteration: advance a value until its adopted result is done.

The original SDK owns all Runs, approvals, budgets and recovery. This example
uses only local SQLite and read-only arithmetic; the independent call ledger
does not prove exactly-once effects for arbitrary external business writes.
"""

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from relf_agent import (
    BoundedLoopPolicy,
    DynamicWorkflowSpec,
    GraphNode,
    GraphWorkflowSpec,
    LocalEngine,
    NodeExecutorRegistry,
    NodeExecutorSpec,
    SQLiteStore,
    ToolRegistry,
    ValueRef,
)

TASK = {"target": 3}


class ReceiptLedger:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.connection = sqlite3.connect(self.path)
        with self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS calls (seq INTEGER PRIMARY KEY,effect_key TEXT)"
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS receipts (effect_key TEXT PRIMARY KEY,input TEXT,result TEXT)"
            )

    def record(self, input, result, effect_key):
        original = json.dumps(input, sort_keys=True)
        with self.connection:
            self.connection.execute("INSERT INTO calls(effect_key) VALUES (?)", (effect_key,))
            found = self.connection.execute(
                "SELECT input,result FROM receipts WHERE effect_key=?", (effect_key,)
            ).fetchone()
            if found is not None:
                if found[0] != original:
                    raise ValueError("Original iteration input changed under its effect key")
                return json.loads(found[1])
            self.connection.execute(
                "INSERT INTO receipts VALUES (?,?,?)", (effect_key, original, json.dumps(result))
            )
            return result

    def counts(self):
        return (
            self.connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0],
            self.connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],
        )

    def close(self):
        self.connection.close()


class AdvanceNode:
    """Replace this structural async component with a managed business client."""

    def __init__(self, client):
        self.client = client

    @property
    def identity(self):
        return {"kind": "example-loop-advance", "version": "1", "ledger": str(self.client.path)}

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        previous = input["previous"]
        value = (0 if previous is None else previous["value"]) + 1
        result = {
            "done": value >= input["task"]["target"],
            "value": value,
            "iteration": input["iteration"],
        }
        return self.client.record(input, result, context.effect_key)


def workflow():
    return DynamicWorkflowSpec(
        "loop-example",
        {
            "worker": GraphWorkflowSpec(
                "advance", [GraphNode("advance", executor="advance")], output=ValueRef("advance")
            )
        },
        planner="bounded-loop",
        verifier="bounded-loop",
        plan_mode="dag",
        child_budget=1,
        max_steps=3,
        max_revisions=3,
        max_concurrency=1,
        max_depth=3,
    )


def create_engine(db_path, client):
    nodes = NodeExecutorRegistry()
    nodes.register(
        NodeExecutorSpec(
            "advance",
            "Advance one approved iteration",
            effect="read_only",
            requires_approval=True,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        ),
        AdvanceNode(client),
    )
    loop = BoundedLoopPolicy("worker", max_iterations=3)
    store = SQLiteStore(db_path)
    try:
        return LocalEngine(
            store,
            providers={},
            tools=ToolRegistry(),
            workflow_executors=nodes,
            planners={"bounded-loop": loop},
            plan_verifiers={"bounded-loop": loop},
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


async def run_demo(db_path, client, command_id, *, pause_second_approval=False):
    before, _ = client.counts()
    with create_engine(db_path, client) as engine:
        handle = engine.submit(workflow(), TASK, command_id=command_id, budget=3)
        duplicate = engine.submit(workflow(), TASK, command_id=command_id, budget=3)
        for _ in range(4):
            done = await engine.drive(handle.run_id)
            if done.state == "succeeded":
                break
            if done.state != "waiting_approval":
                raise RuntimeError(f"Unexpected loop state: {done.state}: {done.error}")
            requests, receipts = client.counts()
            if pause_second_approval and requests == 1:
                return {
                    "run_id": handle.run_id,
                    "state": done.state,
                    "pending": child_pending(engine, handle.run_id),
                    "requests_total": requests,
                    "receipts_total": receipts,
                }
            items = child_pending(engine, handle.run_id)
            if len(items) != 1:
                raise RuntimeError("Expected one original iteration awaiting approval")
            pending = items[0]
            options = {"command_id": command_id + ":approve:" + pending["action_id"]}
            approved = engine.approve(
                pending["child_run_id"], pending["action_id"], pending["digest"], **options
            )
            assert (
                engine.approve(
                    pending["child_run_id"], pending["action_id"], pending["digest"], **options
                )
                == approved
            )
        if done.state != "succeeded":
            raise RuntimeError("Loop did not complete within its bounded approval rounds")
        spent = engine.diagnostics(handle.run_id).budget["spent"]

    # Reopen the original authority; an equal command finds the original Run.
    with create_engine(db_path, client) as engine:
        replay = engine.submit(workflow(), TASK, command_id=command_id, budget=3)
        final = await engine.drive(replay.run_id)
        assert final.state == "succeeded" and final.result == done.result
        replayed = 0
        for child in engine.diagnostics(handle.run_id).workflow["children"]:
            action = engine.status(child["run_id"]).actions[0]
            options = {"command_id": command_id + ":approve:" + action["id"]}
            receipt = engine.approve(child["run_id"], action["id"], action["digest"], **options)
            assert receipt == engine.approve(
                child["run_id"], action["id"], action["digest"], **options
            )
            replayed += 1
    requests, receipts = client.counts()
    return {
        "run_id": handle.run_id,
        "state": final.state,
        "result": final.result,
        "spent": spent,
        "receipt_replay_matches": handle == duplicate == replay and replayed == 3,
        "requests_this_process": requests - before,
        "requests_total": requests,
        "receipts_total": receipts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", help="Execution SQLite; independent audit uses PATH.business.sqlite"
    )
    parser.add_argument("--command-id", default="bounded-loop-demo")
    parser.add_argument("--pause-second-approval", action="store_true")
    args = parser.parse_args()

    def run(path):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        client = ReceiptLedger(str(path) + ".business.sqlite")
        try:
            result = asyncio.run(
                run_demo(
                    path, client, args.command_id, pause_second_approval=args.pause_second_approval
                )
            )
        finally:
            client.close()
        print(json.dumps(result, sort_keys=True))

    if args.db:
        run(args.db)
    else:
        with TemporaryDirectory(prefix="relf-bounded-loop-") as directory:
            run(Path(directory) / "runs.sqlite")


if __name__ == "__main__":
    # Keep the same import identity in first execution and later cold recovery.
    from bounded_loop_workflow import main as run_example

    run_example()
