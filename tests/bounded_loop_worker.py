"""Independent business evidence; loop execution remains with original Engines."""

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

    def append(self, kind, input, result=None, effect_key=None):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO calls(kind,effect_key,input,result) VALUES (?,?,?,?)",
                (kind, effect_key, json.dumps(input), json.dumps(result)),
            )
            if effect_key is not None:
                db.execute(
                    "INSERT OR IGNORE INTO effects VALUES (?,?)", (effect_key, json.dumps(result))
                )
                stored = db.execute(
                    "SELECT result FROM effects WHERE effect_key=?", (effect_key,)
                ).fetchone()
                assert json.loads(stored[0]) == result

    def receipt(self, effect_key):
        with closing(sqlite3.connect(self.path)) as db:
            stored = db.execute(
                "SELECT result FROM effects WHERE effect_key=?", (effect_key,)
            ).fetchone()
            return None if stored is None else json.loads(stored[0])

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
    def __init__(self, ledger, mode="normal"):
        self.ledger, self.mode = ledger, mode
        self.query_enabled = False

    @property
    def identity(self):
        return {
            "kind": "bounded-loop-business",
            "version": "1",
            "ledger": str(self.ledger.path),
            "mode": self.mode,
        }

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        previous = input["previous"]
        value = (0 if previous is None else previous["value"]) + 1
        result = {
            "done": value >= input["task"]["target"],
            "value": value,
            "iteration": input["iteration"],
        }
        self.ledger.append("work", input, result, context.effect_key)
        if self.mode == "unknown" and input["iteration"] == 2:
            raise ConnectionError("Committed business receipt was not delivered")
        return result

    async def reconcile(self, input, config, context):
        await asyncio.sleep(0)
        self.ledger.append("query", input)
        if not self.query_enabled:
            return None
        result = self.ledger.receipt(context.effect_key)
        return (
            None
            if result is None
            else r.EffectObservation(result, "original-loop-business-receipt")
        )


class CountedPolicy:
    """Test audit around the pure policy; the SDK policy itself does no I/O."""

    def __init__(self, ledger, max_iterations=3):
        assert hasattr(r, "BoundedLoopPolicy"), "Bounded-loop policy is not exported yet"
        self.ledger = ledger
        self.delegate = r.BoundedLoopPolicy("worker", max_iterations=max_iterations)

    @property
    def identity(self):
        return {
            "kind": "counted-bounded-loop",
            "version": "1",
            "policy": self.delegate.identity,
            "ledger": str(self.ledger.path),
        }

    async def plan(self, request, caller):
        self.ledger.append("plan", request.to_dict())
        return await self.delegate.plan(request, caller)

    def verify(self, request):
        result = self.delegate.verify(request)
        self.ledger.append("verify", request.to_dict(), result.to_dict())
        return result


def registry(worker, *, approval=False, effect="read_only"):
    nodes = r.NodeExecutorRegistry()
    nodes.register(
        r.NodeExecutorSpec(
            "advance",
            "Advance one adopted iteration",
            effect=effect,
            requires_approval=approval,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        ),
        worker,
    )
    return nodes


def definition(*, max_revisions=3, max_steps=3):
    return r.DynamicWorkflowSpec(
        "bounded-loop",
        {
            "worker": r.GraphWorkflowSpec(
                "advance",
                [r.GraphNode("advance", executor="advance")],
                output=r.ValueRef("advance"),
            )
        },
        planner="bounded-loop",
        verifier="bounded-loop",
        plan_mode="dag",
        child_budget=1,
        max_revisions=max_revisions,
        max_steps=max_steps,
        max_concurrency=1,
        max_depth=3,
    )


def local_engine(
    root, *, approval=False, mode="normal", worker=None, max_iterations=3, store=None, policy=None
):
    ledger = Ledger(root)
    worker = worker or BusinessNode(ledger, mode)
    loop = CountedPolicy(ledger, max_iterations)
    store = store or r.SQLiteStore(Path(root) / "run.sqlite")
    try:
        engine = r.LocalEngine(
            store,
            providers={},
            tools=r.ToolRegistry(),
            workflow_executors=registry(
                worker,
                approval=approval,
                effect="queryable_write" if mode == "unknown" else "read_only",
            ),
            planners={"bounded-loop": loop},
            plan_verifiers={"bounded-loop": loop},
            policy=policy,
        )
    except BaseException:
        store.close()
        raise
    return engine, ledger, worker


class CutStore(r.SQLiteStore):
    def __init__(self, root, window):
        self.root, self.window, self.root_id, self.pending = Path(root), window, None, None
        super().__init__(self.root / "run.sqlite")

    def emit(self, run_id, kind, data=None):
        super().emit(run_id, kind, data)
        if self.window and run_id == self.root_id and kind == self.window:
            revision = self.run(run_id)["orchestration"]["revision"]
            if revision == (0 if kind == "plan_verified" else 1):
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


def temporal_runtime(root, *, approval=False):
    from relf_agent.temporal_activities import TemporalRuntime

    ledger = Ledger(root)
    loop = CountedPolicy(ledger)
    return TemporalRuntime(
        providers={},
        tools=r.ToolRegistry(),
        workflow_executors=registry(BusinessNode(ledger), approval=approval),
        planners={"bounded-loop": loop},
        plan_verifiers={"bounded-loop": loop},
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
            task_queue=os.environ["RELF_BOUNDED_LOOP_QUEUE"],
            runtime=runtime,
            release=runtime.orchestration_release,
        ):
            (root / ("ready-" + label + ".json")).write_text(
                json.dumps({"package": r.__file__, "release": runtime.orchestration_release})
            )
            try:
                while not (root / ("stop-" + label)).exists():  # noqa: ASYNC110 -- parent owns marker
                    await asyncio.sleep(0.02)
            finally:
                await close_temporal_runtime(runtime)
        (root / ("closed-" + label)).touch()
    finally:
        await close_temporal_runtime(runtime)


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
    with local_engine(args.root, store=CutStore(args.root, args.window))[0] as engine:
        handle = engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
        assert args.run_id is None or args.run_id == handle.run_id
        engine.store.root_id = handle.run_id
        print(json.dumps({"run_id": handle.run_id}), flush=True)
        done = asyncio.run(engine.drive(handle.run_id))
        print(json.dumps({"state": done.state, "result": done.result}), flush=True)


if __name__ == "__main__":
    from tests.bounded_loop_worker import main as imported_main

    imported_main()
