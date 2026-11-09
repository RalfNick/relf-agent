"""Safe projections of existing close responsibility, never execution facts."""

_AUTHORITIES = frozenset({"unknown", "local", "temporal"})
_OWNERSHIP = frozenset({"unknown", "owned", "borrowed", "mixed"})
_STAGES = frozenset(
    {
        "unknown",
        "run_drain",
        "rpc_drain",
        "construction",
        "execution_drain",
        "handler_drain",
        "end_ack",
        "worker_start",
        "worker_stop",
        "authority_close",
        "resource_close",
    }
)
_BLOCKERS = frozenset(
    {"run", "rpc", "construction", "handler", "thread", "end_ack", "worker", "resource"}
)


def _choice(value, allowed):
    return value if type(value) is str and value in allowed else "unknown"


def _counts(value):
    if type(value) is dict:
        items = value.items()
    elif type(value) in {list, tuple}:
        items = ((item.get("kind"), item.get("count")) for item in value if type(item) is dict)
    else:
        return {}
    counts = {}
    for kind, count in items:
        if (
            type(kind) is str
            and kind in _BLOCKERS
            and type(count) is int
            and 0 <= count <= 2**63 - 1
        ):
            counts[kind] = max(counts.get(kind, 0), count)
    return counts


def make_close_diagnostics(
    *, authority="unknown", stage="unknown", ownership="unknown", blockers=None
):
    """Copy only fixed labels and real counts; never inspect a legacy report."""
    return {
        "schema_version": 1,
        "state": "incomplete",
        "authority": _choice(authority, _AUTHORITIES),
        "stage": _choice(stage, _STAGES),
        "ownership": _choice(ownership, _OWNERSHIP),
        "blockers": [{"kind": kind, "count": count} for kind, count in _counts(blockers).items()],
        "retry_action": "retain_original_instance_and_retry_close",
    }


def safe_close_diagnostics(value=None):
    """Normalize constructor metadata without formatting arbitrary objects."""
    if type(value) is not dict:
        return make_close_diagnostics()
    return make_close_diagnostics(
        authority=value.get("authority"),
        stage=value.get("stage"),
        ownership=value.get("ownership"),
        blockers=value.get("blockers"),
    )


def enrich_close_diagnostics(
    error, *, authority="unknown", stage="unknown", ownership="unknown", blockers=None
):
    """Fill unknown context, keeping the original exception and specific cause."""
    from .errors import CloseIncomplete

    if not isinstance(error, CloseIncomplete):
        return error
    current = error.diagnostics
    additional = make_close_diagnostics(
        authority=authority, stage=stage, ownership=ownership, blockers=blockers
    )
    for name in ("authority", "stage", "ownership"):
        if current[name] == "unknown":
            current[name] = additional[name]
    counts = _counts(current["blockers"])
    for kind, count in _counts(additional["blockers"]).items():
        counts[kind] = max(counts.get(kind, 0), count)
    current["blockers"] = [{"kind": kind, "count": count} for kind, count in counts.items()]
    error._close_diagnostics = current
    return error
