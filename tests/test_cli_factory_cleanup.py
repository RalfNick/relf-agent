"""Rejected CLI extension objects retain real cleanup and coordinator ownership."""

import asyncio
import json
import sqlite3
import sys
import types

import pytest

from relf_agent import LocalEngine, SQLiteStore, ToolRegistry
from relf_agent.cli import load_engine, main
from relf_agent.errors import CoordinatorBusy, DefinitionMismatch, ValidationError
from relf_agent.runtime_builder import RuntimeBuildError


class EngineProxy:
    def __init__(self, engine):
        self.engine = engine

    def __getattr__(self, name):
        return getattr(self.engine, name)


@pytest.fixture
def configured_factory(tmp_path, monkeypatch):
    engines, candidates = [], []
    path = tmp_path / "runs.sqlite"

    def install(wrapper):
        def factory(db):
            engine = LocalEngine(SQLiteStore(db), providers={}, tools=ToolRegistry())
            engines.append(engine)
            candidate = wrapper(engine)
            candidates.append(candidate)
            return candidate

        module = types.ModuleType("cli_cleanup_fixture")
        module.create_engine = factory
        monkeypatch.setitem(sys.modules, module.__name__, module)
        return path, engines, candidates

    yield install
    for engine in engines:
        engine.close()


def assert_closed_and_unoccupied(engine, path):
    with pytest.raises(sqlite3.ProgrammingError):
        engine.store.conn.execute("SELECT 1")
    with SQLiteStore(path) as store:
        assert store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        lease = store.create_coordinator()
        lease.acquire()
        lease.release()


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_unreadable_engine_method_is_a_configuration_error_and_releases_ownership(
    configured_factory, error_type
):
    failure = error_type("adapter metadata unavailable")

    class Invalid(EngineProxy):
        @property
        def drive(self):
            raise failure

    path, engines, _ = configured_factory(Invalid)
    with pytest.raises(ValidationError) as rejected:
        load_engine(path, "cli_cleanup_fixture:create_engine")
    assert rejected.value.__cause__ is failure
    assert_closed_and_unoccupied(engines[0], path)


@pytest.mark.parametrize(
    "error_type", [KeyboardInterrupt, asyncio.CancelledError, SystemExit, DefinitionMismatch]
)
def test_interrupted_engine_validation_closes_before_propagating_original(
    configured_factory, error_type
):
    failure = error_type("engine validation interrupted")

    class Interrupted(EngineProxy):
        @property
        def drive(self):
            raise failure

    path, engines, _ = configured_factory(Interrupted)
    with pytest.raises(error_type) as rejected:
        load_engine(path, "cli_cleanup_fixture:create_engine")
    assert rejected.value is failure
    assert_closed_and_unoccupied(engines[0], path)


@pytest.mark.parametrize(
    "error_type", [RuntimeError, KeyboardInterrupt, asyncio.CancelledError, SystemExit]
)
def test_incomplete_rejected_engine_cleanup_exposes_original_retry_handle(
    configured_factory, error_type
):
    failure = error_type("cleanup interrupted")

    class Invalid(EngineProxy):
        drive = None
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise failure
            self.engine.close()

    path, engines, candidates = configured_factory(Invalid)
    rejected = None
    try:
        load_engine(path, "cli_cleanup_fixture:create_engine")
    except BaseException as error:
        rejected = error
    assert isinstance(rejected, RuntimeBuildError), type(rejected).__name__
    assert rejected.__cause__ is failure
    assert rejected.cleanup is candidates[0]
    with SQLiteStore(path) as store:
        with pytest.raises(CoordinatorBusy):
            store.create_coordinator().acquire()
    rejected.cleanup.close()
    assert candidates[0].attempts == 2
    assert_closed_and_unoccupied(engines[0], path)


@pytest.mark.parametrize("error_type", [RuntimeError, AttributeError])
def test_unreadable_cleanup_method_keeps_the_candidate_for_retry(configured_factory, error_type):
    failure = error_type("cleanup method unavailable")

    class Invalid:
        drive = None
        accesses = 0

        def __init__(self, engine):
            self.engine = engine

        @property
        def submit(self):
            return self.engine.submit

        @property
        def close(self):
            self.accesses += 1
            if self.accesses == 1:
                raise failure
            return self.engine.close

    path, engines, candidates = configured_factory(Invalid)
    rejected = None
    try:
        load_engine(path, "cli_cleanup_fixture:create_engine")
    except BaseException as error:
        rejected = error
    assert isinstance(rejected, RuntimeBuildError), type(rejected).__name__
    assert rejected.__cause__ is failure
    assert rejected.cleanup is candidates[0]
    with SQLiteStore(path) as store:
        with pytest.raises(CoordinatorBusy):
            store.create_coordinator().acquire()
    rejected.cleanup.close()
    assert_closed_and_unoccupied(engines[0], path)


def test_cli_reports_unreadable_engine_without_leaking_details_or_accepting_a_run(
    configured_factory, capsys
):
    class Invalid(EngineProxy):
        @property
        def drive(self):
            raise RuntimeError("host-sensitive fixture detail")

    path, engines, _ = configured_factory(Invalid)
    assert (
        main(
            [
                "--db",
                str(path),
                "--factory",
                "cli_cleanup_fixture:create_engine",
                "resume",
                "not-accepted",
            ]
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["code"] == "validation_error"
    assert "host-sensitive fixture detail" not in output.err
    assert_closed_and_unoccupied(engines[0], path)
