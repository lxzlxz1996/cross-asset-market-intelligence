"""Shared canonical serialization and SHA-256 primitives for immutable identities."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented in canonical finite JSON."""


def _canonical_default(value: object) -> object:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise CanonicalizationError("Canonical datetimes must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError("Canonical Decimal values must be finite")
        if value.is_zero():
            return "0"
        return format(value.normalize(), "f")
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported canonical JSON scalar: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return compact UTF-8-ready JSON with sorted keys and finite numeric values."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=_canonical_default,
        )
    except (TypeError, ValueError) as error:
        raise CanonicalizationError(str(error)) from error


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical JSON encoded as UTF-8 without a BOM."""

    return canonical_json(value).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    """Return the explicit SHA-256 semantic identity of canonical JSON content."""

    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def raw_file_sha256(path: Path) -> str:
    """Return SHA-256 over exact raw file bytes, without line-ending normalization."""

    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
