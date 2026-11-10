"""Default fan-out proposes work; existing Local authority owns every effect."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import relf_agent as r
from relf_agent.errors import AuthorizationDenied

from .fan_out_worker import BusinessNode, Ledger, definition, local_engine


async def until(predicate):
    async with asyncio.timeout(5):
        while True:
            if predicate():
                return
            await asyncio.sleep(0.005)


@pytest.mark.parametrize("concurrency", [2, 3])
@pytest.mark.parametrize("reduce", [False, True])
def test_reverse_completion_keeps_input_order_and_existing_concurrency(
    tmp_path, concurrency, reduce
):
    async def exercise():
        class Gated(BusinessNode):
            def __init__(self, ledger):
                super().__init__(ledger)
                self.active, self.peak, self.entered, self.finished = 0, 0, [], []
                self.gates = {n: asyncio.Event() for n in range(1, 4)}
                if concurrency == 2:
                    self.gates[3].set()

            async def execute(self, input, config, context):
                self.active += 1
                self.peak = max(self.peak, self.active)
                self.entered.append(input)
                try:
                    await self.gates[input].wait()
                    result = await super().execute(input, config, context)
                    self.finished.append(input)
                    return result
                finally:
                    self.active -= 1

        node = Gated(Ledger(tmp_path))
        engine, ledger, _ = local_engine(tmp_path, reducer=reduce, worker=node)
        with engine:
            handle = engine.submit(
                definition(reducer=reduce, concurrency=concurrency),
                [1, 2, 3],
                command_id="same",
                budget=4,
            )
            running = asyncio.create_task(engine.drive(handle.run_id))
            try:
                await until(lambda: len(node.entered) == concurrency)
                assert node.active == node.peak == concurrency
                for value in reversed(range(1, concurrency + 1)):
                    node.gates[value].set()
                    await until(lambda value=value: value in node.finished)
                result = await asyncio.wait_for(running, 5)
            finally:
                for gate in node.gates.values():
                    gate.set()
                await asyncio.gather(running, return_exceptions=True)
            expected = {f"map-{n:04d}": (n + 1) ** 2 for n in range(3)}
            assert result.state == "succeeded"
            assert result.result == (
                {"keys": list(expected), "values": list(expected.values()), "total": 14}
                if reduce
                else expected
            )
            assert node.finished[:concurrency] == list(reversed(range(1, concurrency + 1)))
            assert node.peak == concurrency
            assert len(ledger.rows("plan")) == 1
            assert len(ledger.rows("map")) == 3 and len(ledger.rows("reduce")) == int(reduce)
            assert engine.diagnostics(handle.run_id).budget == {
                "limit": 4,
                "held": 0,
                "spent": 3 + int(reduce),
            }

    asyncio.run(exercise())


def test_approval_pause_close_reopen_and_repeated_commands_do_not_repeat_business(tmp_path):
    engine, ledger, _ = local_engine(tmp_path, approval=True)
    spec = definition()
    with engine:
        handle = engine.submit(spec, [1, 2, 3], command_id="same", budget=4)
        assert asyncio.run(engine.drive(handle.run_id)).state == "waiting_approval"
        assert ledger.rows("map") == ledger.rows("reduce") == []
        original = engine.store.run(handle.run_id)["orchestration"]["proposal"]
    with local_engine(tmp_path, approval=True)[0] as resumed:
        assert resumed.submit(spec, [1, 2, 3], command_id="same", budget=4) == handle
        for _ in range(5):
            snapshot = asyncio.run(resumed.drive(handle.run_id))
            if snapshot.state == "succeeded":
                break
            pending = []
            for child in resumed.diagnostics(handle.run_id).workflow["children"]:
                pending.extend(
                    (child["run_id"], p) for p in resumed.status(child["run_id"]).pending
                )
            assert pending
            for child, p in pending:
                receipt = resumed.approve(
                    child, p["action_id"], p["digest"], command_id="approve-" + child
                )
                assert (
                    resumed.approve(
                        child, p["action_id"], p["digest"], command_id="approve-" + child
                    )
                    == receipt
                )
        assert snapshot.state == "succeeded" and snapshot.result["total"] == 14
        assert resumed.store.run(handle.run_id)["orchestration"]["proposal"] == original
        assert len(ledger.rows("plan")) == 1 and len(ledger.rows("map")) == 3
        assert len(ledger.rows("reduce")) == 1
        before = ledger.rows()
        assert asyncio.run(resumed.drive(handle.run_id)).result == snapshot.result
        assert ledger.rows() == before


def test_original_budget_refusal_happens_before_any_worker(tmp_path):
    with local_engine(tmp_path)[0] as engine:
        handle = engine.submit(definition(), [1, 2, 3], command_id="budget", budget=0)
        result = asyncio.run(engine.drive(handle.run_id))
        assert result.state == "failed"
        assert engine.diagnostics(handle.run_id).budget == {"limit": 0, "held": 0, "spent": 0}
        assert Ledger(tmp_path).rows("map") == Ledger(tmp_path).rows("reduce") == []


def test_original_host_authorization_still_denies_selected_worker_before_dispatch(tmp_path):
    seen = []

    def policy(scope, spec, arguments):
        seen.append((scope, spec.name))
        raise AuthorizationDenied("Host refuses this batch operation")

    with local_engine(tmp_path, policy=policy)[0] as engine:
        handle = engine.submit(definition(), [1, 2, 3], command_id="denied", budget=4)
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "failed"
        assert seen and all(
            scope == r.Scope() and name == "__relf_node__:square" for scope, name in seen
        )
        assert Ledger(tmp_path).rows("map") == Ledger(tmp_path).rows("reduce") == []
        assert engine.diagnostics(handle.run_id).budget == {"limit": 4, "held": 0, "spent": 0}
        children = engine.diagnostics(handle.run_id).workflow["children"]
        assert any(
            (engine.status(child["run_id"]).error or {}).get("code") == "authorization_denied"
            for child in children
        )


def test_parent_cancel_waits_original_workers_and_never_runs_reducer(tmp_path):
    async def exercise():
        entered, finish = [], asyncio.Event()

        class Held(BusinessNode):
            async def execute(self, input, config, context):
                entered.append(input)
                await finish.wait()
                return await super().execute(input, config, context)

        engine, ledger, _ = local_engine(tmp_path, worker=Held(Ledger(tmp_path)))
        with engine:
            handle = engine.submit(definition(), [1, 2, 3], command_id="cancel", budget=4)
            task = asyncio.create_task(engine.drive(handle.run_id))
            try:
                await until(lambda: len(entered) == 2)
                receipt = engine.cancel(handle.run_id, command_id="cancel-root")
                assert engine.cancel(handle.run_id, command_id="cancel-root") == receipt
                finish.set()
                assert (await asyncio.wait_for(task, 5)).state == "cancelled"
                assert ledger.rows("reduce") == [] and len(entered) == 2
                assert engine.diagnostics(handle.run_id).budget["held"] == 0
            finally:
                finish.set()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_unknown_effect_blocks_reducer_then_original_receipt_reconciles_once(tmp_path):
    engine, ledger, worker = local_engine(tmp_path, mode="unknown")
    with engine:
        handle = engine.submit(definition(), [1, 2, 3], command_id="unknown", budget=4)
        assert asyncio.run(engine.drive(handle.run_id)).state in {
            "waiting_reconciliation",
            "outcome_unknown",
        }
        assert ledger.rows("reduce") == []
        worker.query_enabled = True
        result = asyncio.run(engine.drive(handle.run_id))
        assert result.state == "succeeded" and result.result["total"] == 14
        assert len(ledger.rows("plan")) == 1
        assert len(ledger.rows("map")) == 3 and len(ledger.rows("reduce")) == 1
        assert len({row["effect_key"] for row in ledger.rows("map")}) == 3


@pytest.mark.parametrize(
    "window", ["plan_proposal_received", "plan_revision_adopted", "dag_nodes_completed"]
)
def test_real_sqlite_process_cuts_reuse_plan_and_completed_child_results(tmp_path, window):
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"}}
    env["PYTHONPATH"] = str(Path(r.__file__).resolve().parent.parent)
    # Execute the checked-in test helper while selecting this interpreter's SDK.
    command = [sys.executable, "-m", "tests.fan_out_worker", str(tmp_path)]
    crashed = subprocess.run(
        [*command, "--window", window],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert crashed.returncode == 77, crashed.stderr
    run_id = json.loads(crashed.stdout.splitlines()[0])["run_id"]
    cut = json.loads((tmp_path / "cut.json").read_text())
    assert cut["window"] == window
    before = Ledger(tmp_path).rows()
    assert len([row for row in before if row["kind"] == "plan"]) == 1
    assert len([row for row in before if row["kind"] == "map"]) == int(
        window == "dag_nodes_completed"
    )
    resumed = subprocess.run(
        [*command, "--run-id", run_id],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads(resumed.stdout.splitlines()[-1])
    assert result == {
        "state": "succeeded",
        "result": {"keys": ["map-0000", "map-0001", "map-0002"], "values": [9, 1, 4], "total": 14},
    }
    rows = Ledger(tmp_path).rows()
    assert len([row for row in rows if row["kind"] == "plan"]) == 1
    assert len([row for row in rows if row["kind"] == "map"]) == 3
    assert len([row for row in rows if row["kind"] == "reduce"]) == 1
    assert len({row["effect_key"] for row in rows if row["kind"] != "plan"}) == 4


def test_standalone_example_approval_and_repeat_do_not_repeat_original_calls(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples" / "fan_out_workflow.py"
    outside = tmp_path / "outside"
    outside.mkdir()
    example = outside / source.name
    shutil.copy2(source, example)
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"}}
    command = [
        sys.executable,
        str(example),
        "--db",
        str(outside / "runs.sqlite"),
        "--command-id",
        "same",
    ]

    def call(*args):
        result = subprocess.run(
            [*command, *args], cwd=outside, env=env, text=True, capture_output=True, timeout=20
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    paused = call("--pause-before-approval")
    assert paused["state"] == "waiting_approval" and paused["requests_total"] == 0
    done, repeated = call(), call()
    assert done["run_id"] == repeated["run_id"] == paused["run_id"]
    assert done["state"] == repeated["state"] == "succeeded"
    assert (
        done["result"]
        == repeated["result"]
        == {"keys": ["map-0000", "map-0001", "map-0002"], "values": [9, 1, 4], "total": 14}
    )
    assert done["requests_total"] == repeated["requests_total"] == 4
    assert done["requests_this_process"] == 4 and repeated["requests_this_process"] == 0
    assert done["receipt_replay_matches"] and repeated["receipt_replay_matches"]
    assert done["spent"] == repeated["spent"] == 4
