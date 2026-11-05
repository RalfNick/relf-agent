"""Fixed node metadata and original parent/child envelopes; no execution I/O."""

from dataclasses import asdict

from .errors import DefinitionMismatch, ValidationError
from .schema_validation import is_valid
from .types import Scope, canonical, credits, digest
from .workflow_executors import NodeExecutorSpec, _embedded_schema, is_alias

MARKER = "workflow_node"


def is_node_request(request):
    return (
        type(request) is dict
        and type(request.get("definition")) is dict
        and request["definition"].get("kind") == "executor"
    )


def validate_protocol(manifest):
    if type(manifest) is not dict:
        raise DefinitionMismatch("Temporal nodes require a fixed runtime manifest")
    if "workflow_node_protocol" not in manifest and "workflow_nodes" not in manifest:
        return
    value = manifest.get("workflow_nodes")
    if (
        type(manifest.get("workflow_node_protocol")) is not int
        or manifest["workflow_node_protocol"] != 1
        or manifest.get("kernel") != "temporal-3"
        or "tool_execution_protocol" not in manifest
        or type(value) is not dict
        or set(value) != {"protocol", "tool_executor", "registrations"}
        or type(value["protocol"]) is not int
        or value["protocol"] != 1
        or type(value["tool_executor"]) is not dict
        or not value["tool_executor"]
        or type(value["registrations"]) is not dict
        or not value["registrations"]
    ):
        raise DefinitionMismatch("Unsupported original Temporal node protocol")
    from .temporal_state import validate_schema_references

    aliases = {name for name in manifest.get("tools", {}) if is_alias(name)}
    if aliases != set(value["registrations"]):
        raise DefinitionMismatch("Temporal node tools differ from their fixed registrations")
    for alias, registration in value["registrations"].items():
        try:
            if (
                type(registration) is not dict
                or set(registration) != {"spec", "component", "implementation_digest"}
                or type(registration["component"]) is not dict
                or not registration["component"]
                or type(registration["implementation_digest"]) is not str
                or len(registration["implementation_digest"]) != 64
                or any(c not in "0123456789abcdef" for c in registration["implementation_digest"])
            ):
                raise DefinitionMismatch("Invalid original node component metadata")
            spec = NodeExecutorSpec(**registration["spec"])
            tool = manifest["tools"][alias]
            if alias != "__relf_node__:" + spec.name or (
                tool["name"] != alias
                or tool["config"] != {"node_executor": registration}
                or any(
                    tool[field] != getattr(spec, field)
                    for field in ("description", "version", "effect", "requires_approval", "cost")
                )
                or tool["input_schema"]
                != {
                    "type": "object",
                    "properties": {
                        "input": _embedded_schema(spec.input_schema),
                        "config": {
                            "allOf": [{"type": "object"}, _embedded_schema(spec.config_schema)]
                        },
                    },
                    "required": ["input", "config"],
                    "additionalProperties": False,
                }
            ):
                raise DefinitionMismatch("Temporal node registration and Tool metadata disagree")
            validate_schema_references(spec.output_schema)
        except (KeyError, TypeError, ValueError) as exc:
            raise DefinitionMismatch("Invalid fixed Temporal node registration") from exc
    canonical(value)


def _text(value):
    return type(value) is str and bool(value.strip()) and len(value) <= 1024


def child_request(state, node, value, budget):
    key = f"{state.planning_revision}:{node.id}"
    command = "ralf-child:" + digest([state.scope, state.run_id, key])
    run_id = "ralf-temporal-" + digest([state.scope, command])
    alias = node.tool
    body = {
        "definition": {
            "kind": "executor",
            "name": node.id,
            "version": state.manifest["tools"][alias]["version"],
            "steps": [{"tool": alias, "output_schema": node.output_schema}],
        },
        "input": value,
        "budget": budget,
        "session_id": None,
        MARKER: {
            "version": 1,
            "scope": state.scope,
            "parent_run_id": state.run_id,
            "parent_execution_epoch": state.epoch,
            "parent_release_digest": state.release_digest,
            "node_id": node.id,
            "planning_revision": state.planning_revision,
            "run_id": run_id,
            "command_id": command,
        },
    }
    validate_node_request(body, state.manifest)
    return body


def validate_node_request(request, manifest):
    validate_protocol(manifest)
    if not is_node_request(request) or manifest.get("workflow_node_protocol") != 1:
        raise DefinitionMismatch("Executor children require their original node release")
    try:
        if set(request) != {"definition", "input", "budget", "session_id", MARKER}:
            raise ValidationError("Node child has unsupported request fields")
        definition, origin = request["definition"], request[MARKER]
        if (
            set(definition) != {"kind", "name", "version", "steps"}
            or type(definition["steps"]) is not list
            or len(definition["steps"]) != 1
            or type(origin) is not dict
            or set(origin)
            != {
                "version",
                "scope",
                "parent_run_id",
                "parent_execution_epoch",
                "parent_release_digest",
                "node_id",
                "planning_revision",
                "run_id",
                "command_id",
            }
            or type(origin["version"]) is not int
            or origin["version"] != 1
            or any(
                not _text(origin[name])
                for name in (
                    "parent_run_id",
                    "parent_execution_epoch",
                    "node_id",
                    "run_id",
                    "command_id",
                )
            )
            or type(origin["planning_revision"]) is not int
            or origin["planning_revision"] < 0
            or request["session_id"] is not None
            or definition["name"] != origin["node_id"]
            or type(origin["parent_release_digest"]) is not str
            or len(origin["parent_release_digest"]) != 64
            or any(c not in "0123456789abcdef" for c in origin["parent_release_digest"])
        ):
            raise ValidationError("Invalid original node child request")
        scope = asdict(Scope(**origin["scope"]))
        if scope != origin["scope"]:
            raise ValidationError("Invalid original node Scope")
        command = "ralf-child:" + digest(
            [scope, origin["parent_run_id"], f"{origin['planning_revision']}:{origin['node_id']}"]
        )
        if origin["command_id"] != command or origin["run_id"] != "ralf-temporal-" + digest(
            [scope, command]
        ):
            raise DefinitionMismatch("Node child lost its original parent-derived identity")
        step = definition["steps"][0]
        if (
            type(step) is not dict
            or set(step) != {"tool", "output_schema"}
            or not is_alias(step["tool"])
        ):
            raise ValidationError("A node child requires one registered private Tool step")
        registration = manifest["workflow_nodes"]["registrations"][step["tool"]]
        if definition["version"] != registration["spec"]["version"]:
            raise DefinitionMismatch("Node child version differs from its fixed registration")
        if type(request["input"]) is not dict or set(request["input"]) != {"input", "config"}:
            raise ValidationError("Node child requires separate complete input and config")
        if not is_valid(request["input"], manifest["tools"][step["tool"]]["input_schema"]):
            raise ValidationError("Node child input/config differ from the registered Schema")
        from .temporal_state import validate_schema_references
        from .workflow import _schema

        _schema(step["output_schema"])
        validate_schema_references(step["output_schema"])
        credits(request["budget"])
        canonical(request)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Malformed original node child request") from exc
    return request


def validate_node_identity(request, scope, run_id, command_id):
    origin = request[MARKER]
    if origin["scope"] != scope or origin["run_id"] != run_id or origin["command_id"] != command_id:
        raise DefinitionMismatch("Node Workflow identity differs from its accepted parent intent")


def validate_graph(graph, request, manifest):
    if "workflow_node_protocol" not in manifest and any(node.agent is None for node in graph.nodes):
        raise ValidationError("Temporal graph supports Agent nodes only")
    nodes = [node for node in graph.nodes if node.executor is not None]
    if any(node.agent is None and node.executor is None for node in graph.nodes):
        raise ValidationError("Temporal graph supports Agent or registered executor nodes only")
    if not nodes:
        return
    validate_protocol(manifest)
    if manifest.get("workflow_node_protocol") != 1:
        raise DefinitionMismatch("Temporal executor graph requires its original node release")
    stack = [request["definition"]]
    completion = False
    while stack:
        definition = stack.pop()
        completion = completion or definition.get("completion_policy") is not None
        stack.extend(definition.get("members", {}).values())
    if (
        any(
            name in request
            for name in (
                "session_turn",
                "session_observer",
                "session_lineage",
                "session_native_history",
                "session_root_snapshot",
            )
        )
        or request.get("session_history")
        or "coding_composition_protocol" in manifest
        or "deployment_admission_protocol" in manifest
        or completion
    ):
        raise ValidationError(
            "Temporal executor graphs require the supported stateless composition"
        )
    from .governance import TemporalExecutionPolicy
    from .temporal_state import validate_schema_references

    policy = (
        TemporalExecutionPolicy.from_identity(manifest["execution_policy"])
        if "execution_policy" in manifest
        else TemporalExecutionPolicy()
    )

    for node in nodes:
        alias = "__relf_node__:" + node.executor
        if policy.allowed_tools is not None and alias not in policy.allowed_tools:
            raise ValidationError("Tool forbidden by execution policy")
        try:
            registration = manifest["workflow_nodes"]["registrations"][alias]
        except KeyError as exc:
            raise DefinitionMismatch("Temporal node executor is not registered") from exc
        if not is_valid(node.config, registration["spec"]["config_schema"]):
            raise ValidationError("Node config does not match its registered Schema")
        validate_schema_references(node.output_schema)


def action_id(request):
    return request[MARKER]["run_id"] + ":tool:0:executor"


def validate_node_envelope(request, manifest):
    if type(request) is not dict:
        raise ValidationError("Node activity requires a fixed request object")
    if type(manifest) is not dict:
        raise DefinitionMismatch("Node activity requires its fixed runtime manifest")
    alias = request.get("tool")
    if "node_request" not in request:
        if manifest.get("workflow_node_protocol") == 1 and is_alias(alias):
            raise DefinitionMismatch("Private node Tool requires its original child request")
        return
    if not is_alias(alias) or manifest.get("workflow_node_protocol") != 1:
        raise DefinitionMismatch("Ordinary Tool cannot import a private node request")
    body = validate_node_request(request["node_request"], manifest)
    if alias != body["definition"]["steps"][0]["tool"]:
        raise DefinitionMismatch("Node envelope selected another registered executor")
    origin = body[MARKER]
    from .temporal_bindings import request_release_digest

    expected_action = action_id(body)
    operation = {
        "run_id": origin["run_id"],
        "action_id": expected_action,
        "scope": origin["scope"],
        "tool": manifest["tools"][alias],
        "arguments": body["input"],
    }
    if (
        request.get("runtime_manifest") != manifest
        or request.get("scope") != origin["scope"]
        or request.get("run_id") != origin["run_id"]
        or request.get("action_id") != expected_action
        or request.get("attempt_id") != expected_action + ":attempt:1"
        or request.get("effect_key")
        != "ralf-temporal:" + digest([origin["scope"], origin["run_id"], expected_action])
        or request.get("operation_digest") != digest(operation)
        or request.get("arguments") != body["input"]
        or alias != body["definition"]["steps"][0]["tool"]
        or request.get("tool_manifest") != manifest["tools"][alias]
        or request.get("release_digest") != request_release_digest(body, manifest)
        or not _text(request.get("execution_epoch"))
        or "step_bindings" in request
    ):
        raise DefinitionMismatch("Node envelope differs from its original child execution")
