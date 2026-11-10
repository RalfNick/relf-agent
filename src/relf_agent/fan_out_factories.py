"""Opt-in pure fan-out Planner assembly, without resources or scheduling."""

from .errors import ValidationError
from .fan_out_planning import FanOutDAGPlanner

FIELDS = frozenset({"worker", "reducer", "items_path", "max_items", "version"})


def validate(config):
    if type(config) is not dict or set(config) - FIELDS:
        raise ValidationError("Fan-out configuration contains unsupported fields")
    FanOutDAGPlanner(**config)


def build(config, context):
    validate(config)
    return {"fan-out": FanOutDAGPlanner(**config)}


def register_fan_out_factory(registry):
    registry.register("planners", "fan-out", build, validator=validate)
