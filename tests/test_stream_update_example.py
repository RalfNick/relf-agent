import json
import os
import subprocess
import sys
from pathlib import Path


def test_offline_example_installed_path_and_original_command_replay(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/stream_updates.py"
    application = tmp_path / "app.py"
    application.write_bytes(source.read_bytes())
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    # Source pytest needs its explicit source path; installed checks have no src.
    import relf_agent

    package_parent = Path(relf_agent.__file__).resolve().parent.parent
    if package_parent.name == "src":
        env["PYTHONPATH"] = str(package_parent)
    results = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, str(application), "--db", str(tmp_path / "runs.sqlite")],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        records = [json.loads(line) for line in result.stdout.splitlines()]
        assert {row["kind"] for row in records[:-1]} >= {
            "model_delta",
            "tool_delta",
            "model_end",
            "tool_end",
        }
        results.append(records)
    assert results[0][-1]["state"] == results[1][-1]["state"] == "succeeded"
    assert results[0][-1]["run_id"] == results[1][-1]["run_id"]
    assert results[0][-1]["model_calls"] == 2 and results[0][-1]["tool_calls"] == 1
    assert results[1][-1]["model_calls"] == results[1][-1]["tool_calls"] == 0
    assert results[0][:-1] == results[1][:-1]
