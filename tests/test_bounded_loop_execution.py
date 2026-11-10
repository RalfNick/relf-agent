"""Real Local execution must retain original bounded-loop child facts."""

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

from .bounded_loop_worker import BusinessNode, Ledger, definition, local_engine


def expected(iteration, *, target=3):
    return {"done": iteration >= target, "value": iteration, "iteration": iteration}


def work_inputs(ledger):
    return [json.loads(row["input"]) for row in ledger.rows("work")]


def assert_original_iterations(engine, run_id, ledger, count):
    children = engine.diagnostics(run_id).workflow["children"]
    assert [c["id"] for c in children] == [f"r{i}.step.iteration" for i in range(count)]
    assert len({c["run_id"] for c in children}) == count
    assert len({row["effect_key"] for row in ledger.rows("work")}) == count
    assert [value["iteration"] for value in work_inputs(ledger)] == list(range(1, count + 1))
    assert [value["previous"] for value in work_inputs(ledger)] == [
        None,
        *[expected(i) for i in range(1, count)],
    ]


@pytest.mark.parametrize("target", [1, 3])
def test_real_iterations_converge_and_early_success_uses_only_adopted_previous(tmp_path, target):
    engine, ledger, _ = local_engine(tmp_path)
    with engine:
        handle = engine.submit(definition(), {"target": target}, command_id="same", budget=3)
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "succeeded" and done.result == expected(target, target=target)
        assert len(ledger.rows("plan")) == len(ledger.rows("verify")) == target
        assert_original_iterations(engine, handle.run_id, ledger, target)
        assert engine.diagnostics(handle.run_id).budget == {"limit": 3, "spent": target, "held": 0}
        before = ledger.rows()
        assert (
            engine.submit(definition(), {"target": target}, command_id="same", budget=3) == handle
        )
        assert asyncio.run(engine.drive(handle.run_id)).result == done.result
        assert ledger.rows() == before


def test_last_iteration_without_success_is_failed_and_never_dispatched_again(tmp_path):
    engine, ledger, _ = local_engine(tmp_path, max_iterations=2)
    with engine:
        handle = engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "failed"
        assert (done.error or {}).get("code") == "child_run_failed"
        assert_original_iterations(engine, handle.run_id, ledger, 2)
        final = json.loads(ledger.rows("verify")[-1]["result"])
        assert final == {
            "status": "failed",
            "result": {
                "reason": "loop_iteration_limit",
                "iterations": 2,
                "last_result": expected(2),
            },
        }
        before = ledger.rows()
        assert asyncio.run(engine.drive(handle.run_id)).state == "failed"
        assert ledger.rows() == before


@pytest.mark.parametrize("limit", ["max_revisions", "max_steps", "budget"])
def test_original_host_limits_may_stop_before_policy_allowance(tmp_path, limit):
    engine, ledger, _ = local_engine(tmp_path)
    with engine:
        spec = definition(**({limit: 1} if limit != "budget" else {}))
        budget = 1 if limit == "budget" else 3
        handle = engine.submit(spec, {"target": 3}, command_id="limited", budget=budget)
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "failed"
        assert len(ledger.rows("work")) == 1
        assert engine.diagnostics(handle.run_id).budget == {"limit": budget, "spent": 1, "held": 0}
        assert work_inputs(ledger) == [{"task": {"target": 3}, "previous": None, "iteration": 1}]
        if limit == "max_revisions":
            assert done.error["code"] == "plan_revision_limit"


def pending(engine, root_id):
    return [
        (child["run_id"], p)
        for child in engine.diagnostics(root_id).workflow["children"]
        for p in engine.status(child["run_id"]).pending
    ]


def approve_pending(engine, root_id):
    items = pending(engine, root_id)
    assert len(items) == 1
    child, p = items[0]
    command = "approve-" + child
    receipt = engine.approve(child, p["action_id"], p["digest"], command_id=command)
    assert engine.approve(child, p["action_id"], p["digest"], command_id=command) == receipt
    return items[0]


def test_second_round_approval_reopen_retains_prior_result_and_original_command(tmp_path):
    engine, ledger, _ = local_engine(tmp_path, approval=True)
    with engine:
        handle = engine.submit(definition(), {"target": 3}, command_id="same", budget=3)
        assert asyncio.run(engine.drive(handle.run_id)).state == "waiting_approval"
        approve_pending(engine, handle.run_id)
        assert asyncio.run(engine.drive(handle.run_id)).state == "waiting_approval"
        assert len(ledger.rows("work")) == 1
        original = pending(engine, handle.run_id)
        assert engine.store.run(handle.run_id)["orchestration"]["revision"] == 1
    with local_engine(tmp_path, approval=True)[0] as resumed:
        assert resumed.submit(definition(), {"target": 3}, command_id="same", budget=3) == handle
        assert pending(resumed, handle.run_id) == original
        for _ in range(2):
            approve_pending(resumed, handle.run_id)
            done = asyncio.run(resumed.drive(handle.run_id))
        assert done.state == "succeeded" and done.result == expected(3)
        assert_original_iterations(resumed, handle.run_id, ledger, 3)
        assert [json.loads(row["input"])["revision"] for row in ledger.rows("plan")] == [0, 1, 2]
        assert resumed.diagnostics(handle.run_id).budget == {"limit": 3, "spent": 3, "held": 0}


def test_second_round_host_authorization_is_not_bypassed_by_loop_replanning(tmp_path):
    seen = []

    def policy(scope, spec, arguments):
        seen.append((scope, spec.name, arguments["input"]["iteration"]))
        if arguments["input"]["iteration"] == 2:
            raise AuthorizationDenied("Original host rejects the second iteration")

    engine, ledger, _ = local_engine(tmp_path, policy=policy)
    with engine:
        handle = engine.submit(definition(), {"target": 3}, command_id="deny", budget=3)
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "failed" and len(ledger.rows("work")) == 1
        assert seen and all(
            scope == r.Scope() and name == "__relf_node__:advance" for scope, name, _ in seen
        )
        children = engine.diagnostics(handle.run_id).workflow["children"]
        assert len(children) == 2
        assert engine.status(children[1]["run_id"]).error["code"] == "authorization_denied"
        assert engine.diagnostics(handle.run_id).budget == {"limit": 3, "spent": 1, "held": 0}


def test_unknown_second_result_cannot_become_previous_before_original_receipt_query(tmp_path):
    engine, ledger, worker = local_engine(tmp_path, mode="unknown")
    with engine:
        handle = engine.submit(definition(), {"target": 3}, command_id="unknown", budget=3)
        assert asyncio.run(engine.drive(handle.run_id)).state in {
            "waiting_reconciliation",
            "outcome_unknown",
        }
        assert len(ledger.rows("work")) == 2
        assert [json.loads(row["input"])["revision"] for row in ledger.rows("plan")] == [0, 1]
        worker.query_enabled = True
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "succeeded" and done.result == expected(3)
        assert_original_iterations(engine, handle.run_id, ledger, 3)
        assert ledger.rows("query")


def test_cancel_during_second_actual_handler_stops_iteration_and_releases_original_owner(tmp_path):
    async def exercise():
        entered, finish, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class Held(BusinessNode):
            async def execute(self, input, config, context):
                if input["iteration"] == 2:
                    entered.set()
                    try:
                        await finish.wait()
                    except asyncio.CancelledError:
                        await finish.wait()
                        raise
                    finally:
                        stopped.set()
                return await super().execute(input, config, context)

        engine, ledger, _ = local_engine(tmp_path, worker=Held(Ledger(tmp_path)))
        with engine:
            handle = engine.submit(definition(), {"target": 3}, command_id="cancel", budget=3)
            task = asyncio.create_task(engine.drive(handle.run_id))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                receipt = engine.cancel(handle.run_id, command_id="cancel-root")
                assert engine.cancel(handle.run_id, command_id="cancel-root") == receipt
                assert not stopped.is_set()
                finish.set()
                assert (await asyncio.wait_for(task, 5)).state == "cancelled"
                assert stopped.is_set()
                assert all(value["iteration"] < 3 for value in work_inputs(ledger))
                assert engine.diagnostics(handle.run_id).budget["held"] == 0
            finally:
                finish.set()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def subprocess_env():
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"}}
    env["PYTHONPATH"] = str(Path(r.__file__).resolve().parent.parent)
    return env


@pytest.mark.parametrize("window", ["plan_verified", "plan_replanning", "plan_revision_adopted"])
def test_original_sqlite_revision_process_cuts_never_repeat_accepted_business(tmp_path, window):
    command = [sys.executable, "-m", "tests.bounded_loop_worker", str(tmp_path)]
    crashed = subprocess.run(
        [*command, "--window", window],
        env=subprocess_env(),
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert crashed.returncode == 77, crashed.stderr
    run_id = json.loads(crashed.stdout.splitlines()[0])["run_id"]
    cut = json.loads((tmp_path / "cut.json").read_text())
    assert cut["window"] == window
    ledger = Ledger(tmp_path)
    assert len(ledger.rows("work")) == 1
    assert cut["run"]["orchestration"]["results"] == {"r0.step.iteration": expected(1)}
    before = ledger.rows("work")
    resumed = subprocess.run(
        [*command, "--run-id", run_id],
        env=subprocess_env(),
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout.splitlines()[-1]) == {
        "state": "succeeded",
        "result": expected(3),
    }
    assert ledger.rows("work")[:1] == before
    assert len(ledger.rows("work")) == 3
    assert [json.loads(row["input"])["revision"] for row in ledger.rows("plan")] == [0, 1, 2]
    assert work_inputs(ledger) == [
        {"task": {"target": 3}, "previous": None, "iteration": 1},
        {"task": {"target": 3}, "previous": expected(1), "iteration": 2},
        {"task": {"target": 3}, "previous": expected(2), "iteration": 3},
    ]
    assert len({row["effect_key"] for row in ledger.rows("work")}) == 3


def test_standalone_example_second_approval_resume_and_repeat_outside_checkout(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/bounded_loop_workflow.py"
    outside = tmp_path / "outside"
    outside.mkdir()
    example = outside / source.name
    shutil.copy2(source, example)
    command = [
        sys.executable,
        str(example),
        "--db",
        str(outside / "runs.sqlite"),
        "--command-id",
        "same",
    ]

    def run(extra=()):
        result = subprocess.run(
            [*command, *extra],
            env=subprocess_env(),
            cwd=outside,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout.splitlines()[-1])

    waiting = run(["--pause-second-approval"])
    assert waiting["state"] == "waiting_approval" and waiting["requests_total"] == 1
    done = run()
    assert done["run_id"] == waiting["run_id"] and done["state"] == "succeeded"
    assert done["result"] == expected(3)
    assert (
        done["requests_this_process"] == 2 and done["requests_total"] == done["receipts_total"] == 3
    )
    assert done["spent"] == 3 and done["receipt_replay_matches"] is True
    repeated = run()
    assert repeated["run_id"] == waiting["run_id"]
    assert (
        repeated["requests_this_process"] == 0
        and repeated["requests_total"] == repeated["receipts_total"] == 3
    )
