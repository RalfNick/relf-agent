"""Run the editable component through the installed suite, never a supplied verdict."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_editable_independent_node_example_passes_original_suite_and_retains_evidence(tmp_path):
    script = Path(__file__).parents[1] / "examples/node_executor_contract.py"
    assert script.is_file(), "Editable independent node example is missing"
    evidence = tmp_path / "evidence"
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "TMPDIR", "LANG"}}
    result = subprocess.run(
        [sys.executable, str(script), "--evidence-dir", str(evidence)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["role"] == "node-executor" and report["status"] == "passed"
    assert report["passed"] == report["total"] == 10
    assert report["failed"] == report["not_verified"] == 0
    assert len(list(evidence.glob("N*/result.json"))) == 10
    assert all(item["observations"]["cleanup_complete"] for item in report["cases"])
