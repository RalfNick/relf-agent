"""Local presentation appends use only the original coordinator/store."""

from .errors import DefinitionMismatch
from .stream_reporting import attempt_scope


def reporting(engine, run_id, action_id, attempt_id, operation):
    if getattr(engine, "stream_updates", None) is None:
        # Preserve the default cost, but shadow a parent's reporting context.
        return attempt_scope(None, operation, action_id, attempt_id, None)
    run = engine._authorized(run_id)
    identity = engine._step_manifest(run).get("stream_updates")

    async def publish(value):
        with engine.store.transaction():
            current = engine._authorized(run_id)
            action = next((a for a in current["actions"] if a["id"] == action_id), None)
            if (
                action is None
                or action["kind"] != operation
                or not any(a["id"] == attempt_id for a in action["attempts"])
            ):
                raise DefinitionMismatch("Progress lost its original Attempt")
            engine.store.emit(run_id, "agent_update", value)

    return attempt_scope(identity, operation, action_id, attempt_id, publish)
