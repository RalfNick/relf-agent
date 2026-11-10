"""Fan-out is an explicit pure Planner choice, never a new default authority."""

import asyncio
import json

import pytest

import relf_agent as r
from relf_agent.errors import ValidationError
from relf_agent.runtime_builder import EchoProvider
from relf_agent.temporal_components import default_components, orchestration_identity
from relf_agent.types import digest


def options():
    return {
        "worker": "item",
        "reducer": "summary",
        "items_path": ["payload", "records"],
        "max_items": 4,
        "version": "batch-1",
    }


def profile():
    return r.RuntimeProfile(
        "batch",
        "1",
        {"default": {"adapter": "offline-echo"}},
        {"planners": {"adapter": "fan-out", "config": options()}},
    )


def catalog_file(tmp_path, extension, *, temporal=False):
    path = tmp_path / ("runtime." + extension)
    if extension == "json":
        value = {
            "schema_version": 1,
            "default": {"name": "batch", "version": "1"},
            "profiles": [
                {
                    "name": "batch",
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
        path.write_text(
            ('kind = "temporal-profiles"\n' if temporal else "")
            + """schema_version = 1
[default]
name = "batch"
version = "1"
[[profiles]]
name = "batch"
version = "1"
[profiles.providers.default]
adapter = "offline-echo"
[profiles.components.planners]
adapter = "fan-out"
[profiles.components.planners.config]
worker = "item"
reducer = "summary"
items_path = ["payload", "records"]
max_items = 4
version = "batch-1"
"""
        )
    return path


def test_public_export_and_explicit_pure_factory_use_only_original_planner_mapping():
    assert hasattr(r, "FanOutDAGPlanner")
    assert "FanOutDAGPlanner" in r.__all__
    assert len(r.__all__) == len(set(r.__all__))
    supplied = options()
    factory, prepared = r.ComponentRegistry().prepare(
        "planners", {"adapter": "fan-out", "config": supplied}
    )
    supplied["items_path"].append("caller-change")
    created = factory(prepared, None)
    assert set(created) == {"fan-out"}
    assert isinstance(created["fan-out"], r.FanOutDAGPlanner)
    assert created["fan-out"].identity == r.FanOutDAGPlanner(**options()).identity
    prepared["items_path"].append("later-change")
    assert created["fan-out"].identity == r.FanOutDAGPlanner(**options()).identity


def test_empty_explicit_factory_config_has_useful_pure_default():
    factory, prepared = r.ComponentRegistry().prepare(
        "planners", {"adapter": "fan-out", "config": {}}
    )
    created = factory(prepared, None)
    assert set(created) == {"fan-out"}
    assert created["fan-out"].identity == r.FanOutDAGPlanner().identity


@pytest.mark.parametrize("extension", ["json", "toml"])
@pytest.mark.parametrize("construction", ["build", "abuild"])
def test_local_declared_fan_out_runs_through_existing_factory_and_authority(
    tmp_path, extension, construction
):
    selected = r.load_catalog(catalog_file(tmp_path, extension)).default
    assert selected.identity == profile().identity
    flow = r.DynamicWorkflowSpec(
        "batch",
        {
            "item": r.AgentSpec("item-agent", "Return this item"),
            "summary": r.AgentSpec("summary-agent", "Summarize accepted item results"),
        },
        planner="fan-out",
        plan_mode="dag",
        child_budget=2,
        max_steps=3,
        max_concurrency=2,
    )

    async def exercise(runtime):
        chosen = runtime._orchestration.planners["fan-out"]
        assert chosen.identity == r.FanOutDAGPlanner(**options()).identity
        handle = runtime.submit(
            flow, {"payload": {"records": [1, 2]}}, command_id="batch", budget=16
        )
        done = await runtime.drive(handle.run_id)
        assert done.state == "succeeded"
        gathered = json.loads(done.result["echo"])
        assert list(gathered) == ["map-0000", "map-0001"]
        assert [json.loads(item["echo"]) for item in gathered.values()] == [1, 2]
        original_events = runtime.events(handle.run_id)
        assert (await runtime.drive(handle.run_id)).result == done.result
        assert runtime.events(handle.run_id) == original_events

    if construction == "build":
        with r.RuntimeBuilder().build(selected, tmp_path / "run.sqlite") as runtime:
            asyncio.run(exercise(runtime))
    else:

        async def run():
            async with await r.RuntimeBuilder().abuild(
                selected, tmp_path / "run.sqlite"
            ) as runtime:
                await exercise(runtime)

        asyncio.run(run())


@pytest.mark.parametrize("extension", ["json", "toml"])
def test_temporal_profile_selects_same_planner_without_worker_or_service(tmp_path, extension):
    from relf_agent.temporal_builder import TemporalRuntimeBuilder
    from relf_agent.temporal_profile import TemporalProfileCatalog

    selected = TemporalProfileCatalog.from_file(
        catalog_file(tmp_path, extension, temporal=True)
    ).default_profile

    async def run():
        assembly = await TemporalRuntimeBuilder().abuild(selected)
        try:
            actual = assembly._runtime.planners["fan-out"]
            assert actual.identity == r.FanOutDAGPlanner(**options()).identity
            manifest = assembly.release["orchestration"]["planners"]["fan-out"]
            assert manifest["identity"] == actual.identity
            assert manifest["agent"] is None
            assert assembly._worker is None and assembly._client is None
            assert assembly._context._resources == []
        finally:
            await assembly.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "config",
    [
        {"unknown": True},
        {"worker": ""},
        {"max_items": True},
        {"items_path": ["p"] * 32},
        {"reducer": "summary", "max_items": 256},
    ],
)
@pytest.mark.parametrize("construction", ["build", "abuild", "temporal-abuild"])
def test_invalid_fan_out_refuses_before_provider_or_store_allocation(
    tmp_path, config, construction
):
    registry, calls = r.ComponentRegistry(), []
    assert ("planners", "fan-out") in registry._factories

    def provider(config, context):
        calls.append("provider")
        pytest.fail("Invalid Planner configuration allocated a Provider")

    def store(*args, **kwargs):
        calls.append("store")
        pytest.fail("Invalid Planner configuration allocated a Store")

    registry.register("provider", "must-not-construct", provider)
    providers = {"default": {"adapter": "must-not-construct"}}
    components = {"planners": {"adapter": "fan-out", "config": config}}
    path = tmp_path / "never.sqlite"
    if construction == "temporal-abuild":
        from relf_agent.temporal_builder import TemporalRuntimeBuilder
        from relf_agent.temporal_profile import TemporalProfile

        async def temporal():
            with pytest.raises(ValidationError):
                await TemporalRuntimeBuilder(registry).abuild(
                    TemporalProfile("bad", "1", providers, components), data_path=path
                )

        asyncio.run(temporal())
    else:
        selected = r.RuntimeProfile("bad", "1", providers, components)
        builder = r.RuntimeBuilder(registry, store_factory=store)
        if construction == "build":
            with pytest.raises(ValidationError):
                builder.build(selected, path)
        else:

            async def local():
                with pytest.raises(ValidationError):
                    await builder.abuild(selected, path)

            asyncio.run(local())
    assert calls == [] and not path.exists()


def test_unselected_planner_tables_and_ordinary_temporal_identity_keep_baseline(tmp_path):
    teams, planners, verifiers = default_components()
    assert set(planners) == {"rule", "model", "dag-rule", "dag-model"}
    assert digest(orchestration_identity(teams, planners, verifiers)) == (
        "ee461ffd77a6d533e558b4c0bf66ac9c1268cf522e305dbbb0967114ce98a3db"
    )
    temporal = r.TemporalRuntime(
        providers={"default": EchoProvider("offline")}, tools=r.ToolRegistry()
    )
    assert digest(temporal.manifest) == (
        "6995f742a043cebc63f047bbc3ea833e41da3b8a86ad26650672a386f34d4f44"
    )
    assert "fan-out" not in temporal.planners
    with r.RuntimeBuilder().build(
        r.RuntimeProfile("ordinary", "1", {"default": {"adapter": "offline-echo"}}),
        tmp_path / "ordinary.sqlite",
    ) as runtime:
        assert set(runtime._orchestration.planners) == {"rule", "dag-rule", "dag-model"}
        accepted = runtime.submit(r.AgentSpec("ordinary", "Answer"), "q", command_id="ordinary")
        assert asyncio.run(runtime.drive(accepted.run_id)).state == "succeeded"
