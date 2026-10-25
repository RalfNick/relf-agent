"""Rejected constructed runtimes cannot lose their original execution owner."""

import asyncio
import sqlite3

import pytest

from relf_agent import (
    AgentSpec,
    ComponentRegistry,
    LocalEngine,
    ModelResponse,
    ProfiledEngine,
    RuntimeBuilder,
    RuntimeCatalog,
    RuntimeProfile,
    SQLiteStore,
    ToolRegistry,
)
from relf_agent.errors import CoordinatorBusy, ValidationError
from relf_agent.runtime_builder import EchoProvider, RuntimeBuildError


def new_engine(path, *, profile=None):
    return LocalEngine(
        SQLiteStore(path),
        providers={"default": EchoProvider("ownership")},
        tools=ToolRegistry(),
        runtime_profile=None if profile is None else profile.identity,
    )


def selected_catalog():
    profile = RuntimeProfile("app", "1", {"default": {"adapter": "offline-echo"}})
    catalog = RuntimeCatalog()
    catalog.register(profile, default=True)
    return catalog


def assert_unoccupied(path):
    with SQLiteStore(path) as store:
        lease = store.create_coordinator()
        lease.acquire()
        lease.release()


@pytest.mark.parametrize("route", ["builder", "legacy"])
@pytest.mark.parametrize("error_type", [KeyboardInterrupt, asyncio.CancelledError, SystemExit])
def test_router_closes_interrupted_candidate_and_can_later_accept_valid_runtime(
    tmp_path, route, error_type
):
    path = tmp_path / "router.sqlite"
    failure = error_type("validation interrupted")
    instances = []
    invalid = True

    class Candidate:
        def __init__(self, engine):
            self.engine = engine

        def __getattr__(self, name):
            return getattr(self.engine, name)

        @property
        def drive(self):
            raise failure

    def construct(path, profile=None):
        engine = new_engine(path, profile=profile)
        instances.append(engine)
        return Candidate(engine) if invalid else engine

    class Builder:
        def build(self, profile, db_path, **options):
            return construct(db_path, profile)

    original = None
    if route == "legacy":
        with new_engine(path) as engine:
            original = engine.submit(AgentSpec("a", "Answer"), "q", command_id="original")
    router = ProfiledEngine(selected_catalog(), path, builder=Builder(), legacy_factory=construct)
    try:
        with pytest.raises(error_type) as rejected:
            if route == "builder":
                router.submit(AgentSpec("a", "Answer"), "q", command_id="new")
            else:
                asyncio.run(router.drive(original.run_id))
        assert rejected.value is failure
        with pytest.raises(sqlite3.ProgrammingError):
            instances[-1].store.conn.execute("SELECT 1")
        assert_unoccupied(path)
        invalid = False
        handle = (
            router.submit(AgentSpec("a", "Answer"), "q", command_id="new")
            if route == "builder"
            else original
        )
        assert asyncio.run(router.drive(handle.run_id)).state == "succeeded"
    finally:
        router.close()
        for instance in instances:
            instance.close()


@pytest.mark.parametrize("error_type", [RuntimeError, AttributeError, asyncio.CancelledError])
def test_router_keeps_failed_close_descriptor_until_explicit_close_retry(tmp_path, error_type):
    path = tmp_path / "failed-close.sqlite"
    failure = error_type("cleanup unavailable")
    instances = []

    class Candidate:
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

    class Builder:
        def build(self, profile, db_path, **options):
            engine = new_engine(db_path, profile=profile)
            instances.append(engine)
            return Candidate(engine)

    router = ProfiledEngine(selected_catalog(), path, builder=Builder())
    try:
        with pytest.raises(error_type) as rejected:
            router.submit(AgentSpec("a", "Answer"), "q", command_id="not-accepted")
        assert rejected.value is failure
        with pytest.raises(ValidationError):
            router.submit(AgentSpec("a", "Answer"), "q", command_id="still-blocked")
        with SQLiteStore(path) as store:
            assert store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
            with pytest.raises(CoordinatorBusy):
                store.create_coordinator().acquire()
        router.close()
        assert_unoccupied(path)
    finally:
        for instance in instances:
            instance.close()
        router.close()


def test_router_without_a_returned_cleanup_port_can_retry_a_different_valid_builder(tmp_path):
    class Builder:
        invalid = True

        def build(self, profile, db_path, **options):
            if self.invalid:
                return object()
            return new_engine(db_path, profile=profile)

    builder = Builder()
    with ProfiledEngine(
        selected_catalog(), tmp_path / "no-owner.sqlite", builder=builder
    ) as router:
        with pytest.raises(ValidationError):
            router.submit(AgentSpec("a", "Answer"), "q", command_id="new")
        builder.invalid = False
        handle = router.submit(AgentSpec("a", "Answer"), "q", command_id="new")
        assert asyncio.run(router.drive(handle.run_id)).state == "succeeded"


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("error_type", [RuntimeError, AttributeError, asyncio.CancelledError])
def test_builder_retains_declared_close_owner_before_closing_store_or_clients(
    tmp_path, asynchronous, error_type
):
    failure = error_type("declared close unavailable")

    class Candidate(LocalEngine):
        drive = None
        accesses = 0

        @property
        def close(self):
            self.accesses += 1
            if self.accesses == 1:
                raise failure
            return super().close

    exercise_builder_cleanup(tmp_path, asynchronous, Candidate, failure)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
def test_builder_retains_dynamic_close_lookup_failure_inside_cleanup_guard(
    tmp_path, asynchronous, error_type
):
    failure = error_type("dynamic close unavailable")

    class Candidate:
        drive = None
        accesses = 0

        def __init__(self, store, **options):
            self.engine = LocalEngine(store, **options)

        @property
        def submit(self):
            return self.engine.submit

        def __getattr__(self, name):
            if name == "close":
                self.accesses += 1
                if self.accesses == 1:
                    raise failure
            return getattr(self.engine, name)

    exercise_builder_cleanup(tmp_path, asynchronous, Candidate, failure)


def exercise_builder_cleanup(tmp_path, asynchronous, candidate_type, failure):
    path = tmp_path / "builder.sqlite"
    clients, candidates, stores = [], [], []

    def provider(config, context):
        clients.append(context.own((tmp_path / "owned.txt").open("w")))
        return EchoProvider("ownership")

    def engine_factory(store, **options):
        stores.append(store)
        candidate = candidate_type(store, **options)
        candidates.append(candidate)
        return candidate

    registry = ComponentRegistry()
    registry.register("provider", "owned", provider)
    profile = RuntimeProfile("app", "1", {"default": {"adapter": "owned"}})
    builder = RuntimeBuilder(registry, engine_factory=engine_factory)

    async def exercise():
        rejected = None
        try:
            if asynchronous:
                await builder.abuild(profile, path)
            else:
                builder.build(profile, path)
        except BaseException as error:
            rejected = error
        assert isinstance(rejected, RuntimeBuildError), type(rejected).__name__
        assert rejected.__cause__ is failure
        assert_cleanup_only(rejected.cleanup)
        assert not clients[0].closed
        assert stores[0].conn.execute("SELECT 1").fetchone()[0] == 1
        with SQLiteStore(path) as store:
            assert store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
            with pytest.raises(CoordinatorBusy):
                store.create_coordinator().acquire()
        if asynchronous:
            await rejected.cleanup.aclose()
        else:
            rejected.cleanup.close()
        assert clients[0].closed
        with pytest.raises(sqlite3.ProgrammingError):
            stores[0].conn.execute("SELECT 1")
        assert_unoccupied(path)

    try:
        asyncio.run(exercise())
    finally:
        for candidate in candidates:
            candidate.close()
        for client in clients:
            client.close()
        for store in stores:
            store.close()


def assert_cleanup_only(runtime):
    operations = (
        lambda: runtime.submit(
            AgentSpec("unexpected", "Must remain stopped"), "q", command_id="no"
        ),
        lambda: runtime.status("not-accepted"),
        lambda: runtime.events("not-accepted"),
        lambda: runtime.cancel("not-accepted", command_id="no-cancel"),
    )
    for operation in operations:
        with pytest.raises(ValidationError):
            operation()


def test_clean_close_refusal_keeps_cached_cancel_for_the_actual_active_runtime(tmp_path):
    async def exercise():
        path = tmp_path / "cached-close.sqlite"
        started, release = asyncio.Event(), asyncio.Event()

        class Provider:
            identity = {"kind": "actual-close-precondition", "version": "1"}

            async def complete(self, messages, tools):
                started.set()
                await release.wait()
                return ModelResponse(output="done")

        registry = ComponentRegistry()
        registry.register("provider", "slow", lambda config, context: Provider())
        profile = RuntimeProfile("app", "1", {"default": {"adapter": "slow"}})
        runtime = RuntimeBuilder(registry).build(profile, path)
        cancel = runtime.cancel
        handle = runtime.submit(AgentSpec("a", "Answer"), "q", command_id="active")
        running = asyncio.create_task(runtime.drive(handle.run_id))
        try:
            await asyncio.wait_for(started.wait(), 2)
            with pytest.raises(ValidationError):
                runtime.close()
            cancel(handle.run_id, command_id="stop-original")
            release.set()
            assert (await asyncio.wait_for(running, 2)).state == "cancelled"
            runtime.close()
            assert_unoccupied(path)
        finally:
            release.set()
            await running
            runtime.close()

    asyncio.run(exercise())
