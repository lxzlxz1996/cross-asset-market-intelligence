"""Read-only current and historical projections for validated FRBNY SOFR."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

import duckdb

from ..data.frbny_sofr import FRBNY_SOFR_SERIES_ID, FRBNY_SOURCE
from ..data.sofr_processing import (
    SOFR_PROCESSING_VERSION,
    RawSofrObservation,
    select_current_sofr_raw_observations,
    sofr_revision_state,
)
from ..exceptions import DashboardLineageError, DashboardReadError, ProcessingValidationError
from .read_model_common import DashboardChange, changes_for_index
from .treasury_read_model import DirectDashboardLineage, RawLineageSummary

SOFR_INDICATOR = "sofr"
_DEFINITION = ("SOFR", "Liquidity", "Overnight funding", "percent")


@dataclass(frozen=True)
class SofrDashboardObservation:
    """One selected immutable SOFR record for the read-only dashboard."""

    indicator_id: Literal["sofr"]
    display_name: str
    category: str
    subcategory: str
    observation_date: date
    value: float
    unit: Literal["percent"]
    processing_version: str
    processed_observation_id: str
    lineage: DirectDashboardLineage
    change_1d: DashboardChange
    change_5d: DashboardChange
    change_20d: DashboardChange


def current_sofr_observation(
    connection: duckdb.DuckDBPyConnection,
) -> SofrDashboardObservation | None:
    """Return the latest deterministic selected SOFR observation, if present."""
    history = sofr_history(connection)
    return history[-1] if history else None


def sofr_history(
    connection: duckdb.DuckDBPyConnection,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[SofrDashboardObservation, ...]:
    """Return one revision-aware selected SOFR observation per stored date."""
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must not be later than end_date")
    selected = _current_sofr_history(connection)
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


def inspect_sofr_lineage(
    connection: duckdb.DuckDBPyConnection, processed_observation_id: str
) -> DirectDashboardLineage:
    """Return and validate the exact FRBNY raw input of one SOFR output."""
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
        raise DashboardReadError("Could not inspect SOFR dashboard lineage") from error
    if row is None:
        raise DashboardLineageError("SOFR dashboard observation does not exist")
    if row != (SOFR_INDICATOR, SOFR_PROCESSING_VERSION):
        raise DashboardLineageError("SOFR dashboard observation uses an unapproved methodology")
    if len(rows) != 1:
        raise DashboardLineageError("SOFR dashboard observation requires exactly one source raw input")
    raw = RawLineageSummary(*rows[0])
    if raw.source != FRBNY_SOURCE or raw.series_id != FRBNY_SOFR_SERIES_ID:
        raise DashboardLineageError("SOFR dashboard observation has an invalid raw source")
    try:
        sofr_revision_state(raw.vintage)
    except ProcessingValidationError as error:
        raise DashboardLineageError("SOFR dashboard observation has invalid raw lineage") from error
    return DirectDashboardLineage(raw)


def _current_sofr_history(
    connection: duckdb.DuckDBPyConnection,
) -> list[tuple[str, str, date, float, str]]:
    try:
        selected_raw = select_current_sofr_raw_observations(connection)
    except ProcessingValidationError as error:
        raise DashboardLineageError("SOFR selection has invalid raw lineage") from error
    except duckdb.Error as error:
        raise DashboardReadError("Could not select current SOFR observations") from error

    selected: list[tuple[str, str, date, float, str]] = []
    for raw in selected_raw:
        if raw.value is None:
            continue
        matches = _processed_matches_for_raw(connection, raw)
        if len(matches) != 1:
            raise DashboardLineageError(
                f"SOFR date {raw.observation_date} requires exactly one processed observation for its selected raw revision"
            )
        identifier, indicator_id, observation_date, value, version = matches[0]
        selected.append((identifier, indicator_id, observation_date, _finite_value(value), version))
    return selected


def _processed_matches_for_raw(
    connection: duckdb.DuckDBPyConnection, raw: RawSofrObservation
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
                SOFR_INDICATOR,
                SOFR_PROCESSING_VERSION,
                raw.observation_date,
                raw.source,
                raw.series_id,
                raw.observation_date,
                raw.vintage,
            ),
        ).fetchall()
    except duckdb.Error as error:
        raise DashboardReadError("Could not match processed SOFR observations to raw lineage") from error


def _build_dashboard_observation(
    connection: duckdb.DuckDBPyConnection,
    selected: tuple[str, str, date, float, str],
    changes: tuple[DashboardChange, DashboardChange, DashboardChange],
) -> SofrDashboardObservation:
    identifier, indicator_id, observation_date, value, processing_version = selected
    display_name, category, subcategory, unit = _DEFINITION
    return SofrDashboardObservation(
        indicator_id=indicator_id,
        display_name=display_name,
        category=category,
        subcategory=subcategory,
        observation_date=observation_date,
        value=value,
        unit=unit,
        processing_version=processing_version,
        processed_observation_id=identifier,
        lineage=inspect_sofr_lineage(connection, identifier),
        change_1d=changes[0],
        change_5d=changes[1],
        change_20d=changes[2],
    )


def _finite_value(value: float | None) -> float:
    if value is None or isinstance(value, bool) or not math.isfinite(float(value)):
        raise DashboardLineageError("Selected SOFR observation has no finite numeric value")
    return float(value)
