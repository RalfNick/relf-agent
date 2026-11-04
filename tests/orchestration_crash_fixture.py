"""Local real-process proposal/child durability windows; counters are test probes."""

from .orchestration_crash_probe import probe  # isort: skip

import argparse
import asyncio
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

from relf_agent import (
    AgentSpec,
    DAGNode,
    DAGProposal,
    DynamicWorkflowSpec,
    LocalEngine,
    ModelResponse,
    PlanProposal,
    PlanStep,
    SQLiteStore,
    TeamSpec,
    ToolRegistry,
    ValueRef,
)

probe.mark("imports_ready")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("--crash")
    parser.add_argument("--run-id")
    parser.add_argument("--dag", action="store_true")
    parser.add_argument("--nested", action="store_true")
    args = parser.parse_args()
    counter = Path(args.database).with_suffix(".counter.sqlite")

    def count(kind):
        with closing(sqlite3.connect(counter)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS counts(kind TEXT)")
            conn.execute("INSERT INTO counts VALUES (?)", (kind,))

    class Provider:
        identity = {"kind": "crash-counted", "version": "1"}

        async def complete(self, messages, tools):
            count("model")
            return ModelResponse(output="done")

    class Planner:
        identity = {"kind": "crash-planner", "version": "1"}

        async def plan(self, request, caller):
            count("plan")
            if args.dag:
                return DAGProposal(
                    [
                        DAGNode("work", "one"),
                        DAGNode("finish", "two", depends_on=("work",), input=ValueRef("work")),
                    ],
                    output=ValueRef("finish"),
                )
            return PlanProposal([PlanStep("work", "one", "task")])

    class Store(SQLiteStore):
        def __init__(self, *args, **kwargs):
            probe.mark("store_init_begin")
            super().__init__(*args, **kwargs)
            probe.mark("store_init_end")

        @contextmanager
        def transaction(self):
            with super().transaction():
                yield
            if (
                args.crash
                and not self.conn.in_transaction
                and self.conn.execute("SELECT 1 FROM events WHERE kind=?", (args.crash,)).fetchone()
            ):
                probe.mark("crash_committed", event_kind=args.crash)
                os._exit(77)

    store = Store(args.database)
    probe.mark("engine_init_begin")
    with LocalEngine(
        store,
        providers={"default": Provider()},
        tools=ToolRegistry(),
        planners={"counted": Planner()},
    ) as e:
        probe.mark("engine_ready")
        run_id = args.run_id
        if run_id is None:
            members = {"one": AgentSpec("one", "One")}
            if args.dag:
                members["two"] = AgentSpec("two", "Two")
            if args.nested:
                members["one"] = TeamSpec(
                    "inner", {"leaf": AgentSpec("leaf", "Leaf")}, child_budget=2
                )
            probe.mark("submit_begin")
            run_id = e.submit(
                DynamicWorkflowSpec(
                    "crash",
                    members,
                    planner="counted",
                    child_budget=4,
                    plan_mode="dag" if args.dag else "flat",
                ),
                "task",
                command_id="s",
                budget=8,
            ).run_id
            probe.mark("submit_end")
        print(json.dumps({"run_id": run_id}), flush=True)
        probe.mark("run_id_flushed")
        probe.mark("drive_begin")
        result = asyncio.run(e.drive(run_id))
        probe.mark("drive_end")
        print(json.dumps(asdict(result)), flush=True)
    probe.mark("engine_closed")


if __name__ == "__main__":
    main()
