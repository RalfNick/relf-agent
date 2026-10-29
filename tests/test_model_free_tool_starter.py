"""Editable optional graph application uses the original installed SDK controls."""

import json
import os
import subprocess
import sys

import pytest

from relf_agent.starter import create_starter

from .test_starter import installed_wheel as _installed_wheel
from .test_starter import subprocess_result

installed_wheel = _installed_wheel


@pytest.fixture(params=["source", "installed"])
def app(tmp_path, installed_wheel, request):
    project = tmp_path / "tools"
    if request.param == "source":
        create_starter(project, template="graph")
        python, cli = sys.executable, [sys.executable, "-m", "relf_agent"]
    else:
        python, executable = installed_wheel
        subprocess_result([executable, "init", project, "--template", "graph"], cwd=tmp_path)
        cli = [executable]

    def run(*args, code=0):
        return json.loads(subprocess_result([python, *args], cwd=project, returncode=code))

    def control(*args, code=0):
        child = subprocess.run(
            [
                str(a)
                for a in [
                    *cli,
                    "--db",
                    ".ralf/tool-graph.sqlite",
                    "--factory",
                    "agent_app.tool_runtime:create_engine",
                    *args,
                ]
            ],
            cwd=project,
            env={"PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert child.returncode == code, child.stderr
        return json.loads(child.stderr if code else child.stdout)

    return project, run, control


def test_editable_tool_graph_runs_without_model_and_reuses_original_receipt(app):
    _, run, control = app
    first = run("-m", "agent_app.tool_graph")
    assert first["state"] == "succeeded"
    assert first["result"] == {"order_id": "ORD-1", "sku": "SKU-1", "available": True}
    assert first["model_actions"] == 0 and first["tool_actions"] == first["credits_spent"] == 2
    assert run("-m", "agent_app.tool_graph") == first
    assert control("resume", first["run_id"])["result"] == first["result"]
    # Optional files do not replace the starter's original Agent graph entry.
    assert (
        run("-m", "agent_app", "--input", "hello", "--command-id", "original")["state"]
        == "succeeded"
    )


def test_tool_graph_submit_only_and_budget_use_original_controls(app):
    _, run, control = app
    queued = run("-m", "agent_app.tool_graph", "--submit-only")
    assert queued["state"] == "queued" and queued["tool_actions"] == queued["credits_spent"] == 0
    assert control("inspect", queued["run_id"])["state"] == "queued"
    assert control("resume", queued["run_id"])["state"] == "succeeded"
    exhausted = run("-m", "agent_app.tool_graph", "--command-id", "low", "--budget", "1", code=1)
    assert exhausted["state"] == "failed" and exhausted["credits_spent"] == 1


def test_tool_graph_approval_survives_reopen_and_duplicate_controls(app):
    project, run, control = app
    config = project / "tool-runtime.toml"
    config.write_text(
        config.read_text().replace("requires_approval = false", "requires_approval = true")
    )
    first = run("-m", "agent_app.tool_graph")
    assert first["state"] == "waiting_approval" and first["credits_spent"] == 0
    for index in range(2):
        pending = first["pending"][0]
        args = (
            "approve",
            first["run_id"],
            pending["action_id"],
            "--digest",
            pending["digest"],
            "--command-id",
            "approve-" + str(index),
        )
        receipt = control(*args)
        assert receipt["apply_state"] == "applied" and control(*args) == receipt
        first = control("resume", first["run_id"])
        assert first["state"] == ("waiting_approval" if index == 0 else "succeeded")
    # Reopen yet again: both Tool Actions, no model, exactly two reservations spent.
    final = run("-m", "agent_app.tool_graph")
    assert final["state"] == "succeeded" and final["model_actions"] == 0
    assert final["credits_spent"] == final["tool_actions"] == 2


def test_tool_graph_recovers_original_profile_despite_unusable_new_default(app):
    project, run, control = app
    queued = run("-m", "agent_app.tool_graph", "--submit-only")
    path = project / "tool-runtime.toml"
    old = path.read_text()
    replacement = """[[profiles]]
name = "async-tool-orders"
version = "2"
[profiles.providers.default]
adapter = "not-installed"
"""
    path.write_text(old.replace('version = "1"', 'version = "2"', 1) + "\n" + replacement)
    assert run("-m", "agent_app.tool_graph", "--submit-only") == queued
    assert control("resume", queued["run_id"])["state"] == "succeeded"
    assert run("-m", "agent_app.tool_graph")["credits_spent"] == 2
    # Missing original version refuses execution; observation alone still works.
    path.write_text(
        'schema_version = 1\n[default]\nname = "async-tool-orders"\nversion = "2"\n' + replacement
    )
    assert control("inspect", queued["run_id"])["state"] == "succeeded"
    assert control("resume", queued["run_id"], code=2)["code"] == "definition_mismatch"
