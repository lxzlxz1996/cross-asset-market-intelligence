from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data.treasury_processing import (
    DIRECT_TREASURY_PROCESSING_VERSION,
    approved_indicator_for,
    process_approved_fred_treasuries,
    process_fred_treasury_series,
    select_latest_raw_vintages,
)
from cross_asset_market_intelligence.data import treasury_processing
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import ProcessingPersistenceError, ProcessingValidationError
from cross_asset_market_intelligence.lineage import RawInputIdentity, processed_observation_id


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "processing.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _insert_raw(
    connection: duckdb.DuckDBPyConnection,
    series_id: str,
    value: float | None,
    vintage: str,
    *,
    observation_date: date = date(2026, 9, 15),
) -> None:
    connection.execute(
        """
        INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
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


def _vintage(day: int) -> str:
    return f"fred_realtime:2026-09-{day:02d}:9999-12-31"


def test_dgs2_maps_only_to_two_year_indicator() -> None:
    assert approved_indicator_for("fred", "DGS2") == "us_treasury_2y_yield"


def test_dgs10_maps_only_to_ten_year_indicator() -> None:
    assert approved_indicator_for("fred", "DGS10") == "us_treasury_10y_yield"


def test_unsupported_fred_series_and_non_fred_source_are_rejected() -> None:
    with pytest.raises(ProcessingValidationError, match="Unsupported FRED"):
        approved_indicator_for("fred", "SOFR")
    with pytest.raises(ProcessingValidationError, match="Unsupported source"):
        approved_indicator_for("other", "DGS2")


def test_direct_processing_preserves_percent_values_and_source_lineage(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", 4.25, _vintage(16))
        _insert_raw(connection, "DGS10", 4.50, _vintage(16))
        result = process_approved_fred_treasuries(connection)
        rows = connection.execute(
            """
            SELECT processed.indicator_id, processed.value, processed.processing_version,
                   input.input_role, input.raw_series_id, input.raw_vintage
            FROM processed_observations processed
            JOIN processed_observation_inputs input USING (processed_observation_id)
            ORDER BY processed.indicator_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert result.inserted == 2
    assert rows == [
        (
            "us_treasury_10y_yield",
            4.50,
            DIRECT_TREASURY_PROCESSING_VERSION,
            "source",
            "DGS10",
            _vintage(16),
        ),
        (
            "us_treasury_2y_yield",
            4.25,
            DIRECT_TREASURY_PROCESSING_VERSION,
            "source",
            "DGS2",
            _vintage(16),
        ),
    ]


def test_processed_identity_reuses_lineage_helper(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", 4.25, _vintage(16))
        process_fred_treasury_series(connection, "fred", "DGS2")
        actual = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    expected = processed_observation_id(
        "us_treasury_2y_yield",
        date(2026, 9, 15),
        DIRECT_TREASURY_PROCESSING_VERSION,
        [RawInputIdentity("source", "fred", "DGS2", date(2026, 9, 15), _vintage(16))],
    )
    assert actual == expected


def test_identical_processing_is_idempotent_and_leaves_raw_unchanged(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", 4.25, _vintage(16))
        raw_before = connection.execute("SELECT * FROM raw_observations").fetchall()
        assert process_fred_treasury_series(connection, "fred", "DGS2").inserted == 1
        assert process_fred_treasury_series(connection, "fred", "DGS2").inserted == 0
        raw_after = connection.execute("SELECT * FROM raw_observations").fetchall()
        counts = connection.execute(
            "SELECT count(*), count(DISTINCT processed_observation_id) FROM processed_observations"
        ).fetchone()
    finally:
        connection.close()

    assert raw_after == raw_before
    assert counts == (1, 1)


def test_missing_raw_value_is_skipped_without_a_processed_numeric_row(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", None, _vintage(16))
        result = process_fred_treasury_series(connection, "fred", "DGS2")
        processed_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    assert result.inserted == 0
    assert result.skipped_missing == 1
    assert processed_count == 0


def test_latest_vintage_selection_is_deterministic_and_preserves_prior_output(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", 4.25, _vintage(16))
        first = process_fred_treasury_series(connection, "fred", "DGS2")
        old_identifier = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
        _insert_raw(connection, "DGS2", 4.50, _vintage(17))
        selected = select_latest_raw_vintages(connection, "fred", "DGS2")
        second = process_fred_treasury_series(connection, "fred", "DGS2")
        rows = connection.execute(
            "SELECT processed_observation_id, value, processing_version FROM processed_observations ORDER BY value"
        ).fetchall()
    finally:
        connection.close()

    assert first.inserted == 1
    assert selected[0].vintage == _vintage(17)
    assert second.inserted == 1
    assert rows[0] == (old_identifier, 4.25, DIRECT_TREASURY_PROCESSING_VERSION)
    assert rows[1][1:] == (4.50, DIRECT_TREASURY_PROCESSING_VERSION)
    assert rows[0][0] != rows[1][0]


def test_processing_is_atomic_when_lineage_cannot_be_inserted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", 4.25, _vintage(16))
        def invalid_input(**_: object) -> RawInputIdentity:
            return RawInputIdentity("source", "fred", "DGS2", date(2026, 9, 15), "missing")

        monkeypatch.setattr(treasury_processing, "RawInputIdentity", invalid_input)
        with pytest.raises(ProcessingPersistenceError, match="complete processed"):
            process_fred_treasury_series(connection, "fred", "DGS2")
        assert connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0] == 0
    finally:
        connection.close()


def test_dgs2_and_dgs10_remain_independent_processed_series(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "DGS2", 4.25, _vintage(16))
        _insert_raw(connection, "DGS10", 4.50, _vintage(16))
        process_fred_treasury_series(connection, "fred", "DGS2")
        process_fred_treasury_series(connection, "fred", "DGS10")
        indicators = connection.execute(
            "SELECT indicator_id FROM processed_observations ORDER BY indicator_id"
        ).fetchall()
    finally:
        connection.close()

    assert indicators == [("us_treasury_10y_yield",), ("us_treasury_2y_yield",)]
