"""Existing CLI close errors show only fixed actionable observation data."""

import json

import pytest

from relf_agent import cli
from relf_agent.close_diagnostics import make_close_diagnostics
from relf_agent.errors import CloseIncomplete, ValidationError


@pytest.mark.parametrize("format", ["json", "text"])
def test_cli_close_incomplete_renders_safe_stage_and_retry(monkeypatch, capsys, format):
    failure = CloseIncomplete(
        {"private": "secret-business-endpoint"},
        diagnostics=make_close_diagnostics(
            authority="temporal", stage="end_ack", ownership="owned", blockers={"end_ack": 1}
        ),
    )

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(cli, "load_engine", fail)
    assert cli.main(["--format", format, "demo"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "secret-business-endpoint" not in output.err
    if format == "json":
        value = json.loads(output.err)
        assert value["code"] == "close_incomplete"
        assert value["diagnostics"]["stage"] == "end_ack"
        assert value["diagnostics"]["blockers"] == [{"kind": "end_ack", "count": 1}]
    else:
        assert "stage=end_ack" in output.err
        assert "retry=retain_original_instance_and_retry_close" in output.err


def test_cli_other_typed_errors_keep_original_shape(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ValidationError("invalid fixture")

    monkeypatch.setattr(cli, "load_engine", fail)
    assert cli.main(["demo"]) == 2
    assert json.loads(capsys.readouterr().err) == {
        "code": "validation_error",
        "message": "invalid fixture",
    }


def test_cli_wrapped_actual_close_keeps_original_engine_retry_and_error_contract(
    tmp_path, monkeypatch, capsys
):
    from relf_agent import LocalEngine, SQLiteStore, ToolRegistry
    from relf_agent.errors import CoordinatorBusy
    from relf_agent.runtime_builder import EchoProvider

    path = tmp_path / "execution.sqlite"
    spec = tmp_path / "agent.json"
    spec.write_text(json.dumps({"name": "agent", "instructions": "Reply"}))
    raw = LocalEngine(
        SQLiteStore(path), providers={"default": EchoProvider("once")}, tools=ToolRegistry()
    )
    failure = CloseIncomplete(
        {"private": "owned-close-name"},
        diagnostics=make_close_diagnostics(
            authority="local", stage="authority_close", ownership="owned"
        ),
    )

    class OwnedEngine:
        close_calls = 0

        def __getattr__(self, name):
            return getattr(raw, name)

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise failure
            raw.close()

    owned = OwnedEngine()
    monkeypatch.setattr(cli, "load_engine", lambda *args: owned)
    args = [
        "--db",
        str(path),
        "--factory",
        "test:explicit",
        "run",
        "--spec",
        str(spec),
        "--input",
        "q",
        "--command-id",
        "once",
        "--submit-only",
    ]
    try:
        assert cli.main(args) == 2
        output = capsys.readouterr()
        assert output.out == ""
        result = json.loads(output.err)
        assert result["code"] == "validation_error"
        assert result["message"] == "Runtime component construction failed"
        assert result["diagnostics"]["stage"] == "authority_close"
        assert "owned-close-name" not in output.err
        with SQLiteStore(path) as observer:
            assert observer.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
            with pytest.raises(CoordinatorBusy):
                observer.create_coordinator().acquire()
    finally:
        owned.close()
    assert owned.close_calls == 2
    with SQLiteStore(path) as observer:
        lease = observer.create_coordinator()
        lease.acquire()
        lease.release()


def test_cli_does_not_walk_arbitrary_cause_chains(monkeypatch, capsys):
    from relf_agent.runtime_builder import RuntimeBuildError

    inside = CloseIncomplete("private report", diagnostics=make_close_diagnostics(stage="end_ack"))
    middle = RuntimeBuildError(object())
    middle.__cause__ = inside
    outside = RuntimeBuildError(object())
    outside.__cause__ = middle

    def fail(*args):
        raise outside

    monkeypatch.setattr(cli, "load_engine", fail)
    assert cli.main(["demo"]) == 2
    assert set(json.loads(capsys.readouterr().err)) == {"code", "message"}
