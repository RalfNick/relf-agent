"""Explicit pure loop roles, without resources or execution ownership."""

from .bounded_loop import BoundedLoopPolicy
from .errors import ValidationError
from .workflow import BranchCondition, decode_binding

FIELDS = frozenset({"worker", "until", "max_iterations", "version"})


def _options(config):
    if type(config) is not dict or set(config) - FIELDS:
        raise ValidationError("Bounded loop configuration contains unsupported fields")
    options = dict(config)
    condition = options.get("until")
    if condition is not None:
        if (
            type(condition) is not dict
            or set(condition) - {"value", "equals", "negate"}
            or not {"value", "equals"}.issubset(condition)
        ):
            raise ValidationError("Bounded loop until requires an explicit condition")
        options["until"] = BranchCondition(
            decode_binding(condition["value"]),
            condition["equals"],
            condition.get("negate", False),
        )
    return options


def validate(config):
    BoundedLoopPolicy(**_options(config))


def build(config, context):
    return {"bounded-loop": BoundedLoopPolicy(**_options(config))}


def register_bounded_loop_factories(registry):
    for role in ("planners", "plan_verifiers"):
        registry.register(role, "bounded-loop", build, validator=validate)
