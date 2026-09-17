"""Read-only current and historical projections for approved Treasury indicators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import duckdb

from ..data.treasury_processing import DIRECT_TREASURY_PROCESSING_VERSION
from ..data.treasury_spread_processing import (
    TREASURY_SPREAD_INDICATOR,
    TREASURY_SPREAD_PROCESSING_VERSION,
    select_current_direct_treasury_observations,
)
from ..exceptions import DashboardLineageError, DashboardReadError, ProcessingValidationError
from .read_model_common import DashboardChange, changes_for_index

DIRECT_INDICATORS = ("us_treasury_2y_yield", "us_treasury_10y_yield")
APPROVED_TREASURY_INDICATORS = (*DIRECT_INDICATORS, TREASURY_SPREAD_INDICATOR)


@dataclass(frozen=True)
class RawLineageSummary:
    """The exact raw observation backing a direct dashboard observation."""

    source: str
    series_id: str
    observation_date: date
    vintage: str


@dataclass(frozen=True)
class DirectDashboardLineage:
    """Lineage summary for one direct dashboard observation."""

    raw_input: RawLineageSummary


@dataclass(frozen=True)
class SpreadDashboardLineage:
    """Immediate processed dependencies and transitive raw inputs for the spread."""

    ten_year_processed_observation_id: str
    two_year_processed_observation_id: str
    ten_year_raw_input: RawLineageSummary
    two_year_raw_input: RawLineageSummary


@dataclass(frozen=True)
class TreasuryDashboardObservation:
    """One immutable processed record selected for a read-only dashboard projection."""

    indicator_id: str
    display_name: str
    category: str
    subcategory: str
    observation_date: date
    value: float
    unit: Literal["percent", "percentage_points"]
    processing_version: str
    processed_observation_id: str
    lineage: DirectDashboardLineage | SpreadDashboardLineage
    change_1d: "DashboardChange"
    change_5d: "DashboardChange"
    change_20d: "DashboardChange"


_DEFINITIONS = {
    "us_treasury_2y_yield": ("2-Year Treasury Yield", "Rates", "Treasury yield curve", "percent"),
    "us_treasury_10y_yield": ("10-Year Treasury Yield", "Rates", "Treasury yield curve", "percent"),
    TREASURY_SPREAD_INDICATOR: ("10Y minus 2Y Yield Curve", "Rates", "Yield-curve spread", "percentage_points"),
}


def current_treasury_dashboard(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, TreasuryDashboardObservation | None]:
    """Return one current projection (or explicit unavailability) per approved indicator."""
    return {indicator_id: current_treasury_observation(connection, indicator_id) for indicator_id in APPROVED_TREASURY_INDICATORS}


def current_treasury_observation(
    connection: duckdb.DuckDBPyConnection, indicator_id: str
) -> TreasuryDashboardObservation | None:
    """Return the latest available deterministic dashboard observation for one indicator."""
    history = treasury_history(connection, indicator_id)
    return history[-1] if history else None


def treasury_history(
    connection: duckdb.DuckDBPyConnection,
    indicator_id: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[TreasuryDashboardObservation, ...]:
    """Return one current selected observation per valid date in ascending date order."""
    _require_approved_indicator(indicator_id)
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must not be later than end_date")
    if indicator_id in DIRECT_INDICATORS:
        selected = _current_direct_history(connection, indicator_id)
    else:
        selected = _current_spread_history(connection)
    observations = [
        _build_dashboard_observation(connection, observation, changes_for_index(selected, index))
        for index, observation in enumerate(selected)
    ]
    return tuple(
        observation
        for observation in observations
        if (start_date is None or observation.observation_date >= start_date)
        and (end_date is None or observation.observation_date <= end_date)
    )


def inspect_treasury_lineage(
    connection: duckdb.DuckDBPyConnection, processed_observation_id: str
) -> DirectDashboardLineage | SpreadDashboardLineage:
    """Inspect exact direct or transitive raw lineage for a selected Treasury record."""
    try:
        row = connection.execute(
            """
            SELECT indicator_id, processing_version
            FROM processed_observations
            WHERE processed_observation_id = ?
            """,
            (processed_observation_id,),
        ).fetchone()
    except duckdb.Error as error:
        raise DashboardReadError("Could not inspect Treasury dashboard lineage") from error
    if row is None:
        raise DashboardLineageError("Dashboard observation does not exist")
    indicator_id, processing_version = row
    _require_approved_indicator(indicator_id)
    if indicator_id in DIRECT_INDICATORS:
        if processing_version != DIRECT_TREASURY_PROCESSING_VERSION:
            raise DashboardLineageError("Direct dashboard observation uses an unapproved methodology")
        return DirectDashboardLineage(_direct_raw_lineage(connection, processed_observation_id))
    if processing_version != TREASURY_SPREAD_PROCESSING_VERSION:
        raise DashboardLineageError("Spread dashboard observation uses an unapproved methodology")
    return _spread_lineage(connection, processed_observation_id)


def _current_direct_history(
    connection: duckdb.DuckDBPyConnection, indicator_id: str
) -> list[tuple[str, str, date, float, str]]:
    try:
        direct = select_current_direct_treasury_observations(connection, indicator_id)
    except ProcessingValidationError as error:
        raise DashboardLineageError("Direct Treasury selection has invalid lineage") from error
    except duckdb.Error as error:
        raise DashboardReadError("Could not select current direct Treasury observations") from error
    return [
        (
            observation.processed_observation_id,
            observation.indicator_id,
            observation.observation_date,
            _finite_value(observation.value, observation.indicator_id),
            DIRECT_TREASURY_PROCESSING_VERSION,
        )
        for observation in direct
    ]


def _current_spread_history(
    connection: duckdb.DuckDBPyConnection,
) -> list[tuple[str, str, date, float, str]]:
    ten_year = {row[2]: row for row in _current_direct_history(connection, "us_treasury_10y_yield")}
    two_year = {row[2]: row for row in _current_direct_history(connection, "us_treasury_2y_yield")}
    selected: list[tuple[str, str, date, float, str]] = []
    for observation_date in sorted(set(ten_year) & set(two_year)):
        matches = _spread_matches_for_dependencies(
            connection, observation_date, ten_year[observation_date][0], two_year[observation_date][0]
        )
        if len(matches) > 1:
            raise DashboardLineageError(
                f"Multiple current spread observations match selected upstream inputs on {observation_date}"
            )
        if matches:
            identifier, indicator_id, date_value, value, version = matches[0]
            selected.append((identifier, indicator_id, date_value, _finite_value(value, indicator_id), version))
    return selected


def _spread_matches_for_dependencies(
    connection: duckdb.DuckDBPyConnection,
    observation_date: date,
    ten_year_id: str,
    two_year_id: str,
) -> list[tuple[str, str, date, float | None, str]]:
    try:
        return connection.execute(
            """
            SELECT spread.processed_observation_id, spread.indicator_id, spread.date,
                   spread.value, spread.processing_version
            FROM processed_observations AS spread
            JOIN processed_observation_dependencies AS ten_year
                ON spread.processed_observation_id = ten_year.output_processed_observation_id
                AND ten_year.input_role = 'ten_year'
            JOIN processed_observation_dependencies AS two_year
                ON spread.processed_observation_id = two_year.output_processed_observation_id
                AND two_year.input_role = 'two_year'
            WHERE spread.indicator_id = ?
              AND spread.processing_version = ?
              AND spread.date = ?
              AND ten_year.input_processed_observation_id = ?
              AND two_year.input_processed_observation_id = ?
            """,
            (
                TREASURY_SPREAD_INDICATOR,
                TREASURY_SPREAD_PROCESSING_VERSION,
                observation_date,
                ten_year_id,
                two_year_id,
            ),
        ).fetchall()
    except duckdb.Error as error:
        raise DashboardReadError("Could not select current Treasury spread observations") from error


def _build_dashboard_observation(
    connection: duckdb.DuckDBPyConnection,
    selected: tuple[str, str, date, float, str],
    changes: tuple[DashboardChange, DashboardChange, DashboardChange],
) -> TreasuryDashboardObservation:
    identifier, indicator_id, observation_date, value, processing_version = selected
    display_name, category, subcategory, unit = _DEFINITIONS[indicator_id]
    return TreasuryDashboardObservation(
        indicator_id=indicator_id,
        display_name=display_name,
        category=category,
        subcategory=subcategory,
        observation_date=observation_date,
        value=value,
        unit=unit,
        processing_version=processing_version,
        processed_observation_id=identifier,
        lineage=inspect_treasury_lineage(connection, identifier),
        change_1d=changes[0],
        change_5d=changes[1],
        change_20d=changes[2],
    )


def _direct_raw_lineage(
    connection: duckdb.DuckDBPyConnection, processed_observation_id: str
) -> RawLineageSummary:
    try:
        rows = connection.execute(
            """
            SELECT raw_source, raw_series_id, raw_observation_date, raw_vintage
            FROM processed_observation_inputs
            WHERE processed_observation_id = ? AND input_role = 'source'
            """,
            (processed_observation_id,),
        ).fetchall()
    except duckdb.Error as error:
        raise DashboardReadError("Could not inspect direct Treasury raw lineage") from error
    if len(rows) != 1:
        raise DashboardLineageError("Direct dashboard observation requires exactly one source raw input")
    return RawLineageSummary(*rows[0])


def _spread_lineage(
    connection: duckdb.DuckDBPyConnection, processed_observation_id: str
) -> SpreadDashboardLineage:
    try:
        rows = connection.execute(
            """
            SELECT dependency.input_role, dependency.input_processed_observation_id,
                   upstream.indicator_id
            FROM processed_observation_dependencies AS dependency
            JOIN processed_observations AS upstream
                ON dependency.input_processed_observation_id = upstream.processed_observation_id
            WHERE dependency.output_processed_observation_id = ?
            """,
            (processed_observation_id,),
        ).fetchall()
    except duckdb.Error as error:
        raise DashboardReadError("Could not inspect Treasury spread dependencies") from error
    dependencies = {role: (identifier, indicator_id) for role, identifier, indicator_id in rows}
    expected = {
        "ten_year": "us_treasury_10y_yield",
        "two_year": "us_treasury_2y_yield",
    }
    if set(dependencies) != set(expected) or any(
        dependencies[role][1] != indicator_id for role, indicator_id in expected.items()
    ):
        raise DashboardLineageError("Spread dashboard observation has incomplete or invalid dependencies")
    return SpreadDashboardLineage(
        ten_year_processed_observation_id=dependencies["ten_year"][0],
        two_year_processed_observation_id=dependencies["two_year"][0],
        ten_year_raw_input=_direct_raw_lineage(connection, dependencies["ten_year"][0]),
        two_year_raw_input=_direct_raw_lineage(connection, dependencies["two_year"][0]),
    )


def _finite_value(value: float | None, indicator_id: str) -> float:
    if value is None or isinstance(value, bool):
        raise DashboardLineageError(f"Selected {indicator_id} observation has no numeric value")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise DashboardLineageError(f"Selected {indicator_id} observation has a non-finite value")
    return result


def _require_approved_indicator(indicator_id: str) -> None:
    if indicator_id not in APPROVED_TREASURY_INDICATORS:
        raise ValueError(f"Unsupported Treasury dashboard indicator: {indicator_id}")
