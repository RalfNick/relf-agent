"""Actual Service/Worker evidence for managed nodes, never mock quality claims."""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

import relf_agent as r
from relf_agent.errors import CloseIncomplete
from relf_agent.temporal import TemporalEngine, build_temporal_worker, replay_temporal_history
from relf_agent.types import canonical

from .temporal_workflow_nodes_worker import close_runtime, make_runtime
from .test_temporal_scoped_capacity_service import discover_owned_descendants

pytestmark = pytest.mark.skipif(
    not os.getenv("RALF_TEST_TEMPORAL_ADDRESS"), reason="requires actual owned Temporal Service"
)


def calls(root):
    path = root / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


async def until(operation, predicate):
    async with asyncio.timeout(30):
        while True:
            value = await operation()
            if predicate(value):
                return value
            await asyncio.sleep(0.02)


async def adopted_result(engine, run_id):
    # The child control receipt accepts the command. Its parent observes and
    # adopts the actual result asynchronously through its original History.
    await engine.drive(run_id)
    return await until(
        lambda: engine.status(run_id), lambda s: s.state in {"succeeded", "failed", "cancelled"}
    )


class Workers:
    def __init__(self, client, queue, root, mode, release, dsn):
        self.client, self.queue, self.root, self.mode, self.release, self.dsn = (
            client,
            queue,
            root,
            mode,
            release,
            dsn,
        )
        self.processes = []

    async def start(self, label):
        environment = {
            key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ
        }
        environment.update(
            RALF_TEST_TEMPORAL_ADDRESS=os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
            RALF_TEST_TEMPORAL_NAMESPACE=self.client.namespace,
            RALF_NODE_SERVICE_QUEUE=self.queue,
            RALF_NODE_SERVICE_ROOT=str(self.root),
            RALF_NODE_SERVICE_MODE=self.mode,
            RALF_NODE_SERVICE_LABEL=label,
        )
        if self.dsn is not None:
            environment["RALF_NODE_SERVICE_DSN"] = self.dsn
        with (self.root / (label + ".log")).open("w") as stream:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-m",
                "tests.temporal_workflow_nodes_worker",
                env=environment,
                stdout=stream,
                stderr=stream,
            )
        self.processes.append((label, process))
        async with asyncio.timeout(20):
            while not (self.root / ("ready-" + label + ".json")).exists():  # noqa: ASYNC110 -- actual Worker readiness
                assert process.returncode is None, (self.root / (label + ".log")).read_text()
                await asyncio.sleep(0.02)
        ready = json.loads((self.root / ("ready-" + label + ".json")).read_text())
        assert ready["release"] == json.loads(canonical(self.release))
        assert ready["package"] == r.__file__
        return process

    async def kill(self, process):
        process.kill()
        await asyncio.wait_for(process.wait(), 10)

    async def close(self):
        for label, process in self.processes:
            if process.returncode is not None:
                continue
            (self.root / ("stop-" + label)).touch()
            try:
                assert await asyncio.wait_for(process.wait(), 15) == 0, (
                    self.root / (label + ".log")
                ).read_text()
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()


@asynccontextmanager
async def system(root, mode="read", *, subprocess_worker=False, writes=False):
    from temporalio.client import Client, WorkflowExecutionStatus
    from temporalio.service import RPCError, RPCStatusCode

    client = await Client.connect(
        os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
        namespace=os.environ.get("RALF_TEST_TEMPORAL_NAMESPACE", "default"),
    )
    (root / "actual-client.json").write_text(
        json.dumps({"namespace": client.namespace, "connected": True})
    )
    schema, admin, dsn = None, None, None
    if writes:
        if not os.getenv("RALF_TEST_POSTGRES_DSN"):
            pytest.skip("requires actual owned PostgreSQL EffectJournal")
        import psycopg
        from psycopg import sql

        schema = "node_service_" + uuid.uuid4().hex
        admin = await psycopg.AsyncConnection.connect(
            os.environ["RALF_TEST_POSTGRES_DSN"], autocommit=True
        )
        await admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        dsn = psycopg.conninfo.make_conninfo(
            os.environ["RALF_TEST_POSTGRES_DSN"], options="-csearch_path=" + schema
        )
    runtime, engine, worker, peers, owned = None, None, None, None, set()
    try:
        runtime = await make_runtime(root, mode, dsn=dsn)
        queue = "workflow-node-" + uuid.uuid4().hex
        engine = TemporalEngine(
            client,
            task_queue=queue,
            release=runtime.orchestration_release,
            scope=r.Scope("node-service", queue),
            activity_timeout=10,
            drive_timeout=30,
        )
        peers = Workers(client, queue, root, mode, runtime.orchestration_release, dsn)
        if subprocess_worker:
            await peers.start("initial")
        else:
            worker = build_temporal_worker(
                client, task_queue=queue, runtime=runtime, release=runtime.orchestration_release
            )
            await worker.__aenter__()
        yield engine, runtime, peers, owned
    except BaseException as failure:
        original_failure = failure
        raise
    finally:
        errors = []
        (root / "release-handler").touch()

        async def clean(operation):
            try:
                await operation
            except BaseException as failure:
                errors.append(failure)

        if peers is not None:
            await clean(peers.close())
        if runtime is not None:
            await clean(close_runtime(runtime))
        if worker is not None:
            await clean(worker.__aexit__(None, None, None))
        if engine is not None:
            owned.add(engine.command_registry_id)
            await clean(discover_owned_descendants(client, owned))
            for target in sorted(owned):
                try:
                    handle = client.get_workflow_handle(target)
                    if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                        await handle.terminate(reason="owned Workflow-node test cleanup")
                except RPCError as failure:
                    if failure.status != RPCStatusCode.NOT_FOUND:
                        errors.append(failure)
                except BaseException as failure:
                    errors.append(failure)
            await clean(engine.aclose())
        if admin is not None:
            # Retain schemas/effects as failure evidence; never drop on teardown.
            (root / "retained-schema.json").write_text(
                json.dumps({"schema": schema, "retained": True})
            )
            await clean(admin.close())
        (root / "cleanup.json").write_text(
            json.dumps(
                {
                    "owned_histories": sorted(owned),
                    "histories_terminated_for_test_cleanup": True,
                    "schema_retained": schema,
                    "cleanup_errors": [type(e).__name__ for e in errors],
                }
            )
        )
        if errors:
            original = locals().get("original_failure")
            raise BaseExceptionGroup(
                "Workflow-node test and owned cleanup failures",
                ([original] if original is not None else []) + errors,
            )


async def replay_all(engine, owned, root):
    from relf_agent.temporal_state import MODEL_ACTIVITY

    owned.add(engine.command_registry_id)
    await discover_owned_descendants(engine.client, owned)
    before = (root / "calls.jsonl").read_bytes() if (root / "calls.jsonl").exists() else b""
    scheduled_models = 0
    for index, target in enumerate(sorted(owned)):
        history = await engine.client.get_workflow_handle(target).fetch_history()
        scheduled_models += sum(
            event.HasField("activity_task_scheduled_event_attributes")
            and event.activity_task_scheduled_event_attributes.activity_type.name == MODEL_ACTIVITY
            for event in history.events
        )
        (root / ("history-" + str(index) + ".json")).write_text(history.to_json())
        await replay_temporal_history(history, namespace=engine.client.namespace)
    assert (
        (root / "calls.jsonl").read_bytes() if (root / "calls.jsonl").exists() else b""
    ) == before
    assert scheduled_models == sum(row["kind"] == "model" for row in calls(root))


def serial_graph():
    return r.GraphWorkflowSpec(
        "serial",
        [
            r.GraphNode("first", executor="step"),
            r.GraphNode(
                "second", executor="step", depends_on=("first",), input=r.ValueRef("first")
            ),
        ],
        output=r.ValueRef("second"),
    )


@pytest.mark.parametrize("kind", ["serial", "serial-null", "parallel", "team", "dynamic", "mixed"])
def test_actual_node_graphs_are_model_free_except_explicit_agent(tmp_path, kind):
    async def run():
        async with system(tmp_path, "mixed" if kind == "mixed" else "read") as (
            engine,
            _,
            _,
            owned,
        ):
            definition = serial_graph()
            value, expected, count = [1, None, {"x": False}], [1, None, {"x": False}], 2
            if kind == "serial-null":
                value = expected = None
            elif kind == "parallel":
                definition = r.GraphWorkflowSpec(
                    "parallel",
                    [
                        r.GraphNode(name, executor="step", config={"barrier": True, "slot": name})
                        for name in ["left", "right"]
                    ],
                    output=r.InputMap({name: r.ValueRef(name) for name in ["left", "right"]}),
                    max_concurrency=2,
                )
                expected = {"left": value, "right": value}
            elif kind in {"team", "dynamic"}:
                cls = r.TeamSpec if kind == "team" else r.DynamicWorkflowSpec
                definition = cls("nested", {"graph": definition}, child_budget=8)
                expected = (
                    {"task": value, "results": {}}
                    if kind == "team"
                    else {"task": value, "prior": []}
                )
            elif kind == "mixed":
                definition = r.GraphWorkflowSpec(
                    "mixed",
                    [
                        r.GraphNode("before", executor="step"),
                        r.GraphNode(
                            "agent",
                            agent=r.AgentSpec("agent", "Answer"),
                            depends_on=("before",),
                            input=r.ValueRef("before"),
                        ),
                        r.GraphNode(
                            "after",
                            executor="step",
                            depends_on=("agent",),
                            input=r.ValueRef("agent"),
                        ),
                    ],
                    output=r.ValueRef("after"),
                )
                expected, count = {"agent": True}, 3
            handle = await engine.submit(definition, value, command_id="submit", budget=24)
            owned.add(handle.run_id)
            done = await engine.drive(handle.run_id)
            assert done.state == "succeeded" and done.result == expected, done
            assert await engine.submit(definition, value, command_id="submit", budget=24) == handle
            info = await engine.diagnostics(handle.run_id)
            assert (
                info.budget["spent"] == count
                and info.budget["reserved"] == info.budget["unknown"] == 0
            )
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 2
            assert sum(row["kind"] == "model" for row in calls(tmp_path)) == int(kind == "mixed")
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


def test_actual_node_approval_survives_process_restart(tmp_path):
    async def run():
        async with system(tmp_path, "approval", subprocess_worker=True) as (
            engine,
            _,
            peers,
            owned,
        ):
            definition = r.GraphWorkflowSpec(
                "approved", [r.GraphNode("work", executor="step")], output=r.ValueRef("work")
            )
            handle = await engine.submit(definition, {"value": 7}, command_id="submit", budget=8)
            owned.add(handle.run_id)
            waiting = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state == "waiting_approval"
            )
            (pending,) = waiting.pending
            assert calls(tmp_path) == []
            await peers.kill(peers.processes[0][1])
            await peers.start("replacement")
            receipt = await engine.approve(
                pending["run_id"], pending["action_id"], pending["digest"], command_id="approve"
            )
            assert (
                await engine.approve(
                    pending["run_id"], pending["action_id"], pending["digest"], command_id="approve"
                )
                == receipt
            )
            done = await adopted_result(engine, handle.run_id)
            assert done.state == "succeeded" and done.result == {"value": 7}, done
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 1
            assert sum(row["kind"] == "model" for row in calls(tmp_path)) == 0
            action = (await engine.status(pending["run_id"])).actions[0]
            assert (
                action["id"] == pending["action_id"]
                and action["digest"] == pending["digest"]
                and len(action["attempts"]) == 1
            )
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


@pytest.mark.parametrize("mode", ["unknown", "invalid-write"])
def test_actual_node_write_receipts_remain_original_without_reexecution(tmp_path, mode):
    async def run():
        async with system(tmp_path, mode, writes=True) as (engine, runtime, _, owned):
            definition = r.GraphWorkflowSpec(
                "write", [r.GraphNode("work", executor="step")], output=r.ValueRef("work")
            )
            handle = await engine.submit(
                definition, {"actual": True}, command_id="submit", budget=8
            )
            owned.add(handle.run_id)
            waiting = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state == "waiting_approval"
            )
            (pending,) = waiting.pending
            await engine.approve(
                pending["run_id"], pending["action_id"], pending["digest"], command_id="approve"
            )
            state = "outcome_unknown" if mode == "unknown" else "failed"
            done = await until(
                lambda: engine.status(handle.run_id),
                lambda s: s.state in {state, "waiting_reconciliation", "failed"},
            )
            child = await engine.status(pending["run_id"])
            (action,) = [a for a in child.actions if a["kind"] == "tool"]
            key = action["effect_key"]
            if mode == "unknown":
                assert child.state == "waiting_reconciliation"
                receipt = await engine.reconcile(
                    pending["run_id"], action["id"], command_id="query", query=True
                )
                assert (
                    await engine.reconcile(
                        pending["run_id"], action["id"], command_id="query", query=True
                    )
                    == receipt
                )
                done = await adopted_result(engine, handle.run_id)
                assert done.state == "succeeded" and done.result == {"actual": True}, done
                assert sum(row["kind"] == "query" for row in calls(tmp_path)) == 1
            else:
                assert done.state == "failed"
                assert action["status"] == "completed" and action["result"] == {"actual": True}
                await engine.drive(handle.run_id)
                assert (await engine.status(pending["run_id"])).actions[0]["effect_key"] == key
            settled = await until(
                lambda: engine.diagnostics(handle.run_id), lambda info: info.workflow["quiescent"]
            )
            assert settled.budget["spent"] == 1
            assert settled.budget["reserved"] == settled.budget["unknown"] == 0
            cursor = await runtime.journal.connection.execute(
                "SELECT effect_key,writes FROM node_service_effects"
            )
            assert await cursor.fetchall() == [(key, 1)]
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 1
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


def test_actual_node_cancel_retains_live_handler_and_close_retries(tmp_path):
    async def run():
        async with system(tmp_path, "hold") as (engine, runtime, _, owned):
            definition = r.GraphWorkflowSpec(
                "hold", [r.GraphNode("work", executor="step")], output=r.ValueRef("work")
            )
            handle = await engine.submit(definition, None, command_id="submit", budget=8)
            owned.add(handle.run_id)

            async def entered():
                return (tmp_path / "handler-started").exists()

            await until(entered, bool)
            receipt = await engine.cancel(handle.run_id, command_id="cancel")
            assert await engine.cancel(handle.run_id, command_id="cancel") == receipt
            assert not (tmp_path / "handler-ended").exists()
            info = await engine.diagnostics(handle.run_id)
            assert (
                info.snapshot.state in {"cancelled", "cancelling"}
                and not info.workflow["quiescent"]
            )
            assert not await runtime.wait_context_executions(wait_timeout=0.02)
            with pytest.raises(CloseIncomplete):
                await runtime.close_context_execution(wait_timeout=0.02)
            (tmp_path / "release-handler").touch()
            assert await runtime.wait_context_executions(wait_timeout=10)
            await runtime.close_context_execution(wait_timeout=10)
            await runtime.close_context_execution(wait_timeout=10)
            assert (tmp_path / "handler-ended").exists()
            info = await until(
                lambda: engine.diagnostics(handle.run_id), lambda d: d.workflow["quiescent"]
            )
            assert info.snapshot.state == "cancelled" and info.snapshot.result is None
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 1
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


@pytest.mark.parametrize("mode", ["commit-crash", "receipt-crash"])
def test_actual_node_worker_crash_preserves_real_end_and_receipt_boundaries(tmp_path, mode):
    async def run():
        async with system(tmp_path, mode, subprocess_worker=True, writes=True) as (
            engine,
            runtime,
            peers,
            owned,
        ):
            definition = r.GraphWorkflowSpec(
                "crash", [r.GraphNode("work", executor="step")], output=r.ValueRef("work")
            )
            handle = await engine.submit(
                definition, {"committed": True}, command_id="submit", budget=8
            )
            owned.add(handle.run_id)
            waiting = await until(
                lambda: engine.status(handle.run_id), lambda s: s.state == "waiting_approval"
            )
            (pending,) = waiting.pending
            await engine.approve(
                pending["run_id"], pending["action_id"], pending["digest"], command_id="approve"
            )
            assert await asyncio.wait_for(peers.processes[0][1].wait(), 20) == 77
            assert (tmp_path / "effect-committed").exists() and (tmp_path / "cut-done").exists()
            await peers.start("replacement")
            child = await until(
                lambda: engine.status(pending["run_id"]),
                lambda s: s.state == "waiting_reconciliation",
            )
            (action,) = [a for a in child.actions if a["kind"] == "tool"]
            original_key = action["effect_key"]
            original_attempt = action["attempts"][0]["id"]
            assert len(action["attempts"]) == 1
            cut = next(row for row in calls(tmp_path) if row["kind"] == "cut")
            receipt = await engine.reconcile(
                pending["run_id"], action["id"], command_id="query", query=True
            )
            assert (
                await engine.reconcile(
                    pending["run_id"], action["id"], command_id="query", query=True
                )
                == receipt
            )
            if mode == "receipt-crash":
                assert cut["owner_drained"] is True
                done = await adopted_result(engine, handle.run_id)
                assert done.state == "succeeded" and done.result == {"committed": True}, done
                assert sum(row["kind"] == "query" for row in calls(tmp_path)) == 0
            else:
                # OS process death alone cannot create original History end ACK.
                # Query may confirm the effect, but must not clear actual-end debt.
                assert cut["window"] == "external-commit-without-end"
                info = await engine.diagnostics(pending["run_id"])
                assert not info.workflow["quiescent"]
                parent = await engine.diagnostics(handle.run_id)
                assert (
                    not parent.workflow["quiescent"]
                    and parent.budget["reserved"] + parent.budget["unknown"] > 0
                )
                assert sum(row["kind"] == "query" for row in calls(tmp_path)) == 1
                (tmp_path / "expected-retained-obligation.json").write_text(
                    json.dumps(
                        {
                            "root": handle.run_id,
                            "child": pending["run_id"],
                            "effect_key": original_key,
                            "actual_end_unconfirmed": True,
                            "effect_confirmed": True,
                        }
                    )
                )
            restored = next(
                a for a in (await engine.status(pending["run_id"])).actions if a["kind"] == "tool"
            )
            assert (
                restored["effect_key"] == original_key
                and restored["attempts"][0]["id"] == original_attempt
                and len(restored["attempts"]) == 1
            )
            cursor = await runtime.journal.connection.execute(
                "SELECT effect_key,writes FROM node_service_effects"
            )
            assert await cursor.fetchall() == [(original_key, 1)]
            assert sum(row["kind"] == "execute" for row in calls(tmp_path)) == 1
            await replay_all(engine, owned, tmp_path)

    asyncio.run(asyncio.wait_for(run(), 120))


def test_actual_installed_default_example_repeats_original_submission(tmp_path):
    async def run():
        from dataclasses import asdict

        from temporalio.client import Client, WorkflowExecutionStatus
        from temporalio.service import RPCError, RPCStatusCode

        from relf_agent.temporal_state import MODEL_ACTIVITY, TOOL_ACTIVITY
        from relf_agent.types import digest

        client = await Client.connect(os.environ["RALF_TEST_TEMPORAL_ADDRESS"])
        queue = "workflow-node-example-" + uuid.uuid4().hex
        # The example intentionally uses the SDK default Scope. Run it only in
        # an empty owned scope; never terminate a user's existing default tree.
        scoped = asdict(r.Scope())
        owned = {
            "ralf-temporal-commands-" + digest(scoped),
            "ralf-temporal-" + digest([scoped, "same"]),
        }
        for target in owned:
            try:
                await client.get_workflow_handle(target).describe()
            except RPCError as error:
                if error.status != RPCStatusCode.NOT_FOUND:
                    raise
            else:
                pytest.skip("default example requires a fresh owned Temporal Scope")
        environment = {
            key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ
        }
        script = Path(__file__).parents[1] / "examples/temporal_managed_nodes.py"
        values, histories = [], []
        try:
            for index in range(2):
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(script),
                    "--address",
                    os.environ["RALF_TEST_TEMPORAL_ADDRESS"],
                    "--task-queue",
                    queue,
                    "--command-id",
                    "same",
                    "--input-json",
                    '[1,null,{"message":"完整 JSON"}]',
                    cwd=tmp_path,
                    env=environment,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), 90)
                finally:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                (tmp_path / f"example-{index}.stdout").write_bytes(stdout)
                (tmp_path / f"example-{index}.stderr").write_bytes(stderr)
                assert process.returncode == 0, stderr.decode()
                value = json.loads(stdout)
                assert value["state"] == "succeeded" and value["result"] == [
                    1,
                    None,
                    {"message": "完整 JSON"},
                ]
                assert (
                    value["budget"]["spent"] == 2
                    and value["budget"]["unknown"] == value["budget"]["reserved"] == 0
                )
                owned.add(value["run_id"])
                # The subprocess has closed its Worker. Inspect the original
                # Service Histories without requiring another active poller.
                await discover_owned_descendants(client, owned)
                counts = {"tool": 0, "model": 0}
                for target in sorted(owned):
                    history = await client.get_workflow_handle(target).fetch_history()
                    (tmp_path / f"example-{index}-{len(histories)}-history.json").write_text(
                        history.to_json()
                    )
                    histories.append(history)
                    for event in history.events:
                        if event.HasField("activity_task_scheduled_event_attributes"):
                            name = event.activity_task_scheduled_event_attributes.activity_type.name
                            counts["tool"] += name == TOOL_ACTIVITY
                            counts["model"] += name == MODEL_ACTIVITY
                    await replay_temporal_history(history, namespace=client.namespace)
                assert counts == {"tool": 2, "model": 0}
                values.append(value)
            assert values[0]["run_id"] == values[1]["run_id"]
            assert values[0]["submission_receipt"] == values[1]["submission_receipt"]
            assert values[0]["result"] == values[1]["result"]
        finally:
            await discover_owned_descendants(client, owned)
            for target in sorted(owned):
                try:
                    handle = client.get_workflow_handle(target)
                    if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                        await handle.terminate(reason="owned default Workflow-node example cleanup")
                except RPCError as error:
                    if error.status != RPCStatusCode.NOT_FOUND:
                        raise

    asyncio.run(asyncio.wait_for(run(), 180))
