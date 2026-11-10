"""Pure repeat-and-check policy over original DAG revisions and adopted results."""

from .dag_planning import DAGNode, DAGProposal
from .errors import ValidationError
from .orchestration_types import _identifier, _JsonValue
from .planning import PlanningRequest, Verification
from .types import _require_text, canonical
from .workflow import (
    BranchCondition,
    InputMap,
    Literal,
    ValueRef,
    _resolve,
    decode_binding,
    encode_binding,
)


def _matches(condition, result):
    observed = _resolve(decode_binding(condition["value"]), result, {})
    matched = canonical(observed) == canonical(condition["equals"])
    return not matched if condition["negate"] else matched


class BoundedLoopPolicy(_JsonValue):
    def __init__(self, worker="worker", *, until=None, max_iterations=3, version="1"):
        _identifier(worker)
        _require_text(version, "Bounded loop policy version")
        if type(max_iterations) is not int or not 1 <= max_iterations <= 32:
            raise ValidationError("Bounded loop max_iterations must be an integer from 1 to 32")
        if until is None:
            until = BranchCondition(ValueRef(path=("done",)), True)
        if not isinstance(until, BranchCondition):
            raise ValidationError("Bounded loop until requires a BranchCondition")
        until = BranchCondition(
            decode_binding(encode_binding(until.value)), until.equals, until.negate
        )
        if until.value.source != "input" or not until.value.required:
            raise ValidationError("Bounded loop until requires a required input reference")
        self._data_json = canonical(
            {
                "kind": "bounded-loop-policy",
                "version": version,
                "worker": worker,
                "max_iterations": max_iterations,
                "until": {
                    "value": encode_binding(until.value),
                    "equals": until.equals,
                    "negate": until.negate,
                },
            }
        )

    @property
    def identity(self):
        return self.to_dict()

    def _validated(self, request, completed):
        if not isinstance(request, PlanningRequest):
            raise ValidationError("Bounded loop requires a PlanningRequest")
        value, config = request.to_dict(), self.to_dict()
        revision, results = value["revision"], value["results"]
        if type(revision) is not int or not 0 <= revision < config["max_iterations"]:
            raise ValidationError("Bounded loop revision exceeds its finite iteration allowance")
        if config["worker"] not in value["members"]:
            raise ValidationError("Bounded loop worker must be a registered member")
        if type(results) is not list or len(results) != revision + completed:
            raise ValidationError("Bounded loop history does not match its original phase")
        ids = set()
        for record in results:
            if type(record) is not dict or set(record) != {"id", "member", "result"}:
                raise ValidationError("Bounded loop requires exact adopted result records")
            call_id = record["id"]
            if (
                not isinstance(call_id, str)
                or not 1 <= len(call_id) <= 1024
                or call_id in ids
                or record["member"] != config["worker"]
            ):
                raise ValidationError("Bounded loop result identity or member is invalid")
            try:
                call_id.encode("utf-8")
            except UnicodeError as exc:
                raise ValidationError("Bounded loop result identity requires UTF-8") from exc
            ids.add(call_id)
        # The authority supplies ordered, adopted results; opaque IDs do not prove order.
        previous = results[:-1] if completed else results
        if any(_matches(config["until"], record["result"]) for record in previous):
            raise ValidationError("Bounded loop cannot append work after its stopping condition")
        return value, config

    async def plan(self, request, caller):
        value, config = self._validated(request, 0)
        constraints = value.get("constraints", {})
        for name in ("remaining_steps", "max_nodes", "remaining_revisions"):
            if name in constraints:
                allowance = constraints[name]
                if type(allowance) is not int or allowance < 1:
                    raise ValidationError("Bounded loop requires one original " + name + " slot")
        return DAGProposal(
            [
                DAGNode(
                    "iteration",
                    config["worker"],
                    input=InputMap(
                        {
                            "task": ValueRef(),
                            "previous": Literal(
                                value["results"][-1]["result"] if value["results"] else None
                            ),
                            "iteration": Literal(value["revision"] + 1),
                        }
                    ),
                )
            ],
            output=ValueRef("iteration"),
        )

    def verify(self, request):
        value, config = self._validated(request, 1)
        latest = value["results"][-1]["result"]
        if _matches(config["until"], latest):
            return Verification("succeeded", latest)
        if value["revision"] + 1 >= config["max_iterations"]:
            return Verification(
                "failed",
                {
                    "reason": "loop_iteration_limit",
                    "iterations": value["revision"] + 1,
                    "last_result": latest,
                },
            )
        return Verification("replan")
