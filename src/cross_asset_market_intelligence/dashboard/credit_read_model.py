"""Read-only current and historical projections for validated Credit OAS data."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

import duckdb

from ..data.credit_oas_processing import (
    APPROVED_CREDIT_OAS_MAPPING,
    CREDIT_OAS_PROCESSING_VERSION,
    RawCreditOasObservation,
    select_latest_credit_oas_raw_vintages,
)
from ..data.fred_vintages import fred_vintage_rank
from ..exceptions import DashboardLineageError, DashboardReadError, ProcessingValidationError
from .read_model_common import DashboardChange, changes_for_index
from .treasury_read_model import DirectDashboardLineage, RawLineageSummary

APPROVED_CREDIT_INDICATORS = tuple(APPROVED_CREDIT_OAS_MAPPING.values())
_SERIES_BY_INDICATOR = {indicator_id: series_id for series_id, indicator_id in APPROVED_CREDIT_OAS_MAPPING.items()}
_DEFINITIONS = {
    "us_investment_grade_oas": ("Investment Grade OAS", "Credit", "Investment-grade spreads"),
    "us_high_yield_oas": ("High Yield OAS", "Credit", "High-yield spreads"),
}


@dataclass(frozen=True)
class CreditDashboardObservation:
    """One selected immutable Credit OAS record for a read-only projection."""

    indicator_id: Literal["us_investment_grade_oas", "us_high_yield_oas"]
    display_name: str
    category: str
    subcategory: str
    observation_date: date
    value: float
    unit: Literal["percentage_points"]
    processing_version: str
    processed_observation_id: str
    lineage: DirectDashboardLineage
    change_1d: DashboardChange
    change_5d: DashboardChange
    change_20d: DashboardChange


def current_credit_dashboard(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, CreditDashboardObservation | None]:
    """Return one latest selected Credit projection per approved indicator."""
    return {indicator_id: current_credit_observation(connection, indicator_id) for indicator_id in APPROVED_CREDIT_INDICATORS}


def current_credit_observation(
    connection: duckdb.DuckDBPyConnection, indicator_id: str
) -> CreditDashboardObservation | None:
    """Return the latest selected Credit observation for one approved indicator."""
    history = credit_history(connection, indicator_id)
    return history[-1] if history else None


def credit_history(
    connection: duckdb.DuckDBPyConnection,
    indicator_id: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[CreditDashboardObservation, ...]:
    """Return selected current Credit OAS history in ascending date order."""
    _require_approved_indicator(indicator_id)
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must not be later than end_date")
    selected = _current_credit_history(connection, indicator_id)
    observations = [
        _build_dashboard_observation(connection, row, changes_for_index(selected, index))
        for index, row in enumerate(selected)
    ]
    return tuple(
        observation
        for observation in observations
        if (start_date is None or observation.observation_date >= start_date)
        and (end_date is None or observation.observation_date <= end_date)
    )


def inspect_credit_lineage(
    connection: duckdb.DuckDBPyConnection, processed_observation_id: str
) -> DirectDashboardLineage:
    """Return and validate the exact FRED raw input of one Credit OAS output."""
    try:
        row = connection.execute(
            """
            SELECT indicator_id, processing_version
            FROM processed_observations
            WHERE processed_observation_id = ?
            """,
            (processed_observation_id,),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT raw_source, raw_series_id, raw_observation_date, raw_vintage
            FROM processed_observation_inputs
            WHERE processed_observation_id = ? AND input_role = 'source'
            """,
            (processed_observation_id,),
        ).fetchall()
    except duckdb.Error as error:
        raise DashboardReadError("Could not inspect Credit dashboard lineage") from error
    if row is None:
        raise DashboardLineageError("Credit dashboard observation does not exist")
    indicator_id, processing_version = row
    _require_approved_indicator(indicator_id)
    if processing_version != CREDIT_OAS_PROCESSING_VERSION:
        raise DashboardLineageError("Credit dashboard observation uses an unapproved methodology")
    if len(rows) != 1:
        raise DashboardLineageError("Credit dashboard observation requires exactly one source raw input")
    raw = RawLineageSummary(*rows[0])
    if raw.source != "fred" or raw.series_id != _SERIES_BY_INDICATOR[indicator_id]:
        raise DashboardLineageError("Credit dashboard observation has an invalid raw source")
    try:
        fred_vintage_rank(raw.vintage)
    except ProcessingValidationError as error:
        raise DashboardLineageError("Credit dashboard observation has invalid raw lineage") from error
    return DirectDashboardLineage(raw)


def _current_credit_history(
    connection: duckdb.DuckDBPyConnection, indicator_id: str
) -> list[tuple[str, str, date, float, str]]:
    series_id = _SERIES_BY_INDICATOR[indicator_id]
    try:
        selected_raw = select_latest_credit_oas_raw_vintages(connection, "fred", series_id)
    except ProcessingValidationError as error:
        raise DashboardLineageError("Credit selection has invalid raw lineage") from error
    except duckdb.Error as error:
        raise DashboardReadError("Could not select current Credit observations") from error
    selected: list[tuple[str, str, date, float, str]] = []
    for raw in selected_raw:
        if raw.value is None:
            continue
        matches = _processed_matches_for_raw(connection, indicator_id, raw)
        if len(matches) != 1:
            raise DashboardLineageError(
                f"Credit date {raw.observation_date} requires exactly one processed observation for its selected raw vintage"
            )
        identifier, selected_indicator, observation_date, value, version = matches[0]
        selected.append((identifier, selected_indicator, observation_date, _finite_value(value), version))
    return selected


def _processed_matches_for_raw(
    connection: duckdb.DuckDBPyConnection,
    indicator_id: str,
    raw: RawCreditOasObservation,
) -> list[tuple[str, str, date, float | None, str]]:
    try:
        return connection.execute(
            """
            SELECT processed.processed_observation_id, processed.indicator_id, processed.date,
                   processed.value, processed.processing_version
            FROM processed_observations AS processed
            JOIN processed_observation_inputs AS input
                ON processed.processed_observation_id = input.processed_observation_id
            WHERE processed.indicator_id = ?
              AND processed.processing_version = ?
              AND processed.date = ?
              AND input.input_role = 'source'
              AND input.raw_source = ?
              AND input.raw_series_id = ?
              AND input.raw_observation_date = ?
              AND input.raw_vintage = ?
            """,
            (
                indicator_id,
                CREDIT_OAS_PROCESSING_VERSION,
                raw.observation_date,
                raw.source,
                raw.series_id,
                raw.observation_date,
                raw.vintage,
            ),
        ).fetchall()
    except duckdb.Error as error:
        raise DashboardReadError("Could not match processed Credit observations to raw lineage") from error


def _build_dashboard_observation(
    connection: duckdb.DuckDBPyConnection,
    selected: tuple[str, str, date, float, str],
    changes: tuple[DashboardChange, DashboardChange, DashboardChange],
) -> CreditDashboardObservation:
    identifier, indicator_id, observation_date, value, processing_version = selected
    display_name, category, subcategory = _DEFINITIONS[indicator_id]
    return CreditDashboardObservation(
        indicator_id=indicator_id,
        display_name=display_name,
        category=category,
        subcategory=subcategory,
        observation_date=observation_date,
        value=value,
        unit="percentage_points",
        processing_version=processing_version,
        processed_observation_id=identifier,
        lineage=inspect_credit_lineage(connection, identifier),
        change_1d=changes[0],
        change_5d=changes[1],
        change_20d=changes[2],
    )


def _finite_value(value: float | None) -> float:
    if value is None or isinstance(value, bool) or not math.isfinite(float(value)):
        raise DashboardLineageError("Selected Credit observation has no finite numeric value")
    return float(value)


def _require_approved_indicator(indicator_id: str) -> None:
    if indicator_id not in APPROVED_CREDIT_INDICATORS:
        raise ValueError(f"Unsupported Credit dashboard indicator: {indicator_id}")
