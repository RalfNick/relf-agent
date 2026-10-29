"""Replacement controls return completed, finite DTOs before caller adoption."""

import asyncio
import inspect
import threading
from dataclasses import dataclass, replace

import pytest

from relf_agent import AgentSpec, RuntimeBuilder, RuntimeProfile, Scope
from relf_agent.errors import ValidationError
from relf_agent.task_controls import TaskControlBridge
from relf_agent.types import CommandReceipt, RunDiagnostics, RunHandle, RunSnapshot

KINDS = ["submit", "status", "cancel", "approve", "reconcile", "send_input", "diagnostics"]
COMMANDS = ["submit", "cancel", "approve", "reconcile", "send_input"]


class Controls:
    scope = Scope()

    def __init__(self, value):
        self.value = value
        self.calls = []

    def _response(self, kind):
        self.calls.append(kind)
        return self.value

    def submit(self, *args, **kwargs):
        return self._response("submit")

    def status(self, *args, **kwargs):
        return self._response("status")

    def cancel(self, *args, **kwargs):
        return self._response("cancel")

    def approve(self, *args, **kwargs):
        return self._response("approve")

    def reconcile(self, *args, **kwargs):
        return self._response("reconcile")

    def send_input(self, *args, **kwargs):
        return self._response("send_input")

    def diagnostics(self, *args, **kwargs):
        return self._response("diagnostics")


class AsyncControls(Controls):
    async def submit(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().submit(*args, **kwargs)

    async def status(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().status(*args, **kwargs)

    async def cancel(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().cancel(*args, **kwargs)

    async def approve(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().approve(*args, **kwargs)

    async def reconcile(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().reconcile(*args, **kwargs)

    async def send_input(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().send_input(*args, **kwargs)

    async def diagnostics(self, *args, **kwargs):
        await asyncio.sleep(0)
        return super().diagnostics(*args, **kwargs)


@pytest.fixture(params=[Controls, AsyncControls], ids=["sync", "async"])
def control_type(request):
    return request.param


async def invoke(bridge, kind):
    if kind == "submit":
        return await bridge.submit(AgentSpec("a", "Answer"), "task", command_id="cmd")
    if kind == "status":
        return await bridge.status("run")
    if kind == "cancel":
        return await bridge.cancel("run", command_id="cmd")
    if kind == "approve":
        bridge.require_run_control(kind)
        return await bridge.approve("run", "action", "a" * 64, command_id="cmd")
    if kind == "reconcile":
        bridge.require_run_control(kind)
        return await bridge.reconcile("run", "action", {"confirmed": True}, command_id="cmd")
    if kind == "send_input":
        return await bridge.send_input(
            "run", "input:" + "b" * 64, "a" * 64, "answer", command_id="cmd"
        )
    bridge.require_input_discovery()
    return await bridge.input_diagnostics("run")


def response(kind, nested):
    if kind == "status":
        return RunSnapshot("run", "queued", 0, {"value": nested}, None, (), ())
    if kind == "diagnostics":
        value = RunDiagnostics(
            RunSnapshot("run", "queued", 0, None, None, (), ()), {}, "a" * 64, {}
        )
        # Public nested containers remain mutable after DTO construction.
        value.manifest["value"] = nested
        return value
    receipt = CommandReceipt("cmd", "run", kind, outcome={"value": nested})
    return RunHandle("run", receipt) if kind == "submit" else receipt


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("shape", ["coroutine", "lock", "cycle"])
def test_native_or_cyclic_nested_values_raise_validation_error(control_type, kind, shape):
    entered = []

    async def later():
        entered.append(True)

    value = later() if shape == "coroutine" else threading.Lock() if shape == "lock" else {}
    if shape == "cycle":
        value["self"] = value
    engine = control_type(response(kind, value))
    try:
        with pytest.raises(ValidationError):
            asyncio.run(invoke(TaskControlBridge(engine, engine.scope), kind))
        assert engine.calls == [kind]
        assert entered == []
    finally:
        # The bridge borrows DTO data; its producer owns an invalid nested coroutine.
        if inspect.iscoroutine(value):
            value.close()


@pytest.mark.parametrize("kind", COMMANDS + ["status"])
@pytest.mark.parametrize("invalid", [[], {}], ids=["list", "dict"])
def test_unhashable_state_raises_validation_error(control_type, kind, invalid):
    value = response(kind, None)
    if kind == "status":
        value = replace(value, state=invalid)
    elif kind == "submit":
        value = replace(value, receipt=replace(value.receipt, apply_state=invalid))
    else:
        value = replace(value, apply_state=invalid)
    engine = control_type(value)
    with pytest.raises(ValidationError):
        asyncio.run(invoke(TaskControlBridge(engine, engine.scope), kind))
    assert engine.calls == [kind]


@pytest.mark.parametrize("kind", KINDS)
def test_valid_nested_dtos_are_detached_without_changing_values(control_type, kind):
    engine = control_type(response(kind, {"values": [None, True, 3, "text"]}))
    bridge = TaskControlBridge(engine, engine.scope)
    first = asyncio.run(invoke(bridge, kind))
    assert first == engine.value
    payload = (
        first.manifest
        if kind == "diagnostics"
        else first.result
        if kind == "status"
        else first.receipt.outcome
        if kind == "submit"
        else first.outcome
    )
    payload["value"]["values"].append("caller change")
    second = asyncio.run(invoke(bridge, kind))
    assert second == engine.value
    assert first != second
    assert engine.calls == [kind, kind]


@pytest.mark.parametrize("kind", ["submit", "status", "diagnostics"])
def test_nested_dataclass_payload_remains_typed_and_detached(control_type, kind):
    @dataclass(frozen=True)
    class Detail:
        values: list

    detail = Detail([{"confirmed": True}])
    engine = control_type(response(kind, detail))
    first = asyncio.run(invoke(TaskControlBridge(engine, engine.scope), kind))
    assert first == engine.value
    payload = (
        first.manifest
        if kind == "diagnostics"
        else first.result
        if kind == "status"
        else first.receipt.outcome
    )
    assert isinstance(payload["value"], Detail)
    payload["value"].values[0]["confirmed"] = False
    assert detail.values == [{"confirmed": True}]
    assert first != engine.value


@pytest.mark.parametrize("kind", COMMANDS[1:])
def test_rejected_controls_remain_valid(control_type, kind):
    value = replace(response(kind, None), apply_state="rejected")
    engine = control_type(value)
    assert asyncio.run(invoke(TaskControlBridge(engine, engine.scope), kind)) == value


def test_rejected_response_after_acceptance_can_recover_same_command(tmp_path):
    profile = RuntimeProfile("controls", "1", {"default": {"adapter": "offline-echo"}})
    spec = AgentSpec("a", "Answer")

    async def run():
        with RuntimeBuilder().build(profile, tmp_path / "runs.sqlite") as runtime:

            class Adapter:
                scope = runtime.scope
                invalid = True

                def submit(self, *args, **kwargs):
                    handle = runtime.submit(*args, **kwargs)
                    if self.invalid:
                        return replace(
                            handle,
                            receipt=replace(handle.receipt, outcome={"bad": threading.Lock()}),
                        )
                    return handle

                def status(self, *args, **kwargs):
                    return runtime.status(*args, **kwargs)

                def cancel(self, *args, **kwargs):
                    receipt = runtime.cancel(*args, **kwargs)
                    if self.invalid:
                        return replace(receipt, outcome={"bad": threading.Lock()})
                    return receipt

            adapter = Adapter()
            bridge = TaskControlBridge(adapter, adapter.scope)
            with pytest.raises(ValidationError):
                await bridge.submit(spec, "task", command_id="start")
            original = runtime.submit(spec, "task", command_id="start")
            submitted_events = runtime.events(original.run_id)
            adapter.invalid = False
            recovered = await bridge.submit(spec, "task", command_id="start")
            assert recovered == original
            assert runtime.events(original.run_id) == submitted_events
            assert (await bridge.status(original.run_id)).state == "queued"

            adapter.invalid = True
            with pytest.raises(ValidationError):
                await bridge.cancel(original.run_id, command_id="stop")
            cancelled = runtime.cancel(original.run_id, command_id="stop")
            cancelled_events = runtime.events(original.run_id)
            adapter.invalid = False
            assert await bridge.cancel(original.run_id, command_id="stop") == cancelled
            assert runtime.events(original.run_id) == cancelled_events
            assert (await bridge.status(original.run_id)).state == "cancelled"

    asyncio.run(run())
