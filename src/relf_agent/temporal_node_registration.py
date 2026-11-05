"""Borrowed node registrations; only original Tool Activities execute them."""

import json

from .errors import DefinitionMismatch, ValidationError
from .tools import ToolRegistry, _entry_pin, _same_entry_pin
from .types import canonical
from .workflow_executors import NodeExecutorRegistry, alias_name, is_alias

_REGISTRY_PORTS = ("manifest", "manifests", "tool", "get", "check", "validate_output")


def configure(runtime, registry, tools):
    if registry is not None and not isinstance(registry, NodeExecutorRegistry):
        raise ValidationError("workflow_executors requires a NodeExecutorRegistry")
    runtime.workflow_executors = runtime._workflow_nodes_pin = registry
    runtime._workflow_nodes_adapter = None if registry is None else registry.executor
    runtime._workflow_nodes_methods = (
        None
        if registry is None
        else tuple(
            _entry_pin(getattr(registry.executor, name)) for name in ("execute", "reconcile")
        )
    )
    runtime._workflow_nodes_registry_methods = (
        None
        if registry is None
        else tuple(_entry_pin(getattr(registry, name)) for name in _REGISTRY_PORTS)
    )
    if registry is not None:
        if not isinstance(tools, ToolRegistry):
            raise ValidationError("Temporal requires an explicit ToolRegistry")
        if any(is_alias(name) for name in tools._tools):
            raise ValidationError("Public tools cannot use the reserved Workflow node namespace")
        registered(runtime)


def registered(runtime):
    registry = runtime._workflow_nodes_pin
    if registry is None:
        raise DefinitionMismatch("Workflow node executors are not configured")
    if (
        runtime.workflow_executors is not registry
        or registry.executor is not runtime._workflow_nodes_adapter
        or getattr(registry.executor, "_registry", None) is not registry
    ):
        raise DefinitionMismatch("Original Workflow node registry or adapter changed")
    try:
        methods = tuple(
            _entry_pin(getattr(registry.executor, name)) for name in ("execute", "reconcile")
        )
        ports = tuple(_entry_pin(getattr(registry, name)) for name in _REGISTRY_PORTS)
    except (AttributeError, ValidationError):
        raise DefinitionMismatch("Original Workflow node adapter methods changed") from None
    if not _same_entry_pin(methods, runtime._workflow_nodes_methods):
        raise DefinitionMismatch("Original Workflow node adapter methods changed")
    if not _same_entry_pin(ports, runtime._workflow_nodes_registry_methods):
        raise DefinitionMismatch("Original Workflow node registry methods changed")
    return registry


def publication(runtime):
    if runtime._workflow_nodes_pin is None:
        if runtime.workflow_executors is not None:
            raise DefinitionMismatch("Original Workflow node selection changed")
        return {}, {}
    registry = registered(runtime)
    names = [alias_name(name) for name in sorted(registry._registrations)]
    if any(is_alias(name) for name in runtime.tools._tools):
        raise DefinitionMismatch("Workflow node alias collides with a public tool")
    tools = registry.manifests(names)
    if runtime.journal is None and any(tool["effect"] != "read_only" for tool in tools.values()):
        raise ValidationError("Temporal writes require a durable EffectJournal")
    metadata = {"workflow_node_protocol": 1, "workflow_nodes": registry.manifest(names)}
    registered(runtime)
    return tools, metadata


def resolve(runtime, request):
    """Resolve only a private node's original History-owned request."""
    if runtime._manifest.get("workflow_node_protocol") == 1 or "node_request" in request:
        from .temporal_node_protocol import validate_node_envelope

        # Parent-owned children retain the whole orchestration release. Match
        # that exact variant against original Worker pins, not a base-only
        # manifest or an unverified caller-provided registration. Activity
        # entry points separately validate live owners before and after I/O.
        fixed = runtime._manifest
        if (
            type(request.get("runtime_manifest")) is dict
            and "orchestration" in request["runtime_manifest"]
        ):
            fixed = {**fixed, "orchestration": runtime._orchestration}
        # The SDK wire representation normalizes dataclass tuple metadata to
        # arrays. Normalize only the original pins before exact JSON matching.
        validate_node_envelope(request, json.loads(canonical(fixed)))
        if is_alias(request.get("tool")):
            return registered(runtime).tool(request["tool"])
    return runtime.tools.get(request["tool"])


def executor(runtime, request):
    if runtime._manifest.get("workflow_node_protocol") == 1 and is_alias(request.get("tool")):
        resolve(runtime, request)
        return registered(runtime).executor
    return runtime.executor


def validate_acknowledgement(runtime, request):
    if "node_request" in request or (
        runtime._manifest.get("workflow_node_protocol") == 1 and is_alias(request.get("tool"))
    ):
        resolve(runtime, request)
