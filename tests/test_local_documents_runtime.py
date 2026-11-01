"""Real Local SQLite/Workspace application behavior; controlled offline decisions."""

import asyncio
import json
from dataclasses import replace

import pytest

from relf_agent import ModelResponse, ToolCall
from relf_agent.errors import ProviderError, RalfError
from tests.test_local_documents_files import api, config_file


class DocumentModel:
    identity = {"kind": "local-documents-test", "version": "1"}

    def __init__(self):
        self.messages = []

    async def complete(self, messages, tools):
        self.messages.append(messages)
        observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        request = json.loads(next(m["content"] for m in messages if m["role"] == "user"))
        if not observations:
            return ModelResponse(tool_calls=[ToolCall("search_documents", {"query": "告警"})])
        source = observations[0]["sources"][0]
        if request.get("report_path") and len(observations) == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        "save_report",
                        {
                            "path": request["report_path"],
                            "content": "# 值班报告\n15分钟内确认告警。",
                            "citations": [source["id"]],
                        },
                    )
                ]
            )
        return ModelResponse(
            {"answer": "15分钟内确认告警。", "grounded": True, "citations": [source["id"]]}
        )


def make_config(root):
    config = api("config").load_config(config_file(root))
    (config.documents / "rules.md").write_text("# 值班规则\n告警应在15分钟内确认。\n")
    return config


def test_session_query_and_reopen_recall_use_existing_sqlite(tmp_path):
    config, model = make_config(tmp_path), DocumentModel()

    async def scenario():
        async with api("runtime").Application(config, provider=model) as app:
            handle = await app.submit("记住项目代号 AzureFir", session_id="one", command_id="q1")
            result = await app.observe(handle, wait_timeout=5)
            assert result["state"] == "succeeded"
            assert result["sources"][0]["path"] == "rules.md"
        async with api("runtime").Application(config, provider=model) as app:
            handle = await app.submit("继续解释", session_id="one", command_id="q2")
            assert (await app.observe(handle, wait_timeout=5))["state"] == "succeeded"
            assert "AzureFir" in json.dumps(model.messages[-1], ensure_ascii=False)
        history = api("runtime").history(config, "one")
        assert len(history["turns"]) == 2
        assert all(item["state"] == "succeeded" for item in history["turns"])

    asyncio.run(scenario())


def test_report_approval_reopen_duplicate_receipts_and_exactly_one_output(tmp_path):
    config = make_config(tmp_path)

    async def scenario():
        async with api("runtime").Application(config, provider=DocumentModel()) as app:
            run = await app.submit(
                "生成值班报告", session_id="reports", command_id="r1", report_path="summary.md"
            )
            preview = await app.observe(run, wait_timeout=5)
            assert preview["state"] == "waiting_approval"
            (pending,) = preview["pending"]
            assert pending["path"] == str(config.output / "summary.md")
            assert "15分钟" in pending["content"] and "rules.md" in pending["content"]
            assert not (config.output / "summary.md").exists()
            run_id = run.ref.run_id
        # The original entry has closed; a new instance accepts only the decision.
        async with api("runtime").Application(config, provider=DocumentModel()) as app:
            receipt = app.approve(
                run_id, pending["action_id"], pending["digest"], command_id="approval-r1"
            )
            assert not (config.output / "summary.md").exists()
        # Actual execution is explicitly resumed in another runtime/process boundary.
        async with api("runtime").Application(config, provider=DocumentModel()) as app:
            handle = await app.resume(run_id)
            assert (await app.observe(handle, wait_timeout=5))["state"] == "succeeded"
            assert (
                app.approve(
                    run_id, pending["action_id"], pending["digest"], command_id="approval-r1"
                )
                == receipt
            )
            repeated = await app.submit(
                "生成值班报告", session_id="reports", command_id="r1", report_path="summary.md"
            )
            assert repeated.ref.run_id == run_id
            assert (await app.observe(repeated, wait_timeout=5))["state"] == "succeeded"
        assert (config.output / "summary.md").read_text() == pending["content"]
        assert list(config.output.glob("*.md")) == [config.output / "summary.md"]
        record = api("evidence").read_run(config.database, run_id)
        writes = [a for a in record["actions"] if a.get("tool") == "save_report"]
        assert len(writes) == 1 and len(writes[0]["attempts"]) == 1
        assert writes[0]["result"]["sha256"] == pending["sha256"]

    asyncio.run(scenario())


@pytest.mark.parametrize("decision", ["reject", "cancel"])
def test_declining_or_cancelling_report_does_not_create_target(tmp_path, decision):
    config = make_config(tmp_path)

    async def scenario():
        async with api("runtime").Application(config, provider=DocumentModel()) as app:
            handle = await app.submit(
                "报告", session_id="one", command_id="r1", report_path="denied.md"
            )
            result = await app.observe(handle, wait_timeout=5)
            (pending,) = result["pending"]
            if decision == "reject":
                app.approve(
                    handle.ref.run_id,
                    pending["action_id"],
                    pending["digest"],
                    command_id="reject-r1",
                    approved=False,
                )
                await app.resume(handle.ref.run_id)
            else:
                await app.cancel(handle.ref.run_id)
            terminal = await handle.wait(wait_timeout=5, terminal_only=True)
            assert terminal.snapshot.state in {"failed", "cancelled"}
            assert not (config.output / "denied.md").exists()
        # Native write-root and SQLite leases are released, allowing safe reuse.
        async with api("runtime").Application(config, provider=DocumentModel()):
            pass

    asyncio.run(scenario())


def test_existing_report_is_never_overwritten(tmp_path):
    config = make_config(tmp_path)

    async def scenario():
        async with api("runtime").Application(config, provider=DocumentModel()) as app:
            (config.output / "existing.md").write_text("original")
            handle = await app.submit(
                "报告", session_id="one", command_id="r1", report_path="existing.md"
            )
            preview = await app.observe(handle, wait_timeout=5)
            (pending,) = preview["pending"]
            app.approve(
                handle.ref.run_id,
                pending["action_id"],
                pending["digest"],
                command_id="approve-existing",
            )
            await app.resume(handle.ref.run_id)
            result = await handle.wait(wait_timeout=5)
            assert result.snapshot.state != "succeeded"
            assert (config.output / "existing.md").read_text() == "original"

    asyncio.run(scenario())


def test_changed_configuration_refuses_execution_but_original_task_remains_queryable(tmp_path):
    config = make_config(tmp_path)

    async def scenario():
        async with api("runtime").Application(config, provider=DocumentModel()) as app:
            run = await app.submit(
                "报告", session_id="one", command_id="r1", report_path="summary.md"
            )
            await app.observe(run, wait_timeout=5)
            run_id = run.ref.run_id
        with pytest.raises(RalfError):
            async with api("runtime").Application(
                replace(config, model="changed"), provider=DocumentModel()
            ):
                pass
        assert api("runtime").inspect_run(config, run_id)["state"] == "waiting_approval"

    asyncio.run(scenario())


def test_forged_model_citation_is_not_displayed_as_verified_answer(tmp_path):
    config = make_config(tmp_path)

    class ForgedModel:
        identity = {"kind": "forged-fixture", "version": "1"}

        async def complete(self, messages, tools):
            return ModelResponse({"answer": "invented", "grounded": True, "citations": ["fake"]})

    async def scenario():
        async with api("runtime").Application(config, provider=ForgedModel()) as app:
            handle = await app.submit("问题", session_id="one", command_id="q1")
            with pytest.raises(RalfError, match="引用"):
                await app.observe(handle, wait_timeout=5)

    asyncio.run(scenario())


def test_model_failure_is_observable_and_resources_can_be_reopened(tmp_path):
    config = make_config(tmp_path)

    class FailedModel:
        identity = {"kind": "failed-fixture", "version": "1"}

        def __init__(self):
            self.calls = 0

        async def complete(self, messages, tools):
            self.calls += 1
            raise ProviderError("test connection failed")

    async def scenario():
        model = FailedModel()
        async with api("runtime").Application(config, provider=model) as app:
            handle = await app.submit("问题", session_id="one", command_id="q1")
            result = await app.observe(handle, wait_timeout=5)
            # Original SDK conservatively records a dispatched request as unknown.
            assert result["state"] == "waiting_reconciliation"
            assert result["error"]["code"] == "provider_error"
        assert (
            api("runtime").inspect_run(config, handle.ref.run_id)["state"]
            == "waiting_reconciliation"
        )
        async with api("runtime").Application(config, provider=model) as app:
            resumed = await app.resume(handle.ref.run_id)
            assert (await app.observe(resumed, wait_timeout=5))["state"] == "waiting_reconciliation"
            assert model.calls == 1  # Resume is never a hidden second model request.
            await app.cancel(handle.ref.run_id)
            assert (
                await resumed.wait(wait_timeout=5, terminal_only=True)
            ).snapshot.state == "cancelled"

    asyncio.run(scenario())


def test_wait_timeout_does_not_cancel_and_explicit_cancel_stops_model_before_close(tmp_path):
    config = make_config(tmp_path)

    class SlowModel:
        identity = {"kind": "slow-fixture", "version": "1"}

        def __init__(self):
            self.started, self.stopped, self.release = (
                asyncio.Event(),
                asyncio.Event(),
                asyncio.Event(),
            )

        async def complete(self, messages, tools):
            self.started.set()
            try:
                await self.release.wait()
                return ModelResponse({"answer": "done", "grounded": False, "citations": []})
            finally:
                self.stopped.set()

    async def scenario():
        model = SlowModel()
        async with api("runtime").Application(config, provider=model) as app:
            handle = await app.submit("问题", session_id="one", command_id="q1")
            await model.started.wait()
            result = await app.observe(handle, wait_timeout=0)
            assert result["wait_reason"] == "observation_timeout" and not model.stopped.is_set()
            await app.cancel(handle.ref.run_id)
            assert (await handle.wait(wait_timeout=0)).snapshot.state == "cancelling"
            assert not model.stopped.is_set()
            model.release.set()
            terminal = await handle.wait(wait_timeout=5, terminal_only=True)
            assert terminal.snapshot.state == "cancelled"
        assert model.stopped.is_set()
        async with api("runtime").Application(config, provider=SlowModel()):
            pass

    asyncio.run(scenario())


def test_file_close_failure_keeps_original_resources_for_safe_retry(tmp_path):
    from relf_agent.workspace import WorkspaceError

    config = make_config(tmp_path)

    async def scenario():
        app = await api("runtime").Application(config, provider=DocumentModel()).__aenter__()
        original = app.reports.close

        def fail_close():
            raise WorkspaceError("temporary close failure")

        app.reports.close = fail_close
        with pytest.raises(WorkspaceError):
            await app.aclose()
        assert not app.closed and app.runtime.state == "closed"
        app.reports.close = original
        await app.aclose()
        assert app.closed
        async with api("runtime").Application(config, provider=DocumentModel()):
            pass

    asyncio.run(scenario())


def test_report_cannot_finish_with_text_instead_of_original_save_receipt(tmp_path):
    config = make_config(tmp_path)

    class EarlyTextModel(DocumentModel):
        identity = {"kind": "early-text-fixture", "version": "1"}

        async def complete(self, messages, tools):
            observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
            feedback = any("Completion verification:" in str(m.get("content")) for m in messages)
            if len(observations) == 1 and not feedback:
                source = observations[0]["sources"][0]
                return ModelResponse(
                    {"answer": "报告应包含告警规则", "grounded": True, "citations": [source["id"]]}
                )
            return await super().complete(messages, tools)

    async def scenario():
        async with api("runtime").Application(config, provider=EarlyTextModel()) as app:
            handle = await app.submit(
                "概括报告内容", session_id="one", command_id="r1", report_path="summary.md"
            )
            result = await app.observe(handle, wait_timeout=5)
            assert result["state"] == "waiting_approval"
            assert not (config.output / "summary.md").exists()
            (preview,) = result["pending"]
            app.approve(
                handle.ref.run_id, preview["action_id"], preview["digest"], command_id="approve-1"
            )
            await app.resume(handle.ref.run_id)
            assert (await app.observe(handle, wait_timeout=5))["state"] == "succeeded"
            record = api("evidence").read_run(config.database, handle.ref.run_id)
            assert any(
                a.get("completion_verification", {}).get("verdict", {}).get("status") == "retry"
                for a in record["actions"]
            )
            assert (config.output / "summary.md").read_text() == preview["content"]

    asyncio.run(scenario())


def test_insufficient_report_is_rejected_without_write_or_retry_loop(tmp_path):
    config = make_config(tmp_path)

    class NoEvidence:
        identity = {"kind": "no-evidence-fixture", "version": "1"}

        def __init__(self):
            self.calls = 0

        async def complete(self, messages, tools):
            self.calls += 1
            return ModelResponse(
                {"answer": "资料未提供，无法形成报告。", "grounded": False, "citations": []}
            )

    async def scenario():
        model = NoEvidence()
        async with api("runtime").Application(config, provider=model) as app:
            handle = await app.submit(
                "预算报告", session_id="one", command_id="r1", report_path="budget.md"
            )
            result = await app.observe(handle, wait_timeout=5)
            assert result["state"] == "failed" and result["error"]["code"] == "completion_rejected"
            assert not (config.output / "budget.md").exists()
        assert model.calls == 1

    asyncio.run(scenario())
