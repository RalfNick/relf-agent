"""Node verdicts require actual Local Actions, rather than fixture verdicts."""

import asyncio
import copy
import dataclasses
import importlib
import json
import sqlite3
import types

import pytest

from relf_agent.adapter_contract_types import AdapterContractCleanupPending
from relf_agent.errors import ValidationError


def api():
    try:
        return importlib.import_module("relf_agent.node_adapter_contract")
    except ModuleNotFoundError:
        pytest.fail("The fixed NodeExecutor cases are missing")


class Component:
    def __init__(self):
        self.identity = {"kind": "external-node-test", "version": "1"}
        self.output = None
        self.fail = False
        self.calls = []
        self.close_calls = 0
        self.close_failures = 0
        self.entered = self.release = None

    async def execute(self, input, config, context):
        self.calls.append((copy.deepcopy(input), copy.deepcopy(config), context.effect_key))
        if self.entered is not None:
            self.entered.set()
            await self.release.wait()
        if self.fail:
            raise RuntimeError("private-node-password")
        return copy.deepcopy(self.output)

    def close(self):
        if self.close_failures:
            self.close_failures -= 1
            raise RuntimeError("private-close-password")
        self.close_calls += 1


class Fixture:
    def __init__(self, *, owned=True, transform=None):
        self.owned, self.transform = owned, transform
        self.component = None

    def prepare(self, case_id, workspace):
        module = api()
        component = self.component = Component()

        def configure(kind, data):
            if kind == "output":
                component.output = copy.deepcopy(data["result"])
            elif kind == "reset":
                component.output = None
            else:
                raise ValueError("unknown configuration")

        def fault(kind):
            if kind == "identity-drift":
                component.identity = {"kind": "changed-node"}
            elif kind == "method-drift":

                async def changed(self, input, config, context):
                    self.calls.append((input, config, context.effect_key))
                    return "replacement"

                component.execute = types.MethodType(changed, component)
            elif kind == "handler-error":
                component.fail = True
            elif kind == "reset":
                component.identity = {"kind": "external-node-test", "version": "1"}
                component.fail = False
                component.__dict__.pop("execute", None)
            else:
                raise ValueError("unknown fault")

        def pause(kind):
            assert kind == "execute"
            component.entered, component.release = asyncio.Event(), asyncio.Event()

            async def entered():
                await component.entered.wait()

            def release():
                component.release.set()

            return module.NodeContractPause(entered, release)

        session = module.NodeContractSession(
            component,
            resources=(module.NodeContractResource(component),) if self.owned else (),
            configure=configure,
            inject_fault=fault,
            pause=pause,
            audit=lambda: {
                "execute_calls": len(component.calls),
                "reconcile_calls": 0,
                "close_calls": component.close_calls,
            },
            reopen=lambda: None,
        )
        return self.transform(session) if self.transform else session


@pytest.mark.parametrize(
    "case_id,expected_calls",
    [
        ("N01", 0),
        ("N02", 6),
        ("N03", 0),
        ("N04", 0),
        ("N05", 1),
        ("N06", 0),
        ("N07", 0),
        ("N08", 1),
        ("N09", 1),
        ("N10", 1),
    ],
)
def test_case_uses_real_component_and_original_local_authority(case_id, expected_calls, tmp_path):
    fixture = Fixture()
    result = asyncio.run(api().run_node_case(case_id, fixture, tmp_path))
    assert (result.status, result.code) == ("passed", "verified"), result.to_dict()
    assert result.adapter_digest and result.configuration_digest
    assert result.observations["execute_calls"] == expected_calls
    assert result.observations["reconcile_calls"] == 0
    assert result.observations["cleanup_complete"]
    assert fixture.component.close_calls == 1
    assert result.execution_authority == ("none" if case_id == "N01" else "local")
    if case_id == "N02":
        assert all(
            input == {"items": [None, False, 0, "中文🙂", {"nested": [1, 2]}]}
            and config == {"mode": "full", "nested": {"values": [0, False]}}
            and effect_key
            for input, config, effect_key in fixture.component.calls
        )
    if case_id == "N05":
        assert result.observations["settlement_checks"] >= 1
        assert result.observations["tool_calls"] == 1
    if case_id == "N10":
        assert result.observations["cancelled"] and result.observations["handler_finished"]


@pytest.mark.parametrize(
    "case_id,missing",
    [
        ("N01", "audit"),
        ("N02", "configure"),
        ("N05", "configure"),
        ("N06", "inject_fault"),
        ("N07", "inject_fault"),
        ("N08", "inject_fault"),
        ("N09", "reopen"),
        ("N10", "pause"),
    ],
)
def test_missing_controls_cannot_certify_case(case_id, missing, tmp_path):
    fixture = Fixture(transform=lambda s: dataclasses.replace(s, **{missing: None}))
    result = asyncio.run(api().run_node_case(case_id, fixture, tmp_path))
    assert (result.status, result.code) == ("not_verified", "missing_fixture_capability")
    assert result.observations["cleanup_complete"]


def test_fixture_success_verdict_cannot_supply_component(tmp_path):
    class Verdict:
        def prepare(self, case_id, workspace):
            return {"status": "passed", "component": "success"}

    result = asyncio.run(api().run_node_case("N01", Verdict(), tmp_path))
    assert (result.status, result.code) == ("failed", "invalid_fixture_session")


@pytest.mark.parametrize(
    "field,value",
    [
        ("audit", lambda: {"status": "passed"}),
        ("audit", lambda: {"execute_calls": True, "close_calls": 0}),
        ("configure", lambda kind, data: {"status": "passed"}),
    ],
)
def test_untrusted_management_values_are_redacted_failures(field, value, tmp_path):
    fixture = Fixture(transform=lambda s: dataclasses.replace(s, **{field: value}))
    result = asyncio.run(api().run_node_case("N02", fixture, tmp_path))
    assert result.status == "failed"
    assert "private" not in str(result.to_dict())


def test_real_handler_error_is_redacted_in_all_retained_records(tmp_path):
    result = asyncio.run(api().run_node_case("N08", Fixture(), tmp_path))
    assert result.status == "passed", result.to_dict()
    for path in tmp_path.glob("*.sqlite"):
        assert b"private-node-password" not in path.read_bytes()


def test_borrowed_component_remains_open(tmp_path):
    fixture = Fixture(owned=False)
    result = asyncio.run(api().run_node_case("N10", fixture, tmp_path))
    assert result.status == "passed", result.to_dict()
    assert result.observations["borrowed_closed"] is False
    assert fixture.component.close_calls == 0


def test_owned_close_failure_retains_same_cleanup_without_repeating_execute(tmp_path):
    fixture = Fixture(transform=lambda s: set_close_failure(s))

    async def run():
        with pytest.raises(AdapterContractCleanupPending) as error:
            await api().run_node_case("N02", fixture, tmp_path)
        assert error.value.result.code == "cleanup_failed"
        assert len(fixture.component.calls) == 6 and fixture.component.close_calls == 0
        await error.value.cleanup()
        assert len(fixture.component.calls) == 6 and fixture.component.close_calls == 1

    asyncio.run(run())


def set_close_failure(session):
    session.component.close_failures = 1
    return session


def test_cancelled_case_drains_actual_handler_before_closing_owned_client(tmp_path):
    async def run():
        paused = asyncio.Event()

        def change(session):
            original = session.pause

            def pause(kind):
                gate = original(kind)
                paused.set()
                return gate

            return dataclasses.replace(session, pause=pause)

        fixture = Fixture(transform=change)
        task = asyncio.create_task(api().run_node_case("N10", fixture, tmp_path))
        await paused.wait()
        await fixture.component.entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert fixture.component.release.is_set()
        assert len(fixture.component.calls) == 1 and fixture.component.close_calls == 1

    asyncio.run(asyncio.wait_for(run(), 5))


def test_ordinary_function_returning_coroutine_is_not_an_async_node(tmp_path):
    class Lazy:
        identity = {"kind": "invalid-port"}

        def execute(self, input, config, context):
            raise AssertionError("port admission must not execute")

    fixture = Fixture(transform=lambda s: dataclasses.replace(s, component=Lazy()))
    result = asyncio.run(api().run_node_case("N01", fixture, tmp_path))
    assert result.status == "failed"


@pytest.mark.parametrize("case_id", ["N00", "N11", None, []])
def test_unknown_case_rejected_before_fixture_io(case_id, tmp_path):
    with pytest.raises(ValidationError):
        asyncio.run(api().run_node_case(case_id, object(), tmp_path))


def test_resource_mode_and_management_shape_are_checked():
    with pytest.raises(ValidationError):
        api().NodeContractResource(object(), asynchronous=1)
    with pytest.raises(ValidationError):
        api().NodeContractPause(None, lambda: None)
    with pytest.raises(ValidationError):
        api().NodeContractSession(object(), resources=[object()])


@pytest.mark.parametrize("case_id", ["N06", "N07", "N08"])
def test_noop_fault_callback_cannot_certify_protection(case_id, tmp_path):
    fixture = Fixture(transform=lambda s: dataclasses.replace(s, inject_fault=lambda kind: None))
    result = asyncio.run(api().run_node_case(case_id, fixture, tmp_path))
    assert (result.status, result.code) == ("failed", "contract_violation")


def test_component_ignoring_configured_result_cannot_pass_json_case(tmp_path):
    fixture = Fixture(transform=lambda s: dataclasses.replace(s, configure=lambda kind, data: None))
    result = asyncio.run(api().run_node_case("N02", fixture, tmp_path))
    assert result.status == "failed"


def test_completed_non_json_handler_result_cannot_be_certified(tmp_path):
    class Invalid(Component):
        async def execute(self, input, config, context):
            return object()

    fixture = Fixture(transform=lambda s: dataclasses.replace(s, component=Invalid()))
    result = asyncio.run(api().run_node_case("N02", fixture, tmp_path))
    assert result.status == "failed"


def test_false_pause_signal_is_not_actual_handler_suspension(tmp_path):
    fixture = Fixture(
        transform=lambda s: dataclasses.replace(
            s, pause=lambda kind: api().NodeContractPause(lambda: None, lambda: None)
        )
    )
    result = asyncio.run(api().run_node_case("N10", fixture, tmp_path))
    assert result.status == "failed"
    assert fixture.component.close_calls == 1


def test_failed_pause_release_retains_live_engine_until_original_retry(tmp_path):
    observed = {}

    def change(session):
        original = session.pause

        def pause(kind):
            gate = original(kind)
            observed["releases"] = 0

            def release():
                observed["releases"] += 1
                if observed["releases"] <= 3:
                    raise RuntimeError("private-release-password")
                return gate.release()

            return api().NodeContractPause(gate.wait_entered, release)

        return dataclasses.replace(session, pause=pause)

    async def run():
        fixture = Fixture(transform=change)
        with pytest.raises(AdapterContractCleanupPending) as error:
            await api().run_node_case("N10", fixture, tmp_path)
        assert not fixture.component.release.is_set()
        assert fixture.component.close_calls == 0
        assert "private-release-password" not in str(error.value.result.to_dict())
        await error.value.cleanup()
        assert fixture.component.release.is_set()
        assert fixture.component.close_calls == 1 and len(fixture.component.calls) == 1

    asyncio.run(asyncio.wait_for(run(), 5))


def test_observer_cancel_during_async_prepare_still_closes_returned_owner(tmp_path):
    async def run():
        fixture = Fixture()
        prepared, release = asyncio.Event(), asyncio.Event()

        class Delayed:
            async def prepare(self, case_id, workspace):
                session = fixture.prepare(case_id, workspace)
                prepared.set()
                await release.wait()
                return session

        task = asyncio.create_task(api().run_node_case("N02", Delayed(), tmp_path))
        await prepared.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and fixture.component.close_calls == 0
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert fixture.component.calls == [] and fixture.component.close_calls == 1

    asyncio.run(asyncio.wait_for(run(), 5))


def test_observer_cancel_during_async_close_keeps_original_cleanup_task(tmp_path):
    async def run():
        closing, release = asyncio.Event(), asyncio.Event()

        class Resource:
            calls = 0

            async def aclose(self):
                self.calls += 1
                closing.set()
                await release.wait()

        resource = Resource()
        fixture = Fixture(
            transform=lambda s: dataclasses.replace(
                s, resources=(api().NodeContractResource(resource, asynchronous=True),)
            )
        )
        task = asyncio.create_task(api().run_node_case("N02", fixture, tmp_path))
        await closing.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and resource.calls == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert resource.calls == 1

    asyncio.run(asyncio.wait_for(run(), 5))


@pytest.mark.parametrize("cancel_registration", [False, True])
def test_bad_resource_registration_cleans_later_owners_and_retains_original_debt(
    cancel_registration, tmp_path
):
    async def run():
        closed = []

        class Rejected:
            broken = True

            @property
            def close(self):
                if self.broken:
                    if cancel_registration:
                        raise asyncio.CancelledError()
                    return None
                return lambda: closed.append("repaired")

        rejected = Rejected()

        class Later:
            def close(self):
                closed.append("later")

        fixture = Fixture(
            transform=lambda s: dataclasses.replace(
                s,
                resources=(
                    api().NodeContractResource(rejected),
                    api().NodeContractResource(Later()),
                ),
            )
        )
        with pytest.raises(AdapterContractCleanupPending) as pending:
            await api().run_node_case("N01", fixture, tmp_path)
        assert closed == ["later"]
        assert pending.value.result.observations["cleanup_complete"] is False
        rejected.broken = False
        await pending.value.cleanup()
        await pending.value.cleanup()
        assert closed == ["later", "repaired"]

    asyncio.run(run())


@pytest.mark.parametrize("boundary", ["configure", "fault", "audit", "reset", "prepare"])
def test_nested_returned_task_finishes_before_owner_close_or_report(boundary, tmp_path):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        nested = []
        fixture = Fixture()
        session = None
        fired = False

        async def work(result, apply=None):
            entered.set()
            await release.wait()
            if apply is not None:
                apply()
            return result

        def spawn(result=None, apply=None):
            task = asyncio.create_task(work(result, apply))
            nested.append(task)
            return task

        class Controlled:
            async def prepare(self, case_id, workspace):
                nonlocal session
                session = fixture.prepare(case_id, workspace)
                if boundary == "prepare":
                    return spawn(session)
                original_fault = session.inject_fault
                original_audit = session.audit

                async def configure(kind, data):
                    return spawn()

                async def fault(kind):
                    if (boundary == "fault" and kind != "reset") or (
                        boundary == "reset" and kind == "reset"
                    ):
                        return spawn(apply=lambda: original_fault(kind))
                    return original_fault(kind)

                async def audit():
                    nonlocal fired
                    if not fired:
                        fired = True
                        return spawn()
                    return original_audit()

                if boundary == "configure":
                    return dataclasses.replace(session, configure=configure)
                if boundary in {"fault", "reset"}:
                    return dataclasses.replace(session, inject_fault=fault)
                return dataclasses.replace(session, audit=audit)

        case = "N06" if boundary in {"fault", "reset"} else "N02"
        task = asyncio.create_task(api().run_node_case(case, Controlled(), tmp_path))
        try:
            await entered.wait()
            await asyncio.sleep(0)
            assert not task.done(), "returned live work must remain owned"
            assert fixture.component.close_calls == 0
            task.cancel()
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and fixture.component.close_calls == 0
        finally:
            release.set()
            outcome = await asyncio.gather(task, return_exceptions=True)
            await asyncio.gather(*nested, return_exceptions=True)
            if isinstance(outcome[0], AdapterContractCleanupPending):
                await outcome[0].cleanup()
        assert fixture.component.close_calls == 1
        assert len(nested) == 1, "malformed callbacks must not be repeated"

    asyncio.run(asyncio.wait_for(run(), 5))


def test_nested_returned_future_stays_owned_until_it_finishes(tmp_path):
    async def run():
        entered = asyncio.Event()
        future = asyncio.get_running_loop().create_future()

        async def configure(kind, data):
            entered.set()
            return future

        fixture = Fixture(transform=lambda s: dataclasses.replace(s, configure=configure))
        task = asyncio.create_task(api().run_node_case("N02", fixture, tmp_path))
        try:
            await entered.wait()
            await asyncio.wait((task,), timeout=0.02)
            assert not task.done() and fixture.component.close_calls == 0
        finally:
            future.set_result(None)
            result = await task
        assert result.status == "failed" and fixture.component.close_calls == 1

    asyncio.run(run())


@pytest.mark.parametrize("nested", [False, True])
def test_bool_replaced_with_number_cannot_certify_json_results(nested, tmp_path):
    def transform(value):
        if value is False:
            return 0
        if isinstance(value, list):
            return [transform(item) for item in value]
        if isinstance(value, dict):
            return {key: transform(item) for key, item in value.items()}
        return copy.deepcopy(value)

    class Changed(Component):
        async def execute(self, input, config, context):
            value = await super().execute(input, config, context)
            if nested and type(value) not in {dict, list}:
                return value
            return transform(value)

    fixture = Fixture()

    class Controlled:
        def prepare(self, case_id, workspace):
            session = fixture.prepare(case_id, workspace)
            original = session.component
            original.__class__ = Changed
            return session

    result = asyncio.run(api().run_node_case("N02", Controlled(), tmp_path))
    assert result.status == "failed", "JSON false and numeric zero are distinct"


def test_n10_cancels_actual_drive_caller_and_keeps_original_completed_receipt(tmp_path):
    result = asyncio.run(api().run_node_case("N10", Fixture(), tmp_path))
    assert result.status == "passed", result.to_dict()
    with sqlite3.connect(tmp_path / "consumer-0.sqlite") as connection:
        record = json.loads(connection.execute("SELECT data FROM runs").fetchone()[0])
    assert record["state"] == "cancelled"
    assert len(record["actions"]) == 1
    assert record["actions"][0]["status"] == "completed"
    assert record["actions"][0]["effect_observation"]["result"] == {
        "items": [None, False, 0, "中文🙂", {"nested": [1, 2]}]
    }


def test_suite_retains_registration_debt_until_same_resource_is_repaired(tmp_path):
    from relf_agent import AdapterContractSuite

    async def run():
        class Unadopted:
            close = None

        original = Unadopted()
        closed = []

        class Later:
            def close(self):
                closed.append("later")

        fixture = Fixture(
            transform=lambda s: dataclasses.replace(
                s,
                resources=(
                    api().NodeContractResource(original),
                    api().NodeContractResource(Later()),
                ),
            )
        )
        suite = AdapterContractSuite(role="node-executor")
        report = await suite.run(fixture, evidence_dir=tmp_path / "evidence")
        assert report.status == "failed" and suite.pending_cleanup
        assert report.cases[0].code == "cleanup_failed"
        assert report.cases[0].observations["cleanup_complete"] is False
        assert closed == ["later"]
        original.close = lambda: closed.append("repaired")
        await suite.aclose()
        await suite.aclose()
        assert not suite.pending_cleanup and closed == ["later", "repaired"]

    asyncio.run(run())


def test_rejected_unstarted_coroutine_is_closed_without_executing_it(tmp_path):
    executed = []

    async def unstarted():
        executed.append(True)

    async def configure(kind, data):
        return unstarted()

    fixture = Fixture(transform=lambda s: dataclasses.replace(s, configure=configure))
    result = asyncio.run(api().run_node_case("N02", fixture, tmp_path))
    assert result.status == "failed" and result.observations["cleanup_complete"]
    assert not executed and fixture.component.close_calls == 1


def test_adopted_client_close_failure_preserves_earlier_dependency(tmp_path):
    async def run():
        closed = []

        class Dependency:
            def close(self):
                closed.append("dependency")

        class Client:
            failures = 1

            def close(self):
                assert "dependency" not in closed
                if self.failures:
                    self.failures -= 1
                    raise RuntimeError("client still pending")
                closed.append("client")

        fixture = Fixture(
            transform=lambda s: dataclasses.replace(
                s,
                resources=(
                    api().NodeContractResource(Dependency()),
                    api().NodeContractResource(Client()),
                ),
            )
        )
        with pytest.raises(AdapterContractCleanupPending) as pending:
            await api().run_node_case("N01", fixture, tmp_path)
        assert closed == [], "an adopted owner's dependency must survive its failed close"
        await pending.value.cleanup()
        await pending.value.cleanup()
        assert closed == ["client", "dependency"]

    asyncio.run(run())


@pytest.mark.parametrize("late_close_fails", [False, True])
def test_final_audit_new_visible_owner_is_finalized_once(late_close_fails, tmp_path):
    async def run():
        fixture = Fixture()
        audits = []

        class Late:
            closes = 0
            failed = False

            def close(self):
                if late_close_fails and not self.failed:
                    self.failed = True
                    raise RuntimeError("late owner still pending")
                self.closes += 1

        late = Late()

        def change(session):
            async def audit():
                audits.append(True)
                if len(audits) == 1:
                    return session.audit()

                async def returned_owner():
                    return api().NodeContractSession(
                        session.component, resources=(api().NodeContractResource(late),)
                    )

                return asyncio.create_task(returned_owner())

            return dataclasses.replace(session, audit=audit)

        fixture.transform = change
        if late_close_fails:
            with pytest.raises(AdapterContractCleanupPending) as pending:
                await api().run_node_case("N01", fixture, tmp_path)
            assert not pending.value.result.observations["cleanup_complete"]
            assert late.closes == 0
            await pending.value.cleanup()
            await pending.value.cleanup()
        else:
            result = await api().run_node_case("N01", fixture, tmp_path)
            assert result.status == "failed" and result.observations["cleanup_complete"]
        assert late.closes == 1 and fixture.component.close_calls == 1
        assert len(audits) == 2, "final audit must not be repeated during cleanup"

    asyncio.run(run())


def test_pending_cleanup_restores_case_context_for_late_returned_session(tmp_path):
    async def run():
        fixture = Fixture()
        reset_calls = []

        class Late:
            closes = 0

            def close(self):
                self.closes += 1

        late = Late()

        def change(session):
            async def fault(kind):
                if kind != "reset":
                    return session.inject_fault(kind)
                reset_calls.append(True)
                if len(reset_calls) <= 2:
                    raise RuntimeError("reset pending")
                session.inject_fault(kind)

                async def returned_owner():
                    return api().NodeContractSession(
                        session.component, resources=(api().NodeContractResource(late),)
                    )

                return asyncio.create_task(returned_owner())

            return dataclasses.replace(session, inject_fault=fault)

        fixture.transform = change
        with pytest.raises(AdapterContractCleanupPending) as pending:
            await api().run_node_case("N06", fixture, tmp_path)
        assert fixture.component.close_calls == late.closes == 0
        await pending.value.cleanup()
        await pending.value.cleanup()
        assert fixture.component.close_calls == late.closes == 1
        assert len(reset_calls) == 3

    asyncio.run(run())


def test_foreign_loop_future_retains_original_work_and_owners_until_done(tmp_path):
    foreign_loop = asyncio.new_event_loop()
    future = foreign_loop.create_future()
    calls = []

    async def configure(kind, data):
        calls.append(True)
        return future

    fixture = Fixture(transform=lambda s: dataclasses.replace(s, configure=configure))

    async def run():
        with pytest.raises(AdapterContractCleanupPending) as pending:
            await api().run_node_case("N02", fixture, tmp_path)
        assert not future.done() and fixture.component.close_calls == 0
        assert not pending.value.result.observations["cleanup_complete"]
        future.set_result(None)
        await pending.value.cleanup()
        await pending.value.cleanup()
        assert fixture.component.close_calls == 1 and len(calls) == 1

    try:
        asyncio.run(run())
    finally:
        if not future.done():
            future.set_result(None)
        foreign_loop.close()


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_entire_return_graph_is_retained_before_draining_any_sibling(nested, wrapped, tmp_path):
    foreign_loop = asyncio.new_event_loop()
    foreign = foreign_loop.create_future()

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        callback_calls = []
        live = []

        class Late:
            closes = 0

            def close(self):
                self.closes += 1

        late = Late()

        async def actual_work():
            entered.set()
            await release.wait()

        def change(session):
            async def configure(kind, data):
                callback_calls.append(True)
                actual = asyncio.create_task(actual_work())
                live.append(actual)
                late_session = api().NodeContractSession(
                    session.component, resources=(api().NodeContractResource(late),)
                )
                graph = (
                    {"items": ([foreign], {"work": actual, "session": late_session})}
                    if nested
                    else [
                        foreign,
                        actual,
                        late_session,
                    ]
                )
                if wrapped:
                    done = asyncio.get_running_loop().create_future()
                    done.set_result(graph)
                    return done
                return graph

            return dataclasses.replace(session, configure=configure)

        fixture = Fixture(transform=change)
        cleanup = None
        try:
            with pytest.raises(AdapterContractCleanupPending) as pending:
                await api().run_node_case("N02", fixture, tmp_path)
            await entered.wait()
            assert fixture.component.close_calls == late.closes == 0
            foreign.set_result(None)
            cleanup = asyncio.create_task(pending.value.cleanup())
            await asyncio.wait((cleanup,), timeout=0.02)
            assert not cleanup.done(), "an earlier pending sibling must not hide live work"
            assert fixture.component.close_calls == late.closes == 0
            release.set()
            await cleanup
            await pending.value.cleanup()
            assert fixture.component.close_calls == late.closes == 1
            assert len(callback_calls) == len(live) == 1
        finally:
            release.set()
            if cleanup is not None:
                await asyncio.gather(cleanup, return_exceptions=True)
            await asyncio.gather(*live, return_exceptions=True)

    try:
        asyncio.run(asyncio.wait_for(run(), 5))
    finally:
        if not foreign.done():
            foreign.set_result(None)
        foreign_loop.close()


@pytest.mark.parametrize("has_later", [False, True])
def test_unadopted_client_debt_keeps_earlier_dependency_until_original_repair(has_later, tmp_path):
    async def run():
        closed = []

        class Dependency:
            def close(self):
                closed.append("dependency")

        class Client:
            close = None

        class Later:
            def close(self):
                closed.append("later")

        client = Client()
        resources = [api().NodeContractResource(Dependency()), api().NodeContractResource(client)]
        if has_later:
            resources.append(api().NodeContractResource(Later()))
        fixture = Fixture(transform=lambda s: dataclasses.replace(s, resources=resources))
        with pytest.raises(AdapterContractCleanupPending) as pending:
            await api().run_node_case("N01", fixture, tmp_path)
        assert closed == (["later"] if has_later else [])
        client.close = lambda: closed.append("client")
        await pending.value.cleanup()
        assert closed == (
            ["later", "client", "dependency"] if has_later else ["client", "dependency"]
        )

    asyncio.run(run())
