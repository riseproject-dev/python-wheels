# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
"""JSON Schema validation of state records, proposals and policy."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import jsonschema

from .common import SCHEMA_DIR

KNOWN = ("contribution", "project", "operation", "command", "event",
         "evidence", "proposal", "policy")


class SchemaError(ValueError):
    pass


@lru_cache(maxsize=None)
def _validator(kind: str) -> jsonschema.protocols.Validator:
    if kind not in KNOWN:
        raise SchemaError(f"unknown schema kind {kind!r}")
    with open(SCHEMA_DIR / f"{kind}.schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema, format_checker=cls.FORMAT_CHECKER)


def errors(kind: str, record: Any) -> list[str]:
    return sorted(
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in _validator(kind).iter_errors(record)
    )


def validate(kind: str, record: Any) -> None:
    """Raise SchemaError unless ``record`` is valid. Unknown schema versions
    are rejected (the schemas pin ``schema_version``), so a mutation never
    proceeds on a record this code does not understand."""
    errs = errors(kind, record)
    if errs:
        raise SchemaError(f"invalid {kind} record: " + "; ".join(errs[:10]))
