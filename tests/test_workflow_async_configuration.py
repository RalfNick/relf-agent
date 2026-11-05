"""Explicit Local node factories, original owned lifetime and Temporal fences."""

import asyncio
import json

import pytest

import relf_agent as r
from relf_agent.errors import ValidationError


@pytest.mark.parametrize("extension", ["json", "toml"])
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_default_node_factory_from_catalog_runs_without_model(tmp_path, extension, mode):
    profile = {
        "name": "nodes",
        "version": "1",
        "providers": {},
        "components": {"workflow_executors": {"adapter": "identity", "config": {}}},
    }
    path = tmp_path / ("runtime." + extension)
    if extension == "json":
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "default": {"name": "nodes", "version": "1"},
                    "profiles": [profile],
                }
            )
        )
    else:
        path.write_text("""schema_version = 1
[default]
name = "nodes"
version = "1"
[[profiles]]
name = "nodes"
version = "1"
providers = {}
[profiles.components.workflow_executors]
adapter = "identity"
""")
    selected = r.load_catalog(path).default
    flow = r.GraphWorkflowSpec(
        "identity", [r.GraphNode("identity", executor="identity")], output=r.ValueRef("identity")
    )

    async def exercise(runtime):
        handle = runtime.submit(flow, [1, None, "中"], command_id="submit")
        done = await runtime.drive(handle.run_id)
        assert done.state == "succeeded" and done.result == [1, None, "中"]
        assert len(runtime.store.run(handle.run_id)["actions"]) == 1

    if mode == "sync":
        with r.RuntimeBuilder().build(selected, tmp_path / "run.sqlite") as runtime:
            asyncio.run(exercise(runtime))
    else:

        async def run():
            async with await r.RuntimeBuilder().abuild(
                selected, tmp_path / "run.sqlite"
            ) as runtime:
                await exercise(runtime)

        asyncio.run(run())


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_bad_node_factory_config_refuses_before_store_allocation(tmp_path, mode):
    calls = []

    def store(*args, **kwargs):
        calls.append(True)
        pytest.fail("Invalid node declaration allocated a Store")

    profile = r.RuntimeProfile(
        "bad", "1", {}, {"workflow_executors": {"adapter": "identity", "config": {"unknown": True}}}
    )
    builder = r.RuntimeBuilder(store_factory=store)
    if mode == "sync":
        with pytest.raises(ValidationError):
            builder.build(profile, tmp_path / "run.sqlite")
    else:

        async def run():
            with pytest.raises(ValidationError):
                await builder.abuild(profile, tmp_path / "run.sqlite")

        asyncio.run(run())
    assert calls == [] and not (tmp_path / "run.sqlite").exists()


def test_async_custom_factory_owns_client_through_original_ledger(tmp_path):
    assert hasattr(r, "NodeExecutorRegistry")
    created = []

    class Client:
        identity = {"kind": "owned-node", "version": "1"}

        def __init__(self):
            self.closed = 0

        async def execute(self, input, config, context):
            assert self.closed == 0
            return {"value": input}

        async def aclose(self):
            self.closed += 1

    async def build(config, context):
        component = context.own_async(Client())
        created.append(component)
        nodes = r.NodeExecutorRegistry()
        nodes.register(r.NodeExecutorSpec("custom", "Custom", effect="read_only"), component)
        return nodes

    components = r.ComponentRegistry()
    components.register_async("workflow_executors", "custom", build)
    profile = r.RuntimeProfile("custom", "1", {}, {"workflow_executors": {"adapter": "custom"}})

    async def run():
        async with await r.RuntimeBuilder(components).abuild(
            profile, tmp_path / "run.sqlite"
        ) as runtime:
            flow = r.GraphWorkflowSpec(
                "custom", [r.GraphNode("n", executor="custom")], output=r.ValueRef("n")
            )
            handle = runtime.submit(flow, None, command_id="submit")
            assert (await runtime.drive(handle.run_id)).result == {"value": None}
        assert created[0].closed == 1

    asyncio.run(run())


def test_temporal_profile_rejects_local_executor_component_before_factory():
    from relf_agent.temporal_profile import TemporalProfile

    with pytest.raises(ValidationError, match="Local execution components"):
        TemporalProfile(
            "nodes",
            "1",
            {"default": {"adapter": "offline-echo"}},
            # Node executors are shared now; selecting a Local compiler still
            # cannot change Temporal's execution authority.
            {"workflow_compiler": {"adapter": "static"}},
        )


@pytest.mark.parametrize("wrapped", ["graph", "team", "dynamic"])
def test_temporal_runtime_rejects_executor_graph_recursively_without_rpc(wrapped):
    pytest.importorskip("temporalio")
    from relf_agent.runtime_builder import EchoProvider
    from relf_agent.temporal_activities import TemporalRuntime
    from relf_agent.temporal_state import validate_request
    from relf_agent.types import submission_request

    flow = r.GraphWorkflowSpec("nodes", [r.GraphNode("n", executor="identity")])
    if wrapped == "team":
        flow = r.TeamSpec("team", {"nodes": flow})
    elif wrapped == "dynamic":
        flow = r.DynamicWorkflowSpec("dynamic", {"nodes": flow})
    runtime = TemporalRuntime(
        providers={"default": EchoProvider("offline")}, tools=r.ToolRegistry()
    )
    control = r.GraphWorkflowSpec("control", [r.GraphNode("a", agent=r.AgentSpec("a", "Answer"))])
    if wrapped == "team":
        control = r.TeamSpec("team", {"nodes": control})
    elif wrapped == "dynamic":
        control = r.DynamicWorkflowSpec("dynamic", {"nodes": control})
    validate_request(submission_request(control, "q"), runtime.orchestration_release)
    with pytest.raises(ValidationError, match="Agent nodes only"):
        validate_request(submission_request(flow, "q"), runtime.orchestration_release)


def test_temporal_worker_and_coding_publication_reject_executor_graph():
    pytest.importorskip("temporalio")
    from dataclasses import asdict

    from relf_agent.runtime_builder import EchoProvider
    from relf_agent.temporal_activities import TemporalRuntime
    from relf_agent.temporal_coding_composition_protocol import _direct_agents
    from relf_agent.temporal_parent_state import TemporalParentState
    from relf_agent.types import submission_request

    flow = r.GraphWorkflowSpec("nodes", [r.GraphNode("n", executor="identity")])
    runtime = TemporalRuntime(
        providers={"default": EchoProvider("offline")}, tools=r.ToolRegistry()
    )
    with pytest.raises(ValidationError, match="Agent nodes only"):
        TemporalParentState(
            "root",
            asdict(r.Scope()),
            "submit",
            submission_request(flow, "q"),
            runtime.orchestration_release,
        )
    with pytest.raises(ValidationError, match="Agent nodes only"):
        _direct_agents(flow.to_dict())
