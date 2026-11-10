"""Independent SQLite business evidence for fan-out execution and process cuts."""

import argparse
import asyncio
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

import relf_agent as r


class Ledger:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "business.sqlite"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls (seq INTEGER PRIMARY KEY,kind TEXT,"
                "effect_key TEXT,input TEXT,result TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS effects (effect_key TEXT PRIMARY KEY,result TEXT)"
            )

    def planning(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO calls(kind) VALUES ('plan')")

    def record(self, kind, value, result, context):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO calls(kind,effect_key,input,result) VALUES (?,?,?,?)",
                (kind, context.effect_key, json.dumps(value), json.dumps(result)),
            )
            db.execute(
                "INSERT OR IGNORE INTO effects VALUES (?,?)",
                (context.effect_key, json.dumps(result)),
            )
            row = db.execute(
                "SELECT result FROM effects WHERE effect_key=?", (context.effect_key,)
            ).fetchone()
            assert json.loads(row[0]) == result
            return result

    def receipt(self, effect_key):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT result FROM effects WHERE effect_key=?", (effect_key,)
            ).fetchone()
            return None if row is None else json.loads(row[0])

    def rows(self, kind=None):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM calls" + (" WHERE kind=?" if kind else "") + " ORDER BY seq",
                    (kind,) if kind else (),
                )
            ]


class BusinessNode:
    def __init__(self, ledger, kind="map", mode="normal"):
        self.ledger, self.kind, self.mode = ledger, kind, mode
        self.query_enabled = False

    @property
    def identity(self):
        return {
            "kind": "fan-out-business-node",
            "version": "1",
            "ledger": str(self.ledger.path),
            "operation": self.kind,
            "mode": self.mode,
        }

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        result = (
            input * input
            if self.kind == "map"
            else {"keys": list(input), "values": list(input.values()), "total": sum(input.values())}
        )
        result = self.ledger.record(self.kind, input, result, context)
        if self.mode == "unknown" and self.kind == "map" and input == 2:
            raise ConnectionError("Independent business receipt lost")
        return result

    async def reconcile(self, input, config, context):
        await asyncio.sleep(0)
        if not self.query_enabled:
            return None
        result = self.ledger.receipt(context.effect_key)
        return None if result is None else r.EffectObservation(result, "fan-out-business-ledger")


class CountedPlanner:
    def __init__(self, ledger, *, reducer=True):
        from relf_agent.fan_out_planning import FanOutDAGPlanner

        self.ledger = ledger
        self.delegate = FanOutDAGPlanner("worker", reducer="sum" if reducer else None)

    @property
    def identity(self):
        return {
            "kind": "counted-fan-out",
            "version": "1",
            "planner": self.delegate.identity,
            "ledger": str(self.ledger.path),
        }

    async def plan(self, request, caller):
        self.ledger.planning()
        return await self.delegate.plan(request, caller)


def registry(worker, reducer, *, approval=False, effect="read_only"):
    nodes = r.NodeExecutorRegistry()
    nodes.register(
        r.NodeExecutorSpec(
            "square",
            "Square an item",
            effect=effect,
            requires_approval=approval,
            input_schema={"type": "integer"},
            output_schema={"type": "integer"},
        ),
        worker,
    )
    nodes.register(
        r.NodeExecutorSpec(
            "sum",
            "Sum adopted worker results",
            effect="read_only",
            input_schema={"type": "object"},
        ),
        reducer,
    )
    return nodes


def definition(*, reducer=True, concurrency=2):
    members = {
        "worker": r.GraphWorkflowSpec(
            "square", [r.GraphNode("square", executor="square")], output=r.ValueRef("square")
        )
    }
    if reducer:
        members["sum"] = r.GraphWorkflowSpec(
            "sum", [r.GraphNode("sum", executor="sum")], output=r.ValueRef("sum")
        )
    return r.DynamicWorkflowSpec(
        "bounded-batch",
        members,
        planner="fan-out",
        plan_mode="dag",
        child_budget=1,
        max_steps=8,
        max_revisions=1,
        max_concurrency=concurrency,
        max_depth=3,
    )


def local_engine(
    root, *, reducer=True, approval=False, mode="normal", worker=None, store=None, policy=None
):
    ledger = Ledger(root)
    worker = worker or BusinessNode(ledger, mode=mode)
    reduced = BusinessNode(ledger, "reduce")
    engine = r.LocalEngine(
        store or r.SQLiteStore(Path(root) / "run.sqlite"),
        providers={},
        tools=r.ToolRegistry(),
        workflow_executors=registry(
            worker,
            reduced,
            approval=approval,
            effect="queryable_write" if mode == "unknown" else "read_only",
        ),
        planners={"fan-out": CountedPlanner(ledger, reducer=reducer)},
        policy=policy,
    )
    return engine, ledger, worker


class CutStore(r.SQLiteStore):
    def __init__(self, root, window):
        self.root, self.window, self.root_id, self.pending = Path(root), window, None, None
        super().__init__(self.root / "run.sqlite")

    def emit(self, run_id, kind, data=None):
        super().emit(run_id, kind, data)
        if self.window and run_id == self.root_id and kind == self.window:
            self.pending = kind

    @contextmanager
    def transaction(self):
        outer = not self.conn.in_transaction
        with super().transaction():
            yield
        if outer and self.pending:
            assert not self.conn.in_transaction
            (self.root / "cut.json").write_text(
                json.dumps(
                    {
                        "window": self.pending,
                        "run": self.run(self.root_id),
                        "budget": self.budget(self.root_id),
                    }
                )
            )
            os._exit(77)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--window")
    parser.add_argument("--run-id")
    parser.add_argument("--temporal", action="store_true")
    parser.add_argument("--approval", action="store_true")
    parser.add_argument("--label", default="initial")
    args = parser.parse_args()
    if args.temporal:
        asyncio.run(temporal_worker(args.root, args.approval, args.label))
        return
    store = CutStore(args.root, args.window)
    with local_engine(args.root, store=store)[0] as engine:
        handle = engine.submit(definition(concurrency=1), [3, 1, 2], command_id="same", budget=4)
        assert args.run_id is None or args.run_id == handle.run_id
        store.root_id = handle.run_id
        print(json.dumps({"run_id": handle.run_id}), flush=True)
        result = asyncio.run(engine.drive(handle.run_id))
        print(json.dumps({"state": result.state, "result": result.result}), flush=True)


def temporal_runtime(root, *, approval=False):
    from relf_agent.temporal_activities import TemporalRuntime

    ledger = Ledger(root)
    return TemporalRuntime(
        providers={},
        tools=r.ToolRegistry(),
        workflow_executors=registry(
            BusinessNode(ledger), BusinessNode(ledger, "reduce"), approval=approval
        ),
        planners={"fan-out": CountedPlanner(ledger)},
    )


async def close_temporal_runtime(runtime):
    await runtime.close_context_execution(wait_timeout=10)
    await runtime.tool_execution.aclose(wait_timeout=10)


async def temporal_worker(root, approval, label):
    from temporalio.client import Client

    from relf_agent.temporal import build_temporal_worker

    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    runtime = temporal_runtime(root, approval=approval)
    try:
        async with build_temporal_worker(
            client,
            task_queue=os.environ["RELF_FAN_OUT_QUEUE"],
            runtime=runtime,
            release=runtime.orchestration_release,
        ):
            (root / ("ready-" + label + ".json")).write_text(
                json.dumps(
                    {
                        "package": r.__file__,
                        "release": runtime.orchestration_release,
                    }
                )
            )
            try:
                while not (root / ("stop-" + label)).exists():  # noqa: ASYNC110 -- parent owns marker
                    await asyncio.sleep(0.02)
            finally:
                await close_temporal_runtime(runtime)
        (root / ("closed-" + label)).touch()
    finally:
        await close_temporal_runtime(runtime)


if __name__ == "__main__":
    from tests.fan_out_worker import main as imported_main

    imported_main()
