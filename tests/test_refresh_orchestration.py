from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from cross_asset_market_intelligence.dashboard.data_health_read_model import (
    current_data_health,
    data_health_rows,
    failed_refresh_rows,
)
from cross_asset_market_intelligence.data.fred import FredObservation
from cross_asset_market_intelligence.data.frbny_sofr import FrbnySofrObservation
from cross_asset_market_intelligence.data.refresh_orchestration import refresh_market_data
from cross_asset_market_intelligence.data.sofr_processing import process_sofr
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema


class _FredClient:
    def fetch_observations(self, series_id: str, **_: object) -> list[FredObservation]:
        return [
            FredObservation(
                series_id=series_id,
                observation_date=date(2026, 9, 16),
                value=4.25 if series_id == "DGS2" else 4.50,
                raw_value="4.25" if series_id == "DGS2" else "4.50",
                realtime_start="2026-09-16",
                realtime_end="9999-12-31",
            )
        ]


class _FailingFredClient:
    def fetch_observations(self, series_id: str, **_: object) -> list[FredObservation]:
        raise RuntimeError(f"source request failed for {series_id}: token=super-secret")


class _SofrClient:
    def fetch_observations(self, **_: object) -> list[FrbnySofrObservation]:
        return [
            FrbnySofrObservation(
                effective_date=date(2026, 9, 16),
                percent_rate=3.62,
                revision_indicator="",
                source_record={"effectiveDate": "2026-09-16", "type": "SOFR"},
            )
        ]


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "refresh.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def test_successful_treasury_refresh_records_all_stages_and_is_idempotent(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        first = refresh_market_data(connection, "treasury", fred_client=_FredClient())
        raw_count = connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0]
        processed_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
        second = refresh_market_data(connection, "treasury", fred_client=_FredClient())
        final_raw_count = connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0]
        final_processed_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
        run_count = connection.execute("SELECT count(*) FROM refresh_runs").fetchone()[0]
    finally:
        connection.close()

    assert first.status == "succeeded"
    assert first.stage == "complete"
    assert first.started_timestamp.tzinfo is not None
    assert first.completed_timestamp is not None
    assert first.completed_timestamp >= first.started_timestamp
    assert first.records_inserted == 5
    assert second.status == "succeeded"
    assert second.records_inserted == 0
    assert raw_count == final_raw_count == 2
    assert processed_count == final_processed_count == 3
    assert run_count == 2


def test_failed_ingestion_records_sanitized_error_and_preserves_existing_data(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        successful = refresh_market_data(connection, "sofr", sofr_client=_SofrClient())
        before = connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0]
        failed = refresh_market_data(connection, "treasury", fred_client=_FailingFredClient())
        after = connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0]
        saved = connection.execute(
            "SELECT status, stage, error_type, error_message FROM refresh_runs WHERE refresh_run_id = ?",
            (failed.refresh_run_id,),
        ).fetchone()
    finally:
        connection.close()

    assert successful.status == "succeeded"
    assert failed.status == "failed"
    assert failed.stage == "ingestion"
    assert failed.error_type == "RuntimeError"
    assert "super-secret" not in failed.error_message
    assert saved == ("failed", "ingestion", "RuntimeError", failed.error_message)
    assert before == after == 1


def test_processing_failure_is_visible_after_ingestion_and_keeps_prior_selected_data(
    tmp_path: Path, monkeypatch
) -> None:
    connection = _connection(tmp_path)
    try:
        first = refresh_market_data(connection, "sofr", sofr_client=_SofrClient())
        assert first.status == "succeeded"
        original_processed = connection.execute(
            "SELECT count(*) FROM processed_observations"
        ).fetchone()[0]

        def _fail_processing(*_: object, **__: object) -> object:
            raise ValueError("processing failure")

        monkeypatch.setattr(
            "cross_asset_market_intelligence.data.refresh_orchestration.process_sofr",
            _fail_processing,
        )
        failed = refresh_market_data(connection, "sofr", sofr_client=_SofrClient())
        selected_after_failure = connection.execute(
            "SELECT date, value FROM processed_observations WHERE indicator_id = 'sofr'"
        ).fetchall()
    finally:
        connection.close()

    assert failed.status == "failed"
    assert failed.stage == "processing"
    assert failed.records_inserted == 0
    assert len(selected_after_failure) == original_processed == 1
    assert selected_after_failure == [(date(2026, 9, 16), 3.62)]


def test_data_health_separates_available_data_latest_failure_and_deferred_sources(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        refresh_market_data(connection, "sofr", sofr_client=_SofrClient())
        refresh_market_data(connection, "treasury", fred_client=_FailingFredClient())
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in ("raw_observations", "processed_observations", "refresh_runs")
        }
        records = current_data_health(connection)
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            for table in before
        }
    finally:
        connection.close()

    by_indicator = {record.indicator_id: record for record in records}
    sofr = by_indicator["sofr"]
    assert (sofr.availability, sofr.latest_observation_date, sofr.latest_refresh_status) == (
        "available",
        date(2026, 9, 16),
        "succeeded",
    )
    treasury = by_indicator["us_treasury_2y_yield"]
    assert treasury.availability == "unavailable"
    assert treasury.latest_refresh_status == "failed"
    assert treasury.latest_refresh_stage == "ingestion"
    assert all(by_indicator[indicator].availability == "source_pending" for indicator in ("spx", "vix", "move_index"))
    assert before == after
    assert [row["Availability"] for row in data_health_rows(records)[-3:]] == [
        "source_pending",
        "source_pending",
        "source_pending",
    ]
    assert failed_refresh_rows(records)[0]["Stage"] == "ingestion"


def test_latest_successful_refresh_remains_distinct_from_latest_failed_attempt(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        succeeded = refresh_market_data(connection, "sofr", sofr_client=_SofrClient())
        failed = refresh_market_data(connection, "sofr", sofr_client=_FailingFredClient())
        records = current_data_health(connection)
    finally:
        connection.close()

    sofr = next(record for record in records if record.indicator_id == "sofr")
    assert succeeded.completed_timestamp is not None
    assert failed.status == "failed"
    assert sofr.latest_refresh_status == "failed"
    assert sofr.latest_successful_refresh_timestamp == succeeded.completed_timestamp


def test_refresh_schema_remains_separate_from_market_observations(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        raw_columns = {row[1] for row in connection.execute("PRAGMA table_info('raw_observations')").fetchall()}
        processed_columns = {
            row[1] for row in connection.execute("PRAGMA table_info('processed_observations')").fetchall()
        }
        refresh_columns = {
            row[1] for row in connection.execute("PRAGMA table_info('refresh_runs')").fetchall()
        }
    finally:
        connection.close()

    assert "status" not in raw_columns | processed_columns
    assert {
        "refresh_run_id",
        "pipeline_name",
        "started_timestamp",
        "completed_timestamp",
        "status",
        "stage",
        "records_inserted",
        "records_skipped",
        "error_type",
        "error_message",
    } <= refresh_columns
