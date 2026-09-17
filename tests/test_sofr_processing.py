from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data import sofr_processing
from cross_asset_market_intelligence.data.sofr_processing import (
    SOFR_PROCESSING_VERSION,
    SOFR_TRANSFORMATION,
    RawSofrObservation,
    approved_sofr_indicator_for,
    process_sofr,
    select_current_sofr_raw_observations,
    validate_raw_sofr_observation,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import ProcessingPersistenceError, ProcessingValidationError
from cross_asset_market_intelligence.lineage import RawInputIdentity


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "sofr_processing.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _insert_raw(
    connection: duckdb.DuckDBPyConnection,
    value: float | None,
    vintage: str = "frbny_sofr_revision:original",
    *,
    observation_date: date = date(2026, 9, 15),
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


def test_only_frbny_sofr_maps_to_sofr() -> None:
    assert approved_sofr_indicator_for("frbny", "SOFR") == "sofr"
    with pytest.raises(ProcessingValidationError, match="Unsupported source"):
        approved_sofr_indicator_for("fred", "SOFR")
    with pytest.raises(ProcessingValidationError, match="Unsupported FRBNY series"):
        approved_sofr_indicator_for("frbny", "EFFR")


def test_original_sofr_normalizes_as_native_percent_with_exact_raw_lineage(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, 3.62)
        result = process_sofr(connection)
        row = connection.execute(
            """
            SELECT processed.processed_observation_id, processed.indicator_id, processed.date,
                   processed.value, processed.processing_version, processed.transformation,
                   input.input_role, input.raw_source, input.raw_series_id, input.raw_vintage
            FROM processed_observations AS processed
            JOIN processed_observation_inputs AS input USING (processed_observation_id)
            """
        ).fetchone()
    finally:
        connection.close()

    assert result.inserted == 1
    assert row[1:] == (
        "sofr",
        date(2026, 9, 15),
        3.62,
        SOFR_PROCESSING_VERSION,
        SOFR_TRANSFORMATION,
        "source",
        "frbny",
        "SOFR",
        "frbny_sofr_revision:original",
    )


def test_recognized_revised_sofr_is_selected_without_removing_original_history(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, 3.62)
        first = process_sofr(connection)
        original_id = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
        raw_before_revision = connection.execute("SELECT * FROM raw_observations ORDER BY vintage").fetchall()
        _insert_raw(connection, 3.64, "frbny_sofr_revision:r")
        selected = select_current_sofr_raw_observations(connection)
        second = process_sofr(connection)
        rows = connection.execute(
            "SELECT processed_observation_id, value, processing_version FROM processed_observations ORDER BY value"
        ).fetchall()
        raw_after_revision = connection.execute("SELECT * FROM raw_observations ORDER BY vintage").fetchall()
    finally:
        connection.close()

    assert first.inserted == 1
    assert [(item.value, item.vintage) for item in selected] == [(3.64, "frbny_sofr_revision:r")]
    assert second.inserted == 1
    assert rows[0] == (original_id, 3.62, SOFR_PROCESSING_VERSION)
    assert rows[1][1:] == (3.64, SOFR_PROCESSING_VERSION)
    assert rows[0][0] != rows[1][0]
    assert raw_after_revision[:1] == raw_before_revision
    assert len(raw_after_revision) == 2


def test_sofr_processing_is_idempotent_and_does_not_synthesize_missing_dates(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, 3.62, observation_date=date(2026, 9, 15))
        _insert_raw(connection, 3.64, observation_date=date(2026, 9, 17))
        raw_before = connection.execute("SELECT * FROM raw_observations ORDER BY observation_date").fetchall()
        assert process_sofr(connection).inserted == 2
        assert process_sofr(connection).inserted == 0
        dates = connection.execute("SELECT date FROM processed_observations ORDER BY date").fetchall()
        raw_after = connection.execute("SELECT * FROM raw_observations ORDER BY observation_date").fetchall()
    finally:
        connection.close()

    assert dates == [(date(2026, 9, 15),), (date(2026, 9, 17),)]
    assert raw_after == raw_before


@pytest.mark.parametrize(
    "observation, message",
    [
        (RawSofrObservation("frbny", "SOFR", date(2026, 9, 15), 3.62, "bad"), "not an FRBNY"),
        (RawSofrObservation("frbny", "SOFR", date(2026, 9, 15), 3.62, "frbny_sofr_revision:unknown"), "Unsupported"),
        (RawSofrObservation("frbny", "SOFR", date(2026, 9, 15), float("nan"), "frbny_sofr_revision:original"), "finite"),
        (RawSofrObservation("frbny", "SOFR", date(2026, 9, 15), True, "frbny_sofr_revision:original"), "numeric"),
    ],
)
def test_invalid_sofr_raw_contract_fails_explicitly(
    observation: RawSofrObservation, message: str
) -> None:
    with pytest.raises(ProcessingValidationError, match=message):
        validate_raw_sofr_observation(observation)


def test_null_sofr_raw_value_creates_no_numeric_processed_observation(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, None)
        result = process_sofr(connection)
        count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    assert result.inserted == 0
    assert result.skipped_missing == 1
    assert count == 0


def test_sofr_parent_and_raw_lineage_persist_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, 3.62)

        def invalid_input(**_: object) -> RawInputIdentity:
            return RawInputIdentity("source", "frbny", "SOFR", date(2026, 9, 15), "missing")

        monkeypatch.setattr(sofr_processing, "RawInputIdentity", invalid_input)
        with pytest.raises(ProcessingPersistenceError, match="complete processed SOFR"):
            process_sofr(connection)
        assert connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM processed_observation_inputs").fetchone()[0] == 0
    finally:
        connection.close()
