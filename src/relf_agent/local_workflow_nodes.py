"""Private node dispatch selection over the original Local ToolAction loop."""

from .errors import DefinitionMismatch, ValidationError
from .tools import _entry_pin, _same_entry_pin
from .types import digest
from .workflow_executors import NodeExecutorRegistry, is_alias

_REGISTRY_PORTS = ("manifest", "manifests", "tool", "get", "check", "validate_output")


def configure(engine, registry):
    if registry is not None and not isinstance(registry, NodeExecutorRegistry):
        raise ValidationError("workflow_executors requires a NodeExecutorRegistry")
    engine.workflow_executors = engine._workflow_executors_pin = registry
    engine._workflow_node_executor_pin = None if registry is None else registry.executor
    engine._workflow_node_method_pins = (
        None
        if registry is None
        else tuple(
            _entry_pin(getattr(registry.executor, name)) for name in ("execute", "reconcile")
        )
    )
    engine._workflow_node_registry_pins = (
        None
        if registry is None
        else tuple(_entry_pin(getattr(registry, name)) for name in _REGISTRY_PORTS)
    )
    if registry is not None and getattr(registry.executor, "_registry", None) is not registry:
        raise ValidationError("Workflow node adapter must belong to its original registry")
    if registry is not None and any(is_alias(name) for name in getattr(engine.tools, "_tools", {})):
        raise ValidationError("Public tools cannot use the reserved Workflow node namespace")


def _registry(engine):
    original = engine._workflow_executors_pin
    if original is None:
        raise DefinitionMismatch("Workflow node executors are not configured")
    if (
        engine.workflow_executors is not original
        or original.executor is not engine._workflow_node_executor_pin
    ):
        raise DefinitionMismatch("Original Workflow node registry or executor changed")
    adapter = original.executor
    try:
        methods = tuple(_entry_pin(getattr(adapter, name)) for name in ("execute", "reconcile"))
        ports = tuple(_entry_pin(getattr(original, name)) for name in _REGISTRY_PORTS)
    except (AttributeError, ValidationError):
        raise DefinitionMismatch("Original Workflow node adapter methods changed") from None
    if getattr(adapter, "_registry", None) is not original or not _same_entry_pin(
        methods, engine._workflow_node_method_pins
    ):
        raise DefinitionMismatch("Original Workflow node adapter ownership or methods changed")
    if not _same_entry_pin(ports, engine._workflow_node_registry_pins):
        raise DefinitionMismatch("Original Workflow node registry methods changed")
    return original


def manifests(engine, names):
    private = [name for name in names if is_alias(name)]
    public = [name for name in names if not is_alias(name)]
    tools = engine.tools.manifests(public)
    selected = None
    if private:
        registry = _registry(engine)
        if any(name in getattr(engine.tools, "_tools", {}) for name in private):
            raise DefinitionMismatch("Workflow node alias collides with a public tool")
        tools.update(registry.manifests(private))
        selected = registry.manifest(private)
    return tools, selected, public


def registered_tool(engine, run, index, name):
    if not is_alias(name):
        return engine.tools.get(name)
    try:
        plan = run["plan"]
        if type(index) is not int or not 0 <= index < len(plan["nodes"]):
            raise KeyError("node")
        node = plan["nodes"][index]
        if node["agent"] is not None or node.get("tool") != name:
            raise KeyError("node ownership")
        selected = engine._step_manifest(run, index)["workflow"]["node_executors"]
        registry = _registry(engine)
        actual = registry.manifest([name])
        if any(selected[field] != actual[field] for field in ("protocol", "tool_executor")) or (
            selected["registrations"][name] != actual["registrations"][name]
        ):
            raise KeyError("registration")
        tool = registry.tool(name)
        if digest(tool.manifest) != digest(engine._step_manifest(run, index)["tools"][name]):
            raise KeyError("tool manifest")
        return tool
    except (KeyError, TypeError, IndexError):
        raise DefinitionMismatch(
            "Private node action differs from its fixed Workflow plan"
        ) from None


def execution_component(engine, run, action):
    if not is_alias(action["tool"]):
        return engine.tool_executor
    registered_tool(engine, run, action["node"], action["tool"])
    return _registry(engine).executor


def validate_output(engine, node, result):
    name = node.get("tool")
    if is_alias(name):
        _registry(engine).validate_output(name, result)
