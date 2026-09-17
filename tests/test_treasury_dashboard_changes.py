from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.dashboard.treasury_read_model import (
    current_treasury_observation,
    treasury_history,
)
from cross_asset_market_intelligence.data.treasury_processing import process_fred_treasury_series
from cross_asset_market_intelligence.data.treasury_spread_processing import (
    TREASURY_SPREAD_INDICATOR,
    process_treasury_spread,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "changes.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _insert_history(connection: duckdb.DuckDBPyConnection, dates: list[date]) -> None:
    for index, observation_date in enumerate(dates):
        vintage = f"fred_realtime:2026-09-{index + 1:02d}:9999-12-31"
        connection.execute(
            "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fred", "DGS10", observation_date, 4.00 + index * 0.10,
                datetime(2026, 9, 30, tzinfo=timezone.utc), None, vintage, "{}",
            ),
        )
        connection.execute(
            "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fred", "DGS2", observation_date, 3.00 + index * 0.05,
                datetime(2026, 9, 30, tzinfo=timezone.utc), None, vintage, "{}",
            ),
        )
    process_fred_treasury_series(connection, "fred", "DGS10")
    process_fred_treasury_series(connection, "fred", "DGS2")
    process_treasury_spread(connection)


def test_changes_use_valid_observation_count_not_calendar_days_and_keep_percentage_point_units(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        dates = [date(2026, 9, 1), date(2026, 9, 4), date(2026, 9, 9), date(2026, 9, 15), date(2026, 9, 22), date(2026, 9, 30)]
        _insert_history(connection, dates)
        two_year = current_treasury_observation(connection, "us_treasury_2y_yield")
        spread = current_treasury_observation(connection, TREASURY_SPREAD_INDICATOR)
    finally:
        connection.close()

    assert two_year.change_1d.value == pytest.approx(0.05)
    assert two_year.change_5d.value == pytest.approx(0.25)
    assert two_year.change_20d.value is None
    assert two_year.change_1d.unit == "percentage_points"
    assert spread.change_1d.value == pytest.approx(0.05)
    assert spread.change_5d.value == pytest.approx(0.25)
    assert spread.change_1d.value != pytest.approx(5.0)


def test_twenty_day_lag_requires_twenty_prior_valid_selected_observations(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        dates = [date(2026, 1, 1) + timedelta(days=index * 2) for index in range(21)]
        _insert_history(connection, dates)
        history = treasury_history(connection, "us_treasury_10y_yield")
        current = history[-1]
    finally:
        connection.close()

    assert len(history) == 21
    assert current.change_1d.value == pytest.approx(0.10)
    assert current.change_5d.value == pytest.approx(0.50)
    assert current.change_20d.value == pytest.approx(2.00)


def test_revision_does_not_add_a_lag_observation_and_reads_do_not_mutate_tables(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        dates = [date(2026, 9, 1) + timedelta(days=index * 3) for index in range(6)]
        _insert_history(connection, dates)
        latest_date = dates[-1]
        connection.execute(
            "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fred", "DGS10", latest_date, 5.00,
                datetime(2026, 10, 1, tzinfo=timezone.utc), None,
                "fred_realtime:2026-10-01:9999-12-31", "{}",
            ),
        )
        process_fred_treasury_series(connection, "fred", "DGS10")
        process_treasury_spread(connection)
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in ("raw_observations", "processed_observations", "processed_observation_inputs", "processed_observation_dependencies")
        }
        history = treasury_history(connection, "us_treasury_10y_yield")
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in before
        }
    finally:
        connection.close()

    assert len(history) == 6
    assert history[-1].value == 5.00
    assert history[-1].change_1d.value == pytest.approx(0.60)
    assert after == before


def test_unsupported_indicator_remains_explicit(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        with pytest.raises(ValueError, match="Unsupported"):
            treasury_history(connection, "not_an_indicator")
    finally:
        connection.close()
