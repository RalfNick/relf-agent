"""A release-quality claim must retain every frozen repeat and required check."""

import asyncio
import copy
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


def tool():
    path = Path(__file__).parents[1] / "tools/evaluate_default_chains.py"
    spec = importlib.util.spec_from_file_location("default_chains_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    names = ["case-" + str(i) for i in range(8)]
    expected = {
        "name": "business",
        "case_ids": names,
        "dataset_sha256": "a" * 64,
        "kind": "business-task-evaluation",
        "checks": ["task_success", "tool_arguments", "stop", "approval", "recovery"],
        "limits": {
            "repeats": 3,
            "max_calls": 96,
            "max_cases": 8,
            "max_output_tokens": 2048,
            "timeout_seconds": 45,
            "max_cost_usd": None,
        },
        "provider": {
            "kind": "deepseek-chat-completions",
            "model": "deepseek-flash",
            "json_mode": True,
            "max_output_tokens": 2048,
            "timeout": 45,
            "generation": {"temperature": 0},
        },
        "required_flags": {},
    }
    rows = [
        {
            "case_id": name,
            "repeat": repeat,
            "passed": True,
            "calls": 1,
            "state": "succeeded",
            "metrics": dict.fromkeys(expected["checks"], True),
            "latency_ms": 1,
            "replay_same_receipt": True,
            "recovered_after_restart": True,
        }
        for name in names
        for repeat in range(3)
    ]
    report = {
        "kind": expected["kind"],
        "dataset_sha256": expected["dataset_sha256"],
        "offline": False,
        "model_quality": {"task_success_rate": 1},
        "status": "completed",
        "cases": rows,
        "limits": copy.deepcopy(expected["limits"]),
        "provider": copy.deepcopy(expected["provider"]),
        "passed": 24,
        "total": 24,
        "calls": 24,
        "usage": None,
        "cost_usd": None,
    }
    return report, expected


def test_complete_frozen_live_rows_pass_without_inventing_unknown_cost():
    report, expected = fixture()
    result = tool().assess_chain(report, expected)
    assert result["accepted"] and result["total"] == 24
    assert result["cost_usd"] is None and result["usage"] is None


def test_one_bad_repeat_cannot_hide_behind_overall_ninety_percent():
    report, expected = fixture()
    report["cases"][0]["passed"] = False
    report["cases"][0]["metrics"]["task_success"] = False
    report["passed"] = 23
    report["model_quality"]["task_success_rate"] = 23 / 24
    result = tool().assess_chain(report, expected)
    assert result["overall_rate"] > 0.9 and not result["accepted"]
    assert result["per_case"]["case-0"]["passed"] == 2


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "unattempted",
        "false-recovery",
        "missing-check",
        "offline",
        "no-quality",
        "dataset",
        "config",
        "aggregate",
        "nan",
        "bool-count",
    ],
)
def test_incomplete_or_false_quality_evidence_never_passes(change):
    report, expected = fixture()
    if change == "missing":
        report["cases"].pop()
    elif change == "duplicate":
        report["cases"][-1] = copy.deepcopy(report["cases"][0])
    elif change == "unattempted":
        report["cases"][0]["calls"] = 0
    elif change == "false-recovery":
        report["cases"][0]["recovered_after_restart"] = False
    elif change == "missing-check":
        report["cases"][0]["metrics"].pop("approval")
    elif change == "offline":
        report["offline"] = True
    elif change == "no-quality":
        report["model_quality"] = None
    elif change == "dataset":
        report["dataset_sha256"] = "b" * 64
    elif change == "config":
        report["provider"]["json_mode"] = False
    elif change == "aggregate":
        report["passed"] = 25
    elif change == "nan":
        report["cases"][0]["latency_ms"] = float("nan")
    elif change == "bool-count":
        report["cases"][0]["calls"] = True
    assert not tool().assess_chain(report, expected)["accepted"]


def test_semantic_claim_requires_real_embedding_and_visible_citation_checks():
    report, expected = fixture()
    expected.update(
        name="rag",
        checks=[
            "answer",
            "citation_validity",
            "citation_coverage",
            "decision",
            "pipeline",
            "retrieval_support",
            "recovery",
        ],
    )
    for row in report["cases"]:
        row["checks"] = dict.fromkeys(expected["checks"], True)
        row.pop("metrics")
        row["recovery"] = {"additional_model_calls": 0, "additional_embedding_calls": 0}
    report.update(
        semantic_quality={"offered_support_recall": 1}, embedding={"offline_baseline": False}
    )
    assert tool().assess_chain(report, expected)["accepted"]
    report["embedding"]["offline_baseline"] = True
    assert not tool().assess_chain(report, expected)["accepted"]
    report["embedding"]["offline_baseline"] = False
    report["cases"][0]["checks"]["citation_validity"] = False
    assert not tool().assess_chain(report, expected)["accepted"]


def test_real_disabled_json_mode_identity_keeps_its_existing_omission():
    from relf_agent.planning_evaluation import _safe_identity
    from relf_agent.providers import DeepSeekChatProvider

    report, expected = fixture()
    report["provider"] = _safe_identity(
        DeepSeekChatProvider(
            "deepseek-flash",
            api_key="synthetic",
            json_mode=False,
            max_output_tokens=2048,
            timeout=45,
            temperature=0,
        )
    )
    assert "json_mode" not in report["provider"]
    expected["provider"]["json_mode"] = False
    assert tool().assess_chain(report, expected)["accepted"]


def test_frozen_call_limit_is_not_just_an_aggregate_consistency_check():
    report, expected = fixture()
    report["cases"][0]["calls"] = 97
    report["calls"] = 120
    assert not tool().assess_chain(report, expected)["accepted"]


@pytest.mark.parametrize(
    "change", ["json-bool", "temperature-bool", "flag-int", "quality-empty", "state-failed"]
)
def test_config_and_quality_claims_require_their_exact_meaning(change):
    report, expected = fixture()
    if change == "json-bool":
        report["provider"]["json_mode"] = 1
    elif change == "temperature-bool":
        report["provider"]["generation"]["temperature"] = False
    elif change == "flag-int":
        expected["required_flags"] = {"typed_answers": True}
        report["typed_answers"] = 1
    elif change == "quality-empty":
        report["model_quality"] = {}
    elif change == "state-failed":
        report["cases"][0]["state"] = "failed"
    assert not tool().assess_chain(report, expected)["accepted"]


def test_a_different_model_cannot_be_frozen_as_this_batch():
    with pytest.raises(ValueError, match="fixed"):
        tool().prepare(SimpleNamespace(model="another-model"))


def test_physical_accounting_is_a_separate_required_delivery_gate():
    report, expected = fixture()
    measure = {
        "http_request_count": 24,
        "http_requests": [{"status_code": 200}] * 24,
        "engine_sync_control_invocations": {"submit": 72},
    }
    module = tool()
    assert module.assess_measurements(measure, report, expected)
    measure["http_request_count"] = 23
    assert not module.assess_measurements(measure, report, expected)


def test_native_probe_has_a_whole_call_bound_and_closes_original_source():
    module, closed = tool(), []
    module.PROBE_TIMEOUT_SECONDS = 0.01

    class Provider:
        def stream(self, messages, tools):
            async def source():
                try:
                    await asyncio.sleep(10)
                    yield None
                finally:
                    closed.append(True)

            return source()

    async def run():
        started = time.perf_counter()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(module.stream_probe(Provider()), 0.5)
        assert time.perf_counter() - started < 0.25
        assert closed == [True]

    asyncio.run(run())


def test_offline_rehearsal_failure_has_a_nonzero_exit_without_reading_credentials(
    monkeypatch, tmp_path
):
    module = tool()

    async def run(args, key, prepared):
        assert key is None
        return {
            "quality_accepted": False,
            "chains": {name: {"passed": 0, "total": 3} for name in module.CHAINS},
        }

    monkeypatch.setattr(module, "run", run)
    monkeypatch.setattr(module, "prepare", lambda args: None)
    monkeypatch.setattr(
        module.getpass, "getpass", lambda *args: pytest.fail("offline must not ask for credentials")
    )
    assert (
        module.main(
            [
                "--offline",
                "--wheel",
                "unused",
                "--model-directory",
                "unused",
                "--output",
                str(tmp_path),
            ]
        )
        == 1
    )
