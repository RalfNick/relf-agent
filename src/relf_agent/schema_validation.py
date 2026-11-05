"""Pure instance validation against resources contained in a fixed Schema."""

from jsonschema import Draft202012Validator
from referencing.exceptions import Unresolvable

from .errors import ValidationError
from .responses_format import LOCAL_SCHEMA_REGISTRY


def is_valid(value, schema):
    try:
        return Draft202012Validator(schema, registry=LOCAL_SCHEMA_REGISTRY).is_valid(value)
    except Unresolvable:
        raise ValidationError(
            "Schema reference cannot be resolved within its fixed resources"
        ) from None
    except RecursionError:
        raise ValidationError("Schema validation exceeds the supported recursion depth") from None
