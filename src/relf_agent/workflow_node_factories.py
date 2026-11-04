"""Explicit default registration for borrowed async Workflow node executors."""

from .errors import ValidationError
from .workflow_executors import IdentityNodeExecutor, NodeExecutorRegistry, NodeExecutorSpec


def validate(config):
    if type(config) is not dict or config:
        raise ValidationError("Identity Workflow nodes require empty configuration")


def build(config, context):
    validate(config)
    registry = NodeExecutorRegistry()
    registry.register(
        NodeExecutorSpec("identity", "Return the complete JSON input", effect="read_only"),
        IdentityNodeExecutor(),
    )
    return registry


def register_workflow_nodes(registry):
    registry.register("workflow_executors", "identity", build, validator=validate)
