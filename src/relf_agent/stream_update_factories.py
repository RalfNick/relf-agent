"""Pure declarations for the original bounded presentation policy."""

from .errors import ValidationError
from .stream_updates import StreamUpdatePolicy

FIELDS = frozenset({"max_deltas", "max_bytes", "max_payload_bytes", "publish_timeout"})


def _policy(config):
    if type(config) is not dict or set(config) - FIELDS:
        raise ValidationError("Unknown stream update policy configuration fields")
    return StreamUpdatePolicy(**config)


def validate(config):
    _policy(config)


def build(config, context):
    return _policy(config)


def register_stream_updates(registry):
    registry.register("stream_updates", "bounded", build, validator=validate)
