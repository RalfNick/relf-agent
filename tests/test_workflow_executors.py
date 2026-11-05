import asyncio
import importlib
from dataclasses import FrozenInstanceError

import pytest

from relf_agent.errors import DefinitionMismatch, ValidationError
from relf_agent.executors import DispatchEnvelope, EffectObservation
from relf_agent.types import InvocationContext, Scope


def node_types():
    return importlib.import_module("relf_agent.workflow_executors")


def context():
    return InvocationContext(Scope(), "run", "action", "attempt", "effect-key", "epoch")


def envelope(registry, value=None, config=None, *, manifest=None):
    return DispatchEnvelope(
        context(),
        registry.tool("__relf_node__:business").manifest if manifest is None else manifest,
        {"input": value, "config": {} if config is None else config},
        "operation-digest",
    )


class BusinessExecutor:
    identity = {"kind": "business-node", "version": "1"}

    def __init__(self):
        self.calls = []

    async def execute(self, input, config, context):
        self.calls.append((input, config, context.effect_key, context.attempt_id))
        await asyncio.sleep(0)
        return {"input": input, "config": config}


def registry_with(component=None, **metadata):
    nodes = node_types()
    registry = nodes.NodeExecutorRegistry()
    registry.register(
        nodes.NodeExecutorSpec("business", "Offline business node", effect="read_only", **metadata),
        BusinessExecutor() if component is None else component,
    )
    return registry


@pytest.mark.parametrize("value", [None, False, 0, "value", [1, {"x": 2}], {"value": 3}])
def test_structural_async_executor_receives_complete_json_and_separate_config(value):
    component = BusinessExecutor()
    registry = registry_with(component)
    request = envelope(registry, value, {"mode": "complete"})
    result = asyncio.run(registry.executor.execute(request))
    assert result.result == {"input": value, "config": {"mode": "complete"}}
    assert component.calls == [(value, {"mode": "complete"}, "effect-key", "attempt")]
    assert request.arguments == {"input": value, "config": {"mode": "complete"}}


def test_spec_requires_explicit_effect_and_validated_metadata():
    nodes = node_types()
    with pytest.raises(TypeError):
        nodes.NodeExecutorSpec("business", "Business")
    spec = nodes.NodeExecutorSpec("business", "Business", "read_only")
    with pytest.raises(FrozenInstanceError):
        spec.cost = 3
    for values in (
        {"name": ""},
        {"name": "with:colon"},
        {"name": "a" * 65},
        {"description": " "},
        {"version": ""},
        {"effect": "unknown"},
        {"requires_approval": 1},
        {"cost": True},
        {"cost": -1},
        {"input_schema": {"type": "invalid"}},
        {"config_schema": None},
        {"output_schema": "invalid"},
    ):
        with pytest.raises(ValidationError):
            nodes.NodeExecutorSpec(
                **{"name": "business", "description": "Business", "effect": "read_only", **values}
            )


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"input": 1},
        {"input": 1, "config": []},
        {"input": "wrong", "config": {}},
        {"input": 1, "config": {"mode": "wrong"}},
        {"input": 1, "config": {}, "extra": True},
    ],
)
def test_input_and_config_schemas_reject_before_execute(arguments):
    component = BusinessExecutor()
    registry = registry_with(
        component,
        input_schema={"type": "integer"},
        config_schema={"type": "object", "properties": {"mode": {"const": "safe"}}},
    )
    request = DispatchEnvelope(
        context(), registry.tool("__relf_node__:business").manifest, arguments, "operation-digest"
    )
    with pytest.raises(ValidationError):
        asyncio.run(registry.executor.execute(request))
    assert component.calls == []


def test_registration_snapshots_spec_and_selected_manifests():
    nodes = node_types()
    schema = {"type": "object", "properties": {"amount": {"type": "integer"}}}
    spec = nodes.NodeExecutorSpec("business", "Business", "read_only", input_schema=schema)
    registry = nodes.NodeExecutorRegistry()
    component = BusinessExecutor()
    registry.register(spec, component)
    selected = registry.manifest(["__relf_node__:business"])
    spec.input_schema["properties"]["amount"]["type"] = "string"
    registry.get("business").spec.input_schema["properties"]["amount"]["type"] = "boolean"
    registry.tool("__relf_node__:business").spec.config.clear()
    assert registry.manifest(["__relf_node__:business"]) == selected
    registry.register(nodes.NodeExecutorSpec("other", "Other", "read_only"), BusinessExecutor())
    assert registry.manifest(["__relf_node__:business"]) == selected
    assert registry.get("business").component is component
    assert set(registry.manifests(["__relf_node__:business"])) == {"__relf_node__:business"}
    with pytest.raises(DefinitionMismatch):
        registry.register(spec, component)
    with pytest.raises(DefinitionMismatch):
        registry.tool("business")


def test_unused_registration_drift_does_not_change_selected_release():
    nodes = node_types()
    registry = registry_with()
    other = BusinessExecutor()
    registry.register(nodes.NodeExecutorSpec("other", "Other", "read_only"), other)
    original = registry.manifest(["__relf_node__:business"])
    other.identity = {"kind": "changed"}
    assert registry.manifest(["__relf_node__:business"]) == original
    with pytest.raises(DefinitionMismatch):
        registry.manifest(["__relf_node__:other"])


@pytest.mark.parametrize("mode", ["sync", "async-generator", "missing-identity", "queryable"])
def test_registration_rejects_unsupported_execution_contract(mode):
    nodes = node_types()

    class Invalid:
        identity = {"kind": "invalid", "version": "1"}

        def execute(self, input, config, context):
            return asyncio.sleep(0)

    class Generator:
        identity = {"kind": "generator", "version": "1"}

        async def execute(self, input, config, context):
            yield input

    component = {"sync": Invalid(), "async-generator": Generator()}.get(mode, BusinessExecutor())
    if mode == "missing-identity":
        component.identity = {}
    spec = nodes.NodeExecutorSpec(
        "business", "Business", "queryable_write" if mode == "queryable" else "read_only"
    )
    with pytest.raises(ValidationError):
        nodes.NodeExecutorRegistry().register(spec, component)


@pytest.mark.parametrize("value", [None, False, 0, []])
def test_reconciler_distinguishes_confirmed_json_from_unknown(value):
    nodes = node_types()

    class Queryable(BusinessExecutor):
        async def reconcile(self, input, config, context):
            return EffectObservation(value, "business-receipt")

    component = Queryable()
    registry = nodes.NodeExecutorRegistry()
    registry.register(nodes.NodeExecutorSpec("business", "Business", "queryable_write"), component)
    observed = asyncio.run(registry.executor.reconcile(envelope(registry)))
    assert observed.result == value and observed.source == "business-receipt"
    assert component.calls == []


def test_missing_or_unknown_reconciler_returns_no_evidence():
    registry = registry_with()
    assert asyncio.run(registry.executor.reconcile(envelope(registry))) is None

    class Unknown(BusinessExecutor):
        async def reconcile(self, input, config, context):
            return None

    registry = registry_with(Unknown())
    assert asyncio.run(registry.executor.reconcile(envelope(registry))) is None


def test_reconciler_rejects_raw_json_that_does_not_establish_an_observation():
    class Invalid(BusinessExecutor):
        async def reconcile(self, input, config, context):
            return {"committed": True}

    registry = registry_with(Invalid())
    with pytest.raises(ValidationError):
        asyncio.run(registry.executor.reconcile(envelope(registry)))


def test_output_schema_is_checked_only_at_explicit_completion_boundary():
    registry = registry_with(output_schema={"type": "integer"})
    result = asyncio.run(registry.executor.execute(envelope(registry, 7)))
    assert result.result == {"input": 7, "config": {}}
    with pytest.raises(ValidationError):
        registry.validate_output("__relf_node__:business", result.result)


@pytest.mark.parametrize("drift", ["identity", "method", "code"])
def test_registered_component_drift_blocks_dispatch(drift, monkeypatch):
    component = BusinessExecutor()
    registry = registry_with(component)
    request = envelope(registry)

    async def replacement(self, input, config, context):
        return "changed"

    if drift == "identity":
        component.identity = {"kind": "business-node", "version": "2"}
    elif drift == "method":
        component.execute = replacement.__get__(component)
    else:
        monkeypatch.setattr(BusinessExecutor.execute, "__code__", replacement.__code__)
    with pytest.raises(DefinitionMismatch):
        asyncio.run(registry.executor.execute(request))
    assert component.calls == []


def test_component_drift_during_await_blocks_adoption():
    class Drifting(BusinessExecutor):
        async def execute(self, input, config, context):
            await asyncio.sleep(0)
            self.identity = {"kind": "changed"}
            return input

    registry = registry_with(Drifting())
    with pytest.raises(DefinitionMismatch):
        asyncio.run(registry.executor.execute(envelope(registry)))


def test_component_drift_during_result_serialization_blocks_adoption():
    class Drifting(BusinessExecutor):
        async def execute(self, input, config, context):
            owner = self

            class Result(dict):
                def items(self):
                    owner.identity = {"kind": "changed"}
                    return super().items()

            return Result(value=1)

    registry = registry_with(Drifting())
    with pytest.raises(DefinitionMismatch):
        asyncio.run(registry.executor.execute(envelope(registry)))


def test_async_callable_methods_are_supported_and_pinned(monkeypatch):
    class AsyncMethod:
        async def __call__(self, input, config, context):
            return input

    class Component:
        identity = {"kind": "async-callable", "version": "1"}
        execute = AsyncMethod()

    registry = registry_with(Component())
    request = envelope(registry, [1, 2])
    assert asyncio.run(registry.executor.execute(request)).result == [1, 2]

    async def replacement(self, input, config, context):
        return "changed"

    monkeypatch.setattr(AsyncMethod.__call__, "__code__", replacement.__code__)
    with pytest.raises(DefinitionMismatch):
        asyncio.run(registry.executor.execute(request))


def test_persisted_fingerprint_changes_with_actual_method_code(monkeypatch):
    first = registry_with().manifest(["__relf_node__:business"])
    original = BusinessExecutor.execute
    monkeypatch.setattr(
        original,
        "__code__",
        original.__code__.replace(co_consts=(*original.__code__.co_consts, 97)),
    )
    second = registry_with().manifest(["__relf_node__:business"])
    assert first != second


def test_falsey_async_callable_reconciler_still_reports_confirmed_null():
    class Reconciler:
        def __bool__(self):
            return False

        async def __call__(self, input, config, context):
            return EffectObservation(None, "confirmed-null")

    class Component(BusinessExecutor):
        reconcile = Reconciler()

    registry = registry_with(Component())
    observed = asyncio.run(registry.executor.reconcile(envelope(registry)))
    assert isinstance(observed, EffectObservation)
    assert observed.result is None and observed.source == "confirmed-null"


@pytest.mark.parametrize("location", ["input_schema", "config_schema"])
@pytest.mark.parametrize("schema_id", [None, "", "#"])
def test_independent_local_reference_schemas_keep_their_own_resource_root(location, schema_id):
    value = 7 if location == "input_schema" else {"warehouse": "local"}
    schema = {
        "$defs": {"value": {"const": value}},
        "$ref": "#/$defs/value",
    }
    if schema_id is not None:
        schema["$id"] = schema_id
    registry = registry_with(**{location: schema})
    request = envelope(
        registry,
        value if location == "input_schema" else 7,
        value if location == "config_schema" else {},
    )
    observed = asyncio.run(registry.executor.execute(request))
    assert observed.result == request.arguments
    assert getattr(registry.get("business").spec, location) == schema
    invalid = envelope(registry, "wrong", {"warehouse": "wrong"})
    with pytest.raises(ValidationError):
        asyncio.run(registry.executor.execute(invalid))


@pytest.mark.parametrize(
    ("reference", "anchor"),
    [("$ref", "$anchor"), ("$ref", "$dynamicAnchor"), ("$dynamicRef", "$dynamicAnchor")],
)
def test_embedded_recursive_anchor_schema_preserves_validation(reference, anchor):
    schema = {
        anchor: "node",
        "type": "object",
        "properties": {
            "value": {"type": "integer"},
            "next": {"anyOf": [{"type": "null"}, {reference: "#node"}]},
        },
        "required": ["value", "next"],
        "additionalProperties": False,
    }
    registry = registry_with(input_schema=schema)
    value = {"value": 1, "next": {"value": 2, "next": None}}
    observed = asyncio.run(registry.executor.execute(envelope(registry, value)))
    assert observed.result["input"] == value
    with pytest.raises(ValidationError):
        asyncio.run(
            registry.executor.execute(
                envelope(registry, {"value": 1, "next": {"value": "wrong", "next": None}})
            )
        )


def test_schemas_without_actual_references_keep_the_original_tool_manifest():
    schema = {
        "type": "object",
        "properties": {"literal": {"const": {"$ref": "business-data"}}},
        "default": {"$dynamicRef": "business-data"},
        "examples": [{"$ref": "business-data"}],
    }
    registry = registry_with(input_schema=schema)
    assert registry.tool("__relf_node__:business").spec.input_schema == {
        "type": "object",
        "properties": {
            "input": schema,
            "config": {"allOf": [{"type": "object"}, {"type": "object"}]},
        },
        "required": ["input", "config"],
        "additionalProperties": False,
    }


@pytest.mark.parametrize("schema_id", ["component", "urn:example:component"])
def test_existing_effective_schema_resource_identifier_is_preserved(schema_id):
    schema = {
        "$id": schema_id,
        "$defs": {"value": {"type": "integer"}},
        "$ref": "#/$defs/value",
    }
    registry = registry_with(input_schema=schema)
    assert (
        registry.tool("__relf_node__:business").spec.input_schema["properties"]["input"] == schema
    )
    assert asyncio.run(registry.executor.execute(envelope(registry, 7))).result["input"] == 7


@pytest.mark.parametrize("nested", [False, True])
def test_conflicting_explicit_resource_ids_are_rejected_before_registration(nested):
    input_schema = {
        "$id": "https://example.invalid/part",
        "$defs": {"value": {"type": "integer"}},
        "$ref": "#/$defs/value",
    }
    if nested:
        input_schema = {
            "$id": "https://example.invalid/root",
            "$defs": {"part": {**input_schema, "$id": "part"}},
            "$ref": "part",
        }
    config_schema = {
        "$id": "https://example.invalid/part",
        "$defs": {"value": {"type": "object"}},
        "$ref": "#/$defs/value",
    }
    with pytest.raises(ValidationError, match="conflicting.*resource"):
        registry_with(input_schema=input_schema, config_schema=config_schema)


def test_identical_explicit_resources_may_be_shared_by_input_and_config():
    schema = {
        "$id": "urn:example:shared",
        "$defs": {"value": {"type": "object"}},
        "$ref": "#/$defs/value",
    }
    registry = registry_with(input_schema=schema, config_schema=schema)
    assert asyncio.run(registry.executor.execute(envelope(registry, {}))).result == {
        "input": {},
        "config": {},
    }


def test_independent_relative_subresources_do_not_collide_between_input_and_config():
    input_schema = {
        "$defs": {"part": {"$id": "part", "type": "integer"}},
        "$ref": "part",
    }
    config_schema = {
        "$defs": {"part": {"$id": "part", "type": "object"}},
        "$ref": "part",
    }
    registry = registry_with(input_schema=input_schema, config_schema=config_schema)
    assert asyncio.run(registry.executor.execute(envelope(registry, 7))).result == {
        "input": 7,
        "config": {},
    }


def test_persisted_fingerprint_tracks_async_callable_code(monkeypatch):
    class Method:
        async def __call__(self, input, config, context):
            return input

    class Component:
        identity = {"kind": "callable-code", "version": "1"}
        execute = Method()

    first = registry_with(Component()).manifest(["__relf_node__:business"])
    method = Method.__call__
    monkeypatch.setattr(
        method, "__code__", method.__code__.replace(co_consts=(*method.__code__.co_consts, 89))
    )
    second = registry_with(Component()).manifest(["__relf_node__:business"])
    assert first != second


def test_reconciler_drift_during_result_snapshot_is_rejected():
    class Component(BusinessExecutor):
        async def reconcile(self, input, config, context):
            owner = self

            class Result(EffectObservation):
                @property
                def result(self):
                    owner.identity = {"kind": "changed"}
                    return None

            return Result(None)

    registry = registry_with(Component())
    with pytest.raises(DefinitionMismatch):
        asyncio.run(registry.executor.reconcile(envelope(registry)))


def test_execution_detaches_mutated_input_and_config_from_dispatch():
    class Component(BusinessExecutor):
        async def execute(self, input, config, context):
            input.append(7)
            config["changed"] = True
            return input

    registry = registry_with(Component())
    request = envelope(registry, [1], {"mode": "safe"})
    assert asyncio.run(registry.executor.execute(request)).result == [1, 7]
    assert request.arguments == {"input": [1], "config": {"mode": "safe"}}


@pytest.mark.parametrize("invalid", [float("nan"), object()])
def test_execution_rejects_non_json_results(invalid):
    class Component(BusinessExecutor):
        async def execute(self, input, config, context):
            return invalid

    registry = registry_with(Component())
    with pytest.raises(ValidationError):
        asyncio.run(registry.executor.execute(envelope(registry)))


def test_executor_refuses_forged_tool_manifest():
    component = BusinessExecutor()
    registry = registry_with(component)
    manifest = registry.tool("__relf_node__:business").manifest
    manifest["effect"] = "unqueryable_write"
    with pytest.raises(DefinitionMismatch):
        asyncio.run(registry.executor.execute(envelope(registry, manifest=manifest)))
    assert component.calls == []


def test_identity_default_factory_is_explicit_and_borrows_components():
    nodes = node_types()
    factories = importlib.import_module("relf_agent.workflow_node_factories")
    registrations = []

    class Catalog:
        def register(self, kind, adapter, factory, *, validator):
            registrations.append((kind, adapter, factory, validator))

    factories.register_workflow_nodes(Catalog())
    kind, adapter, build, validate = registrations[0]
    assert (kind, adapter) == ("workflow_executors", "identity")
    assert validate({}) is None
    with pytest.raises(ValidationError):
        validate({"hidden": True})
    registry = build({}, None)
    assert isinstance(registry, nodes.NodeExecutorRegistry)
    request = DispatchEnvelope(
        context(),
        registry.tool("__relf_node__:identity").manifest,
        {"input": [None, {"value": 7}], "config": {}},
        "operation-digest",
    )
    assert asyncio.run(registry.executor.execute(request)).result == [None, {"value": 7}]
    assert nodes.alias_name("business") == "__relf_node__:business"
    assert nodes.is_alias("__relf_node__:business") and nodes.is_alias("__relf_node__:")
    assert not nodes.is_alias(None) and not nodes.is_alias("business")
