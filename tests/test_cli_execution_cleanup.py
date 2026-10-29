"""Accepted CLI engines must finish closing before a successful exit."""

import json
import sys
import types
from contextlib import asynccontextmanager, contextmanager

import pytest

from relf_agent import LocalEngine, SQLiteStore, ToolRegistry
from relf_agent.cli import _closing_engine, load_engine, main
from relf_agent.errors import CoordinatorBusy
from relf_agent.runtime_builder import EchoProvider, RuntimeBuildError


@pytest.fixture
def execution_factory(tmp_path, monkeypatch):
    instances = []
    db = tmp_path / "execution.sqlite"
    spec = tmp_path / "agent.json"
    spec.write_text(json.dumps({"name": "assistant", "instructions": "Answer"}))

    def install(close):
        class Engine:
            def __init__(self, engine):
                self.engine = engine

            def __getattr__(self, name):
                return getattr(self.engine, name)

            def close(self):
                return close(self.engine)

        def factory(path):
            engine = LocalEngine(
                SQLiteStore(path),
                providers={"default": EchoProvider("cleanup")},
                tools=ToolRegistry(),
            )
            instances.append(engine)
            return Engine(engine)

        module = types.ModuleType("cli_execution_cleanup_fixture")
        module.create_engine = factory
        monkeypatch.setitem(sys.modules, module.__name__, module)
        return [
            "--db",
            str(db),
            "--factory",
            "cli_execution_cleanup_fixture:create_engine",
            "run",
            "--spec",
            str(spec),
            "--input",
            "hello",
            "--command-id",
            "once",
            "--submit-only",
        ]

    yield db, instances, install
    for engine in instances:
        engine.close()


@pytest.mark.parametrize("kind", ["coroutine", "generator", "context", "async-context", "bool"])
@pytest.mark.parametrize("submit_only", [False, True])
def test_cli_rejects_unfinished_close_instead_of_reporting_success(
    execution_factory, capsys, kind, submit_only
):
    db, engines, install = execution_factory
    entered = []

    async def coroutine(engine):
        entered.append("close")
        engine.close()

    def generator(engine):
        entered.append("close")
        engine.close()
        yield

    @contextmanager
    def context(engine):
        entered.append("close")
        engine.close()
        yield

    @asynccontextmanager
    async def async_context(engine):
        entered.append("close")
        engine.close()
        yield

    values = {
        "coroutine": coroutine,
        "generator": generator,
        "context": context,
        "async-context": async_context,
        "bool": lambda engine: True,
    }
    args = install(values[kind])
    if not submit_only:
        args.remove("--submit-only")
    assert main(args) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["code"] == "validation_error"
    assert entered == []
    with SQLiteStore(db) as store:
        assert store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        original = store.run(store.conn.execute("SELECT id FROM runs").fetchone()[0])
        assert original["state"] == ("queued" if submit_only else "succeeded")
        with pytest.raises(CoordinatorBusy):
            store.create_coordinator().acquire()
    engines[0].close()
    with SQLiteStore(db) as store:
        lease = store.create_coordinator()
        lease.acquire()
        lease.release()
    retry = install(lambda engine: engine.close())
    if not submit_only:
        retry.remove("--submit-only")
    assert main(retry) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["run_id"] == original["id"]
    if not submit_only:
        assert json.loads(output.out)["result"] == {"echo": "hello", "label": "cleanup"}
    assert output.err == ""
    with SQLiteStore(db) as store:
        assert store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 1


def test_cli_reports_close_failure_without_leaking_extension_details(execution_factory, capsys):
    _, engines, install = execution_factory

    def close(engine):
        raise RuntimeError("fixture-private-close-detail")

    assert main(install(close)) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["code"] == "validation_error"
    assert "fixture-private-close-detail" not in output.err
    engines[0].close()


def test_cli_only_reports_success_after_actual_close(execution_factory, capsys):
    db, _, install = execution_factory
    assert main(install(lambda engine: engine.close())) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["run_id"]
    assert output.err == ""
    with SQLiteStore(db) as store:
        lease = store.create_coordinator()
        lease.acquire()
        lease.release()


@pytest.mark.parametrize("during_operation", [False, True])
def test_failed_execution_cleanup_retains_original_engine_for_retry(
    execution_factory, during_operation
):
    db, _, install = execution_factory
    failure = RuntimeError("close interrupted")
    attempts = []

    def close(engine):
        attempts.append("close")
        if len(attempts) == 1:
            raise failure
        engine.close()

    install(close)
    engine = load_engine(db, "cli_execution_cleanup_fixture:create_engine")
    with pytest.raises(RuntimeBuildError) as rejected, _closing_engine(engine):
        if during_operation:
            raise ValueError("operation failed")
    assert rejected.value.cleanup is engine
    assert rejected.value.__cause__ is failure
    with SQLiteStore(db) as store:
        with pytest.raises(CoordinatorBusy):
            store.create_coordinator().acquire()
    rejected.value.cleanup.close()
    assert attempts == ["close", "close"]
    with SQLiteStore(db) as store:
        lease = store.create_coordinator()
        lease.acquire()
        lease.release()


def test_successful_cleanup_preserves_original_operation_error(execution_factory):
    db, _, install = execution_factory
    install(lambda engine: engine.close())
    engine = load_engine(db, "cli_execution_cleanup_fixture:create_engine")
    failure = ValueError("operation failed")
    with pytest.raises(ValueError) as rejected, _closing_engine(engine):
        raise failure
    assert rejected.value is failure
    with SQLiteStore(db) as store:
        lease = store.create_coordinator()
        lease.acquire()
        lease.release()
