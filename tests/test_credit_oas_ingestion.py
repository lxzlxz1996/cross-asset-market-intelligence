from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data.fred import FredClient
from cross_asset_market_intelligence.data.ingestion import (
    APPROVED_CREDIT_OAS_FRED_SERIES,
    APPROVED_FRED_SERIES,
    APPROVED_TREASURY_FRED_SERIES,
    ingest_approved_fred_series,
    persist_fred_observations,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema


def _payload(*, value: str, realtime_start: str = "2026-09-16") -> dict[str, object]:
    return {
        "realtime_start": realtime_start,
        "realtime_end": "9999-12-31",
        "observations": [
            {
                "realtime_start": realtime_start,
                "realtime_end": "9999-12-31",
                "date": "2026-09-15",
                "value": value,
            }
        ],
    }


def _client(payload: dict[str, object]) -> FredClient:
    return FredClient("test-key", http_get=lambda _: json.dumps(payload).encode("utf-8"))


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "credit_raw.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def test_credit_oas_series_are_explicitly_approved_but_treasury_approval_stays_separate() -> None:
    assert APPROVED_CREDIT_OAS_FRED_SERIES == {"BAMLC0A0CM", "BAMLH0A0HYM2"}
    assert APPROVED_TREASURY_FRED_SERIES == {"DGS2", "DGS10"}
    assert APPROVED_FRED_SERIES == APPROVED_CREDIT_OAS_FRED_SERIES | APPROVED_TREASURY_FRED_SERIES


@pytest.mark.parametrize(
    ("series_id", "raw_value"),
    [("BAMLC0A0CM", "0.82"), ("BAMLH0A0HYM2", "3.45")],
)
def test_credit_oas_raw_values_and_fred_metadata_are_preserved_without_transformation(
    tmp_path: Path, series_id: str, raw_value: str
) -> None:
    connection = _connection(tmp_path)
    retrieved_at = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    try:
        observation = _client(_payload(value=raw_value)).fetch_observations(series_id)[0]
        assert observation.series_id == series_id
        assert persist_fred_observations(connection, [observation], retrieved_at=retrieved_at) == 1
        row = connection.execute(
            """
            SELECT source, series_id, observation_date, value, retrieval_timestamp,
                   publication_timestamp, vintage, metadata
            FROM raw_observations
            """
        ).fetchone()
        assert persist_fred_observations(connection, [observation], retrieved_at=retrieved_at) == 0
    finally:
        connection.close()

    source, stored_series, observation_date, value, stored_retrieved, published, vintage, metadata = row
    assert (source, stored_series, observation_date, value) == ("fred", series_id, date(2026, 9, 15), float(raw_value))
    assert value not in (float(raw_value) * 100, float(raw_value) / 100)
    assert stored_retrieved.tzinfo is not None
    assert stored_retrieved.astimezone(timezone.utc) == retrieved_at
    assert published is None
    assert vintage == "fred_realtime:2026-09-16:9999-12-31"
    assert json.loads(metadata) == {
        "fred_raw_value": raw_value,
        "fred_realtime_end": "9999-12-31",
        "fred_realtime_start": "2026-09-16",
        "is_missing": False,
    }


def test_credit_missing_value_is_preserved_and_no_processed_credit_row_is_created(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        assert ingest_approved_fred_series(_client(_payload(value=".")), connection, "BAMLC0A0CM") == 1
        value, metadata = connection.execute("SELECT value, metadata FROM raw_observations").fetchone()
        processed = connection.execute(
            "SELECT count(*) FROM processed_observations WHERE indicator_id LIKE 'us_%_oas'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert value is None
    assert json.loads(metadata)["is_missing"] is True
    assert processed == 0


def test_credit_raw_ingestion_is_idempotent_and_distinct_fred_vintages_coexist(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        original = _client(_payload(value="0.82", realtime_start="2026-09-16"))
        revised = _client(_payload(value="0.83", realtime_start="2026-09-17"))
        assert ingest_approved_fred_series(original, connection, "BAMLC0A0CM") == 1
        assert ingest_approved_fred_series(original, connection, "BAMLC0A0CM") == 0
        assert ingest_approved_fred_series(revised, connection, "BAMLC0A0CM") == 1
        rows = connection.execute(
            "SELECT value, vintage FROM raw_observations ORDER BY vintage"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        (0.82, "fred_realtime:2026-09-16:9999-12-31"),
        (0.83, "fred_realtime:2026-09-17:9999-12-31"),
    ]


def test_unsupported_fred_series_remains_rejected_by_phase_one_ingestion(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        with pytest.raises(ValueError, match="not approved"):
            ingest_approved_fred_series(_client(_payload(value="1.00")), connection, "SP500")
        assert connection.execute("SELECT count(*) FROM raw_observations").fetchone()[0] == 0
    finally:
        connection.close()
