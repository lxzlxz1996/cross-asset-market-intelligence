from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.dashboard.presentation import (
    direct_lineage_rows,
    format_change,
    format_level,
    historical_chart_rows,
)
from cross_asset_market_intelligence.dashboard.sofr_read_model import (
    current_sofr_observation,
    inspect_sofr_lineage,
    sofr_history,
)
from cross_asset_market_intelligence.data.sofr_processing import SOFR_PROCESSING_VERSION, process_sofr
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import DashboardLineageError


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "sofr_dashboard.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _insert_raw(
    connection: duckdb.DuckDBPyConnection,
    observation_date: date,
    value: float,
    vintage: str = "frbny_sofr_revision:original",
) -> None:
    connection.execute(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "frbny",
            "SOFR",
            observation_date,
            value,
            datetime(2026, 9, 16, tzinfo=timezone.utc),
            None,
            vintage,
            "{}",
        ),
    )


def _three_observations(connection: duckdb.DuckDBPyConnection) -> None:
    _insert_raw(connection, date(2026, 9, 14), 3.62)
    _insert_raw(connection, date(2026, 9, 15), 3.64)
    _insert_raw(connection, date(2026, 9, 16), 3.62)
    process_sofr(connection)


def test_current_sofr_projection_uses_selected_processed_history_and_observation_lags(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _three_observations(connection)
        current = current_sofr_observation(connection)
        history = sofr_history(connection)
    finally:
        connection.close()

    assert current is not None
    assert current.indicator_id == "sofr"
    assert current.display_name == "SOFR"
    assert (current.category, current.subcategory) == ("Liquidity", "Overnight funding")
    assert current.processing_version == SOFR_PROCESSING_VERSION
    assert current.unit == "percent"
    assert current.value == 3.62
    assert current.observation_date == date(2026, 9, 16)
    assert current.change_1d.value == pytest.approx(-0.02)
    assert current.change_1d.unit == "percentage_points"
    assert current.change_5d.value is None
    assert current.change_20d.value is None
    assert [(item.observation_date, item.value) for item in history] == [
        (date(2026, 9, 14), 3.62),
        (date(2026, 9, 15), 3.64),
        (date(2026, 9, 16), 3.62),
    ]


def test_revised_raw_selects_revised_processed_output_without_deleting_original(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, date(2026, 9, 15), 3.62)
        process_sofr(connection)
        original_id = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
        _insert_raw(connection, date(2026, 9, 15), 3.64, "frbny_sofr_revision:r")
        process_sofr(connection)
        current = current_sofr_observation(connection)
        history = sofr_history(connection)
        processed_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
        raw_count = connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0]
    finally:
        connection.close()

    assert processed_count == 2
    assert raw_count == 2
    assert len(history) == 1
    assert current is not None
    assert current.value == 3.64
    assert current.processed_observation_id != original_id
    assert current.lineage.raw_input.vintage == "frbny_sofr_revision:r"


def test_history_keeps_actual_gaps_and_bounds_but_calculates_lags_from_full_selection(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, date(2026, 9, 14), 3.60)
        _insert_raw(connection, date(2026, 9, 16), 3.65)
        _insert_raw(connection, date(2026, 9, 18), 3.70)
        process_sofr(connection)
        history = sofr_history(connection, start_date=date(2026, 9, 16), end_date=date(2026, 9, 18))
    finally:
        connection.close()

    assert [item.observation_date for item in history] == [date(2026, 9, 16), date(2026, 9, 18)]
    assert history[0].change_1d.value == pytest.approx(0.05)
    assert history[1].change_1d.value == pytest.approx(0.05)


def test_exact_raw_lineage_and_presentation_are_inspectable(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _three_observations(connection)
        current = current_sofr_observation(connection)
        assert current is not None
        lineage = inspect_sofr_lineage(connection, current.processed_observation_id)
        rows = historical_chart_rows(sofr_history(connection), "SOFR (%)")
    finally:
        connection.close()

    assert lineage.raw_input.source == "frbny"
    assert lineage.raw_input.series_id == "SOFR"
    assert lineage.raw_input.observation_date == date(2026, 9, 16)
    assert lineage.raw_input.vintage == "frbny_sofr_revision:original"
    assert direct_lineage_rows(current)[0]["raw_vintage"] == "frbny_sofr_revision:original"
    assert format_level(current) == "3.62%"
    assert format_change(current.change_1d.value) == "-0.02 pp"
    assert format_change(current.change_5d.value) == "N/A"
    assert rows[-1] == {"date": "2026-09-16", "series": "SOFR (%)", "value": 3.62}


def test_missing_processed_match_and_reads_are_explicit_and_non_mutating(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _three_observations(connection)
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in ("raw_observations", "processed_observations", "processed_observation_inputs")
        }
        current_sofr_observation(connection)
        sofr_history(connection)
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in before
        }
        _insert_raw(connection, date(2026, 9, 17), 3.61)
        with pytest.raises(DashboardLineageError, match="requires exactly one processed"):
            sofr_history(connection)
    finally:
        connection.close()

    assert after == before
