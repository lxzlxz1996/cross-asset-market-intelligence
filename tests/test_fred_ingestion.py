from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cross_asset_market_intelligence.data.fred import FredClient, parse_fred_observations
from cross_asset_market_intelligence.data.ingestion import (
    ingest_approved_fred_series,
    persist_fred_observations,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import ConfigurationError, SourceResponseError


def _payload(*, value: str = "4.25") -> dict[str, object]:
    return {
        "realtime_start": "2026-09-16",
        "realtime_end": "2026-09-16",
        "observations": [
            {
                "realtime_start": "2026-09-16",
                "realtime_end": "2026-09-16",
                "date": "2026-09-15",
                "value": value,
            }
        ],
    }


def _fake_client(payload: dict[str, object]) -> FredClient:
    return FredClient("test-key", http_get=lambda _: json.dumps(payload).encode("utf-8"))


def _connection(tmp_path: Path):
    connection = connect(tmp_path / "test.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def test_valid_dgs2_response_parses_with_the_requested_series_id() -> None:
    observations = _fake_client(_payload()).fetch_observations("DGS2")

    assert observations[0].series_id == "DGS2"
    assert observations[0].value == 4.25


def test_valid_dgs10_response_parses_with_the_requested_series_id() -> None:
    observations = _fake_client(_payload(value="4.50")).fetch_observations("DGS10")

    assert observations[0].series_id == "DGS10"
    assert observations[0].value == 4.50


def test_missing_fred_value_is_persisted_as_null_with_source_metadata(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        observation = parse_fred_observations("DGS2", _payload(value="."))[0]
        persist_fred_observations(connection, [observation])
        value, metadata = connection.execute(
            "SELECT value, metadata FROM raw_observations"
        ).fetchone()
    finally:
        connection.close()

    assert value is None
    assert json.loads(metadata)["fred_raw_value"] == "."
    assert json.loads(metadata)["is_missing"] is True


def test_retrieval_timestamp_is_timezone_aware(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        observation = parse_fred_observations("DGS2", _payload())[0]
        retrieved_at = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        persist_fred_observations(connection, [observation], retrieved_at=retrieved_at)
        stored_timestamp = connection.execute(
            "SELECT retrieval_timestamp FROM raw_observations"
        ).fetchone()[0]
    finally:
        connection.close()

    assert stored_timestamp.tzinfo is not None
    assert stored_timestamp.astimezone(timezone.utc) == retrieved_at


def test_missing_api_key_raises_clear_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="FRED_API_KEY"):
        FredClient.from_environment()


def test_malformed_fred_response_fails_explicitly() -> None:
    with pytest.raises(SourceResponseError, match="observations list"):
        parse_fred_observations("DGS2", {"unexpected": []})


def test_repeated_ingestion_does_not_duplicate_raw_rows(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        client = _fake_client(_payload())
        assert ingest_approved_fred_series(client, connection, "DGS2") == 1
        assert ingest_approved_fred_series(client, connection, "DGS2") == 0
        assert connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0] == 1
    finally:
        connection.close()


def test_dgs2_and_dgs10_are_stored_as_separate_source_series(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        client = _fake_client(_payload())
        ingest_approved_fred_series(client, connection, "DGS2")
        ingest_approved_fred_series(client, connection, "DGS10")
        series = {
            row[0]
            for row in connection.execute("SELECT DISTINCT series_id FROM raw_observations").fetchall()
        }
    finally:
        connection.close()

    assert series == {"DGS2", "DGS10"}
