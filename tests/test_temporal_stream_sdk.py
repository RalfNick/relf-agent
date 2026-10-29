import asyncio
from dataclasses import asdict
from types import SimpleNamespace

import pytest

pytest.importorskip("temporalio")
from temporalio import activity, workflow

import relf_agent as r
from relf_agent.temporal_activities import TemporalRuntime, registered_activities
from relf_agent.temporal_state import TemporalRunState
from relf_agent.temporal_workflow import TemporalRunWorkflow
from relf_agent.types import submission_request

from .test_local_stream_updates import Provider


def test_registered_model_and_tool_activities_reach_original_sdk_signal(monkeypatch):
    async def run():
        from relf_agent import temporal_session_activities

        async def tree_guard(*args, **kwargs):
            return None

        monkeypatch.setattr(temporal_session_activities, "validate_tree_activity", tree_guard)
        monkeypatch.setattr(
            activity,
            "info",
            lambda: SimpleNamespace(
                workflow_id="run", workflow_run_id="epoch", workflow_namespace="ns"
            ),
        )
        tools, calls = r.ToolRegistry(), []

        @tools.tool(effect="read_only")
        async def change():
            assert await r.emit_tool_delta({"message": "tool step"})
            calls.append(True)
            return {"found": True}

        runtime = TemporalRuntime(
            providers={"default": r.StreamedModelProvider(Provider(), chunk_chars=1)},
            tools=tools,
            stream_updates=r.StreamUpdatePolicy(),
        )
        state = TemporalRunState(
            "run",
            asdict(r.Scope()),
            "s",
            submission_request(r.AgentSpec("a", "Answer", ("change",)), "q"),
            runtime.manifest,
            execution_epoch="epoch",
        )
        instance = object.__new__(TemporalRunWorkflow)
        instance.state = state
        signals = []

        class Client:
            namespace = "ns"

            def get_workflow_handle(self, workflow_id, *, run_id=None):
                assert (workflow_id, run_id) == ("run", "epoch")
                return self

            async def signal(self, name, payload):
                assert name == "agent_update"
                signals.append(payload)
                instance.agent_update(payload)

        functions = {f.__name__: f for f in registered_activities(runtime, Client())}
        for _ in range(5):
            work = state.next_operation()
            if work is None:
                break
            action, request = work
            if action["kind"] == "model":
                state.accept_model(action["id"], await functions["model"](request))
            else:
                state.accept_tool(action["id"], await functions["tool"](request))
        assert state.state == "succeeded" and len(calls) == 1
        assert {s["update"]["operation"] for s in signals} == {"model", "tool"}
        before = state.diagnostics()
        instance.agent_update({"invalid": True})
        assert state.diagnostics() == before
        definition = workflow._Definition.must_from_class(TemporalRunWorkflow)
        assert "agent_update" in definition.signals

    asyncio.run(run())


def test_original_sdk_workflow_sandbox_accepts_new_pure_signal():
    async def run():
        from relf_agent.temporal import _workflow_runner

        _workflow_runner().prepare_workflow(
            workflow._Definition.must_from_class(TemporalRunWorkflow)
        )

    asyncio.run(run())
