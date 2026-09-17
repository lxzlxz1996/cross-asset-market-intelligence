from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.dashboard.credit_read_model import (
    current_credit_dashboard,
    current_credit_observation,
    credit_history,
    inspect_credit_lineage,
)
from cross_asset_market_intelligence.data.credit_oas_processing import (
    CREDIT_OAS_PROCESSING_VERSION,
    process_credit_oas_series,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import DashboardLineageError


IG = "BAMLC0A0CM"
HY = "BAMLH0A0HYM2"
IG_INDICATOR = "us_investment_grade_oas"
HY_INDICATOR = "us_high_yield_oas"


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "credit_read.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _vintage(day: int) -> str:
    return f"fred_realtime:2026-09-{day:02d}:9999-12-31"


def _insert_raw(
    connection: duckdb.DuckDBPyConnection,
    series_id: str,
    observation_date: date,
    value: float,
    vintage: str = "fred_realtime:2026-09-16:9999-12-31",
) -> None:
    connection.execute(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "fred",
            series_id,
            observation_date,
            value,
            datetime(2026, 9, 16, tzinfo=timezone.utc),
            None,
            vintage,
            "{}",
        ),
    )


def _history(connection: duckdb.DuckDBPyConnection, series_id: str, base: float) -> list[date]:
    dates = [date(2026, 7, 1) + timedelta(days=index * 2) for index in range(22)]
    for index, observation_date in enumerate(dates):
        _insert_raw(connection, series_id, observation_date, base + index * 0.01)
    process_credit_oas_series(connection, "fred", series_id)
    return dates


def test_current_credit_projection_exposes_both_approved_indicators_and_percentage_point_changes(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        dates = _history(connection, IG, 0.70)
        _history(connection, HY, 2.60)
        dashboard = current_credit_dashboard(connection)
    finally:
        connection.close()

    ig = dashboard[IG_INDICATOR]
    hy = dashboard[HY_INDICATOR]
    assert ig is not None and hy is not None
    assert (ig.display_name, ig.category, ig.subcategory, ig.unit) == (
        "Investment Grade OAS",
        "Credit",
        "Investment-grade spreads",
        "percentage_points",
    )
    assert (hy.display_name, hy.unit) == ("High Yield OAS", "percentage_points")
    assert ig.observation_date == dates[-1]
    assert ig.processing_version == CREDIT_OAS_PROCESSING_VERSION
    assert ig.change_1d.value == pytest.approx(0.01)
    assert ig.change_5d.value == pytest.approx(0.05)
    assert ig.change_20d.value == pytest.approx(0.20)
    assert ig.change_1d.unit == ig.change_5d.unit == ig.change_20d.unit == "percentage_points"


def test_latest_fred_vintage_backed_output_is_selected_without_exposing_older_revision(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        observation_date = date(2026, 9, 15)
        _insert_raw(connection, IG, observation_date, 0.78, _vintage(16))
        process_credit_oas_series(connection, "fred", IG)
        old_id = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
        _insert_raw(connection, IG, observation_date, 0.80, _vintage(17))
        process_credit_oas_series(connection, "fred", IG)
        history = credit_history(connection, IG_INDICATOR)
        processed_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    assert processed_count == 2
    assert len(history) == 1
    assert history[0].value == 0.80
    assert history[0].processed_observation_id != old_id
    assert history[0].lineage.raw_input.vintage == _vintage(17)


def test_history_is_ascending_uses_observation_count_lags_and_preserves_calendar_gaps(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        dates = _history(connection, HY, 2.50)
        history = credit_history(connection, HY_INDICATOR, start_date=dates[1], end_date=dates[-1])
    finally:
        connection.close()

    assert [item.observation_date for item in history] == dates[1:]
    assert history[-1].change_1d.value == pytest.approx(0.01)
    assert history[-1].change_5d.value == pytest.approx(0.05)
    assert history[-1].change_20d.value == pytest.approx(0.20)


def test_insufficient_history_lineage_and_read_only_behavior_are_explicit(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, IG, date(2026, 9, 14), 0.78)
        _insert_raw(connection, IG, date(2026, 9, 16), 0.80)
        process_credit_oas_series(connection, "fred", IG)
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in (
                "raw_observations",
                "processed_observations",
                "processed_observation_inputs",
                "processed_observation_dependencies",
            )
        }
        current = current_credit_observation(connection, IG_INDICATOR)
        assert current is not None
        lineage = inspect_credit_lineage(connection, current.processed_observation_id)
        credit_history(connection, IG_INDICATOR)
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in before
        }
        _insert_raw(connection, IG, date(2026, 9, 18), 0.81)
        with pytest.raises(DashboardLineageError, match="requires exactly one processed"):
            credit_history(connection, IG_INDICATOR)
        with pytest.raises(ValueError, match="Unsupported Credit"):
            current_credit_observation(connection, "unsupported")
    finally:
        connection.close()

    assert current.change_1d.value == pytest.approx(0.02)
    assert current.change_5d.value is None
    assert current.change_20d.value is None
    assert lineage.raw_input.source == "fred"
    assert lineage.raw_input.series_id == IG
    assert lineage.raw_input.observation_date == date(2026, 9, 16)
    assert after == before
