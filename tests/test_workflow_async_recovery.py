"""Native process death keeps node effects under the original action authority."""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

import relf_agent as r
from relf_agent.types import canonical


def worker(root, phase, window, effect, parallel, query, value):
    # Follow the interpreter's actually imported package. The same selection is
    # valid from a source checkout and an isolated installed-wheel environment.
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(r.__file__).resolve().parent.parent)
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).with_name("workflow_async_crash_fixture.py")),
            str(root),
            phase,
            window,
            effect,
            "parallel" if parallel else "serial",
            "query" if query else "no-query",
            canonical(value),
        ],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=25)
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        raise
    assert process.wait(timeout=10) == process.returncode
    (root / f"{phase}-stdout.txt").write_text(stdout)
    (root / f"{phase}-stderr.txt").write_text(stderr)
    (root / f"{phase}-process.json").write_text(
        canonical({"pid": process.pid, "returncode": process.returncode, "waited_reaped": True})
    )
    return process.returncode, stdout, stderr


def durable(root, run_id):
    with r.SQLiteStore(root / "run.sqlite", readonly=True) as store:
        return {
            "run": store.run(run_id),
            "budget": store.budget(run_id),
            "events": store.events(run_id),
            "reservations": [
                dict(row) for row in store.conn.execute("SELECT * FROM reservations ORDER BY id")
            ],
            "commands": [
                dict(row) for row in store.conn.execute("SELECT * FROM commands ORDER BY id")
            ],
        }


def service(root):
    with closing(sqlite3.connect(root / "service.sqlite")) as db:
        db.row_factory = sqlite3.Row
        return {
            "calls": [dict(row) for row in db.execute("SELECT * FROM calls ORDER BY seq")],
            "effects": [
                dict(row) for row in db.execute("SELECT * FROM effects ORDER BY effect_key")
            ],
        }


def call_count(evidence, kind):
    return sum(row["kind"] == kind for row in evidence["calls"])


@pytest.mark.parametrize(
    "window,effect,parallel,query,value,retry,parked",
    [
        ("intent", "read_only", False, False, [1, None], True, False),
        ("intent", "idempotent_write", False, True, [2, None], True, False),
        ("intent", "queryable_write", False, True, None, False, True),
        ("intent", "unqueryable_write", False, False, None, False, True),
        ("external", "read_only", False, False, None, True, False),
        ("external", "idempotent_write", False, True, [3, None], False, False),
        ("external", "idempotent_write", False, False, [4, None], True, False),
        ("external", "queryable_write", False, True, None, False, False),
        ("external", "unqueryable_write", False, False, None, False, True),
        ("receipt", "queryable_write", False, True, [5, None], False, False),
        ("receipt", "unqueryable_write", True, False, None, False, False),
        ("action", "queryable_write", False, True, None, False, False),
        ("action", "unqueryable_write", True, False, [6, None], False, False),
    ],
)
def test_process_crash_recovery_keeps_original_node_action_and_external_effect(
    tmp_path, window, effect, parallel, query, value, retry, parked
):
    code, _, stderr = worker(tmp_path, "crash", window, effect, parallel, query, value)
    assert code == 77, stderr
    refs = json.loads((tmp_path / "refs.json").read_text())
    run_id = refs["handle"]["run_id"]
    before = durable(tmp_path, run_id)
    business_before = service(tmp_path)
    original = before["run"]["actions"][0]
    crash = json.loads((tmp_path / "crash.json").read_text())
    assert crash["run"] == before["run"] and crash["budget"] == before["budget"]
    assert len(before["run"]["actions"]) == len(original["attempts"]) == 1
    assert original["tool"] == "__relf_node__:write" and original["approved"]
    assert original["arguments"] == {"input": value, "config": {"mode": "fixed", "version": 1}}
    expected_status = {
        "intent": "executing",
        "external": "executing",
        "receipt": "receipt_received",
        "action": "completed",
    }[window]
    assert original["status"] == expected_status
    assert before["budget"] == {
        "limit": 12,
        "held": 0 if window == "action" else 2,
        "spent": 2 if window == "action" else 0,
    }
    assert call_count(business_before, "execute") == (0 if window == "intent" else 1)
    assert call_count(business_before, "reconcile") == 0
    assert len(business_before["effects"]) == int(window != "intent" and effect != "read_only")
    if window == "receipt":
        assert original["effect_observation"]["result"] == value and "result" not in original
    if window == "action":
        assert original["result"] == value
    assert not any(event.kind == "workflow_node_completed" for event in before["events"])
    if parallel:
        assert before["run"]["plan"]["schema_version"] == 3
        assert "execution" in before["run"]["workflow"]["nodes"]["write"]

    code, stdout, stderr = worker(tmp_path, "resume", window, effect, parallel, query, value)
    assert code == 0, stderr
    actual = json.loads(stdout)
    after = durable(tmp_path, run_id)
    business_after = service(tmp_path)
    action = after["run"]["actions"][0]
    assert (
        actual["state"]
        == after["run"]["state"]
        == ("waiting_reconciliation" if parked else "succeeded")
    )
    assert actual["result"] == (None if parked else value)
    assert len(after["run"]["actions"]) == 1
    assert after["run"]["definition"] == before["run"]["definition"]
    assert after["run"]["manifest"] == before["run"]["manifest"]
    assert after["run"]["release_digest"] == before["run"]["release_digest"]
    for key in ("id", "digest", "effect_key", "arguments", "approved", "node"):
        assert action[key] == original[key]
    assert action["attempts"][0]["id"] == original["attempts"][0]["id"]
    assert len(action["attempts"]) == (2 if retry else 1)
    assert after["commands"] == before["commands"]
    assert len(after["reservations"]) == (2 if retry else 1)
    assert after["budget"] == {
        "limit": 12,
        "held": 2 if retry or parked else 0,
        "spent": 0 if parked else 2,
    }
    if parked:
        assert action["status"] == "outcome_unknown"
    else:
        assert action["status"] == "completed" and action["result"] == value
        assert after["run"]["workflow"]["nodes"]["write"]["state"] == "completed"
    expected_calls = 1 if window != "external" or not retry else 2
    if parked and window == "intent":
        expected_calls = 0
    assert call_count(business_after, "execute") == expected_calls
    expected_queries = 0 if not query or window in {"receipt", "action"} else (2 if parked else 1)
    assert call_count(business_after, "reconcile") == expected_queries
    expected_effects = int(effect != "read_only" and (window != "intent" or not parked))
    assert len(business_after["effects"]) == expected_effects
    for call in business_after["calls"]:
        assert call["effect_key"] == original["effect_key"]
        assert json.loads(call["input"]) == value
        assert json.loads(call["config"]) == {"mode": "fixed", "version": 1}
        assert call["attempt_id"] in {attempt["id"] for attempt in action["attempts"]}
    if window in {"receipt", "action"}:
        assert business_after == business_before
        assert action["effect_observation"] == original["effect_observation"]
        receipts = [event.seq for event in after["events"] if event.kind == "tool_receipt_recorded"]
        commits = [event.seq for event in after["events"] if event.kind == "tool_result_committed"]
        completed = [
            event.seq for event in after["events"] if event.kind == "workflow_node_completed"
        ]
        assert len(receipts) == len(commits) == len(completed) == 1
        assert receipts[0] < commits[0] < completed[0]
    dispatches = [event for event in after["events"] if event.kind == "tool_dispatch_intent"]
    assert len(dispatches) == len(action["attempts"])

    if window == "external" and effect == "unqueryable_write":
        code, stdout, stderr = worker(tmp_path, "confirm", window, effect, parallel, query, value)
        assert code == 0, stderr
        assert json.loads(stdout)["state"] == "succeeded"
        confirmed = durable(tmp_path, run_id)
        action = confirmed["run"]["actions"][0]
        assert action["result"] is None and action["receipt"]["source"] == "local-owner"
        assert action["id"] == original["id"] and len(action["attempts"]) == 1
        assert confirmed["budget"] == {"limit": 12, "held": 0, "spent": 2}
        assert service(tmp_path) == business_after
        code, stdout, stderr = worker(
            tmp_path, "verify-confirmation", window, effect, parallel, query, value
        )
        assert code == 0, stderr
        assert json.loads(stdout) == {"state": "succeeded", "result": None, "run_id": run_id}
        assert service(tmp_path) == business_after
        assert durable(tmp_path, run_id)["commands"] == confirmed["commands"]
