"""Read-only operational health projection for all Phase 1 target indicators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import duckdb

from ..data.refresh_orchestration import RefreshRun
from ..exceptions import DashboardLineageError, DashboardReadError
from .credit_read_model import current_credit_dashboard
from .sofr_read_model import current_sofr_observation
from .treasury_read_model import current_treasury_dashboard


AvailabilityState = Literal["available", "unavailable", "source_pending"]


@dataclass(frozen=True)
class DataHealthRecord:
    """One operational status record; it contains no financial interpretation."""

    indicator_id: str
    display_name: str
    pipeline_name: str | None
    source_identity: str
    availability: AvailabilityState
    latest_observation_date: date | None
    latest_observation_value: float | None
    latest_refresh_status: str | None
    latest_refresh_attempt_timestamp: datetime | None
    latest_successful_refresh_timestamp: datetime | None
    latest_refresh_stage: str | None
    latest_refresh_error_type: str | None
    latest_refresh_error_message: str | None


_IMPLEMENTED = (
    ("us_treasury_2y_yield", "2-Year Treasury Yield", "treasury", "FRED / Treasury"),
    ("us_treasury_10y_yield", "10-Year Treasury Yield", "treasury", "FRED / Treasury"),
    ("us_treasury_10y_minus_2y", "10Y minus 2Y Yield Curve", "treasury", "Derived / Treasury"),
    ("sofr", "SOFR", "sofr", "FRBNY / SOFR"),
    ("us_investment_grade_oas", "Investment Grade OAS", "credit", "FRED / Credit"),
    ("us_high_yield_oas", "High Yield OAS", "credit", "FRED / Credit"),
)

_DEFERRED = (
    ("spx", "S&P 500", "S&P Dow Jones Indices / FRED distribution"),
    ("vix", "VIX", "Cboe"),
    ("move_index", "MOVE Index", "ICE Data Indices"),
)


def current_data_health(connection: duckdb.DuckDBPyConnection) -> tuple[DataHealthRecord, ...]:
    """Project selected data and separate operational attempts without mutation."""
    latest_runs = _latest_runs_by_pipeline(connection)
    latest_successes = _latest_successes_by_pipeline(connection)
    observations = _implemented_observations(connection)
    records: list[DataHealthRecord] = []
    for indicator_id, display_name, pipeline_name, source_identity in _IMPLEMENTED:
        observation = observations[indicator_id]
        run = latest_runs.get(pipeline_name)
        success = latest_successes.get(pipeline_name)
        records.append(
            DataHealthRecord(
                indicator_id=indicator_id,
                display_name=display_name,
                pipeline_name=pipeline_name,
                source_identity=source_identity,
                availability="available" if observation is not None else "unavailable",
                latest_observation_date=None if observation is None else observation.observation_date,
                latest_observation_value=None if observation is None else observation.value,
                latest_refresh_status=None if run is None else run.status,
                latest_refresh_attempt_timestamp=None if run is None else run.started_timestamp,
                latest_successful_refresh_timestamp=None
                if success is None
                else success.completed_timestamp,
                latest_refresh_stage=None if run is None else run.stage,
                latest_refresh_error_type=None if run is None else run.error_type,
                latest_refresh_error_message=None if run is None else run.error_message,
            )
        )
    records.extend(
        DataHealthRecord(
            indicator_id=indicator_id,
            display_name=display_name,
            pipeline_name=None,
            source_identity=source_identity,
            availability="source_pending",
            latest_observation_date=None,
            latest_observation_value=None,
            latest_refresh_status=None,
            latest_refresh_attempt_timestamp=None,
            latest_successful_refresh_timestamp=None,
            latest_refresh_stage=None,
            latest_refresh_error_type=None,
            latest_refresh_error_message=None,
        )
        for indicator_id, display_name, source_identity in _DEFERRED
    )
    return tuple(records)


def data_health_rows(records: tuple[DataHealthRecord, ...]) -> list[dict[str, object]]:
    """Shape compact display rows without changing health or market data."""
    return [
        {
            "Indicator": record.display_name,
            "Availability": record.availability,
            "Latest data date": None
            if record.latest_observation_date is None
            else record.latest_observation_date.isoformat(),
            "Last refresh": record.latest_refresh_status or "not_attempted",
            "Pipeline": record.pipeline_name or "source_pending",
        }
        for record in records
    ]


def failed_refresh_rows(records: tuple[DataHealthRecord, ...]) -> list[dict[str, object]]:
    """Expose concise failed-run diagnostics, intentionally excluding stack traces."""
    return [
        {
            "Indicator": record.display_name,
            "Pipeline": record.pipeline_name,
            "Attempted": None
            if record.latest_refresh_attempt_timestamp is None
            else record.latest_refresh_attempt_timestamp.isoformat(),
            "Stage": record.latest_refresh_stage,
            "Error type": record.latest_refresh_error_type,
            "Error": record.latest_refresh_error_message,
        }
        for record in records
        if record.latest_refresh_status == "failed"
    ]


def _implemented_observations(connection: duckdb.DuckDBPyConnection) -> dict[str, object | None]:
    """Reuse the approved read models; a projection issue means unavailable, not mutation."""
    try:
        treasury = current_treasury_dashboard(connection)
        sofr = current_sofr_observation(connection)
        credit = current_credit_dashboard(connection)
    except (DashboardLineageError, DashboardReadError, duckdb.Error):
        return {indicator_id: None for indicator_id, *_ in _IMPLEMENTED}
    return {**treasury, "sofr": sofr, **credit}


def _latest_runs_by_pipeline(connection: duckdb.DuckDBPyConnection) -> dict[str, RefreshRun]:
    return _runs_by_pipeline(connection, "status IN ('running', 'succeeded', 'failed', 'skipped')")


def _latest_successes_by_pipeline(connection: duckdb.DuckDBPyConnection) -> dict[str, RefreshRun]:
    return _runs_by_pipeline(connection, "status = 'succeeded'")


def _runs_by_pipeline(
    connection: duckdb.DuckDBPyConnection, status_predicate: str
) -> dict[str, RefreshRun]:
    """Read the latest durable run per pipeline, tolerating pre-1.8B databases."""
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    if "refresh_runs" not in tables:
        return {}
    rows = connection.execute(
        f"""
        SELECT refresh_run_id, pipeline_name, started_timestamp, completed_timestamp,
               status, stage, records_inserted, records_skipped, error_type, error_message
        FROM refresh_runs
        WHERE {status_predicate}
        QUALIFY row_number() OVER (
            PARTITION BY pipeline_name
            ORDER BY started_timestamp DESC, refresh_run_id DESC
        ) = 1
        """
    ).fetchall()
    return {row[1]: RefreshRun(*row) for row in rows}
