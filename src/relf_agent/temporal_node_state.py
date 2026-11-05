"""Pure node proposals over the original History ToolAction and evidence rules."""

from .errors import RalfError, ValidationError
from .temporal_node_protocol import action_id
from .types import digest
from .workflow import validate_output


def next_operation(state):
    step = state.step
    manifest = state.manifest["tools"][step["tool"]]
    if not state.actions:
        identity = action_id(state.request)
        arguments = state.request["input"]
        operation = {
            "run_id": state.run_id,
            "action_id": identity,
            "scope": state.scope,
            "tool": manifest,
            "arguments": arguments,
        }
        state.actions.append(
            {
                "id": identity,
                "kind": "tool",
                "node": 0,
                "tool": step["tool"],
                "arguments": arguments,
                "digest": digest(operation),
                "effect_key": "ralf-temporal:" + digest([state.scope, state.run_id, identity]),
                "call_id": identity,
                "approved": False,
                "status": "ready",
                "attempts": [],
            }
        )
        state._emit("workflow_node_action_recorded", {"action_id": identity})
    action = state.actions[0]
    if action["status"] == "completed":
        if (
            state.pending_acks
            or state.deferred_acks
            or state.active_evidence_ack is not None
            or state.reconcile_requests
            or state.active_reconciliation is not None
            or not state.quiescent
        ):
            return None
        try:
            node_schema = manifest["config"]["node_executor"]["spec"]["output_schema"]
            result = validate_output(action["result"], node_schema)
            result = validate_output(result, step["output_schema"])
        except RalfError as exc:
            state.state, state.error = "failed", {"code": exc.code}
            state._emit("run_failed", state.error)
            return None
        state.state, state.result = "succeeded", result
        state._emit("node_completed", {"node": 0, "result_digest": digest(result)})
        state._emit("run_succeeded", {"result_digest": digest(result)})
        return None
    if action["status"] in {"waiting_approval", "blocked", "outcome_unknown", "failed"}:
        return None
    if action["status"] != "ready":
        raise ValidationError("Invalid original node ToolAction phase")
    if manifest["requires_approval"] and not action["approved"]:
        action["status"], state.state = "waiting_approval", "waiting_approval"
        state._emit("approval_requested", {"action_id": action["id"], "digest": action["digest"]})
        return None
    if not state._reserve(action, manifest["cost"]):
        return None
    from .temporal_tool_execution_state import prepare

    return action, prepare(state, action, state.envelope(action))
