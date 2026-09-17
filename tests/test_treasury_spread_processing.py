from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data.treasury_processing import (
    DIRECT_TREASURY_PROCESSING_VERSION,
    process_fred_treasury_series,
)
from cross_asset_market_intelligence.data.treasury_spread_processing import (
    TREASURY_SPREAD_INDICATOR,
    TREASURY_SPREAD_PROCESSING_VERSION,
    calculate_treasury_10y_minus_2y,
    process_treasury_spread,
    select_current_direct_treasury_observations,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import ProcessingValidationError


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "spread.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _vintage(day: int) -> str:
    return f"fred_realtime:2026-09-{day:02d}:9999-12-31"


def _insert_raw(
    connection: duckdb.DuckDBPyConnection,
    series_id: str,
    value: float | None,
    vintage: str,
    *,
    observation_date: date = date(2026, 9, 15),
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


def _create_direct_inputs(
    connection: duckdb.DuckDBPyConnection,
    *,
    ten_year: float | None = 4.30,
    two_year: float | None = 3.80,
    ten_date: date = date(2026, 9, 15),
    two_date: date = date(2026, 9, 15),
    ten_vintage: str = "fred_realtime:2026-09-16:9999-12-31",
    two_vintage: str = "fred_realtime:2026-09-16:9999-12-31",
) -> None:
    _insert_raw(connection, "DGS10", ten_year, ten_vintage, observation_date=ten_date)
    _insert_raw(connection, "DGS2", two_year, two_vintage, observation_date=two_date)
    process_fred_treasury_series(connection, "fred", "DGS10")
    process_fred_treasury_series(connection, "fred", "DGS2")


def test_same_date_inputs_create_exact_percentage_point_spread_and_dependencies(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _create_direct_inputs(connection)
        direct_ids = {
            indicator: identifier
            for identifier, indicator in connection.execute(
                """
                SELECT processed_observation_id, indicator_id
                FROM processed_observations
                WHERE indicator_id IN ('us_treasury_10y_yield', 'us_treasury_2y_yield')
                """
            ).fetchall()
        }
        result = process_treasury_spread(connection)
        row = connection.execute(
            """
            SELECT processed.indicator_id, processed.value, processed.processing_version,
                   dependency.input_role, dependency.input_processed_observation_id,
                   upstream.indicator_id, upstream.value
            FROM processed_observations AS processed
            JOIN processed_observation_dependencies AS dependency
                ON processed.processed_observation_id = dependency.output_processed_observation_id
            JOIN processed_observations AS upstream
                ON dependency.input_processed_observation_id = upstream.processed_observation_id
            WHERE processed.indicator_id = ?
            ORDER BY dependency.input_role
            """,
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchall()
    finally:
        connection.close()

    assert result.inserted == 1
    assert row == [
        (
            TREASURY_SPREAD_INDICATOR,
            0.50,
            TREASURY_SPREAD_PROCESSING_VERSION,
            "ten_year",
            direct_ids["us_treasury_10y_yield"],
            "us_treasury_10y_yield",
            4.30,
        ),
        (
            TREASURY_SPREAD_INDICATOR,
            0.50,
            TREASURY_SPREAD_PROCESSING_VERSION,
            "two_year",
            direct_ids["us_treasury_2y_yield"],
            "us_treasury_2y_yield",
            3.80,
        ),
    ]


def test_calculation_is_ten_year_minus_two_year_without_basis_point_conversion() -> None:
    assert calculate_treasury_10y_minus_2y(4.30, 3.80) == pytest.approx(0.50)
    assert calculate_treasury_10y_minus_2y(4.30, 3.80) != 50.0


def test_mismatched_or_missing_direct_inputs_produce_no_spread(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _create_direct_inputs(connection, ten_date=date(2026, 9, 15), two_date=date(2026, 9, 16))
        assert process_treasury_spread(connection).inserted == 0
        _create_direct_inputs(
            connection,
            ten_year=4.30,
            two_year=None,
            ten_date=date(2026, 9, 17),
            two_date=date(2026, 9, 17),
        )
        assert process_treasury_spread(connection).inserted == 0
        _create_direct_inputs(
            connection,
            ten_year=None,
            two_year=3.80,
            ten_date=date(2026, 9, 18),
            two_date=date(2026, 9, 18),
        )
        assert process_treasury_spread(connection).inserted == 0
    finally:
        connection.close()


def test_non_finite_selected_direct_value_is_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS10", 4.30, _vintage(16))
        _insert_raw(connection, "DGS2", 3.80, _vintage(16))
        connection.execute(
            "INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "ten_nonfinite",
                "us_treasury_10y_yield",
                date(2026, 9, 15),
                float("inf"),
                DIRECT_TREASURY_PROCESSING_VERSION,
                "fixture",
                datetime(2026, 9, 16, tzinfo=timezone.utc),
            ),
        )
        connection.execute(
            """
            INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("ten_nonfinite", "source", "fred", "DGS10", date(2026, 9, 15), _vintage(16)),
        )
        process_fred_treasury_series(connection, "fred", "DGS2")
        with pytest.raises(ProcessingValidationError, match="finite numeric"):
            process_treasury_spread(connection)
    finally:
        connection.close()


def test_only_approved_direct_processing_version_is_selected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS10", 4.30, _vintage(16))
        _insert_raw(connection, "DGS2", 3.80, _vintage(16))
        for identifier, indicator, series in (
            ("unapproved_ten", "us_treasury_10y_yield", "DGS10"),
            ("unapproved_two", "us_treasury_2y_yield", "DGS2"),
        ):
            connection.execute(
                "INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    indicator,
                    date(2026, 9, 15),
                    4.0,
                    "unapproved_methodology_v1",
                    "fixture",
                    datetime(2026, 9, 16, tzinfo=timezone.utc),
                ),
            )
            connection.execute(
                "INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, "source", "fred", series, date(2026, 9, 15), _vintage(16)),
            )
        assert select_current_direct_treasury_observations(connection, "us_treasury_10y_yield") == []
        assert process_treasury_spread(connection).inserted == 0
    finally:
        connection.close()


def test_newer_upstream_vintage_creates_new_immutable_spread_and_preserves_old_output(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _create_direct_inputs(connection, ten_vintage=_vintage(16), two_vintage=_vintage(16))
        assert process_treasury_spread(connection).inserted == 1
        old_spread = connection.execute(
            "SELECT processed_observation_id FROM processed_observations WHERE indicator_id = ?",
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchone()[0]
        _insert_raw(connection, "DGS10", 4.50, _vintage(17))
        process_fred_treasury_series(connection, "fred", "DGS10")
        assert process_treasury_spread(connection).inserted == 1
        rows = connection.execute(
            """
            SELECT processed_observation_id, value, processing_version
            FROM processed_observations
            WHERE indicator_id = ?
            ORDER BY value
            """,
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchall()
    finally:
        connection.close()

    assert rows[0] == (old_spread, 0.50, TREASURY_SPREAD_PROCESSING_VERSION)
    assert rows[1][2] == TREASURY_SPREAD_PROCESSING_VERSION
    assert rows[1][1] == pytest.approx(0.70)
    assert rows[0][0] != rows[1][0]


def test_spread_rerun_is_idempotent_and_has_no_direct_raw_inputs(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _create_direct_inputs(connection)
        assert process_treasury_spread(connection).inserted == 1
        assert process_treasury_spread(connection).inserted == 0
        direct_input_count = connection.execute(
            """
            SELECT count(*) FROM processed_observation_inputs AS input
            JOIN processed_observations AS processed USING (processed_observation_id)
            WHERE processed.indicator_id = ?
            """,
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert direct_input_count == 0


def test_spread_transitively_reaches_both_exact_fred_raw_vintages_without_modifying_inputs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        _create_direct_inputs(connection, ten_vintage=_vintage(16), two_vintage=_vintage(17))
        direct_before = connection.execute(
            "SELECT * FROM processed_observations WHERE indicator_id != ? ORDER BY processed_observation_id",
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchall()
        raw_before = connection.execute("SELECT * FROM raw_observations ORDER BY series_id").fetchall()
        process_treasury_spread(connection)
        lineage = connection.execute(
            """
            SELECT dependency.input_role, raw.series_id, raw.observation_date, raw.vintage
            FROM processed_observations AS spread
            JOIN processed_observation_dependencies AS dependency
                ON spread.processed_observation_id = dependency.output_processed_observation_id
            JOIN processed_observation_inputs AS input
                ON dependency.input_processed_observation_id = input.processed_observation_id
            JOIN raw_observations AS raw
                ON input.raw_source = raw.source
                AND input.raw_series_id = raw.series_id
                AND input.raw_observation_date = raw.observation_date
                AND input.raw_vintage = raw.vintage
            WHERE spread.indicator_id = ?
            ORDER BY dependency.input_role
            """,
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchall()
        direct_after = connection.execute(
            "SELECT * FROM processed_observations WHERE indicator_id != ? ORDER BY processed_observation_id",
            (TREASURY_SPREAD_INDICATOR,),
        ).fetchall()
        raw_after = connection.execute("SELECT * FROM raw_observations ORDER BY series_id").fetchall()
    finally:
        connection.close()

    assert lineage == [
        ("ten_year", "DGS10", date(2026, 9, 15), _vintage(16)),
        ("two_year", "DGS2", date(2026, 9, 15), _vintage(17)),
    ]
    assert direct_after == direct_before
    assert raw_after == raw_before
