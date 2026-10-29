"""Finite observation DTO serialization without deep-copying unvalidated leaves."""

import json
from dataclasses import fields, is_dataclass

from .errors import ValidationError


def _fields(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    raise TypeError("DTO data requires finite JSON values")


def canonical_dto(value):
    # Project nested dataclasses during traversal; unlike asdict, this never
    # deep-copies a native/lazy leaf before refusing it. JSON detects cycles.
    try:
        return json.dumps(
            value,
            default=_fields,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise ValidationError("DTO data requires finite JSON values") from exc
