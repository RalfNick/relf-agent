"""Existing Local Tool Actions need no dummy model in versioned configuration."""

import asyncio
import json

import pytest

import relf_agent as r
from relf_agent.errors import DefinitionMismatch, ValidationError


async def increment(value: int):
    await asyncio.sleep(0)
    return value + 1


def tools_factory(config, context):
    assert not config
    tools = r.ToolRegistry()
    tools.register_function(increment, effect="read_only")
    return tools


def builder():
    registry = r.ComponentRegistry()
    registry.register("tools", "fixture-async", tools_factory)
    return r.RuntimeBuilder(registry)


def profile():
    return r.RuntimeProfile("no-model", "1", {}, components={"tools": {"adapter": "fixture-async"}})


def graph(concurrency=1):
    return r.GraphWorkflowSpec(
        "increments",
        [
            r.GraphNode("first", tool="increment", input=r.Literal({"value": 1})),
            r.GraphNode("second", tool="increment", input=r.Literal({"value": 2})),
        ],
        max_concurrency=concurrency,
    )


@pytest.mark.parametrize("concurrency", [1, 2])
def test_explicit_empty_profile_executes_original_async_tool_actions(tmp_path, concurrency):
    with builder().build(profile(), tmp_path / "run.sqlite") as engine:
        handle = engine.submit(graph(concurrency), {}, command_id="s", budget=2)
        result = asyncio.run(engine.drive(handle.run_id))
        assert result.state == "succeeded" and result.result == {"first": 2, "second": 3}
        info = engine.diagnostics(handle.run_id)
        assert info.manifest["providers"] == {} and info.budget["spent"] == 2
        assert [a["kind"] for a in result.actions] == ["tool", "tool"]


@pytest.mark.parametrize("mixed", [False, True])
def test_model_agent_is_refused_before_run_acceptance(tmp_path, mixed):
    spec = r.AgentSpec("needs-model", "Answer")
    if mixed:
        spec = r.GraphWorkflowSpec(
            "mixed",
            [
                r.GraphNode("agent", agent=spec),
                r.GraphNode("tool", tool="increment", input=r.Literal({"value": 1})),
            ],
        )
    with builder().build(profile(), tmp_path / "run.sqlite") as engine:
        with pytest.raises(DefinitionMismatch):
            engine.submit(spec, {}, command_id="invalid")
    with r.SQLiteStore(tmp_path / "run.sqlite", readonly=True) as store:
        assert store.conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["json", "toml"])
def test_explicit_empty_profile_roundtrips_without_implicit_defaults(tmp_path, kind):
    path = tmp_path / ("runtime." + kind)
    if kind == "json":
        content = json.dumps(
            {
                "schema_version": 1,
                "default": {"name": "no-model", "version": "1"},
                "profiles": [
                    {
                        "name": "no-model",
                        "version": "1",
                        "providers": {},
                        "components": {"tools": {"adapter": "fixture-async"}},
                    }
                ],
            }
        )
    else:
        content = """schema_version = 1
[default]
name = "no-model"
version = "1"
[[profiles]]
name = "no-model"
version = "1"
providers = {}
[profiles.components.tools]
adapter = "fixture-async"
"""
    path.write_text(content)
    selected = r.load_catalog(path).default
    assert selected.identity == profile().identity and selected.providers == {}


def test_temporal_still_refuses_empty_providers_before_building_resources():
    from relf_agent.temporal_profile import TemporalProfile

    with pytest.raises(ValidationError):
        TemporalProfile("not-supported", "1", {})


@pytest.mark.parametrize("providers", [None, [], "", False, 0])
def test_wrong_type_does_not_become_empty_provider_mapping(providers):
    with pytest.raises(ValidationError):
        r.RuntimeProfile("bad", "1", providers)


@pytest.mark.parametrize("kind", ["json", "toml"])
def test_catalog_never_supplies_missing_provider_field(tmp_path, kind):
    path = tmp_path / ("missing." + kind)
    if kind == "json":
        value = json.dumps(
            {
                "schema_version": 1,
                "default": {"name": "missing", "version": "1"},
                "profiles": [{"name": "missing", "version": "1"}],
            }
        )
    else:
        value = """schema_version = 1
[default]
name = "missing"
version = "1"
[[profiles]]
name = "missing"
version = "1"
"""
    path.write_text(value)
    with pytest.raises(ValidationError):
        r.load_catalog(path)


def test_graph_starter_exports_optional_model_free_tool_example(tmp_path):
    from relf_agent.starter import create_starter

    app = create_starter(tmp_path / "graph", template="graph")
    assert {
        "agent_app/tool_graph.py",
        "agent_app/tool_runtime.py",
        "tool-graph.json",
        "tool-runtime.toml",
    } <= set(app.files)
