"""Observing a run must not execute constants or count unrelated cloned code."""

import inspect
import sys
import threading
from types import SimpleNamespace

import pytest

from .test_default_chain_acceptance import tool


def test_unrelated_python_code_constants_are_never_hashed_by_observer():
    class Constant:
        def __hash__(self):
            raise AssertionError("Observer executed unrelated code constant")

    code = (lambda: None).__code__.replace(co_consts=(None, Constant()))
    measurement = tool().Measurements()
    measurement.profile(SimpleNamespace(f_code=code), "call", None)
    assert not measurement.controls


def test_equal_but_distinct_code_is_not_an_original_engine_invocation():
    from relf_agent import LocalEngine

    code = inspect.unwrap(LocalEngine.submit).__code__
    clone = code.replace()
    assert clone == code and clone is not code
    measurement = tool().Measurements()
    measurement.profile(SimpleNamespace(f_code=clone), "call", None)
    assert not measurement.controls


@pytest.mark.parametrize("fallback", [False, True])
def test_original_engine_controls_are_counted_and_profile_restored_on_exception(
    tmp_path, monkeypatch, fallback
):
    from relf_agent import AgentSpec, LocalEngine, SQLiteStore, ToolRegistry

    class Provider:
        identity = {"kind": "offline-observer-regression", "version": "1"}

        async def complete(self, messages, tools):
            raise AssertionError("No model dispatch during measurement regression")

    previous = sys.getprofile()
    if fallback:
        monkeypatch.delattr(sys, "monitoring", raising=False)
    with LocalEngine(
        SQLiteStore(tmp_path / "run.sqlite"),
        providers={"default": Provider()},
        tools=ToolRegistry(),
    ) as engine:
        measurement = tool().Measurements()
        with pytest.raises(RuntimeError, match="application stopped"), measurement:
            handle = engine.submit(AgentSpec("a", "Answer"), "q", command_id="s")
            engine.cancel(handle.run_id, command_id="c")
            raise RuntimeError("application stopped")
        assert sys.getprofile() is previous
        assert measurement.controls["submit"] == measurement.controls["cancel"] == 1
        assert engine.status(handle.run_id).state == "cancelled"


def test_callback_uses_no_frame_arguments_or_locals():
    from relf_agent import LocalEngine

    class Frame:
        f_code = inspect.unwrap(LocalEngine.status).__code__

        @property
        def f_locals(self):
            raise AssertionError("Frame arguments must stay private")

    measurement = tool().Measurements()
    measurement.profile(Frame(), "call", object())
    measurement.profile(Frame(), "return", object())
    assert dict(measurement.controls) == {"status": 1}


@pytest.mark.skipif(not hasattr(sys, "monitoring"), reason="Python 3.12 local monitoring")
def test_monitoring_is_local_and_callbacks_and_slot_are_released_on_error():
    from relf_agent import LocalEngine

    monitoring = sys.monitoring
    codes = [
        inspect.unwrap(getattr(LocalEngine, name)).__code__
        for name in ("submit", "approve", "cancel", "reconcile", "status", "diagnostics")
    ]
    assert monitoring.get_tool(2) is None
    with pytest.raises(RuntimeError, match="application stopped"), tool().Measurements():
        assert monitoring.get_tool(2) is not None
        assert monitoring.get_events(2) == 0
        assert all(
            monitoring.get_local_events(2, code) == monitoring.events.PY_START for code in codes
        )
        assert sys.getprofile() is None
        raise RuntimeError("application stopped")
    assert monitoring.get_tool(2) is None and monitoring.get_events(2) == 0
    assert all(monitoring.get_local_events(2, code) == 0 for code in codes)
    monitoring.use_tool_id(2, "check-release")
    try:
        assert monitoring.register_callback(2, monitoring.events.PY_START, None) is None
    finally:
        monitoring.free_tool_id(2)


@pytest.mark.skipif(not hasattr(sys, "monitoring"), reason="Python 3.12 local monitoring")
def test_partial_monitor_registration_is_cleaned_before_failure_returns(monkeypatch):
    from relf_agent import LocalEngine

    original, calls = sys.monitoring, []

    class Monitoring:
        def __getattr__(self, name):
            return getattr(original, name)

        def set_local_events(self, owner, code, events):
            if events:
                calls.append(code)
                if len(calls) == 2:
                    raise RuntimeError("registration rejected")
            return original.set_local_events(owner, code, events)

    monkeypatch.setattr(sys, "monitoring", Monitoring())
    with pytest.raises(RuntimeError, match="registration rejected"):
        with tool().Measurements():
            pytest.fail("The incomplete observer cannot start work")
    assert original.get_tool(2) is None
    code = inspect.unwrap(LocalEngine.submit).__code__
    assert original.get_local_events(2, code) == 0
    original.use_tool_id(2, "check-partial-release")
    try:
        assert original.register_callback(2, original.events.PY_START, None) is None
    finally:
        original.free_tool_id(2)


@pytest.mark.skipif(not hasattr(sys, "monitoring"), reason="Python 3.12 local monitoring")
def test_existing_monitor_owner_is_not_replaced_or_disabled():
    monitoring = sys.monitoring
    monitoring.use_tool_id(2, "another-observer")
    monitoring.set_events(2, monitoring.events.PY_START)
    try:
        with pytest.raises(RuntimeError):
            with tool().Measurements():
                pytest.fail("An occupied observer slot cannot be stolen")
        assert monitoring.get_tool(2) == "another-observer"
        assert monitoring.get_events(2) == monitoring.events.PY_START
    finally:
        monitoring.set_events(2, 0)
        monitoring.free_tool_id(2)


@pytest.mark.skipif(not hasattr(sys, "monitoring"), reason="Python 3.12 local monitoring")
def test_detached_foreign_callback_is_preserved_when_registration_refuses():
    monitoring = sys.monitoring

    def callback(code, offset):
        return None

    monitoring.use_tool_id(2, "previous-observer")
    monitoring.register_callback(2, monitoring.events.PY_START, callback)
    monitoring.free_tool_id(2)  # CPython deliberately retains callbacks here.
    try:
        with pytest.raises(RuntimeError):
            with tool().Measurements():
                pytest.fail("Stale foreign callbacks are not ours to replace")
        assert monitoring.get_tool(2) is None
        monitoring.use_tool_id(2, "inspect-preserved-callback")
        assert monitoring.register_callback(2, monitoring.events.PY_START, None) is callback
    finally:
        if monitoring.get_tool(2) is None:
            monitoring.use_tool_id(2, "cleanup-test-callback")
        monitoring.register_callback(2, monitoring.events.PY_START, None)
        monitoring.free_tool_id(2)


@pytest.mark.skipif(not hasattr(sys, "monitoring"), reason="Python 3.12 local monitoring")
def test_local_events_do_not_add_other_thread_invocations_to_current_thread_scope():
    from relf_agent import LocalEngine

    measurement = tool().Measurements()
    assert callable(getattr(measurement, "on_start", None))
    code = inspect.unwrap(LocalEngine.status).__code__
    with measurement:
        worker = threading.Thread(target=lambda: measurement.on_start(code, 0))
        worker.start()
        worker.join()
        assert not measurement.controls
        measurement.on_start(code, 0)
        assert dict(measurement.controls) == {"status": 1}


@pytest.mark.parametrize("fallback", [False, True])
def test_rejected_reentry_preserves_outer_window_and_releases_it(monkeypatch, fallback):
    previous = sys.getprofile()
    if fallback:
        monkeypatch.delattr(sys, "monitoring", raising=False)
    measurement = tool().Measurements()
    try:
        with measurement:
            started = measurement.started
            with pytest.raises(RuntimeError):
                with measurement:
                    pytest.fail("An active observer cannot reenter itself")
            assert measurement.started == started
        assert sys.getprofile() is previous
    finally:
        sys.setprofile(previous)
