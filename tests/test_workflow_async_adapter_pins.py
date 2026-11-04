"""An approved node cannot silently switch its private dispatch implementation."""

import asyncio

import pytest

import relf_agent as r
from relf_agent.errors import DefinitionMismatch

from .test_workflow_async_nodes import Echo, engine, registry


@pytest.mark.parametrize("concurrency", [1, 2])
@pytest.mark.parametrize("mutation", ["execute", "reconcile", "registry", "code"])
def test_private_adapter_drift_refuses_dispatch_then_original_can_retry(
    tmp_path, concurrency, mutation
):
    component, other = Echo(), Echo()
    nodes = registry(component, approval=True)
    adapter = nodes.executor
    spec = r.GraphWorkflowSpec(
        "pins",
        [r.GraphNode("n", executor="business")],
        output=r.ValueRef("n"),
        max_concurrency=concurrency,
    )

    async def substitute(envelope):
        return r.EffectObservation("substituted")

    async def substitute_method(self, envelope):
        return r.EffectObservation("substituted")

    with engine(tmp_path / "run.sqlite", nodes) as runtime:
        handle = runtime.submit(spec, 7, command_id="submit")
        paused = asyncio.run(runtime.drive(handle.run_id))
        assert paused.state == "waiting_approval"
        pending = paused.pending[0]
        if mutation == "registry":
            original = adapter._registry
            adapter._registry = registry(other, approval=True)
        elif mutation == "code":
            original = adapter.execute.__func__.__code__
            adapter.execute.__func__.__code__ = substitute_method.__code__
        else:
            original = getattr(adapter, mutation)
            setattr(adapter, mutation, substitute)
        try:
            receipt = runtime.approve(
                handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
            )
            with pytest.raises(DefinitionMismatch):
                asyncio.run(runtime.drive(handle.run_id))
            assert component.calls == other.calls == []
        finally:
            if mutation == "registry":
                adapter._registry = original
            elif mutation == "code":
                adapter.execute.__func__.__code__ = original
            else:
                setattr(adapter, mutation, original)
        assert (
            runtime.approve(
                handle.run_id, pending["action_id"], pending["digest"], command_id="approve"
            )
            == receipt
        )
        assert asyncio.run(runtime.drive(handle.run_id)).result == 7
        assert len(component.calls) == 1 and not other.calls


def test_private_adapter_drift_during_await_cannot_commit_node_success(tmp_path):
    class Change(Echo):
        async def execute(self, input, config, context):
            self.calls.append(input)
            nodes.executor.execute = substitute
            await asyncio.sleep(0)
            return input

    async def substitute(envelope):
        return r.EffectObservation("substituted")

    component = Change()
    nodes = registry(component)
    original = nodes.executor.execute
    with engine(tmp_path / "run.sqlite", nodes) as runtime:
        handle = runtime.submit(
            r.GraphWorkflowSpec("await", [r.GraphNode("n", executor="business")]),
            7,
            command_id="submit",
        )
        try:
            done = asyncio.run(runtime.drive(handle.run_id))
            assert done.state != "succeeded"
            assert component.calls == [7]
            assert (
                runtime.store.run(handle.run_id)["actions"][0]["effect_observation"]["result"] == 7
            )
        finally:
            nodes.executor.execute = original
