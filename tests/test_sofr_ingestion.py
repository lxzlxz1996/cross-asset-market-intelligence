from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from cross_asset_market_intelligence.data.frbny_sofr import (
    FRBNY_SOFR_SERIES_ID,
    FRBNY_SOURCE,
    FrbnySofrClient,
    parse_frbny_sofr_observations,
)
from cross_asset_market_intelligence.data.sofr_ingestion import ingest_sofr, persist_sofr_observations
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import PersistenceError, SourceResponseError, SourceRetrievalError
from cross_asset_market_intelligence.data import sofr_ingestion


def _payload(*, rate: object = 5.31, revision_indicator: str = "") -> dict[str, object]:
    return {
        "refRates": [
            {
                "effectiveDate": "2026-09-15",
                "type": "SOFR",
                "percentRate": rate,
                "percentPercentile1": 5.25,
                "revisionIndicator": revision_indicator,
            }
        ]
    }


def _client(payload: dict[str, object]) -> FrbnySofrClient:
    return FrbnySofrClient(http_get=lambda _: json.dumps(payload).encode("utf-8"))


def _connection(tmp_path: Path):
    connection = connect(tmp_path / "sofr.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def test_official_sofr_record_maps_the_effective_date_and_native_percent_rate() -> None:
    observation = _client(_payload()).fetch_observations()[0]

    assert observation.effective_date == date(2026, 9, 15)
    assert observation.percent_rate == 5.31
    assert observation.vintage_key == "frbny_sofr_revision:original"


def test_range_request_uses_the_official_search_contract() -> None:
    requested_urls: list[str] = []
    client = FrbnySofrClient(
        http_get=lambda url: requested_urls.append(url) or json.dumps(_payload()).encode("utf-8")
    )

    client.fetch_observations(observation_start=date(2026, 9, 1), observation_end=date(2026, 9, 15))

    assert requested_urls == [
        "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?"
        "startDate=2026-09-01&endDate=2026-09-15&type=rate"
    ]


def test_sofr_raw_mapping_preserves_source_metadata_and_has_no_invented_publication_time(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    retrieved_at = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    try:
        assert persist_sofr_observations(
            connection,
            parse_frbny_sofr_observations(_payload()),
            retrieved_at=retrieved_at,
        ) == 1
        row = connection.execute(
            """
            SELECT source, series_id, observation_date, value, retrieval_timestamp,
                   publication_timestamp, vintage, metadata
            FROM raw_observations
            """
        ).fetchone()
        processed_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    source, series_id, observation_date, value, stored_retrieved, published, vintage, metadata = row
    assert (source, series_id, observation_date, value, vintage) == (
        FRBNY_SOURCE,
        FRBNY_SOFR_SERIES_ID,
        date(2026, 9, 15),
        5.31,
        "frbny_sofr_revision:original",
    )
    assert stored_retrieved.tzinfo is not None
    assert stored_retrieved.astimezone(timezone.utc) == retrieved_at
    assert published is None
    assert json.loads(metadata)["frbny_revision_indicator"] == ""
    assert json.loads(metadata)["frbny_source_record"]["percentRate"] == 5.31
    assert processed_count == 0


def test_same_official_sofr_vintage_is_idempotent_and_revised_indicator_coexists(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        assert ingest_sofr(_client(_payload(rate=5.31)), connection) == 1
        assert ingest_sofr(_client(_payload(rate=5.31)), connection) == 0
        assert ingest_sofr(_client(_payload(rate=5.33, revision_indicator="r")), connection) == 1
        rows = connection.execute(
            "SELECT value, vintage FROM raw_observations ORDER BY vintage"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [(5.31, "frbny_sofr_revision:original"), (5.33, "frbny_sofr_revision:r")]


def test_source_gaps_are_not_fabricated(tmp_path: Path) -> None:
    payload = _payload()
    payload["refRates"] = [
        _payload()["refRates"][0],
        {"effectiveDate": "2026-09-17", "type": "SOFR", "percentRate": 5.32, "revisionIndicator": ""},
    ]
    connection = _connection(tmp_path)
    try:
        assert ingest_sofr(_client(payload), connection) == 2
        dates = connection.execute("SELECT observation_date FROM raw_observations ORDER BY observation_date").fetchall()
    finally:
        connection.close()

    assert dates == [(date(2026, 9, 15),), (date(2026, 9, 17),)]


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"unexpected": []}, "refRates list"),
        (_payload(rate="5.31"), "Invalid"),
        (_payload(rate=float("nan")), "not finite"),
        ({"refRates": [{"effectiveDate": "2026-09-15", "type": "SOFR", "percentRate": 5.31}]}, "Invalid"),
        (_payload() | {"refRates": [{"effectiveDate": "2026-09-15", "type": "EFFR", "percentRate": 5.31, "revisionIndicator": ""}]}, "unexpected rate type"),
    ],
)
def test_malformed_or_invalid_sofr_records_fail_explicitly(
    payload: dict[str, object], message: str
) -> None:
    with pytest.raises(SourceResponseError, match=message):
        parse_frbny_sofr_observations(payload)


def test_network_failure_is_visible() -> None:
    client = FrbnySofrClient(http_get=lambda _: (_ for _ in ()).throw(OSError("offline")))

    with pytest.raises(SourceRetrievalError, match="FRBNY SOFR request failed"):
        client.fetch_observations()


def test_persistence_failure_is_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _connection(tmp_path)
    try:
        monkeypatch.setattr(
            sofr_ingestion,
            "persist_raw_observation_records",
            lambda *_, **__: (_ for _ in ()).throw(PersistenceError("database unavailable")),
        )
        with pytest.raises(PersistenceError, match="database unavailable"):
            persist_sofr_observations(connection, parse_frbny_sofr_observations(_payload()))
    finally:
        connection.close()
