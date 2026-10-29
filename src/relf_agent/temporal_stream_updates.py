"""Bounded presentation Signals; original Workflow History alone adopts them."""

import json

from .errors import DefinitionMismatch
from .stream_reporting import attempt_scope
from .stream_updates import StreamUpdatePolicy, update_value
from .types import canonical

SIGNAL = "agent_update"


def callbacks(client, request, info):
    fixed = json.loads(
        canonical(
            {
                name: request[name]
                for name in ("scope", "run_id", "release_digest", "execution_epoch")
            }
        )
    )
    namespace = info.workflow_namespace
    handle = None
    if client is not None and (
        client.namespace == namespace
        and fixed["run_id"] == info.workflow_id
        and fixed["execution_epoch"] == info.workflow_run_id
    ):
        handle = client.get_workflow_handle(info.workflow_id, run_id=info.workflow_run_id)

    async def publish(update):
        if handle is None or client.namespace != namespace:
            raise DefinitionMismatch("Stream publication lost original Workflow epoch or namespace")
        await handle.signal(SIGNAL, fixed | {"update": update})
        if client.namespace != namespace:
            raise DefinitionMismatch("Stream namespace changed during publication")

    return publish


async def observe_activity(request, operation, call, publisher):
    identity = request["runtime_manifest"].get("stream_updates")
    if identity is None:
        return await call()
    with attempt_scope(
        identity, operation, request["action_id"], request["attempt_id"], publisher
    ) as scope:
        result = await call()
    return result | {"stream_observation": scope.summary}


def accept_update(state, payload):
    identity = state.manifest.get("stream_updates")
    if identity is None:
        raise DefinitionMismatch("Original Workflow did not select stream updates")
    policy = StreamUpdatePolicy.from_identity(identity)
    if (
        type(payload) is not dict
        or set(payload) != {"scope", "run_id", "release_digest", "execution_epoch", "update"}
        or any(
            payload[name] != value
            for name, value in {
                "scope": state.scope,
                "run_id": state.run_id,
                "release_digest": state.release_digest,
                "execution_epoch": state.epoch,
            }.items()
        )
    ):
        raise DefinitionMismatch("Stream update differs from original Workflow binding")
    value = update_value(payload["update"], policy)
    action = next((a for a in state.actions if a["id"] == value["action_id"]), None)
    if (
        action is None
        or action["kind"] != value["operation"]
        or not any(a["id"] == value["attempt_id"] for a in action["attempts"])
    ):
        raise DefinitionMismatch("Stream update differs from original Attempt")
    if action["status"] != "executing":
        return False
    if not hasattr(state, "_stream_update_counts"):
        state._stream_update_counts = {}
    stats = state._stream_update_counts.setdefault(
        value["attempt_id"],
        {
            "sequence": 0,
            "count": 0,
            "bytes": 0,
            "gap": False,
        },
    )
    if value["sequence"] <= stats["sequence"]:
        return False
    size = len(canonical(value["payload"]).encode("utf-8"))
    if value["kind"] != "gap" and (
        stats["count"] >= policy.max_deltas or stats["bytes"] + size > policy.max_bytes
    ):
        if not stats["gap"]:
            state._emit(
                "agent_update",
                value | {"kind": "gap", "payload": {"reason": "capacity"}},
                bump=False,
            )
            stats["gap"] = True
        stats["sequence"] = value["sequence"]
        return False
    if value["sequence"] > stats["sequence"] + 1 and not stats["gap"]:
        state._emit(
            "agent_update",
            value
            | {
                "kind": "gap",
                "sequence": value["sequence"] - 1,
                "payload": {"reason": "transport_gap", "expected": stats["sequence"] + 1},
            },
            bump=False,
        )
        stats["gap"] = True
    if value["kind"] == "gap":
        if stats["gap"]:
            stats["sequence"] = value["sequence"]
            return False
        stats["gap"] = True
    else:
        stats["count"] += 1
        stats["bytes"] += size
    state._emit("agent_update", value, bump=False)
    stats["sequence"] = value["sequence"]
    return True


def remember_observation(state, action_id, response):
    if "stream_updates" not in state.manifest or type(response) is not dict:
        return
    action = next((a for a in state.actions if a["id"] == action_id), None)
    observation = response.get("stream_observation")
    if action is None or observation is None:
        return
    if (
        type(observation) is not dict
        or set(observation) != {"published", "truncated", "reason"}
        or type(observation["published"]) is not int
        or not 0 <= observation["published"] <= 1024
        or type(observation["truncated"]) is not bool
        or observation["reason"]
        not in (None, "capacity", "invalid_payload", "payload_limit", "publisher_error")
    ):
        observation = {"published": 0, "truncated": True, "reason": "invalid_observation"}
    action["stream_observation"] = dict(observation)


def decorate_fact(state, kind, data):
    if kind not in {
        "model_response_recorded",
        "tool_result_committed",
        "effect_reconciled",
        "action_outcome_unknown",
    }:
        return data
    action = next((a for a in state.actions if a["id"] == data.get("action_id")), None)
    if action is None or action["kind"] not in {"model", "tool"} or not action["attempts"]:
        return data
    attempt = action["attempts"][-1]["id"]
    stats = getattr(state, "_stream_update_counts", {}).get(attempt, {})
    observation = action.get(
        "stream_observation", {"published": 0, "truncated": False, "reason": None}
    )
    observation = observation | {"recorded": stats.get("count", 0)}
    if stats.get("gap") or observation["published"] != observation["recorded"]:
        observation = observation | {
            "truncated": True,
            "reason": observation["reason"] or "transport_gap",
        }
    return data | {
        "stream_end": {
            "operation": action["kind"],
            "action_id": action["id"],
            "attempt_id": attempt,
            "observation": observation,
        }
    }
