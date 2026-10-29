"""Run the frozen four-chain acceptance with an explicitly installed SDK.

No runtime changes, prompt tuning, hidden retries or credential discovery.
Use --offline for rehearsal; --live explicitly permits supplier requests.
"""

import argparse
import asyncio
import getpass
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
import resource
import sys
import threading
import time
from collections import Counter
from pathlib import Path

WHEEL_SHA256 = "3ca80c594b9d5e18946f4c016c41655754baee6284c8b96d05bc1107b9f64463"
VERSION = "0.1.0a8+maintenance.54f45574ad74b3af"
MODEL = "deepseek-flash"
PROBE_TIMEOUT_SECONDS = 45
CHAINS = ("business", "rag", "plan", "team")
CHECKS = {
    "business": ("task_success", "tool_arguments", "stop", "approval", "recovery"),
    "rag": (
        "answer",
        "citation_validity",
        "citation_coverage",
        "decision",
        "pipeline",
        "retrieval_support",
        "recovery",
    ),
    "plan": (
        "status",
        "total",
        "stopped",
        "lookup_receipt",
        "calculator_receipt",
        "prior_evidence",
        "managed_members",
        "recovery",
        "current_lineage",
        "parent_completion",
    ),
}
CHECKS["team"] = CHECKS["plan"]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as stream:
        stream.write(encoded + "\n")


def same_json(actual, expected):
    """JSON numbers may compare numerically; booleans never stand for numbers."""
    if type(expected) is bool:
        return actual is expected
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and actual == expected
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(same_json(actual[k], v) for k, v in expected.items())
        )
    return type(actual) is type(expected) and actual == expected


def assess_chain(report, expected):
    """Audit report claims against the pre-run selection, not aggregate green."""
    reasons = set()
    ids, repeats = expected["case_ids"], expected["limits"]["repeats"]
    frozen = {(name, repeat) for name in ids for repeat in range(repeats)}
    rows, seen, per_case = (
        report.get("cases", []),
        set(),
        {name: {"passed": 0, "total": repeats} for name in ids},
    )
    if report.get("offline") is not False or not isinstance(report.get("model_quality"), dict):
        reasons.add("not_live_quality")
    if report.get("status") != "completed" or report.get("kind") != expected["kind"]:
        reasons.add("incomplete_report")
    if report.get("dataset_sha256") != expected["dataset_sha256"]:
        reasons.add("dataset_mismatch")
    if not same_json(report.get("limits"), expected["limits"]):
        reasons.add("configuration_mismatch")
    provider = report.get("provider", {})
    if provider.get("offline_fixture") is True or any(
        not same_json(provider.get(k, False) if k == "json_mode" else provider.get(k), v)
        for k, v in expected["provider"].items()
    ):
        reasons.add("configuration_mismatch")
    for key, value in expected["required_flags"].items():
        if not same_json(report.get(key), value):
            reasons.add("configuration_mismatch")
    if expected["name"] == "rag" and (
        not isinstance(report.get("semantic_quality"), dict)
        or report.get("embedding", {}).get("offline_baseline") is not False
    ):
        reasons.add("not_semantic_quality")
    passed = calls = declared_passed = 0
    for row in rows:
        if not isinstance(row, dict):
            reasons.add("invalid_row")
            continue
        key = (row.get("case_id"), row.get("repeat"))
        if type(key[0]) is not str or type(key[1]) is not int or key not in frozen or key in seen:
            reasons.add("selection_mismatch")
            continue
        seen.add(key)
        checks = row.get("metrics" if expected["name"] == "business" else "checks", {})
        valid = isinstance(checks, dict) and all(
            checks.get(name) is True for name in expected["checks"]
        )
        if not valid:
            reasons.add("required_check_failed")
        valid &= row.get("state") == "succeeded"
        count = row.get("calls")
        latency = row.get("latency_ms")
        if (
            type(count) is not int
            or count < 1
            or type(latency) not in (int, float)
            or not math.isfinite(latency)
            or latency < 0
        ):
            reasons.add("invalid_measurement")
            valid = False
        else:
            calls += count
        if row.get("replay_same_receipt") is not True:
            valid = False
        if expected["name"] == "rag":
            recovery = row.get("recovery", {})
            if set(recovery) != {"additional_model_calls", "additional_embedding_calls"} or any(
                type(v) is not int or v != 0 for v in recovery.values()
            ):
                valid = False
        elif row.get("recovered_after_restart") is not True:
            valid = False
        if not valid:
            reasons.add("row_evidence_failed")
        claim = row.get("passed")
        declared_passed += claim is True
        if type(claim) is not bool or claim != valid:
            reasons.add("row_claim_mismatch")
        if claim is True and valid:
            passed += 1
            per_case[key[0]]["passed"] += 1
    if seen != frozen:
        reasons.add("selection_mismatch")
    if (
        type(report.get("passed")) is not int
        or report["passed"] != declared_passed
        or type(report.get("total")) is not int
        or report["total"] != len(frozen)
        or type(report.get("calls")) is not int
        or report["calls"] != calls
    ):
        reasons.add("aggregate_mismatch")
    rate = passed / len(frozen)
    if calls > expected["limits"]["max_calls"]:
        reasons.add("call_limit_exceeded")
    quality = report.get("model_quality")
    if not isinstance(quality, dict) or not same_json(
        quality.get("task_success_rate"), declared_passed / len(frozen)
    ):
        reasons.add("quality_claim_mismatch")
    if rate < 0.9:
        reasons.add("overall_rate_below_threshold")
    if any(row["passed"] / repeats < 0.8 for row in per_case.values()):
        reasons.add("case_rate_below_threshold")
    # Missing usage/cost remains unknown and is not made a zero-charge claim.
    return {
        "accepted": not reasons,
        "reasons": sorted(reasons),
        "passed": passed,
        "total": len(frozen),
        "overall_rate": rate,
        "per_case": per_case,
        "calls": calls,
        "usage": report.get("usage"),
        "cost_usd": report.get("cost_usd"),
    }


def assess_measurements(measure, report, expected):
    count, requests = measure.get("http_request_count"), measure.get("http_requests")
    controls = measure.get("engine_sync_control_invocations", {})
    return (
        type(count) is int
        and 0 < count <= expected["limits"]["max_calls"]
        and count == report.get("calls")
        and isinstance(requests, list)
        and len(requests) == count
        and all(row.get("status_code") == 200 for row in requests)
        and isinstance(controls, dict)
        and type(controls.get("submit")) is int
        and controls["submit"] > 0
        and all(type(v) is int and v >= 0 for v in controls.values())
    )


class Measurements:
    """Count original sync Engine bodies without replacing them or reading args."""

    def __init__(self):
        from relf_agent import LocalEngine

        # Retain actual code objects so their identities cannot be recycled.
        # Hashing CodeType walks constants and may execute unrelated __hash__.
        self.originals = tuple(
            (inspect.unwrap(getattr(LocalEngine, name)).__code__, name)
            for name in ("submit", "approve", "cancel", "reconcile", "status", "diagnostics")
        )
        self.codes = {id(code): name for code, name in self.originals}
        self.controls = Counter()
        self.requests = []
        self.thread = threading.get_ident()
        self.monitoring = None
        self.owner_name = "relf-evaluation-controls-" + str(id(self))
        self.owned = self.registered = False
        self.active = False
        self.locals = []
        self.prior_callback = None

    def profile(self, frame, event, arg):
        if event == "call" and threading.get_ident() == self.thread:
            name = self.codes.get(id(frame.f_code))
            if name is not None:
                self.controls[name] += 1

    def on_start(self, code, offset):
        if threading.get_ident() == self.thread:
            name = self.codes.get(id(code))
            if name is not None:
                self.controls[name] += 1

    def release_monitor(self):
        monitoring = self.monitoring
        if not self.owned:
            return
        if monitoring.get_tool(monitoring.PROFILER_ID) != self.owner_name:
            raise RuntimeError("Control observer ownership changed")
        for code in self.locals:
            monitoring.set_local_events(monitoring.PROFILER_ID, code, 0)
        self.locals.clear()
        if self.registered:
            monitoring.register_callback(
                monitoring.PROFILER_ID, monitoring.events.PY_START, self.prior_callback
            )
            self.registered = False
        monitoring.free_tool_id(monitoring.PROFILER_ID)
        self.owned = False

    async def on_request(self, request):
        request.extensions["evaluation_request_index"] = len(self.requests)
        self.requests.append(
            {
                "started_seconds": time.perf_counter() - self.started,
                "headers_seconds": None,
                "status_code": None,
            }
        )

    async def on_response(self, response):
        row = self.requests[response.request.extensions["evaluation_request_index"]]
        row.update(
            headers_seconds=time.perf_counter() - self.started, status_code=response.status_code
        )

    def __enter__(self):
        if self.active or self.owned:
            raise RuntimeError("Control observer is already active")
        self.started, self.cpu = time.perf_counter(), resource.getrusage(resource.RUSAGE_SELF)
        self.previous = sys.getprofile()
        if self.previous is not None:
            raise RuntimeError("Existing profiler is active")
        self.thread = threading.get_ident()
        self.monitoring = getattr(sys, "monitoring", None)
        if self.monitoring is None:
            self.backend = "sys.setprofile-code-identity"
            sys.setprofile(self.profile)
            self.active = True
            return self
        monitoring = self.monitoring
        owner = monitoring.PROFILER_ID
        if monitoring.get_tool(owner) is not None or monitoring.get_events(owner):
            raise RuntimeError("Control monitoring slot is already in use")
        monitoring.use_tool_id(owner, self.owner_name)
        self.owned = True
        try:
            self.prior_callback = monitoring.register_callback(
                owner, monitoring.events.PY_START, self.on_start
            )
            self.registered = True
            if self.prior_callback is not None:
                raise RuntimeError("Foreign callback remains registered")
            for code, _ in self.originals:
                if monitoring.get_local_events(owner, code):
                    raise RuntimeError("Foreign local events remain registered")
                self.locals.append(code)
                monitoring.set_local_events(owner, code, monitoring.events.PY_START)
        except BaseException:
            self.release_monitor()
            raise
        self.backend = "sys.monitoring-local-py-start"
        self.active = True
        return self

    def __exit__(self, *args):
        if self.monitoring is None:
            sys.setprofile(self.previous)
        else:
            self.release_monitor()
        self.active = False

    def result(self):
        used = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "total_seconds": time.perf_counter() - self.started,
            "cpu_user_seconds": used.ru_utime - self.cpu.ru_utime,
            "cpu_system_seconds": used.ru_stime - self.cpu.ru_stime,
            "process_high_water_rss_bytes": used.ru_maxrss
            * (1 if platform.system() == "Darwin" else 1024),
            "engine_sync_control_invocations": dict(self.controls),
            "control_scope": "owning thread, original LocalEngine sync bodies including internal calls; excludes async drive and transport queries",
            "http_requests": self.requests,
            "http_request_count": len(self.requests),
            "first_incremental_text_seconds": None,
            "incremental_text_reason": "non-streaming default quality configuration",
            "profiling_enabled": True,
            "control_observer": self.backend,
            "all_python_frames_profiled": self.backend == "sys.setprofile-code-identity",
            "performance_improvement_claimed": False,
        }


def business_verifier():
    from relf_agent.completion import ToolReceiptVerifier

    return ToolReceiptVerifier(
        "apply_fix",
        when={
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"const": "resolved"}},
        },
        result_schema={
            "type": "object",
            "required": ["applied"],
            "properties": {"applied": {"const": True}},
        },
        argument_bindings={"ticket_id": "/ticket_id", "fix": "/fix"},
    )


def inputs(model):
    from relf_agent.business_evaluation import load_business_cases
    from relf_agent.orchestration_evaluation import load_orchestration_cases
    from relf_agent.planning_evaluation import _safe_identity
    from relf_agent.providers import DeepSeekChatProvider
    from relf_agent.rag_evaluation_cases import load_rag_cases
    from relf_agent.types import digest

    datasets = {
        "business": load_business_cases(),
        "rag": load_rag_cases(),
        "plan": load_orchestration_cases(),
        "team": load_orchestration_cases(),
    }
    specs = {}
    for name, cases in datasets.items():
        flags = (
            {"typed_answers": True}
            if name == "rag"
            else (
                {
                    "completion_gate": True,
                    "member_verification": True,
                    "orchestration_kind": "plan-and-execute" if name == "plan" else "team",
                }
                if name in ("plan", "team")
                else {}
            )
        )
        if name == "business":
            verifier = business_verifier()
            flags = {
                "completion_verifier": {
                    "kind": verifier.identity["kind"],
                    "identity_digest": digest(verifier.identity),
                }
            }
        declared = _safe_identity(
            DeepSeekChatProvider(
                model,
                api_key="configuration-only",
                base_url="https://api.deepseek.com",
                json_mode=name in ("business", "rag"),
                max_output_tokens=2048,
                timeout=45,
                temperature=0,
            )
        )
        specs[name] = {
            "name": name,
            "case_ids": [c["id"] for c in cases],
            "checks": CHECKS[name],
            "dataset_sha256": digest({"version": "1", "cases": cases}),
            "kind": "business-task-evaluation"
            if name == "business"
            else ("rag-task-evaluation" if name == "rag" else "orchestration-task-evaluation"),
            "limits": {
                "max_cases": len(cases),
                "repeats": 3,
                "max_calls": 96,
                "max_output_tokens": 2048,
                "timeout_seconds": 45,
                "max_cost_usd": None,
            },
            "provider": {**declared, "json_mode": name in ("business", "rag")},
            "required_flags": flags,
        }
    return datasets, specs


async def evaluate(name, provider, cases, limits, evidence, model_directory):
    if name == "business":
        from relf_agent.business_evaluation import evaluate_business

        verifier = business_verifier()
        return await evaluate_business(
            provider,
            cases=cases,
            limits=limits,
            evidence_dir=evidence,
            completion_verifier=verifier,
        )
    if name == "rag":
        from relf_agent.semantic_rag_reference import evaluate_semantic_rag

        return await evaluate_semantic_rag(
            provider,
            cases=cases,
            limits=limits,
            model_directory=model_directory,
            evidence_dir=evidence,
            typed_answers=True,
            max_embedding_calls=128,
        )
    from relf_agent.orchestration_evaluation import evaluate_orchestration

    return await evaluate_orchestration(
        provider,
        cases=cases,
        limits=limits,
        evidence_dir=evidence,
        kind="plan-and-execute" if name == "plan" else "team",
        completion_gate=True,
        member_verification=True,
    )


async def stream_probe(provider):
    """One extra read-only native stream, separate from scored task Runs."""
    started, first, final = time.perf_counter(), None, None
    source = provider.stream(
        [{"role": "user", "content": 'Return exactly {"status":"ready"} as JSON.'}], []
    )
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            async for event in source:
                if event.kind == "text" and event.text and first is None:
                    first = time.perf_counter() - started
                elif event.kind == "response":
                    final = event.response
    finally:
        await source.aclose()
    return {
        "status": "completed" if final is not None else "incomplete",
        "first_incremental_text_seconds": first,
        "total_seconds": time.perf_counter() - started,
        "usage": None if final is None else final.usage,
        "generation_requests": 1,
        "separate_from_quality_scores": True,
        "framework_task_run": False,
    }


def prepare(args):
    if args.model != MODEL:
        raise ValueError("This batch has one fixed model")
    started = time.perf_counter()
    import relf_agent
    from relf_agent.semantic_rag_reference import ASSET_MANIFEST

    if relf_agent.__version__ != VERSION or "/site-packages/" not in str(relf_agent.__file__):
        raise ValueError("Use the exact isolated candidate installation")
    if sha256(args.wheel) != WHEEL_SHA256:
        raise ValueError("Candidate wheel digest differs")
    # Verify exact package payload, not just a version string. Private version is
    # already embedded in both installed SDK and wheel.
    import zipfile

    installed = Path(relf_agent.__file__).parent
    with zipfile.ZipFile(args.wheel) as archive:
        for name in archive.namelist():
            if name.startswith("relf_agent/") and not name.endswith("/"):
                if (
                    archive.read(name)
                    != (installed / name.removeprefix("relf_agent/")).read_bytes()
                ):
                    raise ValueError("Installed product differs from wheel")
    for name, expected in ASSET_MANIFEST["assets"].items():
        path = Path(args.model_directory) / name
        if (
            path.is_symlink()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError("Semantic asset differs")
    datasets, specs = inputs(args.model)
    # Optional dependency imports are cold setup, before the timed task/control
    # profiler. No model is loaded and no API is called by this explicit import.
    importlib.import_module("sentence_transformers")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    manifest = {
        "version": VERSION,
        "wheel_sha256": WHEEL_SHA256,
        "sdk_module": str(relf_agent.__file__),
        "runner_sha256": sha256(__file__),
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": sorted(
            (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
        ),
        "offline": args.offline,
        "model": args.model,
        "specs": specs,
        "datasets": datasets,
        "semantic_assets": ASSET_MANIFEST,
        "secret_saved": False,
        "inputs_verified_seconds": time.perf_counter() - started,
        "readiness_boundary": "exact SDK/assets/config and optional dependencies verified; model weights load in RAG task",
    }
    write_json(output / "inputs.json", manifest)
    print(
        json.dumps(
            {
                "phase": "inputs_verified",
                "version": VERSION,
                "offline": args.offline,
                "inputs_verified_seconds": manifest["inputs_verified_seconds"],
            }
        ),
        flush=True,
    )
    return datasets, specs, output


async def run(args, key, prepared):
    import httpx

    from relf_agent.planning_evaluation import EvaluationLimits
    from relf_agent.providers import DeepSeekChatProvider

    datasets, specs, output = prepared
    summaries = {}
    for name in CHAINS:
        metrics = Measurements()
        with metrics:
            async with httpx.AsyncClient(
                follow_redirects=False,
                event_hooks={"request": [metrics.on_request], "response": [metrics.on_response]},
            ) as client:
                if args.offline:
                    from relf_agent.business_evaluation_cli import _OfflineBusinessProvider
                    from relf_agent.orchestration_evaluation import OfflineOrchestrationProvider
                    from relf_agent.rag_evaluation import OfflineRAGProvider

                    provider = (
                        _OfflineBusinessProvider()
                        if name == "business"
                        else (
                            OfflineRAGProvider()
                            if name == "rag"
                            else OfflineOrchestrationProvider()
                        )
                    )
                else:
                    provider = DeepSeekChatProvider(
                        args.model,
                        api_key=key,
                        base_url="https://api.deepseek.com",
                        json_mode=name in ("business", "rag"),
                        max_output_tokens=2048,
                        timeout=45,
                        temperature=0,
                        client=client,
                    )
                report = await evaluate(
                    name,
                    provider,
                    datasets[name],
                    EvaluationLimits(**specs[name]["limits"]),
                    output / (name + "-evidence"),
                    args.model_directory,
                )
        write_json(output / (name + "-report.json"), report)
        measure = metrics.result()
        if not args.offline and measure["http_request_count"] != report["calls"]:
            measure["physical_request_accounting_matches"] = False
        else:
            measure["physical_request_accounting_matches"] = True
        write_json(output / (name + "-measurements.json"), measure)
        summaries[name] = assess_chain(report, specs[name])
        if not args.offline:
            summaries[name]["measurements_accepted"] = assess_measurements(
                measure, report, specs[name]
            )
            if not summaries[name]["measurements_accepted"]:
                summaries[name]["accepted"] = False
                summaries[name]["reasons"].append("physical_measurement_mismatch")
        print(
            json.dumps(
                {
                    "phase": name,
                    "passed": report["passed"],
                    "total": report["total"],
                    "accepted": summaries[name]["accepted"],
                }
            ),
            flush=True,
        )
    probe = None
    if args.stream_probe and not args.offline:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            provider = DeepSeekChatProvider(
                args.model,
                api_key=key,
                base_url="https://api.deepseek.com",
                json_mode=False,
                max_output_tokens=2048,
                timeout=45,
                temperature=0,
                client=client,
            )
            probe = await stream_probe(provider)
        write_json(output / "native-stream-probe.json", probe)
    summary = {
        "version": VERSION,
        "wheel_sha256": WHEEL_SHA256,
        "offline": args.offline,
        "quality_accepted": not args.offline and all(row["accepted"] for row in summaries.values()),
        "chains": summaries,
        "native_stream_probe": probe,
        "external_adoption_qualified": False,
        "framework_parity_qualified": False,
        "platform_qualified": False,
    }
    write_json(output / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--live", action="store_true")
    secret = parser.add_mutually_exclusive_group()
    secret.add_argument("--key-env", default="DEEPSEEK_API_KEY")
    secret.add_argument("--prompt-key", action="store_true")
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--model-directory", required=True)
    parser.add_argument("--model", default=MODEL, choices=[MODEL])
    parser.add_argument("--output", required=True)
    parser.add_argument("--stream-probe", action="store_true")
    args = parser.parse_args(argv)
    key = None
    try:
        if not args.offline:
            key = (
                getpass.getpass("DeepSeek credential (masked; process memory only): ")
                if args.prompt_key
                else os.environ.get(args.key_env)
            )
            if not key:
                raise ValueError("Credential is not configured")
        prepared = prepare(args)
        result = asyncio.run(run(args, key, prepared))
        rehearsal_passed = set(result["chains"]) == set(CHAINS) and all(
            row["passed"] == row["total"] for row in result["chains"].values()
        )
        return 0 if (rehearsal_passed if args.offline else result["quality_accepted"]) else 1
    except Exception as error:
        # Never expose supplier messages, task content, secrets or traceback.
        print(
            json.dumps(
                {
                    "status": "incomplete",
                    "exception_class": type(error).__name__,
                    "quality_accepted": False,
                }
            ),
            flush=True,
        )
        return 2
    finally:
        key = None


if __name__ == "__main__":
    raise SystemExit(main())
