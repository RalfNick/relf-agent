"""Separate CLI processes against a local protocol fixture, never model quality."""

import asyncio
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.test_local_documents_files import APP, api
from tests.test_local_documents_runtime import DocumentModel, make_config


@contextmanager
def model_server(*, hold=False, fail=False):
    model, requests = DocumentModel(), []
    entered, release = threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            entered.set()
            if fail:
                self.send_error(503)
                return
            if hold and not release.wait(15):
                self.send_error(504)
                return
            result = asyncio.run(model.complete(body["messages"], body.get("tools", [])))
            message = {"role": "assistant", "content": None}
            if result.tool_calls:
                message["tool_calls"] = [
                    {
                        "id": f"call-{len(requests)}-{index}",
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for index, call in enumerate(result.tool_calls)
                ]
            else:
                message["content"] = json.dumps(result.output, ensure_ascii=False)
            data = json.dumps(
                {
                    "choices": [
                        {
                            "index": 0,
                            "message": message,
                            "finish_reason": "tool_calls" if result.tool_calls else "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 20},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, requests, entered, release
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(5)


def configured(root, port):
    make_config(root)
    path = root / "assistant.toml"
    path.write_text(
        path.read_text()
        .replace('adapter="deepseek"', 'adapter="chat-completions"')
        .replace("https://api.deepseek.com", f"http://127.0.0.1:{port}/v1")
    )
    return api("config").load_config(path), path


def cli_environment(*, key=True):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    # Source tests explicitly identify app + SDK. Installed tests copy no src.
    root_src = Path(__file__).resolve().parents[1] / "src"
    sources = [str(p) for p in (APP, root_src) if p.is_dir()]
    if sources:
        env["PYTHONPATH"] = os.pathsep.join(sources)
    if key:
        env["TEST_MODEL_KEY"] = "synthetic-local-protocol-key"
    else:
        env.pop("TEST_MODEL_KEY", None)
    return env


def command(path, *args):
    return [sys.executable, "-m", "local_documents", "--config", str(path), "--json", *args]


def invoke(path, *args, key=True):
    result = subprocess.run(
        command(path, *args),
        cwd=path.parent,
        env=cli_environment(key=key),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def test_cli_real_process_report_preview_approval_recovery_and_duplicates(tmp_path):
    with model_server() as (port, requests, _, _):
        config, path = configured(tmp_path, port)
        result = invoke(
            path, "report", "总结告警规则", "--output", "summary.md", "--command-id", "report-1"
        )
        assert result["state"] == "waiting_approval"
        (preview,) = result["pending"]
        assert not (config.output / "summary.md").exists()
        approval = [
            "approve",
            result["run_id"],
            "--action",
            preview["action_id"],
            "--digest",
            preview["digest"],
            "--yes",
        ]
        receipt = invoke(path, *approval)
        assert not (config.output / "summary.md").exists()
        assert invoke(path, *approval) == receipt
        resumed = invoke(path, "resume", result["run_id"])
        assert resumed["state"] == "succeeded"
        assert (config.output / "summary.md").read_text() == preview["content"]
        calls = len(requests)
        assert invoke(path, *approval) == receipt
        assert invoke(path, "resume", result["run_id"])["state"] == "succeeded"
        replay = invoke(
            path, "report", "总结告警规则", "--output", "summary.md", "--command-id", "report-1"
        )
        assert replay["run_id"] == result["run_id"] and len(requests) == calls
        assert invoke(path, "status", result["run_id"], key=False)["state"] == "succeeded"
        assert len(invoke(path, "history", key=False)["turns"]) == 1
        record = api("evidence").read_run(config.database, result["run_id"])
        (write,) = [a for a in record["actions"] if a.get("tool") == "save_report"]
        assert len(write["attempts"]) == 1 and write["status"] == "completed"


def test_cli_restart_session_and_interactive_stdin(tmp_path):
    with model_server() as (port, requests, _, _):
        _, path = configured(tmp_path, port)
        first = invoke(path, "ask", "项目代号 AzureFir，解释告警规则", "--command-id", "one")
        assert first["sources"][0]["path"] == "rules.md"
        assert invoke(path, "ask", "继续解释", "--command-id", "two")["state"] == "succeeded"
        assert "AzureFir" in json.dumps(requests[-1]["messages"], ensure_ascii=False)
        chat = subprocess.run(
            command(path, "chat"),
            input="解释告警规则\n/quit\n",
            cwd=path.parent,
            env=cli_environment(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert chat.returncode == 0, chat.stderr
        assert "rules.md" in chat.stdout and "15分钟" in chat.stdout
        assert len(invoke(path, "history", key=False)["turns"]) == 3


def test_cli_ctrl_c_waits_inflight_request_then_closes_without_tool_effect(tmp_path):
    with model_server(hold=True) as (port, requests, entered, release):
        config, path = configured(tmp_path, port)
        process = subprocess.Popen(
            command(path, "ask", "解释告警", "--command-id", "cancel-one"),
            cwd=path.parent,
            env=cli_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert entered.wait(10)
            process.send_signal(signal.SIGINT)
            deadline = time.monotonic() + 10
            while True:
                connection = sqlite3.connect(config.database)
                try:
                    current = json.loads(connection.execute("SELECT data FROM runs").fetchone()[0])
                finally:
                    connection.close()
                if current["state"] == "cancelling":
                    break
                assert time.monotonic() < deadline, current["state"]
                time.sleep(0.01)
            # Permit the supplier response; cancellation must prevent its tool proposal.
            release.set()
            stdout, stderr = process.communicate(timeout=20)
        finally:
            release.set()
            if process.poll() is None:
                process.kill()
                process.wait()
        assert process.returncode == 130, (stdout, stderr)
        result = json.loads(stdout)
        assert result["state"] == "cancelled" and len(requests) == 1
        record = api("evidence").read_run(config.database, result["run_id"])
        assert not any(a.get("kind") == "tool" for a in record["actions"])
        assert invoke(path, "status", result["run_id"], key=False)["state"] == "cancelled"
        # A new process must be able to take both original leases after shutdown.
        assert (
            invoke(path, "ask", "解释告警", "--command-id", "after-cancel")["state"] == "succeeded"
        )


def test_cli_missing_key_is_clear_and_does_not_create_execution_store(tmp_path):
    with model_server() as (port, requests, _, _):
        config, path = configured(tmp_path, port)
        result = subprocess.run(
            command(path, "ask", "解释告警"),
            cwd=path.parent,
            env=cli_environment(key=False),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2
        error = json.loads(result.stdout)
        assert error["error"] == "validation_error" and "TEST_MODEL_KEY" in error["message"]
        assert not config.database.exists() and requests == []


def test_cli_native_connection_failure_retains_unknown_and_never_retries_implicitly(tmp_path):
    with model_server(fail=True) as (port, requests, _, _):
        _, path = configured(tmp_path, port)
        failed = subprocess.run(
            command(path, "ask", "解释告警", "--command-id", "failed-one"),
            cwd=path.parent,
            env=cli_environment(),
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert failed.returncode == 2
        result = json.loads(failed.stdout)
        assert (
            result["state"] == "waiting_reconciliation"
            and result["error"]["code"] == "provider_error"
        )
        assert len(requests) == 1
        resumed = subprocess.run(
            command(path, "resume", result["run_id"]),
            cwd=path.parent,
            env=cli_environment(),
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert resumed.returncode == 2 and len(requests) == 1
        assert (
            invoke(path, "status", result["run_id"], key=False)["state"] == "waiting_reconciliation"
        )
        assert invoke(path, "cancel", result["run_id"])["state"] == "cancelled"


def test_cli_noninteractive_confirmation_is_required_and_rejection_never_writes(tmp_path):
    with model_server() as (port, requests, _, _):
        config, path = configured(tmp_path, port)
        result = invoke(
            path, "report", "总结告警规则", "--output", "reject.md", "--command-id", "reject-one"
        )
        run_id = result["run_id"]
        refused = subprocess.run(
            command(path, "approve", run_id),
            cwd=path.parent,
            env=cli_environment(),
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert refused.returncode == 2 and json.loads(refused.stdout)["error"] == "validation_error"
        assert invoke(path, "status", run_id, key=False)["state"] == "waiting_approval"
        calls = len(requests)
        invoke(path, "approve", run_id, "--reject", "--yes")
        assert invoke(path, "status", run_id, key=False)["state"] == "failed"
        assert not (config.output / "reject.md").exists() and len(requests) == calls
