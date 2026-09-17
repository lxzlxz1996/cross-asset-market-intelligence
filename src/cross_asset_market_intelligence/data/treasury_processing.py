"""Direct, versioned normalization of approved FRED Treasury raw observations."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import ProcessingPersistenceError, ProcessingValidationError
from ..lineage import RawInputIdentity, processed_observation_id

APPROVED_FRED_TREASURY_MAPPING = {
    "DGS2": "us_treasury_2y_yield",
    "DGS10": "us_treasury_10y_yield",
}
DIRECT_TREASURY_PROCESSING_VERSION = "fred_treasury_direct_percent_identity_v1"
DIRECT_TREASURY_TRANSFORMATION = "validated_identity_percent_per_annum"
FRED_VINTAGE_PREFIX = "fred_realtime:"


@dataclass(frozen=True)
class RawTreasuryObservation:
    """A raw row selected for direct Treasury normalization."""

    source: str
    series_id: str
    observation_date: date
    value: float | None
    vintage: str


@dataclass(frozen=True)
class TreasuryProcessingResult:
    """Counts returned by one direct-normalization run."""

    inserted: int
    skipped_missing: int


def approved_indicator_for(source: str, series_id: str) -> str:
    """Return the only approved Phase 1.3B source-to-indicator mapping."""
    if source != "fred":
        raise ProcessingValidationError(f"Unsupported source for Treasury processing: {source}")
    try:
        return APPROVED_FRED_TREASURY_MAPPING[series_id]
    except KeyError as error:
        raise ProcessingValidationError(f"Unsupported FRED Treasury series: {series_id}") from error


def select_latest_raw_vintages(
    connection: duckdb.DuckDBPyConnection, source: str, series_id: str
) -> list[RawTreasuryObservation]:
    """Select one deterministic latest FRED real-time vintage per observation date.

    FRED's Phase 1.2 vintage key encodes its date-level real-time start and end.
    The record with the greatest `(realtime_start, realtime_end, vintage)` tuple is
    selected for each date; ISO dates make that lexical ordering chronological.
    """
    approved_indicator_for(source, series_id)
    rows = connection.execute(
        """
        SELECT source, series_id, observation_date, value, vintage
        FROM raw_observations
        WHERE source = ? AND series_id = ?
        """,
        (source, series_id),
    ).fetchall()
    selected: dict[date, tuple[tuple[str, str, str], RawTreasuryObservation]] = {}
    for row in rows:
        observation = RawTreasuryObservation(*row)
        validate_raw_treasury_observation(observation)
        rank = _fred_vintage_rank(observation.vintage)
        current = selected.get(observation.observation_date)
        if current is None or rank > current[0]:
            selected[observation.observation_date] = (rank, observation)
    return [selected[observation_date][1] for observation_date in sorted(selected)]


def validate_raw_treasury_observation(observation: RawTreasuryObservation) -> None:
    """Validate source, lineage, date, and numeric contract without changing raw data."""
    approved_indicator_for(observation.source, observation.series_id)
    if not isinstance(observation.observation_date, date):
        raise ProcessingValidationError("Raw Treasury observation date must be a date")
    _fred_vintage_rank(observation.vintage)
    if observation.value is not None:
        if isinstance(observation.value, bool) or not isinstance(observation.value, (int, float)):
            raise ProcessingValidationError("Raw Treasury value must be numeric or null")
        if not math.isfinite(float(observation.value)):
            raise ProcessingValidationError("Raw Treasury value must be finite")


def process_approved_fred_treasuries(
    connection: duckdb.DuckDBPyConnection, *, logger: logging.Logger | None = None
) -> TreasuryProcessingResult:
    """Normalize the latest selected raw vintage for each approved Treasury series."""
    initialize_phase_0_schema(connection)
    inserted = 0
    skipped_missing = 0
    for series_id in sorted(APPROVED_FRED_TREASURY_MAPPING):
        result = process_fred_treasury_series(connection, "fred", series_id)
        inserted += result.inserted
        skipped_missing += result.skipped_missing
    if logger is not None:
        logger.info(
            "Treasury processing inserted %s processed observations and skipped %s missing values",
            inserted,
            skipped_missing,
        )
    return TreasuryProcessingResult(inserted=inserted, skipped_missing=skipped_missing)


def process_fred_treasury_series(
    connection: duckdb.DuckDBPyConnection, source: str, series_id: str
) -> TreasuryProcessingResult:
    """Normalize one approved source series without retrieving or mutating raw data."""
    indicator_id = approved_indicator_for(source, series_id)
    selected = select_latest_raw_vintages(connection, source, series_id)
    records = []
    skipped_missing = 0
    for raw in selected:
        if raw.value is None:
            skipped_missing += 1
            continue
        input_identity = RawInputIdentity(
            input_role="source",
            raw_source=raw.source,
            raw_series_id=raw.series_id,
            raw_observation_date=raw.observation_date,
            raw_vintage=raw.vintage,
        )
        records.append(
            (
                processed_observation_id(
                    indicator_id,
                    raw.observation_date,
                    DIRECT_TREASURY_PROCESSING_VERSION,
                    [input_identity],
                ),
                indicator_id,
                raw.observation_date,
                float(raw.value),
                input_identity,
            )
        )
    inserted = _persist_processed_records(connection, records)
    return TreasuryProcessingResult(inserted=inserted, skipped_missing=skipped_missing)


def _persist_processed_records(
    connection: duckdb.DuckDBPyConnection,
    records: Iterable[tuple[str, str, date, float, RawInputIdentity]],
) -> int:
    """Persist complete parent-and-lineage pairs in a single transaction."""
    rows = list(records)
    if not rows:
        return 0
    transaction_started = False
    try:
        connection.execute("BEGIN TRANSACTION")
        transaction_started = True
        inserted = 0
        for identifier, indicator_id, observation_date, value, input_identity in rows:
            existing = connection.execute(
                "SELECT 1 FROM processed_observations WHERE processed_observation_id = ?",
                (identifier,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO processed_observations (
                    processed_observation_id, indicator_id, date, value,
                    processing_version, transformation, created_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    identifier,
                    indicator_id,
                    observation_date,
                    value,
                    DIRECT_TREASURY_PROCESSING_VERSION,
                    DIRECT_TREASURY_TRANSFORMATION,
                    datetime.now(timezone.utc),
                ),
            )
            connection.execute(
                """
                INSERT INTO processed_observation_inputs (
                    processed_observation_id, input_role, raw_source, raw_series_id,
                    raw_observation_date, raw_vintage
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    identifier,
                    input_identity.input_role,
                    input_identity.raw_source,
                    input_identity.raw_series_id,
                    input_identity.raw_observation_date,
                    input_identity.raw_vintage,
                ),
            )
            if existing is None:
                inserted += 1
        connection.execute("COMMIT")
        return inserted
    except duckdb.Error as error:
        if transaction_started:
            connection.execute("ROLLBACK")
        raise ProcessingPersistenceError(
            "Could not persist complete processed Treasury observation lineage"
        ) from error


def _fred_vintage_rank(vintage: str) -> tuple[str, str, str]:
    """Validate and rank the Phase 1.2 FRED date-level vintage key."""
    if not isinstance(vintage, str) or not vintage.startswith(FRED_VINTAGE_PREFIX):
        raise ProcessingValidationError("Raw Treasury vintage is missing or not a FRED real-time key")
    parts = vintage.split(":")
    if len(parts) != 3 or not parts[1] or not parts[2]:
        raise ProcessingValidationError("Raw Treasury vintage is malformed")
    try:
        realtime_start = date.fromisoformat(parts[1])
        realtime_end = date.fromisoformat(parts[2])
    except ValueError as error:
        raise ProcessingValidationError("Raw Treasury vintage contains invalid dates") from error
    if realtime_start > realtime_end:
        raise ProcessingValidationError("Raw Treasury vintage end precedes its start")
    return (parts[1], parts[2], vintage)
