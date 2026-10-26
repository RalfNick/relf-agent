"""Alpha 8 packaging must retain technical identity and work on PyPI."""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_alpha8_metadata_and_installed_entry_version_agree():
    import relf_agent

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == relf_agent.__version__ == "0.1.0a8"
    assert project["name"] == "relf-agent"
    assert project["scripts"]["relf"] == "relf_agent.cli:main"
    assert project["description"].startswith("Relf-Agent:")
    assert project["urls"]["Repository"] == "https://github.com/RalfNick/relf-agent"
    assert project["urls"]["Issues"] == "https://github.com/RalfNick/relf-agent/issues"


def test_package_long_description_document_links_resolve_outside_github():
    readme = (ROOT / "README.md").read_text()
    links = re.findall(r"\]\(([^)]+)\)", readme)
    relative = [url for url in links if not url.startswith(("https://", "http://", "#"))]
    assert relative == [], f"PyPI cannot resolve repository-relative links: {relative}"
    assert "0.1.0a8" in readme
    assert "Reliable and Extensible Lifecycle Framework for Intelligent Agents" in readme


def test_frozen_readme_does_not_turn_into_a_false_unpublished_notice_after_upload():
    readme = (ROOT / "README.md").read_text()
    for stale_status in ("尚未推送或发布", "尚未发布到PyPI", "PyPI 尚未发布", "本候选尚未公开发布"):
        assert stale_status not in readme


def test_gate_can_inspect_an_explicit_manifest_without_changing_historical_default(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version":"0.1.0a8","artifacts":{}}\n')
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/release_gate.py"),
            "--plan",
            "--manifest",
            str(manifest),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert run.returncode == 0, run.stderr
    import json

    assert json.loads(run.stdout) == {"version": "0.1.0a8", "artifacts": {}}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["manifest.json"]


def test_interruption_gate_matches_real_pytest_collection():
    import json

    # Exercise the actual selector and the same sorted-node boundary as the installed gate.
    spec = json.loads((ROOT / "tools/release_gate_manifest.alpha8.json").read_text())
    phase = spec["tests"]["interruptions"]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only", *phase["selectors"]],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    import importlib.util

    loader = importlib.util.spec_from_file_location(
        "a7_collection_gate", ROOT / "tools/release_gate.py"
    )
    gate = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(gate)
    assert len(gate.check_collection(result.stdout, phase)) == 9


def test_a8_freezes_recent_cleanup_regressions_without_reducing_original_gate():
    import hashlib
    import importlib.util
    import json

    spec = json.loads((ROOT / "tools/release_gate_manifest.alpha8.json").read_text())
    old = json.loads((ROOT / "tools/release_gate_manifest.alpha7.json").read_text())
    assert spec["version"] == "0.1.0a8"
    assert spec["artifact_source_commit"] == "ac920069e206f39d75ef0ab334f41b0619ca5a27"
    assert spec["product_files"] == 442
    assert spec["test_corrections"] == []
    for phase in ("main", "related", "interruptions"):
        assert spec["tests"][phase] == old["tests"][phase]
    assert spec["linux_container_limits"] == old["linux_container_limits"]
    assert spec["linux_arm64_images"] == old["linux_arm64_images"]
    assert spec["linux_amd64_images"] == old["linux_amd64_images"]
    assert spec["tests"]["ownership"]["selectors"] == ["tests/test_runtime_failure_ownership.py"]
    assert spec["tests"]["cli_factory"]["selectors"] == ["tests/test_cli_factory_cleanup.py"]
    loader = importlib.util.spec_from_file_location(
        "a8_collection_gate", ROOT / "tools/release_gate.py"
    )
    gate = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(gate)
    for name, count in (("ownership", 21), ("cli_factory", 13)):
        phase = spec["tests"][name]
        assert phase["count"] == count
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--collect-only", *phase["selectors"]],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert len(gate.check_collection(result.stdout, phase)) == count
    assert (
        hashlib.sha256((ROOT / "tools/release_gate_manifest.alpha7.json").read_bytes()).hexdigest()
        == "41ebadcb3ac263a8b1cded3b0b0edbe9067e2a598caaccecdd9b192d7e0aa7f7"
    )
