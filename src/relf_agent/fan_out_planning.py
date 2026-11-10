"""Pure bounded batch proposals over original DAG and child execution contracts."""

from .dag_planning import DAGNode, DAGProposal
from .errors import ValidationError
from .orchestration_types import _identifier, _JsonValue
from .planning import PlanningRequest
from .types import _require_text, canonical
from .workflow import InputMap, ValueRef, _resolve


class FanOutDAGPlanner(_JsonValue):
    def __init__(self, worker="worker", *, reducer=None, items_path=(), max_items=32, version="1"):
        _identifier(worker)
        if reducer is not None:
            _identifier(reducer)
        _require_text(version, "Fan-out planner version")
        path = ValueRef(path=items_path).path
        if len(path) > 31:
            raise ValidationError("Fan-out items_path must leave one binding slot for its index")
        maximum = 256 if reducer is None else 255
        if type(max_items) is not int or not 1 <= max_items <= maximum:
            raise ValidationError("Fan-out max_items exceeds its finite DAG allowance")
        self._data_json = canonical(
            {
                "kind": "fan-out-dag-planner",
                "version": version,
                "worker": worker,
                "reducer": reducer,
                "items_path": list(path),
                "max_items": max_items,
            }
        )

    @property
    def identity(self):
        return self.to_dict()

    async def plan(self, request, caller):
        if not isinstance(request, PlanningRequest):
            raise ValidationError("Fan-out requires a PlanningRequest")
        value = request.to_dict()
        if type(value["revision"]) is not int or value["revision"] != 0:
            raise ValidationError("Fan-out requires the initial planning revision")
        if type(value["results"]) is not list or value["results"]:
            raise ValidationError("Fan-out does not replan accepted child results")
        config = self.to_dict()
        if config["worker"] not in value["members"] or (
            config["reducer"] is not None and config["reducer"] not in value["members"]
        ):
            raise ValidationError("Fan-out worker and reducer must be registered members")
        path = tuple(config["items_path"])
        items = _resolve(ValueRef(path=path), value["task"], {})
        if type(items) is not list or not 1 <= len(items) <= config["max_items"]:
            raise ValidationError("Fan-out requires a non-empty list within max_items")
        count = len(items) + (config["reducer"] is not None)
        constraints = value.get("constraints", {})
        for name in ("remaining_steps", "max_nodes"):
            if name in constraints:
                limit = constraints[name]
                if type(limit) is not int or limit < 0 or count > limit:
                    raise ValidationError("Fan-out exceeds the original " + name + " allowance")
        nodes = [
            DAGNode(f"map-{i:04d}", config["worker"], input=ValueRef(path=(*path, i)))
            for i in range(len(items))
        ]
        results = InputMap({node.id: ValueRef(node.id) for node in nodes})
        if config["reducer"] is None:
            return DAGProposal(nodes, output=results)
        nodes.append(
            DAGNode(
                "reduce",
                config["reducer"],
                depends_on=tuple(node.id for node in nodes),
                input=results,
            )
        )
        return DAGProposal(nodes, output=ValueRef("reduce"))
