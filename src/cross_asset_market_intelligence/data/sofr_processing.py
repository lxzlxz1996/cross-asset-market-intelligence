"""Validated, percent-preserving normalization of official FRBNY SOFR raw data."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import ProcessingValidationError
from ..lineage import RawInputIdentity, processed_observation_id
from .frbny_sofr import FRBNY_SOFR_SERIES_ID, FRBNY_SOURCE, FRBNY_SOFR_VINTAGE_PREFIX
from .processed_persistence import ProcessedRawRecord, persist_processed_raw_records

APPROVED_SOFR_MAPPING = {(FRBNY_SOURCE, FRBNY_SOFR_SERIES_ID): "sofr"}
SOFR_PROCESSING_VERSION = "frbny_sofr_direct_percent_identity_v1"
SOFR_TRANSFORMATION = "validated_identity_percent_per_annum"
SOFR_ORIGINAL_REVISION_STATE = "original"
SOFR_REVISED_REVISION_STATE = "r"


@dataclass(frozen=True)
class RawSofrObservation:
    """One stored FRBNY SOFR raw row available for local normalization."""

    source: str
    series_id: str
    observation_date: date
    value: float | None
    vintage: str


@dataclass(frozen=True)
class SofrProcessingResult:
    """Counts returned by a SOFR normalization run."""

    inserted: int
    skipped_missing: int


def approved_sofr_indicator_for(source: str, series_id: str) -> str:
    """Return the sole approved Phase 1.6B source-to-indicator mapping."""
    if source != FRBNY_SOURCE:
        raise ProcessingValidationError(f"Unsupported source for SOFR processing: {source}")
    if series_id != FRBNY_SOFR_SERIES_ID:
        raise ProcessingValidationError(f"Unsupported FRBNY series for SOFR processing: {series_id}")
    return APPROVED_SOFR_MAPPING[(source, series_id)]


def select_current_sofr_raw_observations(
    connection: duckdb.DuckDBPyConnection,
) -> list[RawSofrObservation]:
    """Prefer a recognized revised FRBNY state over original for each date."""
    rows = connection.execute(
        """
        SELECT source, series_id, observation_date, value, vintage
        FROM raw_observations
        WHERE source = ? AND series_id = ?
        """,
        (FRBNY_SOURCE, FRBNY_SOFR_SERIES_ID),
    ).fetchall()
    selected: dict[date, dict[str, RawSofrObservation]] = {}
    for row in rows:
        observation = RawSofrObservation(*row)
        validate_raw_sofr_observation(observation)
        revision_state = sofr_revision_state(observation.vintage)
        states_for_date = selected.setdefault(observation.observation_date, {})
        states_for_date[revision_state] = observation

    return [
        states[SOFR_REVISED_REVISION_STATE]
        if SOFR_REVISED_REVISION_STATE in states
        else states[SOFR_ORIGINAL_REVISION_STATE]
        for _, states in sorted(selected.items())
    ]


def sofr_revision_state(vintage: str) -> str:
    """Validate the exact Phase 1.6A original/revised raw-vintage contract."""
    if not isinstance(vintage, str) or not vintage.startswith(FRBNY_SOFR_VINTAGE_PREFIX):
        raise ProcessingValidationError("Raw SOFR vintage is missing or not an FRBNY revision key")
    state = vintage.removeprefix(FRBNY_SOFR_VINTAGE_PREFIX)
    if state not in {SOFR_ORIGINAL_REVISION_STATE, SOFR_REVISED_REVISION_STATE}:
        raise ProcessingValidationError(f"Unsupported FRBNY SOFR revision state: {state}")
    return state


def validate_raw_sofr_observation(observation: RawSofrObservation) -> None:
    """Validate the stored raw contract without mutating data or filling gaps."""
    approved_sofr_indicator_for(observation.source, observation.series_id)
    if not isinstance(observation.observation_date, date):
        raise ProcessingValidationError("Raw SOFR observation date must be a date")
    sofr_revision_state(observation.vintage)
    if observation.value is not None:
        if isinstance(observation.value, bool) or not isinstance(observation.value, (int, float)):
            raise ProcessingValidationError("Raw SOFR value must be numeric or null")
        if not math.isfinite(float(observation.value)):
            raise ProcessingValidationError("Raw SOFR value must be finite")


def process_sofr(
    connection: duckdb.DuckDBPyConnection,
    *,
    logger: logging.Logger | None = None,
) -> SofrProcessingResult:
    """Normalize local selected FRBNY SOFR raw observations, without retrieval."""
    initialize_phase_0_schema(connection)
    indicator_id = approved_sofr_indicator_for(FRBNY_SOURCE, FRBNY_SOFR_SERIES_ID)
    records: list[ProcessedRawRecord] = []
    skipped_missing = 0
    for raw in select_current_sofr_raw_observations(connection):
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
                    SOFR_PROCESSING_VERSION,
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
        processing_version=SOFR_PROCESSING_VERSION,
        transformation=SOFR_TRANSFORMATION,
        subject="SOFR",
    )
    if logger is not None:
        logger.info("SOFR processing inserted %s observations and skipped %s missing values", inserted, skipped_missing)
    return SofrProcessingResult(inserted=inserted, skipped_missing=skipped_missing)
