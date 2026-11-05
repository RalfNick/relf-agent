"""Temporal node assembly reuses the original factory/lifecycle contracts."""

import asyncio
import json

import pytest

import relf_agent as r
from relf_agent.errors import ValidationError


def profile(adapter="identity", providers=None):
    return r.TemporalProfile(
        "nodes",
        "1",
        {} if providers is None else providers,
        {"workflow_executors": {"adapter": adapter, "config": {}}},
    )


def test_pure_node_profile_builds_without_provider_or_local_execution_store(tmp_path):
    async def run():
        assembly = await r.TemporalRuntimeBuilder(base_dir=tmp_path).abuild(profile())
        try:
            assert assembly.release["providers"] == {}
            assert assembly.release["workflow_node_protocol"] == 1
            assert assembly.release["tool_execution_protocol"]["version"] == 1
            assert assembly.capabilities["managed_workflow_nodes"] is True
            assert assembly.release["runtime_profile"] == profile().identity
            assert not any(tmp_path.iterdir())
            runtime = assembly._runtime
            assert not runtime.tools._tools
            assert "__relf_node__:identity" in assembly.release["tools"]
        finally:
            await assembly.aclose()
        assert not any(tmp_path.iterdir())

    asyncio.run(run())


def test_temporal_node_catalog_json_and_toml_have_same_fixed_profile(tmp_path):
    payload = {
        "kind": "temporal-profiles",
        "schema_version": 1,
        "default": {"name": "nodes", "version": "1"},
        "profiles": [profile().to_dict()],
    }
    json_path, toml_path = tmp_path / "nodes.json", tmp_path / "nodes.toml"
    json_path.write_text(json.dumps(payload))
    toml_path.write_text("""kind="temporal-profiles"
schema_version=1
[default]
name="nodes"
version="1"
[[profiles]]
name="nodes"
version="1"
providers={}
[profiles.components.workflow_executors]
adapter="identity"
[profiles.components.workflow_executors.config]
""")
    first, second = (
        r.TemporalProfileCatalog.from_file(path).default_profile for path in (json_path, toml_path)
    )
    assert first.identity == second.identity == profile().identity


def test_empty_provider_profile_still_requires_explicit_node_component():
    with pytest.raises(ValidationError):
        r.TemporalProfile("empty", "1", {})


def test_invalid_node_adapter_is_preflighted_before_any_factory_io(tmp_path):
    made = []

    def factory(config, context):
        made.append(True)
        raise AssertionError("Invalid declarations must be rejected before construction")

    registry = r.ComponentRegistry()
    registry.register("provider", "probe", factory)

    async def run():
        with pytest.raises(ValidationError):
            await r.TemporalRuntimeBuilder(registry, base_dir=tmp_path).abuild(
                profile("missing", {"default": {"adapter": "probe"}})
            )

    asyncio.run(run())
    assert made == [] and not any(tmp_path.iterdir())


def test_async_node_factory_client_is_closed_by_original_assembly_owner(tmp_path):
    clients = []

    class Client:
        def __init__(self):
            self.closed = False

        async def aclose(self):
            self.closed = True

    class Business:
        identity = {"kind": "configured-node", "version": "1"}

        async def execute(self, input, config, context):
            assert not self.client.closed
            return input

    async def factory(config, context):
        client = context.own_async(Client())
        clients.append(client)
        component = Business()
        component.client = client
        nodes = r.NodeExecutorRegistry()
        nodes.register(r.NodeExecutorSpec("business", "Business", "read_only"), component)
        return nodes

    registry = r.ComponentRegistry()
    registry.register_async("workflow_executors", "business", factory)

    async def run():
        assembly = await r.TemporalRuntimeBuilder(registry, base_dir=tmp_path).abuild(
            profile("business")
        )
        assert len(clients) == 1 and not clients[0].closed
        assert "__relf_node__:business" in assembly.release["tools"]
        await assembly.aclose()
        await assembly.aclose()
        assert clients[0].closed

    asyncio.run(run())
