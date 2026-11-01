"""Human terminal data is inert; original JSON and approved file bytes are not edited."""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from relf_agent import ModelResponse, Scope, ToolCall
from relf_agent.types import digest
from tests.test_local_documents_files import api
from tests.test_local_documents_runtime import make_config

CONTROL_TEXT = (
    "普通中文\n\t下一行 "
    "\x1b[8m隐藏段落\x1b[0m \x1b]8;;https://example.invalid\x07链接\x1b]8;;\x1b\\ "
    "\x00\x01\x08\r\x0b\x0c\x1f\x7f\x80\x85\x9b\x9d\x9f "
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)
VISIBLE_TEXT = (
    "普通中文\n\t下一行 "
    r"\x1b[8m隐藏段落\x1b[0m \x1b]8;;https://example.invalid\x07链接\x1b]8;;\x1b\ "
    r"\x00\x01\x08\x0d\x0b\x0c\x1f\x7f\x80\x85\x9b\x9d\x9f "
    r"\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)


@pytest.mark.parametrize(
    "value",
    [
        {"run_id": CONTROL_TEXT},
        {"run_id": "run", "state": CONTROL_TEXT},
        {"run_id": "run", "record_state": CONTROL_TEXT},
        {"command_id": CONTROL_TEXT},
        {"configuration_mismatch": True, "message": CONTROL_TEXT},
        {"answer": CONTROL_TEXT},
        {"error": CONTROL_TEXT},
        {"error": "validation_error", "message": CONTROL_TEXT},
        *[
            {
                "pending": [
                    {
                        **dict(
                            path="report.md", action_id="action", digest="digest", content="正文\n"
                        ),
                        field: CONTROL_TEXT,
                    }
                ]
            }
            for field in ("path", "action_id", "digest", "content")
        ],
        *[
            {
                "turns": [
                    {
                        **dict(turn_seq=1, run_id="run", state="succeeded", question="问题"),
                        field: CONTROL_TEXT,
                    }
                ]
            }
            for field in ("turn_seq", "run_id", "state", "question")
        ],
        *[
            {
                "answer": "回答",
                "sources": [
                    {
                        **dict(
                            path="rules.md", start_line=1, end_line=2, start_column=3, sha256="hash"
                        ),
                        field: CONTROL_TEXT,
                    }
                ],
            }
            for field in ("path", "start_line", "end_line", "start_column", "sha256")
        ],
    ],
    ids=[
        "run-id",
        "state",
        "record-state",
        "command-id",
        "configuration-message",
        "answer",
        "error-code",
        "error-message",
        "preview-path",
        "preview-action",
        "preview-digest",
        "preview-content",
        "history-sequence",
        "history-run",
        "history-state",
        "history-question",
        "source-path",
        "source-start",
        "source-end",
        "source-column",
        "source-hash",
    ],
)
def test_every_human_field_displays_control_characters_visibly_without_editing_data(value, capsys):
    original = copy.deepcopy(value)
    api("cli").emit(value)
    output = capsys.readouterr().out
    assert VISIBLE_TEXT in output
    assert "\x1b" not in output and "\r" not in output and "\u202e" not in output
    assert value == original


def test_json_preserves_control_characters_in_all_original_fields(capsys):
    value = {
        "answer": CONTROL_TEXT,
        "command_id": CONTROL_TEXT,
        "pending": [{"content": CONTROL_TEXT}],
    }
    original = copy.deepcopy(value)
    api("cli").emit(value, as_json=True)
    assert json.loads(capsys.readouterr().out) == original
    assert value == original


def test_plain_human_text_keeps_newlines_tabs_and_chinese(capsys):
    api("cli").emit({"run_id": "run-1", "state": "succeeded", "answer": "普通中文\n\t下一行"})
    assert capsys.readouterr().out == "Run: run-1  状态: succeeded\n\n普通中文\n\t下一行\n"


def test_supplementary_unicode_format_control_uses_a_complete_visible_escape(capsys):
    api("cli").emit({"answer": "普通中文\U000e0001结尾"})
    assert capsys.readouterr().out == "\n普通中文\\U000e0001结尾\n"


def test_input_prompt_displays_controls_visibly_without_changing_read_line(
    tmp_path, monkeypatch, capsys
):
    cli = api("cli")
    path = tmp_path / "input.txt"
    path.write_text("yes\n剩余输入\n")
    with path.open() as stream:
        monkeypatch.setattr(cli.sys, "stdin", stream)
        assert asyncio.run(cli.read_line(CONTROL_TEXT)) == "yes\n"
        assert stream.readline() == "剩余输入\n"
    assert capsys.readouterr().err == VISIBLE_TEXT


def test_observe_stderr_displays_run_id_controls_visibly(capsys):
    async def observe(handle, *, wait_timeout):
        return {"state": "succeeded"}

    async def scenario():
        return await api("cli").observe(
            SimpleNamespace(observe=observe),
            SimpleNamespace(ref=SimpleNamespace(run_id=CONTROL_TEXT)),
            SimpleNamespace(wait_timeout=5),
            asyncio.Event(),
        )

    assert asyncio.run(scenario()) == {"state": "succeeded"}
    assert capsys.readouterr().err == "Run: " + VISIBLE_TEXT + "\n"


def test_argument_error_displays_untrusted_argument_controls_visibly(capsys):
    with pytest.raises(SystemExit) as error:
        api("cli").parser().parse_args(["status", "run", "--unknown=" + CONTROL_TEXT])
    assert error.value.code == 2
    assert VISIBLE_TEXT in capsys.readouterr().err


REPORT_BODY = (
    "# 审批报告\n\t普通中文。\n"
    "\x1b[8m必须显示的隐藏段落\x1b[0m\n"
    "\x1b]8;;https://example.invalid\x07链接\x1b]8;;\x1b\\\n"
    "覆盖\r原文\x08；C0=\x01；C1=\x85\x9b；双向=\u202e\u2066正文\u2069。"
)


class ControlReportModel:
    identity = {"kind": "control-report-terminal-fixture", "version": "1"}

    async def complete(self, messages, tools):
        observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        if not observations:
            return ModelResponse(tool_calls=[ToolCall("search_documents", {"query": "告警"})])
        source = observations[0]["sources"][0]
        if len(observations) == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        "save_report",
                        {
                            "path": "summary.md",
                            "content": REPORT_BODY,
                            "citations": [source["id"]],
                        },
                    )
                ]
            )
        return ModelResponse(
            {"answer": "已保存\x1b[8m原报告\x1b[0m", "grounded": True, "citations": [source["id"]]}
        )


def test_real_approval_preview_is_inert_but_reopened_resume_saves_exact_original_bytes(
    tmp_path, monkeypatch, capsys
):
    config, cli = make_config(tmp_path), api("cli")

    async def answer_yes(prompt, interrupted):
        return "yes"

    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(cli, "input_line", answer_yes)

    async def scenario():
        async with api("runtime").Application(config, provider=ControlReportModel()) as app:
            handle = await app.submit(
                "生成报告",
                session_id="terminal",
                command_id="report-original",
                report_path="summary.md",
            )
            result = await app.observe(handle, wait_timeout=5)
            assert result["state"] == "waiting_approval"
            (pending,) = result["pending"]
            original = copy.deepcopy(result)
            expected = pending["content"].encode("utf-8")
            assert expected.startswith(REPORT_BODY.encode("utf-8"))
            assert pending["sha256"] == hashlib.sha256(expected).hexdigest()
            assert not (config.output / "summary.md").exists()
            cli.emit(result, as_json=True)
            assert json.loads(capsys.readouterr().out) == original
        async with api("runtime").Application(config, provider=ControlReportModel()) as app:
            args = SimpleNamespace(
                command="approve",
                run_id=handle.ref.run_id,
                action=pending["action_id"],
                digest=pending["digest"],
                yes=False,
                reject=False,
                command_id="approve-original",
            )
            receipt = await cli.perform(app, args, asyncio.Event())
            human = capsys.readouterr().out
            assert "控制字符转义显示，保存原文" in human
            assert "必须显示的隐藏段落" in human
            assert r"\x1b[8m必须显示的隐藏段落\x1b[0m" in human
            assert "\x1b" not in human and "\r" not in human and "\x08" not in human
            assert r"\x85\x9b" in human and r"\u202e\u2066正文\u2069" in human
            assert receipt["record_state"] == "durably_recorded"
            assert result == original
            assert not (config.output / "summary.md").exists()
        async with api("runtime").Application(config, provider=ControlReportModel()) as app:
            resumed = await app.resume(handle.ref.run_id)
            final = await app.observe(resumed, wait_timeout=5)
            assert final["state"] == "succeeded"
            assert final["answer"] == "已保存\x1b[8m原报告\x1b[0m"
            assert (
                app.approve(
                    handle.ref.run_id,
                    pending["action_id"],
                    pending["digest"],
                    command_id="approve-original",
                )
                == receipt
            )
            assert (await app.observe(await app.resume(handle.ref.run_id), wait_timeout=5))[
                "state"
            ] == "succeeded"
        saved = (config.output / "summary.md").read_bytes()
        assert saved == expected and b"\x1b[8m" in saved
        assert hashlib.sha256(saved).hexdigest() == pending["sha256"]
        record = api("evidence").read_run(config.database, handle.ref.run_id)
        (write,) = [action for action in record["actions"] if action.get("tool") == "save_report"]
        assert write["id"] == pending["action_id"] and write["digest"] == pending["digest"]
        assert write["arguments"]["content"] == REPORT_BODY
        assert write["status"] == "completed" and len(write["attempts"]) == 1
        assert write["result"]["sha256"] == pending["sha256"]
        assert write["result"]["bytes"] == len(expected)
        assert write["result"]["request_digest"] == digest(
            {
                "scope": {"workspace": Scope().workspace, "principal": Scope().principal},
                "path": "summary.md",
                "text": pending["content"],
                "expected_version": None,
            }
        )

    asyncio.run(scenario())
