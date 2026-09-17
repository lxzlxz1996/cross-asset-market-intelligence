"""Direct, versioned normalization of approved FRED Treasury raw observations."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import ProcessingValidationError
from ..lineage import RawInputIdentity, processed_observation_id
from .fred_vintages import FRED_VINTAGE_PREFIX, fred_vintage_rank
from .processed_persistence import ProcessedRawRecord, persist_processed_raw_records

APPROVED_FRED_TREASURY_MAPPING = {
    "DGS2": "us_treasury_2y_yield",
    "DGS10": "us_treasury_10y_yield",
}
DIRECT_TREASURY_PROCESSING_VERSION = "fred_treasury_direct_percent_identity_v1"
DIRECT_TREASURY_TRANSFORMATION = "validated_identity_percent_per_annum"


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
        rank = fred_vintage_rank(observation.vintage)
        current = selected.get(observation.observation_date)
        if current is None or rank > current[0]:
            selected[observation.observation_date] = (rank, observation)
    return [selected[observation_date][1] for observation_date in sorted(selected)]


def validate_raw_treasury_observation(observation: RawTreasuryObservation) -> None:
    """Validate source, lineage, date, and numeric contract without changing raw data."""
    approved_indicator_for(observation.source, observation.series_id)
    if not isinstance(observation.observation_date, date):
        raise ProcessingValidationError("Raw Treasury observation date must be a date")
    fred_vintage_rank(observation.vintage)
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
    records: list[ProcessedRawRecord] = []
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
            ProcessedRawRecord(
                processed_observation_id=processed_observation_id(
                    indicator_id,
                    raw.observation_date,
                    DIRECT_TREASURY_PROCESSING_VERSION,
                    [input_identity],
                ),
                indicator_id=indicator_id,
                observation_date=raw.observation_date,
                value=float(raw.value),
                input_identity=input_identity,
            )
        )
    inserted = persist_processed_raw_records(
        connection,
        records,
        processing_version=DIRECT_TREASURY_PROCESSING_VERSION,
        transformation=DIRECT_TREASURY_TRANSFORMATION,
        subject="Treasury",
    )
    return TreasuryProcessingResult(inserted=inserted, skipped_missing=skipped_missing)
