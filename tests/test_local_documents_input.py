"""Bounded real-pipe input regressions, without model calls or listening sockets."""

import asyncio
import json
import subprocess
import sys
import textwrap

import pytest

from tests.test_local_documents_cli import cli_environment, command
from tests.test_local_documents_files import api, config_file


def test_chat_consumes_two_commands_while_stdin_pipe_remains_open(tmp_path):
    path = config_file(tmp_path)
    process = subprocess.Popen(
        command(path, "chat"),
        cwd=tmp_path,
        env=cli_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        process.stdin.write("/help\n/quit\n")
        process.stdin.flush()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pytest.fail("chat stalled on the second complete line in a still-open pipe")
        assert process.stdin is not None and not process.stdin.closed
        assert process.returncode == 0, process.stderr.read()
        assert json.loads(process.stdout.read()) == {"session_id": "main", "closed": True}
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


PIPE_SETUP = """
import asyncio
import os
import sys
from local_documents.cli import read_line

async def scenario():
    read_fd, write_fd = os.pipe()
    stream = os.fdopen(read_fd, "r", encoding="utf-8")
    original = sys.stdin
    sys.stdin = stream
    try:
BODY
    finally:
        sys.stdin = original
        stream.close()
        if write_fd is not None:
            os.close(write_fd)

asyncio.run(scenario())
"""


def run_pipe_probe(body):
    # A broken blocking readline would prevent an in-loop timeout from firing.
    # Isolate the loop so the parent can always kill and reap the probe.
    program = PIPE_SETUP.replace("BODY", textwrap.indent(textwrap.dedent(body), "        "))
    try:
        result = subprocess.run(
            [sys.executable, "-c", program],
            env=cli_environment(),
            capture_output=True,
            text=True,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("partial stdin blocked the event loop (probe killed and reaped)")
    assert result.returncode == 0, result.stderr


def test_partial_line_cancellation_keeps_bytes_and_removes_reader():
    run_pipe_probe("""
        os.write(write_fd, b"hel")
        reading = asyncio.create_task(read_line(""))
        await asyncio.sleep(0.03)
        assert not reading.done()
        reading.cancel()
        try:
            await reading
        except asyncio.CancelledError:
            pass
        assert not asyncio.get_running_loop().remove_reader(read_fd)
        os.write(write_fd, b"lo\\n")
        assert await asyncio.wait_for(read_line(""), 0.5) == "hello\\n"
        os.close(write_fd)
        write_fd = None
        assert await asyncio.wait_for(read_line(""), 0.5) == ""
        assert not asyncio.get_running_loop().remove_reader(read_fd)
    """)


def test_utf8_split_chunks_complete_lines_and_final_unterminated_line():
    run_pipe_probe("""
        payload = "你好\\nsecond\\n尾".encode("utf-8")
        os.write(write_fd, payload[:2])
        reading = asyncio.create_task(read_line(""))
        await asyncio.sleep(0.03)
        assert not reading.done()
        os.write(write_fd, payload[2:])
        assert await asyncio.wait_for(reading, 0.5) == "你好\\n"
        assert await asyncio.wait_for(read_line(""), 0.5) == "second\\n"
        os.close(write_fd)
        write_fd = None
        assert await asyncio.wait_for(read_line(""), 0.5) == "尾"
        assert await asyncio.wait_for(read_line(""), 0.5) == ""
        assert not asyncio.get_running_loop().remove_reader(read_fd)
    """)


def test_buffered_lines_belong_to_their_original_stream():
    run_pipe_probe("""
        os.write(write_fd, b"first\\nremaining\\n")
        assert await asyncio.wait_for(read_line(""), 0.5) == "first\\n"
        other_fd, other_write = os.pipe()
        with os.fdopen(other_fd, "r", encoding="utf-8") as other:
            try:
                sys.stdin = other
                os.write(other_write, b"other\\n")
                assert await asyncio.wait_for(read_line(""), 0.5) == "other\\n"
            finally:
                sys.stdin = stream
                os.close(other_write)
        assert await asyncio.wait_for(read_line(""), 0.5) == "remaining\\n"
    """)


def test_input_interrupt_cancels_partial_line_without_leaving_an_input_task():
    run_pipe_probe("""
        from local_documents.cli import input_line

        interrupted = asyncio.Event()
        os.write(write_fd, b"part")
        reading = asyncio.create_task(input_line("", interrupted))
        await asyncio.sleep(0.03)
        interrupted.set()
        assert await asyncio.wait_for(reading, 0.5) == "\\n"
        assert not interrupted.is_set()
        assert not asyncio.get_running_loop().remove_reader(read_fd)
        assert asyncio.all_tasks() == {asyncio.current_task()}
        os.write(write_fd, b"ial\\n/quit\\n")
        assert await asyncio.wait_for(input_line("", interrupted), 0.5) == "partial\\n"
        assert await asyncio.wait_for(input_line("", interrupted), 0.5) == "/quit\\n"
    """)


def test_regular_file_stdin_keeps_lines_and_eof(tmp_path, monkeypatch):
    path = tmp_path / "input.txt"
    path.write_text("first\n尾", encoding="utf-8")

    async def scenario():
        assert await api("cli").read_line("") == "first\n"
        assert await api("cli").read_line("") == "尾"
        assert await api("cli").read_line("") == ""

    with path.open(encoding="utf-8") as stream:
        monkeypatch.setattr(sys, "stdin", stream)
        asyncio.run(scenario())
