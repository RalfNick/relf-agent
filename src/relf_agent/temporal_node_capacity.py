"""Bounded capacity admission in the original node Action/Workflow History."""

import copy
import math

from .errors import DefinitionMismatch, RalfError
from .temporal_node_capacity_owner import NODE_OWNER_KIND
from .types import digest

MAX_DEFERRALS = 64
WAIT_CODE = "node_capacity_wait"


def selected(manifest):
    owner = manifest.get("tool_execution_protocol", {}).get("owner", {})
    return (
        manifest.get("workflow_node_protocol") == 1
        and owner.get("kind") == NODE_OWNER_KIND
        and owner.get("behavior_version") == "workflow-node-capacity-1"
    )


def owns(state):
    return selected(state.manifest) and state.request["definition"]["kind"] == "executor"


def envelope(state, action, request):
    if not owns(state):
        return request
    value = action.setdefault(
        "node_capacity", {"version": 1, "ordinal": 0, "phase": "dispatch", "refusals": []}
    )
    return {**request, "node_capacity_ordinal": value["ordinal"]}


def _proof(request):
    return {
        name: copy.deepcopy(request[name])
        for name in ("scope", "run_id", "action_id", "release_digest", "execution_epoch")
    } | {"request_digest": digest(request), "ordinal": request["node_capacity_ordinal"]}


def refusal(request):
    return {
        "ok": False,
        "code": WAIT_CODE,
        "dispatched": False,
        "handler_not_started": True,
        "node_capacity": _proof(request),
    }


def unstarted(request, code):
    return {
        "ok": False,
        "code": code,
        "dispatched": False,
        "handler_not_started": True,
        "node_not_started": _proof(request),
    }


def begin_window(state, action, *, now, total_seconds):
    if not owns(state):
        return
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (now, total_seconds)):
        raise DefinitionMismatch("Node capacity requires its original finite History window")
    if total_seconds <= 0 or not math.isfinite(now + total_seconds):
        raise DefinitionMismatch("Node capacity requires its original positive History window")
    value = action["node_capacity"]
    if "deadline" not in value:
        value.update(started_at=now, deadline=now + total_seconds)


def waiting(state):
    if owns(state):
        return next(
            (
                a
                for a in state.actions
                if a.get("node_capacity", {}).get("phase") == "waiting"
                and a["status"] == "executing"
                and not state.tool_executions[a["id"]].get("owns_remote_uncertainty")
            ),
            None,
        )
    return None


def _unclaimed(record):
    return "invocation_id" not in record


def _finish(state, action, code):
    record = state.tool_executions[action["id"]]
    if action["status"] in {"completed", "failed", "outcome_unknown"} or record.get(
        "owns_remote_uncertainty"
    ):
        return False
    if not _unclaimed(record):
        state.operation_unknown(action["id"], "node_capacity_proof_rejected")
        return False
    record.update(execution_stopped=True, capacity_fenced=True)
    action["node_capacity"]["phase"] = "closed"
    state._settle(action, undispatched=True)
    action["status"] = "failed"
    if state.state not in {"succeeded", "failed", "cancelled"}:
        state.state, state.error = "failed", {"code": code}
    state._emit("node_capacity_closed", {"action_id": action["id"], "code": code})
    return False


def observe(state, action_id, response):
    if not owns(state) or type(response) is not dict:
        return False
    if not ("node_capacity" in response or "node_not_started" in response):
        return False
    action = next(a for a in state.actions if a["id"] == action_id)
    value = action["node_capacity"]
    if action["status"] in {"completed", "failed", "outcome_unknown"}:
        return True  # Late no-start evidence cannot reopen settled or uncertain work.
    record = state.tool_executions[action_id]
    if value["phase"] == "waiting" and record.get("capacity_fenced"):
        return True  # The accepted no-start fence cannot be undone by a foreign late reply.
    try:
        identity = digest(response)
    except (RalfError, ValueError, TypeError, RecursionError):
        state.operation_unknown(action_id, "node_capacity_proof_rejected")
        return True
    if any(item["digest"] == identity for item in value["refusals"]):
        return True  # Re-observing a recorded no-start reply cannot fence a new invocation.
    request = envelope(state, action, state.envelope(action))
    is_wait = "node_capacity" in response
    expected = refusal(request) if is_wait else unstarted(request, response.get("code"))
    marker = response.get("node_capacity" if is_wait else "node_not_started")
    if (
        response != expected
        or response.get("ok") is not False
        or response.get("dispatched") is not False
        or response.get("handler_not_started") is not True
        or type(marker) is not dict
        or type(marker.get("ordinal")) is not int
        or digest(request) != record["request_digest"]
        or not _unclaimed(record)
        or value["phase"] != "dispatch"
    ):
        state.operation_unknown(action_id, "node_capacity_proof_rejected")
        return True
    # Only this History can fence its unclaimed request before a later transport.
    record.update(execution_stopped=True, capacity_fenced=True)
    if not is_wait:
        value["refusals"].append({"ordinal": value["ordinal"], "digest": identity})
        _finish(state, action, response["code"])
        return True
    value["refusals"].append({"ordinal": value["ordinal"], "digest": identity})
    value["phase"] = "waiting"
    state.active_action = None
    state._emit("node_capacity_waiting", {"action_id": action_id, "ordinal": value["ordinal"]})
    if state.state in {"succeeded", "failed", "cancelled"}:
        _finish(state, action, "cancelled" if state.state == "cancelled" else "target_closed")
    elif len(value["refusals"]) >= MAX_DEFERRALS:
        _finish(state, action, "node_capacity_timeout")
    return True


def delay(state, *, now):
    action = waiting(state)
    if action is None:
        return 0
    value = action["node_capacity"]
    if "deadline" not in value:
        raise DefinitionMismatch("Capacity waiting requires its original History deadline")
    backoff = min(1.0, 0.1 * 2 ** min(len(value["refusals"]) - 1, 4))
    value.setdefault("retry_at", min(now + backoff, value["deadline"]))
    return max(0, min(value["retry_at"], value["deadline"]) - now)


def resume(state, *, now, timer_fired=False):
    action = waiting(state)
    if action is None:
        return False
    value = action["node_capacity"]
    if state.state in {"succeeded", "failed", "cancelled"}:
        return _finish(state, action, "target_closed")
    if now >= value["deadline"] or len(value["refusals"]) >= MAX_DEFERRALS:
        return _finish(state, action, "node_capacity_timeout")
    if not timer_fired and now < value.get("retry_at", now):
        return False
    value.pop("retry_at", None)
    value.update(ordinal=value["ordinal"] + 1, phase="retry_ready")
    state._emit("node_capacity_ready", {"action_id": action["id"], "ordinal": value["ordinal"]})
    return True


def retry_operation(state, action):
    if not owns(state) or action.get("node_capacity", {}).get("phase") != "retry_ready":
        return None
    from .temporal_tool_execution_state import prepare

    action["node_capacity"]["phase"] = "dispatch"
    state.active_action = action["id"]
    return action, prepare(state, action, state.envelope(action))


def cancel_waiting(state):
    if owns(state):
        for action in state.actions:
            if action.get("node_capacity", {}).get("phase") in {"waiting", "retry_ready"}:
                _finish(state, action, "cancelled")


def transport_id(action):
    identity = action["attempts"][0]["id"]
    ordinal = action.get("node_capacity", {}).get("ordinal", 0)
    return identity if ordinal == 0 else identity + ":capacity:" + str(ordinal)


def ack_transport_id(state, evidence):
    action = next(a for a in state.actions if a["id"] == evidence["action_id"])
    value = action["node_capacity"]
    ordinal = value.get("ack_ordinal", 0) + 1
    value["ack_ordinal"] = ordinal
    return "ack:" + action["id"] + ":capacity:" + str(ordinal)


def remaining(state, action, *, now):
    value = action["node_capacity"]
    seconds = value["deadline"] - now
    if seconds <= 0:
        _finish(state, action, "node_capacity_timeout")
        return 0
    return seconds


def fail_unadmitted(state, action, code):
    if not owns(state):
        return False
    if action["status"] in {"completed", "failed", "outcome_unknown"}:
        return True
    if not _unclaimed(state.tool_executions[action["id"]]):
        return False
    _finish(state, action, code)
    return True
