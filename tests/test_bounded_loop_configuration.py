"""Explicit loop roles share pure configuration, never execution ownership."""

import asyncio
import copy
import json

import pytest

import relf_agent as r
from relf_agent.errors import ValidationError
from relf_agent.runtime_builder import EchoProvider
from relf_agent.temporal_components import default_components, orchestration_identity
from relf_agent.types import digest


def options():
    return {
        "worker": "perform",
        "until": {
            "value": {"kind": "ref", "path": ["checks", 0, "stop"]},
            "equals": "continue",
            "negate": True,
        },
        "max_iterations": 2,
        "version": "review-1",
    }


def registry():
    value = r.ComponentRegistry()
    for role in ("planners", "plan_verifiers"):
        assert (role, "bounded-loop") in value._factories
    return value


def profile():
    return r.RuntimeProfile(
        "review",
        "1",
        {"default": {"adapter": "offline-echo"}},
        {
            role: {"adapter": "bounded-loop", "config": options()}
            for role in ("planners", "plan_verifiers")
        },
    )


def catalog_file(tmp_path, extension, *, temporal=False):
    path = tmp_path / ("runtime." + extension)
    if extension == "json":
        value = {
            "schema_version": 1,
            "default": {"name": "review", "version": "1"},
            "profiles": [
                {
                    "name": "review",
                    "version": "1",
                    "providers": profile().providers,
                    "components": profile().components,
                }
            ],
        }
        if temporal:
            value["kind"] = "temporal-profiles"
        path.write_text(json.dumps(value))
    else:
        head = (
            ('kind = "temporal-profiles"\n' if temporal else "")
            + """schema_version = 1
[default]
name = "review"
version = "1"
[[profiles]]
name = "review"
version = "1"
[profiles.providers.default]
adapter = "offline-echo"
"""
        )
        for role in ("planners", "plan_verifiers"):
            head += f"""
[profiles.components.{role}]
adapter = "bounded-loop"
[profiles.components.{role}.config]
worker = "perform"
max_iterations = 2
version = "review-1"
[profiles.components.{role}.config.until]
equals = "continue"
negate = true
[profiles.components.{role}.config.until.value]
kind = "ref"
path = ["checks", 0, "stop"]
"""
        path.write_text(head)
    return path


class ReviewNode:
    identity = {"kind": "configured-loop-review", "version": "1"}

    def __init__(self):
        self.inputs = []

    async def execute(self, input, config, context):
        self.inputs.append(copy.deepcopy(input))
        previous = input["previous"]
        return {
            "checks": [{"stop": "continue" if input["iteration"] < 2 else "ready"}],
            "round": input["iteration"],
            "previous_round": None if previous is None else previous["round"],
            "ticket": input["task"]["ticket"],
        }


def with_worker(registrations, node):
    def build(config, context):
        assert config == {}
        nodes = r.NodeExecutorRegistry()
        nodes.register(
            r.NodeExecutorSpec("review", "Review adopted previous output", "read_only"), node
        )
        return nodes

    registrations.register("workflow_executors", "review", build)
    return registrations


def workflow():
    member = r.GraphWorkflowSpec(
        "review-member", [r.GraphNode("review", executor="review")], output=r.ValueRef("review")
    )
    return r.DynamicWorkflowSpec(
        "review-loop",
        {"perform": member},
        planner="bounded-loop",
        verifier="bounded-loop",
        plan_mode="dag",
        child_budget=1,
        max_steps=3,
        max_revisions=3,
        max_depth=3,
    )


def test_public_export_and_two_roles_create_detached_pure_instances():
    assert hasattr(r, "BoundedLoopPolicy")
    assert "BoundedLoopPolicy" in r.__all__
    assert len(r.__all__) == len(set(r.__all__))
    registrations = registry()
    policies = []
    for role in ("planners", "plan_verifiers"):
        supplied = options()
        factory, prepared = registrations.prepare(
            role, {"adapter": "bounded-loop", "config": supplied}
        )
        supplied["until"]["value"]["path"].append("caller-change")
        created = factory(prepared, None)
        assert set(created) == {"bounded-loop"}
        policy = created["bounded-loop"]
        assert isinstance(policy, r.BoundedLoopPolicy)
        before = policy.identity
        prepared["until"]["equals"] = "later-change"
        assert policy.identity == before
        expected = r.BoundedLoopPolicy(
            "perform",
            until=r.BranchCondition(r.ValueRef(path=("checks", 0, "stop")), "continue", True),
            max_iterations=2,
            version="review-1",
        )
        assert policy.identity == expected.identity
        policies.append(policy)
    assert policies[0] is not policies[1] and policies[0].identity == policies[1].identity


@pytest.mark.parametrize("role", ["planners", "plan_verifiers"])
def test_empty_config_keeps_original_default_condition_and_finite_iterations(role):
    factory, prepared = registry().prepare(role, {"adapter": "bounded-loop", "config": {}})
    actual = factory(prepared, None)["bounded-loop"]
    assert actual.identity == r.BoundedLoopPolicy().identity
    proposal = asyncio.run(actual.plan(r.PlanningRequest("task", ["worker"], [], 0), None))
    assert proposal.to_dict()["nodes"][0]["member"] == "worker"
    assert actual.verify(
        r.PlanningRequest(
            "task", ["worker"], [{"id": "opaque", "member": "worker", "result": {"done": True}}], 0
        )
    ).to_dict() == {"status": "succeeded", "result": {"done": True}}


@pytest.mark.parametrize("role", ["planners", "plan_verifiers"])
def test_explicit_null_condition_and_iteration_cap_survive_configuration(role):
    configured = {
        "until": {"value": {"kind": "ref", "path": ["answer"]}, "equals": None},
        "max_iterations": 1,
    }
    factory, prepared = registry().prepare(role, {"adapter": "bounded-loop", "config": configured})
    policy = factory(prepared, None)["bounded-loop"]
    records = [{"id": "first", "member": "worker", "result": {"answer": "pending"}}]
    assert policy.verify(r.PlanningRequest("task", ["worker"], records, 0)).to_dict() == {
        "status": "failed",
        "result": {
            "reason": "loop_iteration_limit",
            "iterations": 1,
            "last_result": {"answer": "pending"},
        },
    }
    records[0]["result"] = {"answer": None}
    assert policy.verify(r.PlanningRequest("task", ["worker"], records, 0)).to_dict() == {
        "status": "succeeded",
        "result": {"answer": None},
    }


def test_sdk_same_pure_policy_runs_both_original_roles_with_a_replaced_member(tmp_path):
    node = ReviewNode()
    nodes = r.NodeExecutorRegistry()
    nodes.register(r.NodeExecutorSpec("review", "Review previous output", "read_only"), node)
    policy = r.BoundedLoopPolicy(
        "perform",
        until=r.BranchCondition(r.ValueRef(path=("checks", 0, "stop")), "continue", True),
        max_iterations=2,
        version="sdk-1",
    )
    with r.LocalEngine(
        r.SQLiteStore(tmp_path / "sdk.sqlite"),
        providers={},
        tools=r.ToolRegistry(),
        workflow_executors=nodes,
        planners={"bounded-loop": policy},
        plan_verifiers={"bounded-loop": policy},
    ) as engine:
        handle = engine.submit(workflow(), {"ticket": "INC-7"}, command_id="sdk", budget=2)
        done = asyncio.run(engine.drive(handle.run_id))
        assert done.state == "succeeded", done.error
        assert done.result == {
            "checks": [{"stop": "ready"}],
            "round": 2,
            "previous_round": 1,
            "ticket": "INC-7",
        }
        assert [value["iteration"] for value in node.inputs] == [1, 2]
        assert engine.diagnostics(handle.run_id).budget["spent"] == 2


@pytest.mark.parametrize("extension", ["json", "toml"])
@pytest.mark.parametrize("construction", ["build", "abuild"])
def test_local_declared_alias_condition_path_and_limit_execute_two_adopted_rounds(
    tmp_path, extension, construction
):
    selected = r.load_catalog(catalog_file(tmp_path, extension)).default
    assert selected.identity == profile().identity
    node = ReviewNode()
    registrations = with_worker(registry(), node)
    selected = r.RuntimeProfile(
        selected.name,
        selected.version,
        selected.providers,
        {**selected.components, "workflow_executors": {"adapter": "review"}},
    )

    async def exercise(runtime):
        handle = runtime.submit(workflow(), {"ticket": "INC-7"}, command_id="same", budget=3)
        done = await runtime.drive(handle.run_id)
        assert done.state == "succeeded", done.error
        assert done.result == {
            "checks": [{"stop": "ready"}],
            "round": 2,
            "previous_round": 1,
            "ticket": "INC-7",
        }
        assert node.inputs == [
            {"task": {"ticket": "INC-7"}, "previous": None, "iteration": 1},
            {
                "task": {"ticket": "INC-7"},
                "previous": {
                    "checks": [{"stop": "continue"}],
                    "round": 1,
                    "previous_round": None,
                    "ticket": "INC-7",
                },
                "iteration": 2,
            },
        ]
        assert runtime.diagnostics(handle.run_id).budget["spent"] == 2
        events = runtime.events(handle.run_id)
        repeated = runtime.submit(workflow(), {"ticket": "INC-7"}, command_id="same", budget=3)
        assert repeated == handle
        assert (await runtime.drive(handle.run_id)).result == done.result
        assert runtime.events(handle.run_id) == events and len(node.inputs) == 2

    if construction == "build":
        with r.RuntimeBuilder(registrations).build(selected, tmp_path / "loop.sqlite") as runtime:
            asyncio.run(exercise(runtime))
    else:

        async def run():
            async with await r.RuntimeBuilder(registrations).abuild(
                selected, tmp_path / "loop.sqlite"
            ) as runtime:
                await exercise(runtime)

        asyncio.run(run())


@pytest.mark.parametrize("extension", ["json", "toml"])
def test_temporal_profile_explicitly_assembles_both_roles_without_service_or_owner(
    tmp_path, extension
):
    from relf_agent.temporal_builder import TemporalRuntimeBuilder
    from relf_agent.temporal_profile import TemporalProfileCatalog

    selected = TemporalProfileCatalog.from_file(
        catalog_file(tmp_path, extension, temporal=True)
    ).default_profile

    async def run():
        assembly = await TemporalRuntimeBuilder(registry()).abuild(selected)
        try:
            planner = assembly._runtime.planners["bounded-loop"]
            verifier = assembly._runtime.verifiers["bounded-loop"]
            assert planner is not verifier and planner.identity == verifier.identity
            assert (
                planner.identity
                == r.BoundedLoopPolicy(
                    "perform",
                    until=r.BranchCondition(
                        r.ValueRef(path=("checks", 0, "stop")), "continue", True
                    ),
                    max_iterations=2,
                    version="review-1",
                ).identity
            )
            release = assembly.release["orchestration"]
            assert release["planners"]["bounded-loop"]["identity"] == planner.identity
            assert release["planners"]["bounded-loop"]["agent"] is None
            assert release["verifiers"]["bounded-loop"]["identity"] == verifier.identity
            assert assembly._client is None and assembly._worker is None
            assert assembly._context._resources == []
        finally:
            await assembly.aclose()

    asyncio.run(run())


INVALID = [
    {"unknown": True},
    {"worker": ""},
    {"worker": "bad/name"},
    {"max_iterations": True},
    {"max_iterations": 0},
    {"max_iterations": 33},
    {"max_iterations": 1.5},
    {"version": ""},
    {"until": "predicate"},
    {"until": {}},
    {"until": {"equals": True}},
    {"until": {"value": {"kind": "ref"}}},
    {"until": {"value": {"kind": "ref"}, "equals": True, "unknown": None}},
    {"until": {"value": {"kind": "literal", "value": True}, "equals": True}},
    {"until": {"value": {"kind": "ref", "source": "previous"}, "equals": True}},
    {"until": {"value": {"kind": "ref", "required": False}, "equals": True}},
    {"until": {"value": {"kind": "ref", "path": [-1]}, "equals": True}},
    {"until": {"value": {"kind": "ref", "path": ["p"] * 33}, "equals": True}},
    {"until": {"value": {"kind": "ref"}, "equals": True, "negate": 1}},
    {"until": {"value": {"kind": "ref", "unknown": None}, "equals": True}},
]


@pytest.mark.parametrize("role", ["planners", "plan_verifiers"])
@pytest.mark.parametrize("config", INVALID)
def test_invalid_loop_configuration_is_rejected_by_pure_component_preflight(role, config):
    with pytest.raises(ValidationError):
        registry().prepare(role, {"adapter": "bounded-loop", "config": config})


@pytest.mark.parametrize("role", ["planners", "plan_verifiers"])
@pytest.mark.parametrize("construction", ["build", "abuild", "temporal-abuild"])
def test_invalid_condition_refuses_before_any_provider_or_execution_store(
    tmp_path, role, construction
):
    registrations, allocated = registry(), []

    def provider(config, context):
        allocated.append("provider")
        pytest.fail("Invalid loop configuration allocated a provider")

    def store(*args, **kwargs):
        allocated.append("store")
        pytest.fail("Invalid loop configuration allocated a store")

    registrations.register("provider", "must-not-construct", provider)
    providers = {"default": {"adapter": "must-not-construct"}}
    components = {
        role: {
            "adapter": "bounded-loop",
            "config": {"until": {"value": {"kind": "ref", "source": "other"}, "equals": True}},
        }
    }
    path = tmp_path / "never.sqlite"
    if construction == "temporal-abuild":
        from relf_agent.temporal_builder import TemporalRuntimeBuilder
        from relf_agent.temporal_profile import TemporalProfile

        async def run():
            with pytest.raises(ValidationError):
                await TemporalRuntimeBuilder(registrations).abuild(
                    TemporalProfile("bad", "1", providers, components), data_path=path
                )

        asyncio.run(run())
    else:
        selected = r.RuntimeProfile("bad", "1", providers, components)
        builder = r.RuntimeBuilder(registrations, store_factory=store)
        if construction == "build":
            with pytest.raises(ValidationError):
                builder.build(selected, path)
        else:

            async def run():
                with pytest.raises(ValidationError):
                    await builder.abuild(selected, path)

            asyncio.run(run())
    assert allocated == [] and not path.exists()


def test_unselected_loop_preserves_default_tables_and_ordinary_releases(tmp_path):
    assert (
        digest(orchestration_identity(*default_components()))
        == "ee461ffd77a6d533e558b4c0bf66ac9c1268cf522e305dbbb0967114ce98a3db"
    )
    temporal = r.TemporalRuntime(
        providers={"default": EchoProvider("offline")}, tools=r.ToolRegistry()
    )
    assert (
        digest(temporal.manifest)
        == "6995f742a043cebc63f047bbc3ea833e41da3b8a86ad26650672a386f34d4f44"
    )
    assert "bounded-loop" not in temporal.planners and "bounded-loop" not in temporal.verifiers
    with r.RuntimeBuilder().build(
        r.RuntimeProfile("ordinary", "1", {"default": {"adapter": "offline-echo"}}),
        tmp_path / "ordinary.sqlite",
    ) as runtime:
        assert set(runtime._orchestration.planners) == {"rule", "dag-rule", "dag-model"}
        assert set(runtime._orchestration.verifiers) == {"complete"}
        accepted = runtime.submit(r.AgentSpec("ordinary", "Answer"), "q", command_id="ordinary")
        assert asyncio.run(runtime.drive(accepted.run_id)).state == "succeeded"
