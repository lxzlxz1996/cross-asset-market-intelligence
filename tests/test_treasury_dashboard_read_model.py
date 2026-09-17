from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.dashboard.treasury_read_model import (
    DirectDashboardLineage,
    SpreadDashboardLineage,
    current_treasury_dashboard,
    current_treasury_observation,
    inspect_treasury_lineage,
    treasury_history,
)
from cross_asset_market_intelligence.data.treasury_processing import (
    DIRECT_TREASURY_PROCESSING_VERSION,
    process_fred_treasury_series,
)
from cross_asset_market_intelligence.data.treasury_spread_processing import (
    TREASURY_SPREAD_INDICATOR,
    TREASURY_SPREAD_PROCESSING_VERSION,
    process_treasury_spread,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "dashboard.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _vintage(day: int) -> str:
    return f"fred_realtime:2026-09-{day:02d}:9999-12-31"


def _insert_raw(
    connection: duckdb.DuckDBPyConnection,
    series_id: str,
    value: float | None,
    vintage: str,
    observation_date: date,
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


def _process_pair(
    connection: duckdb.DuckDBPyConnection,
    observation_date: date,
    ten_year: float,
    two_year: float,
    *,
    ten_vintage: str = "fred_realtime:2026-09-16:9999-12-31",
    two_vintage: str = "fred_realtime:2026-09-16:9999-12-31",
) -> None:
    _insert_raw(connection, "DGS10", ten_year, ten_vintage, observation_date)
    _insert_raw(connection, "DGS2", two_year, two_vintage, observation_date)
    process_fred_treasury_series(connection, "fred", "DGS10")
    process_fred_treasury_series(connection, "fred", "DGS2")
    process_treasury_spread(connection)


def test_current_projection_selects_latest_direct_and_spread_revisions_deterministically(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        _process_pair(connection, date(2026, 9, 15), 4.30, 3.80, ten_vintage=_vintage(16), two_vintage=_vintage(16))
        old_spread = current_treasury_observation(connection, TREASURY_SPREAD_INDICATOR)
        _insert_raw(connection, "DGS10", 4.50, _vintage(17), date(2026, 9, 15))
        process_fred_treasury_series(connection, "fred", "DGS10")
        process_treasury_spread(connection)
        dashboard = current_treasury_dashboard(connection)
        spread_rows = connection.execute(
            "SELECT count(*) FROM processed_observations WHERE indicator_id = ?",
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert dashboard["us_treasury_10y_yield"].value == 4.50
    assert dashboard["us_treasury_2y_yield"].value == 3.80
    assert dashboard[TREASURY_SPREAD_INDICATOR].value == pytest.approx(0.70)
    assert dashboard[TREASURY_SPREAD_INDICATOR].processed_observation_id != old_spread.processed_observation_id
    assert spread_rows == 2


def test_indicator_specific_latest_dates_and_explicit_units(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _process_pair(connection, date(2026, 9, 15), 4.30, 3.80)
        _insert_raw(connection, "DGS10", 4.40, _vintage(17), date(2026, 9, 16))
        process_fred_treasury_series(connection, "fred", "DGS10")
        dashboard = current_treasury_dashboard(connection)
    finally:
        connection.close()

    assert dashboard["us_treasury_10y_yield"].observation_date == date(2026, 9, 16)
    assert dashboard["us_treasury_2y_yield"].observation_date == date(2026, 9, 15)
    assert dashboard[TREASURY_SPREAD_INDICATOR].observation_date == date(2026, 9, 15)
    assert dashboard["us_treasury_10y_yield"].unit == "percent"
    assert dashboard["us_treasury_2y_yield"].unit == "percent"
    assert dashboard[TREASURY_SPREAD_INDICATOR].unit == "percentage_points"


def test_history_is_current_selected_per_date_and_sorted_without_duplicates(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _process_pair(connection, date(2026, 9, 15), 4.30, 3.80, ten_vintage=_vintage(16))
        _process_pair(connection, date(2026, 9, 16), 4.40, 3.90, ten_vintage=_vintage(16))
        _insert_raw(connection, "DGS10", 4.50, _vintage(17), date(2026, 9, 15))
        process_fred_treasury_series(connection, "fred", "DGS10")
        process_treasury_spread(connection)
        history = treasury_history(
            connection,
            "us_treasury_10y_yield",
            start_date=date(2026, 9, 15),
            end_date=date(2026, 9, 16),
        )
    finally:
        connection.close()

    assert [(item.observation_date, item.value) for item in history] == [
        (date(2026, 9, 15), 4.50),
        (date(2026, 9, 16), 4.40),
    ]


def test_unsupported_and_empty_dashboard_states_are_explicit(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        assert current_treasury_observation(connection, "us_treasury_2y_yield") is None
        with pytest.raises(ValueError, match="Unsupported"):
            current_treasury_observation(connection, "unsupported")
    finally:
        connection.close()


def test_only_approved_methodologies_are_selected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS10", 4.30, _vintage(16), date(2026, 9, 15))
        connection.execute(
            "INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "wrong_method",
                "us_treasury_10y_yield",
                date(2026, 9, 15),
                4.30,
                "wrong_method_v1",
                "fixture",
                datetime(2026, 9, 16, tzinfo=timezone.utc),
            ),
        )
        connection.execute(
            "INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)",
            ("wrong_method", "source", "fred", "DGS10", date(2026, 9, 15), _vintage(16)),
        )
        assert current_treasury_observation(connection, "us_treasury_10y_yield") is None
        assert current_treasury_observation(connection, TREASURY_SPREAD_INDICATOR) is None
    finally:
        connection.close()


def test_direct_and_spread_lineage_inspection_resolves_exact_dependencies_and_raw_vintages(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        _process_pair(connection, date(2026, 9, 15), 4.30, 3.80, ten_vintage=_vintage(16), two_vintage=_vintage(17))
        direct = current_treasury_observation(connection, "us_treasury_10y_yield")
        spread = current_treasury_observation(connection, TREASURY_SPREAD_INDICATOR)
        direct_lineage = inspect_treasury_lineage(connection, direct.processed_observation_id)
        spread_lineage = inspect_treasury_lineage(connection, spread.processed_observation_id)
    finally:
        connection.close()

    assert isinstance(direct_lineage, DirectDashboardLineage)
    assert direct_lineage.raw_input.series_id == "DGS10"
    assert direct_lineage.raw_input.vintage == _vintage(16)
    assert isinstance(spread_lineage, SpreadDashboardLineage)
    assert spread_lineage.ten_year_processed_observation_id == direct.processed_observation_id
    assert spread_lineage.ten_year_raw_input.vintage == _vintage(16)
    assert spread_lineage.two_year_raw_input.series_id == "DGS2"
    assert spread_lineage.two_year_raw_input.vintage == _vintage(17)


def test_read_operations_do_not_mutate_any_lineage_table(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _process_pair(connection, date(2026, 9, 15), 4.30, 3.80)
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in (
                "raw_observations",
                "processed_observations",
                "processed_observation_inputs",
                "processed_observation_dependencies",
            )
        }
        current_treasury_dashboard(connection)
        treasury_history(connection, TREASURY_SPREAD_INDICATOR)
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in before
        }
    finally:
        connection.close()

    assert after == before
