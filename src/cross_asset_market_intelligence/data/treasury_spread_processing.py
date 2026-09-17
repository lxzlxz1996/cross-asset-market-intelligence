"""Same-date derived processing for the validated Treasury 10Y minus 2Y spread."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import ProcessingPersistenceError, ProcessingValidationError
from ..lineage import ProcessedDependencyIdentity, derived_processed_observation_id
from .treasury_processing import (
    DIRECT_TREASURY_PROCESSING_VERSION,
    RawTreasuryObservation,
    select_latest_raw_vintages,
)

TREASURY_SPREAD_INDICATOR = "us_treasury_10y_minus_2y"
TREASURY_SPREAD_PROCESSING_VERSION = "treasury_10y_minus_2y_percentage_points_v1"
TREASURY_SPREAD_TRANSFORMATION = "same_date_validated_10y_minus_2y_percentage_points"
UPSTREAM_TREASURY_SERIES = {
    "us_treasury_10y_yield": "DGS10",
    "us_treasury_2y_yield": "DGS2",
}


@dataclass(frozen=True)
class DirectProcessedTreasuryObservation:
    """An approved direct Treasury output selected through exact raw lineage."""

    processed_observation_id: str
    indicator_id: str
    observation_date: date
    value: float | None


@dataclass(frozen=True)
class TreasurySpreadProcessingResult:
    """Counts returned by one Treasury-spread processing run."""

    inserted: int
    skipped_missing_input: int


def select_current_direct_treasury_observations(
    connection: duckdb.DuckDBPyConnection, indicator_id: str
) -> list[DirectProcessedTreasuryObservation]:
    """Select approved direct outputs whose raw input is the current FRED vintage.

    For each date, Phase 1.3B chooses the greatest valid FRED real-time vintage.
    This function chooses only the direct processed output with a `source` lineage
    row matching that exact raw primary key and the approved direct methodology.
    """
    try:
        series_id = UPSTREAM_TREASURY_SERIES[indicator_id]
    except KeyError as error:
        raise ProcessingValidationError(f"Unsupported Treasury upstream indicator: {indicator_id}") from error

    selected: list[DirectProcessedTreasuryObservation] = []
    for raw in select_latest_raw_vintages(connection, "fred", series_id):
        if raw.value is None:
            continue
        matches = _processed_matches_for_raw(connection, indicator_id, raw)
        if len(matches) > 1:
            raise ProcessingValidationError(
                f"Multiple approved direct processed observations match {indicator_id} on {raw.observation_date}"
            )
        if matches:
            observation = matches[0]
            _validate_direct_processed_value(observation)
            selected.append(observation)
    return selected


def pair_same_date_treasury_inputs(
    ten_year: Iterable[DirectProcessedTreasuryObservation],
    two_year: Iterable[DirectProcessedTreasuryObservation],
) -> list[tuple[DirectProcessedTreasuryObservation, DirectProcessedTreasuryObservation]]:
    """Pair exactly same-date selected inputs; no filling or date substitution occurs."""
    two_year_by_date = {observation.observation_date: observation for observation in two_year}
    return [
        (ten_year_observation, two_year_by_date[ten_year_observation.observation_date])
        for ten_year_observation in ten_year
        if ten_year_observation.observation_date in two_year_by_date
    ]


def calculate_treasury_10y_minus_2y(ten_year: float, two_year: float) -> float:
    """Calculate 10Y minus 2Y in percentage points without unit conversion."""
    for name, value in (("ten_year", ten_year), ("two_year", two_year)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ProcessingValidationError(f"{name} processed Treasury value must be finite numeric data")
    spread = float(ten_year) - float(two_year)
    if not math.isfinite(spread):
        raise ProcessingValidationError("Treasury spread result must be finite")
    return spread


def process_treasury_spread(
    connection: duckdb.DuckDBPyConnection, *, logger: logging.Logger | None = None
) -> TreasurySpreadProcessingResult:
    """Create immutable same-date spread outputs from selected processed inputs only."""
    initialize_phase_0_schema(connection)
    ten_year = select_current_direct_treasury_observations(connection, "us_treasury_10y_yield")
    two_year = select_current_direct_treasury_observations(connection, "us_treasury_2y_yield")
    pairs = pair_same_date_treasury_inputs(ten_year, two_year)
    matched_dates = {ten.observation_date for ten, _ in pairs}
    skipped_missing_input = len({item.observation_date for item in ten_year + two_year} - matched_dates)
    records = [_build_spread_record(ten, two) for ten, two in pairs]
    inserted = _persist_spread_records(connection, records)
    if logger is not None:
        logger.info(
            "Treasury spread processing inserted %s observations and skipped %s dates missing an input",
            inserted,
            skipped_missing_input,
        )
    return TreasurySpreadProcessingResult(inserted, skipped_missing_input)


def _processed_matches_for_raw(
    connection: duckdb.DuckDBPyConnection,
    indicator_id: str,
    raw: RawTreasuryObservation,
) -> list[DirectProcessedTreasuryObservation]:
    rows = connection.execute(
        """
        SELECT processed.processed_observation_id, processed.indicator_id,
               processed.date, processed.value
        FROM processed_observations AS processed
        JOIN processed_observation_inputs AS input
            ON processed.processed_observation_id = input.processed_observation_id
        WHERE processed.indicator_id = ?
          AND processed.processing_version = ?
          AND processed.date = ?
          AND input.input_role = 'source'
          AND input.raw_source = 'fred'
          AND input.raw_series_id = ?
          AND input.raw_observation_date = ?
          AND input.raw_vintage = ?
        """,
        (
            indicator_id,
            DIRECT_TREASURY_PROCESSING_VERSION,
            raw.observation_date,
            raw.series_id,
            raw.observation_date,
            raw.vintage,
        ),
    ).fetchall()
    return [DirectProcessedTreasuryObservation(*row) for row in rows]


def _validate_direct_processed_value(observation: DirectProcessedTreasuryObservation) -> None:
    if observation.value is None:
        raise ProcessingValidationError(
            f"Selected direct processed value is missing for {observation.indicator_id} on {observation.observation_date}"
        )
    calculate_treasury_10y_minus_2y(observation.value, 0.0)


def _build_spread_record(
    ten_year: DirectProcessedTreasuryObservation,
    two_year: DirectProcessedTreasuryObservation,
) -> tuple[str, date, float, list[ProcessedDependencyIdentity]]:
    if ten_year.observation_date != two_year.observation_date:
        raise ProcessingValidationError("Treasury spread inputs must have the same observation date")
    value = calculate_treasury_10y_minus_2y(ten_year.value, two_year.value)
    dependencies = [
        ProcessedDependencyIdentity("ten_year", ten_year.processed_observation_id),
        ProcessedDependencyIdentity("two_year", two_year.processed_observation_id),
    ]
    identifier = derived_processed_observation_id(
        TREASURY_SPREAD_INDICATOR,
        ten_year.observation_date,
        TREASURY_SPREAD_PROCESSING_VERSION,
        dependencies,
    )
    return identifier, ten_year.observation_date, value, dependencies


def _persist_spread_records(
    connection: duckdb.DuckDBPyConnection,
    records: Iterable[tuple[str, date, float, list[ProcessedDependencyIdentity]]],
) -> int:
    """Persist each derived output and both processed dependencies atomically."""
    rows = list(records)
    if not rows:
        return 0
    transaction_started = False
    try:
        connection.execute("BEGIN TRANSACTION")
        transaction_started = True
        inserted = 0
        for identifier, observation_date, value, dependencies in rows:
            existing = connection.execute(
                "SELECT 1 FROM processed_observations WHERE processed_observation_id = ?", (identifier,)
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
                    TREASURY_SPREAD_INDICATOR,
                    observation_date,
                    value,
                    TREASURY_SPREAD_PROCESSING_VERSION,
                    TREASURY_SPREAD_TRANSFORMATION,
                    datetime.now(timezone.utc),
                ),
            )
            for dependency in dependencies:
                connection.execute(
                    """
                    INSERT INTO processed_observation_dependencies (
                        output_processed_observation_id, input_processed_observation_id, input_role
                    ) VALUES (?, ?, ?)
                    ON CONFLICT DO NOTHING
                    """,
                    (identifier, dependency.input_processed_observation_id, dependency.input_role),
                )
            if existing is None:
                inserted += 1
        connection.execute("COMMIT")
        return inserted
    except duckdb.Error as error:
        if transaction_started:
            connection.execute("ROLLBACK")
        raise ProcessingPersistenceError("Could not persist complete Treasury spread lineage") from error
