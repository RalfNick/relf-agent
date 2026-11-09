"""Node requirements remain separate from every published adapter catalog."""

import asyncio
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from relf_agent.adapter_contract_catalog import catalog_for, catalog_for_case
from relf_agent.adapter_contract_types import AdapterContractCaseResult
from relf_agent.adapter_contracts import AdapterContractSuite, _run_case
from relf_agent.errors import ValidationError

NODE_CASES = (
    ("N01", "identity-and-port"),
    ("N02", "finite-json-and-config"),
    ("N03", "input-schema"),
    ("N04", "config-schema"),
    ("N05", "completed-output-schema"),
    ("N06", "identity-drift"),
    ("N07", "method-drift"),
    ("N08", "handler-errors"),
    ("N09", "approval-budget-and-reopen"),
    ("N10", "cancellation-and-ownership"),
)
NODE_COUNTS = {
    "execute_calls",
    "reconcile_calls",
    "close_calls",
    "tool_calls",
    "model_calls",
    "source_checks",
    "rejection_checks",
    "schema_checks",
    "duplicate_checks",
    "settlement_checks",
}
BOOLEAN_OBSERVATIONS = {
    "runtime_closed",
    "borrowed_closed",
    "handler_finished",
    "cancelled",
    "cleanup_complete",
    "ports_valid",
    "identity_valid",
}


def test_node_catalog_fixes_ten_requirements_and_separate_observation_fields():
    catalog = catalog_for("node-executor", "1", "core")
    assert catalog.cases == NODE_CASES
    assert catalog.case_ids == tuple(f"N{index:02}" for index in range(1, 11))
    assert dict(catalog.labels) == dict(NODE_CASES)
    assert catalog.boolean_observations == BOOLEAN_OBSERVATIONS
    assert catalog.count_observations == NODE_COUNTS
    assert catalog.observation_keys == BOOLEAN_OBSERVATIONS | NODE_COUNTS
    assert (
        catalog.suite_digest == "bc03f5f053143fbdf78ce5bfb77be2ef7849a262ce47e263c07593e69ae1e88f"
    )
    for case_id, label in NODE_CASES:
        assert catalog_for_case(case_id) is catalog
        assert catalog_for_case(case_id).labels[case_id] == label
    with pytest.raises(FrozenInstanceError):
        catalog.profile = "receipts"
    with pytest.raises(TypeError):
        catalog.labels["N01"] = "fixture-verdict"


@pytest.mark.parametrize(
    "role,profile,digest",
    [
        (
            "knowledge-retriever",
            "core",
            "75b02ce8f33a8b8ca99dcdb4a3b9e7f394ceefbf41ea6b31dd22f5c063e56349",
        ),
        (
            "session-store",
            "core",
            "b37cdc0626c7a5ad826cf42456674240d5aa3f053f7161038e06c2faea4c4eaa",
        ),
        (
            "session-store",
            "receipts",
            "2477d0250679d77270f3768f88c9fae691a0cc0e52b16f4d1551f4809281cca9",
        ),
        ("facts-store", "core", "804de8257a8d85015d95163951e08ccaf3f383e359bd3e668ec37cce82c3bb95"),
        (
            "facts-store",
            "managed",
            "da4a9fe8660d5629ffeab856398cb66abeb749564a6bd656693e8f0b65aaca01",
        ),
        (
            "model-provider",
            "core",
            "1a36404389335cbe6e2ab30f6a92dccd89252f637c8a6cef0289c1e2ee820850",
        ),
        (
            "model-provider",
            "tools",
            "4fc9ef0ca0dbc59924fd5160d4fe8b5590e7f3db17df461feebd1b630becd2b6",
        ),
    ],
)
def test_node_extension_preserves_every_original_catalog_digest(role, profile, digest):
    assert catalog_for(role, "1", profile).suite_digest == digest


@pytest.mark.parametrize("version,profile", [("2", "core"), ("1", "tools"), ("1", "receipts")])
def test_node_suite_requires_its_explicit_version_and_core_profile(version, profile):
    with pytest.raises(ValidationError):
        AdapterContractSuite(role="node-executor", contract_version=version, profile=profile)


def test_node_case_observations_accept_only_bounded_node_fields():
    result = AdapterContractCaseResult(
        "N02", "passed", "verified", {"execute_calls": 6, "schema_checks": 1, "ports_valid": True}
    )
    assert result.to_dict()["label"] == "finite-json-and-config"
    for observations in ({"retrieve_calls": 1}, {"execute_calls": True}, {"schema_checks": -1}):
        with pytest.raises(ValidationError):
            AdapterContractCaseResult("N02", "passed", "verified", observations)


def test_unconfigured_node_suite_does_not_create_workspace_or_dispatch(tmp_path, monkeypatch):
    def unexpected_io(*args, **kwargs):
        raise AssertionError("An unconfigured Node suite must not perform testing I/O")

    monkeypatch.setattr(Path, "mkdir", unexpected_io)
    monkeypatch.setattr("relf_agent.adapter_contracts.tempfile.TemporaryDirectory", unexpected_io)
    monkeypatch.setattr("relf_agent.adapter_contracts._run_case", unexpected_io)
    suite = AdapterContractSuite(role="node-executor")
    report = asyncio.run(suite.run(evidence_dir=tmp_path / "evidence")).to_dict()
    assert report["status"] == "not_run"
    assert report["reason"] == "adapter_not_configured"
    assert [case["case_id"] for case in report["cases"]] == [f"N{i:02}" for i in range(1, 11)]
    assert all(case["code"] == "adapter_not_configured" for case in report["cases"])
    assert list(tmp_path.iterdir()) == []


def test_node_dispatch_uses_the_node_checker(tmp_path, monkeypatch):
    fixture = object()
    expected = AdapterContractCaseResult("N01", "not_verified", "missing_fixture_capability")
    module = ModuleType("relf_agent.node_adapter_contract")

    async def run_node_case(case_id, actual_fixture, workspace):
        assert (case_id, actual_fixture, workspace) == ("N01", fixture, tmp_path)
        return expected

    module.run_node_case = run_node_case
    monkeypatch.setitem(sys.modules, module.__name__, module)
    assert asyncio.run(_run_case("N01", fixture, tmp_path)) is expected


def test_unknown_dispatch_role_cannot_fall_through_to_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "relf_agent.adapter_contracts.catalog_for_case",
        lambda case_id: SimpleNamespace(role="unknown"),
    )

    async def unexpected_model_case(*args):
        raise AssertionError("An unknown adapter role reached the model checker")

    monkeypatch.setattr("relf_agent.model_adapter_contract.run_model_case", unexpected_model_case)
    with pytest.raises(ValidationError):
        asyncio.run(_run_case("unknown", object(), tmp_path))


@pytest.mark.parametrize(
    "name",
    ["NodeAdapterFixture", "NodeContractResource", "NodeContractPause", "NodeContractSession"],
)
def test_node_fixture_types_have_public_sdk_exports(name):
    import relf_agent

    assert name in relf_agent.__all__
    assert hasattr(relf_agent, name)
