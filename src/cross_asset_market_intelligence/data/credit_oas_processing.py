"""Validated direct normalization of approved FRED Credit OAS raw observations."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import ProcessingValidationError
from ..lineage import RawInputIdentity, processed_observation_id
from .fred_vintages import fred_vintage_rank
from .processed_persistence import ProcessedRawRecord, persist_processed_raw_records

APPROVED_CREDIT_OAS_MAPPING = {
    "BAMLC0A0CM": "us_investment_grade_oas",
    "BAMLH0A0HYM2": "us_high_yield_oas",
}
CREDIT_OAS_PROCESSING_VERSION = "fred_credit_oas_direct_percentage_points_identity_v1"
CREDIT_OAS_TRANSFORMATION = "validated_identity_percentage_points"


@dataclass(frozen=True)
class RawCreditOasObservation:
    """A raw Credit OAS row selected for direct normalization."""

    source: str
    series_id: str
    observation_date: date
    value: float | None
    vintage: str


@dataclass(frozen=True)
class CreditOasProcessingResult:
    """Counts returned by one Credit OAS direct-normalization run."""

    inserted: int
    skipped_missing: int


def approved_credit_oas_indicator_for(source: str, series_id: str) -> str:
    """Return an explicitly approved Credit OAS source-to-indicator mapping."""
    if source != "fred":
        raise ProcessingValidationError(f"Unsupported source for Credit OAS processing: {source}")
    try:
        return APPROVED_CREDIT_OAS_MAPPING[series_id]
    except KeyError as error:
        raise ProcessingValidationError(f"Unsupported FRED Credit OAS series: {series_id}") from error


def select_latest_credit_oas_raw_vintages(
    connection: duckdb.DuckDBPyConnection, source: str, series_id: str
) -> list[RawCreditOasObservation]:
    """Select the greatest valid FRED realtime vintage per Credit OAS date."""
    approved_credit_oas_indicator_for(source, series_id)
    rows = connection.execute(
        """
        SELECT source, series_id, observation_date, value, vintage
        FROM raw_observations
        WHERE source = ? AND series_id = ?
        """,
        (source, series_id),
    ).fetchall()
    selected: dict[date, tuple[tuple[str, str, str], RawCreditOasObservation]] = {}
    for row in rows:
        observation = RawCreditOasObservation(*row)
        validate_raw_credit_oas_observation(observation)
        rank = fred_vintage_rank(observation.vintage)
        current = selected.get(observation.observation_date)
        if current is None or rank > current[0]:
            selected[observation.observation_date] = (rank, observation)
    return [selected[observation_date][1] for observation_date in sorted(selected)]


def validate_raw_credit_oas_observation(observation: RawCreditOasObservation) -> None:
    """Validate source, exact FRED vintage, and numeric raw contract without mutation."""
    approved_credit_oas_indicator_for(observation.source, observation.series_id)
    if not isinstance(observation.observation_date, date):
        raise ProcessingValidationError("Raw Credit OAS observation date must be a date")
    fred_vintage_rank(observation.vintage)
    if observation.value is not None:
        if isinstance(observation.value, bool) or not isinstance(observation.value, (int, float)):
            raise ProcessingValidationError("Raw Credit OAS value must be numeric or null")
        if not math.isfinite(float(observation.value)):
            raise ProcessingValidationError("Raw Credit OAS value must be finite")


def process_credit_oas(
    connection: duckdb.DuckDBPyConnection, *, logger: logging.Logger | None = None
) -> CreditOasProcessingResult:
    """Normalize both approved Credit OAS series from local raw data only."""
    initialize_phase_0_schema(connection)
    inserted = 0
    skipped_missing = 0
    for series_id in sorted(APPROVED_CREDIT_OAS_MAPPING):
        result = process_credit_oas_series(connection, "fred", series_id, logger=logger)
        inserted += result.inserted
        skipped_missing += result.skipped_missing
    return CreditOasProcessingResult(inserted=inserted, skipped_missing=skipped_missing)


def process_credit_oas_series(
    connection: duckdb.DuckDBPyConnection,
    source: str,
    series_id: str,
    *,
    logger: logging.Logger | None = None,
) -> CreditOasProcessingResult:
    """Normalize one approved Credit OAS series without retrieval or raw mutation."""
    indicator_id = approved_credit_oas_indicator_for(source, series_id)
    records: list[ProcessedRawRecord] = []
    skipped_missing = 0
    for raw in select_latest_credit_oas_raw_vintages(connection, source, series_id):
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
                    CREDIT_OAS_PROCESSING_VERSION,
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
        processing_version=CREDIT_OAS_PROCESSING_VERSION,
        transformation=CREDIT_OAS_TRANSFORMATION,
        subject="Credit OAS",
    )
    result = CreditOasProcessingResult(inserted=inserted, skipped_missing=skipped_missing)
    if logger is not None:
        logger.info(
            "Credit OAS processing for %s inserted %s observations and skipped %s missing values",
            series_id,
            result.inserted,
            result.skipped_missing,
        )
    return result
