"""Versioned async node registrations, dispatched through the original Tool loop.

Registrations borrow their components. This module owns neither Run state nor
client lifecycle, retries, approvals or budget reservations.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from types import CodeType
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urljoin

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Resource
from referencing.jsonschema import DRAFT202012

from .component_fingerprint import _code
from .errors import DefinitionMismatch, ValidationError
from .executors import DispatchEnvelope, EffectObservation
from .ports import validate_component_identity
from .tools import (
    RegisteredTool,
    ToolRegistry,
    ToolSpec,
    _callable_identity,
    _entry_pin,
    _same_entry_pin,
    invoke,
)
from .types import InvocationContext, _require_text, canonical, credits, digest

_PREFIX = "__relf_node__:"
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")
_EFFECTS = {"read_only", "idempotent_write", "queryable_write", "unqueryable_write"}


def is_alias(value):
    """Identify the reserved namespace, including unavailable private names."""
    return isinstance(value, str) and value.startswith(_PREFIX)


def alias_name(name):
    if not isinstance(name, str) or _NAME.fullmatch(name) is None:
        raise ValidationError("Node executor requires a stable name")
    return _PREFIX + name


def _schema(value, label):
    if not isinstance(value, (dict, bool)):
        raise ValidationError(f"{label} requires an object or boolean Schema")
    canonical(value)
    try:
        Draft202012Validator.check_schema(value)
    except SchemaError as exc:
        raise ValidationError(f"Invalid {label} Schema") from exc
    return copy.deepcopy(value)


def _schema_resources(schema):
    """Visit actual Schema positions, never default/const/example JSON values."""
    try:
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)

        def visit(current, base):
            identifier = current.id()
            base = urljoin(base, identifier) if identifier else base
            yield current, base, identifier
            for child in current.subresources():
                yield from visit(child, base)

        yield from visit(resource, "")
    except Exception as exc:
        raise ValidationError("Cannot resolve node executor Schema resources") from exc


def _embedded_schema(schema):
    """Preserve independent local references inside the original Tool envelope."""
    result = copy.deepcopy(schema)
    resources = list(_schema_resources(result))
    if (
        isinstance(result, dict)
        and not resources[0][2]
        and any(
            isinstance(resource.contents, dict)
            and any(name in resource.contents for name in ("$ref", "$dynamicRef"))
            for resource, _, _ in resources
        )
    ):
        # Hierarchical local-only IDs also isolate relative child resources.
        # The shared validator never retrieves this URI from the network.
        result["$id"] = "https://schemas.relf.invalid/node/" + digest(schema) + "/"
    return result


def _check_schema_resource_ids(*schemas):
    resources = {}
    for schema in schemas:
        for resource, base, identifier in _schema_resources(schema):
            if not identifier:
                continue
            encoded = canonical(resource.contents)
            previous = resources.setdefault(base, encoded)
            if previous != encoded:
                raise ValidationError("Node executor has conflicting Schema resource identifiers")


@runtime_checkable
class NodeExecutor(Protocol):
    identity: dict

    async def execute(self, input: Any, config: dict, context: InvocationContext) -> Any: ...


@runtime_checkable
class NodeReconciler(Protocol):
    async def reconcile(
        self, input: Any, config: dict, context: InvocationContext
    ) -> EffectObservation | None: ...


@dataclass(frozen=True)
class NodeExecutorSpec:
    name: str
    description: str
    effect: str
    version: str = "1"
    input_schema: dict | bool = True
    config_schema: dict | bool = field(default_factory=lambda: {"type": "object"})
    output_schema: dict | bool | None = None
    requires_approval: bool = False
    cost: int = 1

    def __post_init__(self):
        alias_name(self.name)
        _require_text(self.description, "Node executor description")
        _require_text(self.version, "Node executor version")
        if not isinstance(self.effect, str) or self.effect not in _EFFECTS:
            raise ValidationError("Unknown node executor effect category")
        if type(self.requires_approval) is not bool:
            raise ValidationError("Node executor approval requires a boolean")
        credits(self.cost)
        for name in ("input_schema", "config_schema", "output_schema"):
            value = getattr(self, name)
            if name != "output_schema" or value is not None:
                object.__setattr__(self, name, _schema(value, f"Node executor {name}"))


def _method_identity(method):
    """Fingerprint direct code only; captured clients/config are declared identity."""
    if method is None:
        return None
    codes = []

    def collect(pin):
        if type(pin) is tuple:
            for item in pin:
                collect(item)
        elif type(pin) is CodeType:
            codes.append(_code(pin))

    collect(_entry_pin(method))
    return {"entry": _callable_identity(method), "code": codes}


@dataclass(frozen=True)
class RegisteredNodeExecutor:
    """Detached SDK descriptor; the component itself remains borrowed."""

    spec: NodeExecutorSpec
    component: NodeExecutor
    _manifest_json: str = field(repr=False)

    @property
    def manifest(self):
        return json.loads(self._manifest_json)


@dataclass(frozen=True)
class _Registration:
    spec: NodeExecutorSpec
    component: NodeExecutor
    methods: tuple[str, ...]
    pins: tuple
    manifest_json: str

    def check(self):
        try:
            identity = validate_component_identity(
                self.component, self.methods, label="Node executor"
            )
            pins = tuple(
                _entry_pin(getattr(self.component, name, None)) for name in ("execute", "reconcile")
            )
        except Exception as exc:
            raise DefinitionMismatch("The original node executor changed") from exc
        if canonical(identity) != canonical(json.loads(self.manifest_json)["component"]) or not (
            _same_entry_pin(pins, self.pins)
        ):
            raise DefinitionMismatch("The original node executor changed")


class NodeToolExecutor:
    """Private dispatch adapter; all effect adoption remains in the Engine."""

    def __init__(self, registry):
        self._registry = registry

    @property
    def identity(self):
        return {
            "kind": "workflow-node-tool-executor",
            "version": "1",
            "protocol": 1,
            "implementation_digest": digest(
                {name: _method_identity(getattr(self, name)) for name in ("execute", "reconcile")}
            ),
        }

    def _registered(self, envelope):
        if not isinstance(envelope, DispatchEnvelope):
            raise ValidationError("Node executor requires a DispatchEnvelope")
        tool = self._registry.tool(envelope.tool_name)
        if digest(tool.manifest) != digest(envelope.tool_manifest):
            raise DefinitionMismatch("Node executor differs from its pinned Tool manifest")
        tool.validate(envelope.arguments)
        return tool

    async def execute(self, envelope):
        tool = self._registered(envelope)

        def check():
            self._registry.check((envelope.tool_name,))
            tool.check()

        result = await invoke(tool.handler, envelope.arguments, envelope.context, verify=check)
        check()
        observation = EffectObservation(result, source="node-executor")
        check()
        return observation

    async def reconcile(self, envelope):
        tool = self._registered(envelope)
        if tool.reconciler is None:
            return None

        def check():
            self._registry.check((envelope.tool_name,))
            tool.check()

        observed = await invoke(tool.reconciler, envelope.arguments, envelope.context, verify=check)
        check()
        if observed is None:
            return None
        if not isinstance(observed, EffectObservation):
            raise ValidationError("Node reconciler must return EffectObservation or None")
        observation = EffectObservation(observed.result, observed.source)
        check()
        return observation


class NodeExecutorRegistry:
    def __init__(self):
        self._registrations: dict[str, _Registration] = {}
        self._tools = ToolRegistry()
        self._executor = NodeToolExecutor(self)

    @property
    def executor(self):
        return self._executor

    def register(self, spec, component):
        if not isinstance(spec, NodeExecutorSpec):
            raise ValidationError("Register a NodeExecutorSpec")
        alias = alias_name(spec.name)
        if spec.name in self._registrations:
            raise DefinitionMismatch(f"Node executor already registered: {spec.name}")
        spec = NodeExecutorSpec(**asdict(spec))
        try:
            reconcile = getattr(component, "reconcile", None)
            methods = ("execute", "reconcile") if reconcile is not None else ("execute",)
            identity = validate_component_identity(component, methods, label="Node executor")
            if spec.effect == "queryable_write" and reconcile is None:
                raise ValidationError("Queryable node executor requires reconcile")
            execute = component.execute
            pins = (_entry_pin(execute), _entry_pin(reconcile))
            implementation = {
                "execute": _method_identity(execute),
                "reconcile": _method_identity(reconcile),
            }
            manifest_json = canonical(
                {
                    "spec": asdict(spec),
                    "component": identity,
                    "implementation_digest": digest(implementation),
                }
            )
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("Cannot register node executor") from exc
        entry = _Registration(spec, component, methods, pins, manifest_json)
        input_schema = _embedded_schema(spec.input_schema)
        config_schema = _embedded_schema(spec.config_schema)
        _check_schema_resource_ids(input_schema, config_schema)

        async def handler(arguments, context):
            entry.check()
            result = await execute(arguments["input"], arguments["config"], context)
            entry.check()
            return result

        async def reconciler(arguments, context):
            entry.check()
            result = await reconcile(arguments["input"], arguments["config"], context)
            entry.check()
            return result

        tool_spec = ToolSpec(
            alias,
            spec.description,
            {
                "type": "object",
                "properties": {
                    "input": input_schema,
                    "config": {"allOf": [{"type": "object"}, config_schema]},
                },
                "required": ["input", "config"],
                "additionalProperties": False,
            },
            version=spec.version,
            effect=spec.effect,
            requires_approval=spec.requires_approval,
            cost=spec.cost,
            config={"node_executor": json.loads(manifest_json)},
        )
        entry.check()
        self._tools.register(
            tool_spec, handler, reconciler=reconciler if reconcile is not None else None
        )
        self._registrations[spec.name] = entry

    def get(self, name):
        try:
            entry = self._registrations[name]
        except (KeyError, TypeError) as exc:
            raise DefinitionMismatch(f"Node executor not registered: {name}") from exc
        entry.check()
        return RegisteredNodeExecutor(
            copy.deepcopy(entry.spec), entry.component, entry.manifest_json
        )

    def _registration(self, alias):
        if not is_alias(alias):
            raise DefinitionMismatch("Node tool requires its private alias")
        return self.get(alias[len(_PREFIX) :])

    def check(self, aliases=()):
        for alias in aliases:
            self._registration(alias)

    def tool(self, alias) -> RegisteredTool:
        self._registration(alias)
        return self._tools.get(alias)

    def manifests(self, aliases):
        return {alias: self.tool(alias).manifest for alias in aliases}

    def manifest(self, aliases):
        return {
            "protocol": 1,
            "tool_executor": self.executor.identity,
            "registrations": {
                alias: self._registration(alias).manifest for alias in sorted(set(aliases))
            },
        }

    def validate_output(self, alias, result):
        registered = self._registration(alias)
        value = json.loads(canonical(result))
        schema = registered.spec.output_schema
        if schema is not None:
            from .schema_validation import is_valid

            if not is_valid(value, schema):
                raise ValidationError("Node executor output does not match its Schema")
        self._registration(alias)
        return value


class IdentityNodeExecutor:
    identity = {"kind": "identity-node-executor", "version": "1"}

    async def execute(self, input, config, context):
        return copy.deepcopy(input)
