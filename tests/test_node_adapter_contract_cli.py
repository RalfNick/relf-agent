"""Node checks run only through an explicitly selected fixture."""

import asyncio
import json
import sqlite3
import sys
from types import ModuleType

import pytest

from relf_agent.adapter_contract_cli import main


def test_node_cli_without_offline_reports_ten_unconfigured_cases_without_io(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    assert main(["--role", "node-executor", "--evidence-dir", "evidence"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["role"], report["profile"], report["status"]) == (
        "node-executor",
        "core",
        "not_run",
    )
    assert report["reason"] == "adapter_not_configured"
    assert [case["case_id"] for case in report["cases"]] == [f"N{i:02}" for i in range(1, 11)]
    assert all(case["status"] == "not_verified" for case in report["cases"])
    assert report["model_quality"] is None and report["semantic_quality"] is None
    assert list(tmp_path.iterdir()) == []


def test_explicit_node_offline_cli_selects_independent_node_reference(monkeypatch):
    class SelectedNodeReference(Exception):
        pass

    module = ModuleType("relf_agent.node_adapter_contract_reference")

    def offline_node_fixture():
        raise SelectedNodeReference

    module.offline_node_fixture = offline_node_fixture
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with pytest.raises(SelectedNodeReference):
        main(["--role", "node-executor", "--offline"])


@pytest.mark.parametrize(
    "arguments",
    [["--role", "unknown", "--offline"], ["--role", "node-executor", "--profile", "tools"]],
)
def test_unknown_role_or_unsupported_node_profile_is_public_validation(arguments, capsys):
    assert main(arguments) == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "invalid",
        "reason": "invalid_contract_configuration",
    }


def test_public_node_offline_fixture_is_inert_and_unconfigured_suite_stays_not_run(
    tmp_path, monkeypatch
):
    import relf_agent

    assert "offline_node_fixture" in relf_agent.__all__
    helper = getattr(relf_agent, "offline_node_fixture", None)
    assert callable(helper), "Missing public offline_node_fixture helper"

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Selecting an offline fixture must not open SQLite")

    monkeypatch.setattr(sqlite3, "connect", unexpected_connection)
    assert helper() is not None
    suite = relf_agent.AdapterContractSuite(role="node-executor")
    report = asyncio.run(suite.run(evidence_dir=tmp_path / "evidence")).to_dict()
    assert report["status"] == "not_run"
    assert report["reason"] == "adapter_not_configured"
    assert all(case["code"] == "adapter_not_configured" for case in report["cases"])
    assert list(tmp_path.iterdir()) == []


def test_public_node_offline_fixture_runs_all_ten_real_core_cases(tmp_path):
    import relf_agent

    helper = getattr(relf_agent, "offline_node_fixture", None)
    assert callable(helper), "Missing public offline_node_fixture helper"

    async def run():
        suite = relf_agent.AdapterContractSuite(role="node-executor", profile="core")
        try:
            return await suite.run(fixture=helper(), evidence_dir=tmp_path / "evidence")
        finally:
            await suite.aclose()

    report = asyncio.run(run()).to_dict()
    assert report["status"] == "passed", report
    assert [case["case_id"] for case in report["cases"]] == [f"N{i:02}" for i in range(1, 11)]
    assert all(case["status"] == "passed" for case in report["cases"])
    assert all((tmp_path / "evidence" / f"N{i:02}" / "result.json").is_file() for i in range(1, 11))
