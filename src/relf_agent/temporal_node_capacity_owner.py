"""Node-only capacity refusals; the original History decides whether to wait."""

from .temporal_context_execution import (
    ContextExecutionOwner,
    ContextExecutionRejected,
    _proof,
)
from .tool_execution import ToolExecutionOwner

NODE_OWNER_KIND = "workflow-node-capacity-owner"


class NodeCapacityUnavailable(ContextExecutionRejected):
    """An open original node owner had no slot and started no operation."""

    def __init__(self):
        super().__init__(handler_not_started=True)


def _full(execution):
    return not execution._closed and len(execution._entries) >= execution.max_calls


def _capacity_refusal(execution, proof, exception, *, full_before):
    # The original execute validates parameters and refuses full ownership
    # without yielding. Snapshot that state before awaiting so an operation's
    # later business error cannot become a capacity refusal when peers fill up.
    return (
        full_before
        and type(exception) is ContextExecutionRejected
        and exception.handler_not_started is True
        and _full(execution)
        and execution._key(_proof(proof)) not in execution._entries
    )


class NodeCapacityOwner(ToolExecutionOwner):
    def __init__(self, *, max_calls=16):
        super().__init__(version="workflow-node-capacity-1", max_calls=max_calls)

    @property
    def identity(self):
        return {**super().identity, "kind": NODE_OWNER_KIND}

    async def execute(self, operation, *, proof, on_end=None):
        original = self._execution
        full_before = not self._closing and _full(original)
        try:
            return await super().execute(operation, proof=proof, on_end=on_end)
        except ContextExecutionRejected as exc:
            if (
                not self._closing
                and self._execution is original
                and _capacity_refusal(original, proof, exc, full_before=full_before)
            ):
                raise NodeCapacityUnavailable() from None
            raise


class NodeNotificationOwner(ContextExecutionOwner):
    def __init__(self, *, max_calls=256):
        super().__init__(max_calls=max_calls)

    async def execute(self, operation, *, proof, on_end=None):
        full_before = _full(self)
        try:
            return await super().execute(operation, proof=proof, on_end=on_end)
        except ContextExecutionRejected as exc:
            if _capacity_refusal(self, proof, exc, full_before=full_before):
                raise NodeCapacityUnavailable() from None
            raise
