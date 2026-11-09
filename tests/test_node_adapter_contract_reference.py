"""The offline reference records actual calls and retains its original client."""

import asyncio
import importlib
import importlib.util
import json

import pytest

from relf_agent import InvocationContext, Scope
from relf_agent.errors import ValidationError


def api():
    name = "relf_agent.node_adapter_contract_reference"
    assert importlib.util.find_spec(name) is not None, "Independent node reference is missing"
    return importlib.import_module(name)


def context():
    return InvocationContext(Scope(), "run", "action", "attempt", "effect", "epoch")


@pytest.mark.parametrize("result", [None, False, 0, "", [1, {"text": "中文"}]])
def test_configured_result_preserves_finite_json_and_records_separate_input_config(
    tmp_path, result
):
    async def run():
        node = api().ReferenceNodeSource(tmp_path / "source.sqlite")
        try:
            node.configure("output", {"result": result})
            actual = await node.execute([None, False, 0], {"mode": "separate"}, context())
            assert json.dumps(actual, sort_keys=True) == json.dumps(result, sort_keys=True)
            assert node.requests() == [
                {"input": [None, False, 0], "config": {"mode": "separate"}, "effect_key": "effect"}
            ]
            assert json.dumps(node.requests()[0]["input"]) == "[null, false, 0]"
            assert node.audit() == {"execute_calls": 1, "reconcile_calls": 0, "close_calls": 0}
        finally:
            node.close()
        node.close()
        assert node.audit()["close_calls"] == 1
        with pytest.raises(ValidationError):
            await node.execute(None, {}, context())

    asyncio.run(run())


def test_reopen_retains_identity_calls_and_completed_configuration(tmp_path):
    async def run():
        node = api().ReferenceNodeSource(tmp_path / "source.sqlite")
        original = node.identity
        try:
            node.configure("output", {"result": {"receipt": True}})
            await node.execute("first", {}, context())
            node.reopen()
            assert node.identity == original
            assert await node.execute("second", {}, context()) == {"receipt": True}
            assert node.audit()["execute_calls"] == 2
            assert node.audit()["close_calls"] == 1
        finally:
            node.close()

    asyncio.run(run())


def test_cancelled_wait_does_not_fabricate_actual_handler_exit(tmp_path):
    async def run():
        node = api().ReferenceNodeSource(tmp_path / "source.sqlite")
        pause = node.pause("execute")
        task = asyncio.create_task(node.execute(None, {}, context()))
        try:
            await asyncio.wait_for(pause.wait_entered(), 2)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            with pytest.raises(ValidationError):
                node.close()
            await pause.release()
            assert await asyncio.wait_for(task, 2) is None
        finally:
            await pause.release()
            await asyncio.gather(task, return_exceptions=True)
            node.close()

    asyncio.run(run())


def test_unconfigured_and_invalid_case_reference_does_not_open_files(tmp_path):
    fixture = api().offline_node_fixture()
    with pytest.raises(ValidationError):
        fixture.prepare("N99", tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("fault", ["identity-drift", "method-drift", "handler-error"])
def test_fault_reset_restores_original_ports_and_identity(tmp_path, fault):
    async def run():
        node = api().ReferenceNodeSource(tmp_path / "source.sqlite")
        original_identity, original_method = node.identity, node.execute
        try:
            node.inject_fault(fault)
            if fault == "identity-drift":
                assert node.identity != original_identity
            elif fault == "method-drift":
                assert node.execute != original_method
            else:
                with pytest.raises(RuntimeError):
                    await node.execute(None, {}, context())
            node.inject_fault("reset")
            assert node.identity == original_identity and node.execute == original_method
            assert await node.execute(None, {}, context()) is None
        finally:
            node.close()

    asyncio.run(run())
