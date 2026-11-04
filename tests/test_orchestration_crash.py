import json
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from .test_cli import subprocess_env


def trace_diagnostics(path):
    try:
        return f"{path.name}:\n{path.read_text()}"
    except OSError as error:
        return f"{path.name}: trace unavailable ({type(error).__name__})"


def run_fixture(command, trace):
    env = subprocess_env()
    env["RELF_TEST_CRASH_TRACE"] = str(trace)
    try:
        return subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as error:
        error.add_note(trace_diagnostics(trace))
        raise


@pytest.mark.parametrize(
    "window",
    [
        "plan_proposal_received",
        "plan_revision_adopted",
        "child_submitted",
        "run_succeeded",
        "plan_verified",
    ],
)
def test_real_process_durability_windows_resume_without_replanning_or_duplicate_child(
    tmp_path, window
):
    path = tmp_path / "crash.sqlite"
    base = [sys.executable, "-m", "tests.orchestration_crash_fixture", str(path)]
    crash_trace = tmp_path / "crash.jsonl"
    recover_trace = tmp_path / "recover.jsonl"
    crashed = run_fixture([*base, "--crash", window], crash_trace)
    assert crashed.returncode == 77, crashed.stderr + "\n" + trace_diagnostics(crash_trace)
    crash_phases = [
        json.loads(line) for line in crash_trace.read_text().splitlines() if line.startswith("{")
    ]
    assert crash_phases[-1]["phase"] == "crash_committed"
    assert crash_phases[-1]["event_kind"] == window
    run_id = json.loads(crashed.stdout.splitlines()[0])["run_id"]
    recovered = run_fixture([*base, "--run-id", run_id], recover_trace)
    assert recovered.returncode == 0, recovered.stderr + "\n" + trace_diagnostics(recover_trace)
    recover_phases = [
        json.loads(line) for line in recover_trace.read_text().splitlines() if line.startswith("{")
    ]
    assert recover_phases[-1]["phase"] == "engine_closed"
    assert json.loads(recovered.stdout.splitlines()[-1])["state"] == "succeeded"
    with closing(sqlite3.connect(path.with_suffix(".counter.sqlite"))) as conn, conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM counts WHERE kind=?", ("plan",)).fetchone()[0] == 1
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM counts WHERE kind=?", ("model",)).fetchone()[0] == 1
        )
    with closing(sqlite3.connect(path)) as conn, conn:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2


@pytest.mark.parametrize("query_error", [False, True])
def test_evidence_connections_are_explicitly_closed_even_when_a_query_fails(
    tmp_path, monkeypatch, query_error
):
    connect = sqlite3.connect
    opened = []

    class EvidenceConnection(sqlite3.Connection):
        explicitly_closed = False
        fail_query = False

        def close(self):
            super().close()
            self.explicitly_closed = True

        def execute(self, sql, *args, **kwargs):
            if self.fail_query and sql.startswith("SELECT COUNT"):
                raise RuntimeError("Injected evidence query failure")
            return super().execute(sql, *args, **kwargs)

    def tracked_connect(path, *args, **kwargs):
        connection = connect(path, *args, factory=EvidenceConnection, **kwargs)
        connection.fail_query = query_error
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
    try:
        if query_error:
            with pytest.raises(RuntimeError, match="Injected evidence query"):
                test_real_process_durability_windows_resume_without_replanning_or_duplicate_child(
                    tmp_path, "run_succeeded"
                )
        else:
            test_real_process_durability_windows_resume_without_replanning_or_duplicate_child(
                tmp_path, "run_succeeded"
            )
        assert len(opened) == (1 if query_error else 2)
        assert all(connection.explicitly_closed for connection in opened)
    finally:
        # A RED reproduction must not itself retain handles until cyclic GC.
        for connection in opened:
            connection.close()
