"""Real Workflow-node business peer; no model or orchestration authority."""

import asyncio
import copy
import json
import os
from pathlib import Path

import relf_agent as r
from relf_agent.temporal import build_temporal_worker
from relf_agent.temporal_activities import TemporalRuntime
from relf_agent.types import canonical


def audit(root, kind, **value):
    with (root / "calls.jsonl").open("a") as stream:
        stream.write(json.dumps({"kind": kind, "pid": os.getpid(), **value}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class BusinessNode:
    def __init__(self, root, mode, dsn=None):
        self.root, self.mode, self.dsn = root, mode, dsn

    @property
    def identity(self):
        return {
            "kind": "actual-workflow-node-fixture",
            "version": "1",
            "root": str(self.root),
            "mode": self.mode,
        }

    async def execute(self, input, config, context):
        audit(
            self.root,
            "execute",
            effect_key=context.effect_key,
            action_id=context.action_id,
            input=input,
            config=config,
        )
        if config.get("barrier"):
            (self.root / ("entered-" + config["slot"])).touch()
            while len(list(self.root.glob("entered-*"))) < 2:  # noqa: ASYNC110 -- actual peer entry
                await asyncio.sleep(0.02)
        if self.mode == "hold":
            (self.root / "handler-started").touch()
            while not (self.root / "release-handler").exists():  # noqa: ASYNC110 -- external fixture fence
                try:
                    await asyncio.sleep(0.02)
                except asyncio.CancelledError:
                    audit(self.root, "cancel-observed", effect_key=context.effect_key)
        result = copy.deepcopy(input)
        if self.dsn is not None:
            from psycopg import AsyncConnection

            connection = await AsyncConnection.connect(self.dsn, autocommit=True)
            try:
                await connection.execute(
                    "INSERT INTO node_service_effects(effect_key,result,writes) VALUES (%s,%s,1) "
                    "ON CONFLICT(effect_key) DO UPDATE SET writes=node_service_effects.writes+1",
                    (context.effect_key, canonical(result)),
                )
            finally:
                await connection.close()
            (self.root / "effect-committed").touch()
            if self.mode == "commit-crash" and not (self.root / "cut-done").exists():
                audit(self.root, "cut", window="external-commit-without-end")
                (self.root / "cut-done").write_text("external-commit-without-end")
                os._exit(77)
            if self.mode == "unknown":
                raise ConnectionError("Synthetic business reply lost after actual commit")
        audit(self.root, "ended", effect_key=context.effect_key)
        if self.mode == "hold":
            (self.root / "handler-ended").touch()
        return result

    async def reconcile(self, input, config, context):
        audit(self.root, "query", effect_key=context.effect_key)
        if self.dsn is None:
            return None
        from psycopg import AsyncConnection

        connection = await AsyncConnection.connect(self.dsn, autocommit=True)
        try:
            cursor = await connection.execute(
                "SELECT result FROM node_service_effects WHERE effect_key=%s", (context.effect_key,)
            )
            row = await cursor.fetchone()
            return (
                None
                if row is None
                else r.EffectObservation(json.loads(row[0]), "actual-pg-node-ledger")
            )
        finally:
            await connection.close()


class MixedProvider:
    identity = {"kind": "node-mixed-offline-provider", "version": "1"}

    def __init__(self, root):
        self.root = root

    async def complete(self, messages, tools):
        audit(self.root, "model")
        return r.ModelResponse({"agent": True})


class ReceiptCutRuntime(TemporalRuntime):
    """Crash strictly after the original Runtime returned and end ACK drained."""

    async def execute_tool(self, request, **options):
        response = await super().execute_tool(request, **options)
        root = self.fixture_root
        if response.get("ok") and not (root / "cut-done").exists():
            # The original physical owner and History end callbacks remain real.
            # This fence must not fabricate proof for a still-running handler.
            assert await self.wait_context_executions(wait_timeout=10)
            audit(
                root,
                "cut",
                window="received-and-actual-end-before-activity-reply",
                owner_drained=True,
            )
            (root / "cut-done").write_text("received-and-actual-end-before-activity-reply")
            os._exit(77)
        return response


async def make_runtime(root, mode, *, dsn=None):
    journal = None
    if dsn is not None:
        from relf_agent.temporal_journal import PostgresEffectJournal

        journal = await PostgresEffectJournal.connect(dsn, backend_id="node-service:" + root.name)
        try:
            await journal.initialize()
            await journal.connection.execute(
                "CREATE TABLE IF NOT EXISTS node_service_effects "
                "(effect_key TEXT PRIMARY KEY,result TEXT NOT NULL,writes INTEGER NOT NULL)"
            )
        except BaseException:
            await journal.aclose()
            raise
    component, registry = BusinessNode(root, mode, dsn), r.NodeExecutorRegistry()
    registry.register(
        r.NodeExecutorSpec(
            "step",
            "Actual service node",
            effect="queryable_write" if dsn is not None else "read_only",
            requires_approval=mode
            in {"approval", "unknown", "invalid-write", "commit-crash", "receipt-crash"},
            output_schema={"type": "integer"} if mode == "invalid-write" else None,
        ),
        component,
    )
    owner = r.ToolExecutionOwner(version="node-service-1", max_calls=8)
    try:
        cls = ReceiptCutRuntime if mode == "receipt-crash" else TemporalRuntime
        runtime = cls(
            providers={"default": MixedProvider(root)} if mode == "mixed" else {},
            tools=r.ToolRegistry(),
            workflow_executors=registry,
            tool_execution=owner,
            journal=journal,
        )
        if mode == "receipt-crash":
            runtime.fixture_root = root
        return runtime
    except BaseException:
        await owner.aclose()
        if journal is not None:
            await journal.aclose()
        raise


async def close_runtime(runtime):
    await runtime.close_context_execution(wait_timeout=10)
    await runtime.tool_execution.aclose(wait_timeout=10)
    if runtime.journal is not None:
        await runtime.journal.aclose()


async def worker_main(root, mode, label):
    from temporalio.client import Client

    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    runtime = await make_runtime(root, mode, dsn=os.environ.get("RALF_NODE_SERVICE_DSN"))
    try:
        async with build_temporal_worker(
            client,
            task_queue=os.environ["RALF_NODE_SERVICE_QUEUE"],
            runtime=runtime,
            release=runtime.orchestration_release,
        ):
            (root / ("ready-" + label + ".json")).write_text(
                json.dumps({"package": r.__file__, "release": runtime.orchestration_release})
            )
            try:
                while not (root / ("stop-" + label)).exists():  # noqa: ASYNC110 -- parent owns stop marker
                    await asyncio.sleep(0.02)
            finally:
                await close_runtime(runtime)
        (root / ("closed-" + label)).touch()
    finally:
        if runtime.journal is not None and not runtime.journal.connection.closed:
            await runtime.journal.aclose()


if __name__ == "__main__":
    # Preserve the exact fixture identity in controller and independent Worker.
    from tests.temporal_workflow_nodes_worker import worker_main as imported_main

    asyncio.run(
        imported_main(
            Path(os.environ["RALF_NODE_SERVICE_ROOT"]),
            os.environ["RALF_NODE_SERVICE_MODE"],
            os.environ["RALF_NODE_SERVICE_LABEL"],
        )
    )
