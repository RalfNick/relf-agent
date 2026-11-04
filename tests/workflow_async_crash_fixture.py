"""Actual process-death windows against one original Run and a local service DB."""

import asyncio
import json
import os
import sqlite3
import sys
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

import relf_agent as r
from relf_agent.types import canonical


class CrashStore(r.SQLiteStore):
    def __init__(self, root, phase, window):
        self.root, self.phase, self.window = root, phase, window
        self.pending_crash = None
        super().__init__(root / "run.sqlite")

    @contextmanager
    def transaction(self):
        outer = not self.conn.in_transaction
        with super().transaction():
            yield
        if outer and self.pending_crash is not None:
            run_id, event = self.pending_crash
            self.pending_crash = None
            self.die(run_id, event)

    def emit(self, run_id, kind, data=None):
        super().emit(run_id, kind, data)
        event = {
            "intent": "tool_dispatch_intent",
            "receipt": "tool_receipt_recorded",
            "action": "tool_result_committed",
        }.get(self.window)
        if self.phase == "crash" and kind == event:
            self.pending_crash = (run_id, kind)

    def die(self, run_id, event):
        # The service uses another connection. The Run read is after its outer
        # transaction committed; an independent reader in the test verifies it.
        assert not self.conn.in_transaction
        (self.root / "crash.json").write_text(
            canonical(
                {
                    "event": event,
                    "run": self.run(run_id),
                    "budget": self.budget(run_id),
                }
            )
        )
        os._exit(77)


class LocalService:
    identity = {"kind": "async-crash-service", "version": "1"}

    def __init__(self, store, effect):
        self.store, self.effect = store, effect
        self.path = store.root / "service.sqlite"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls "
                "(seq INTEGER PRIMARY KEY, kind TEXT, effect_key TEXT, attempt_id TEXT, "
                "input TEXT, config TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS effects "
                "(effect_key TEXT PRIMARY KEY, result TEXT NOT NULL, config TEXT NOT NULL)"
            )

    def call(self, db, kind, input, config, context):
        db.execute(
            "INSERT INTO calls(kind,effect_key,attempt_id,input,config) VALUES (?,?,?,?,?)",
            (kind, context.effect_key, context.attempt_id, canonical(input), canonical(config)),
        )

    async def execute(self, input, config, context):
        await asyncio.sleep(0)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.call(db, "execute", input, config, context)
            # read_only records only a service access audit. Write categories
            # have a unique effect key so a retry can be counted independently
            # from the one external business effect.
            if self.effect != "read_only":
                db.execute(
                    "INSERT OR IGNORE INTO effects VALUES (?,?,?)",
                    (context.effect_key, canonical(input), canonical(config)),
                )
                row = db.execute(
                    "SELECT result,config FROM effects WHERE effect_key=?", (context.effect_key,)
                ).fetchone()
                assert row == (canonical(input), canonical(config))
        if self.store.phase == "crash" and self.store.window == "external":
            self.store.die(context.run_id, "external_commit")
        return input


class QueryableService(LocalService):
    async def reconcile(self, input, config, context):
        await asyncio.sleep(0)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.call(db, "reconcile", input, config, context)
            row = db.execute(
                "SELECT result,config FROM effects WHERE effect_key=?", (context.effect_key,)
            ).fetchone()
        if row is None:
            return None
        assert row[1] == canonical(config)
        return r.EffectObservation(json.loads(row[0]), "service-receipt")


async def exercise(root, phase, window, effect, parallel, query, value):
    store = CrashStore(root, phase, window)
    component = (QueryableService if query else LocalService)(store, effect)
    nodes = r.NodeExecutorRegistry()
    nodes.register(
        r.NodeExecutorSpec(
            "write", "Crash-tested service", effect=effect, requires_approval=True, cost=2
        ),
        component,
    )
    spec = r.GraphWorkflowSpec(
        "async-recovery",
        [r.GraphNode("write", executor="write", config={"mode": "fixed", "version": 1})],
        output=r.ValueRef("write"),
        max_concurrency=2 if parallel else 1,
    )
    runtime = r.LocalEngine(store, providers={}, tools=r.ToolRegistry(), workflow_executors=nodes)
    try:
        handle = runtime.submit(spec, value, command_id="submit", budget=12)
        assert runtime.submit(spec, value, command_id="submit", budget=12) == handle
        if phase == "crash":
            paused = await runtime.drive(handle.run_id)
            assert paused.state == "waiting_approval"
            action = store.run(handle.run_id)["actions"][0]
            approved = runtime.approve(
                handle.run_id, action["id"], action["digest"], command_id="approve"
            )
            refs = {
                "handle": asdict(handle),
                "approval": asdict(approved),
                "action_id": action["id"],
                "action_digest": action["digest"],
            }
            (root / "refs.json").write_text(canonical(refs))
        else:
            refs = json.loads((root / "refs.json").read_text())
            assert asdict(handle) == refs["handle"]
        assert (
            asdict(
                runtime.approve(
                    handle.run_id, refs["action_id"], refs["action_digest"], command_id="approve"
                )
            )
            == refs["approval"]
        )
        result = await runtime.drive(handle.run_id)
        if phase == "crash":
            raise AssertionError(f"The {window} process-death window did not execute: {result}")
        if phase == "confirm":
            assert result.state == "waiting_reconciliation" and value is None
            receipt = runtime.reconcile(
                handle.run_id, refs["action_id"], None, command_id="confirm-null"
            )
            assert (
                runtime.reconcile(handle.run_id, refs["action_id"], None, command_id="confirm-null")
                == receipt
            )
            (root / "confirmation.json").write_text(canonical(asdict(receipt)))
            result = await runtime.drive(handle.run_id)
        # A second drive must neither redispatch a finished effect nor turn
        # missing evidence for a queryable/unqueryable write into a blind retry.
        repeated = await runtime.drive(handle.run_id)
        assert repeated.state == result.state and repeated.result == result.result
        if phase == "verify-confirmation":
            assert asdict(
                runtime.reconcile(handle.run_id, refs["action_id"], None, command_id="confirm-null")
            ) == json.loads((root / "confirmation.json").read_text())
        print(canonical({"state": result.state, "result": result.result, "run_id": handle.run_id}))
    finally:
        runtime.close()


if __name__ == "__main__":
    root, phase, window, effect, parallel, query, value = sys.argv[1:]
    asyncio.run(
        exercise(
            Path(root),
            phase,
            window,
            effect,
            parallel == "parallel",
            query == "query",
            json.loads(value),
        )
    )
