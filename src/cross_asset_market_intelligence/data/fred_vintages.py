"""Validation and deterministic ordering for established FRED realtime vintages."""

from __future__ import annotations

from datetime import date

from ..exceptions import ProcessingValidationError

FRED_VINTAGE_PREFIX = "fred_realtime:"


def fred_vintage_rank(vintage: str) -> tuple[str, str, str]:
    """Validate and rank a FRED date-level real-time vintage key."""
    if not isinstance(vintage, str) or not vintage.startswith(FRED_VINTAGE_PREFIX):
        raise ProcessingValidationError("Raw FRED vintage is missing or not a FRED real-time key")
    parts = vintage.split(":")
    if len(parts) != 3 or not parts[1] or not parts[2]:
        raise ProcessingValidationError("Raw FRED vintage is malformed")
    try:
        realtime_start = date.fromisoformat(parts[1])
        realtime_end = date.fromisoformat(parts[2])
    except ValueError as error:
        raise ProcessingValidationError("Raw FRED vintage contains invalid dates") from error
    if realtime_start > realtime_end:
        raise ProcessingValidationError("Raw FRED vintage end precedes its start")
    return (parts[1], parts[2], vintage)
