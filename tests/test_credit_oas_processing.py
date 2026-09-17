from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data import credit_oas_processing
from cross_asset_market_intelligence.data.credit_oas_processing import (
    CREDIT_OAS_PROCESSING_VERSION,
    CREDIT_OAS_TRANSFORMATION,
    RawCreditOasObservation,
    approved_credit_oas_indicator_for,
    process_credit_oas,
    process_credit_oas_series,
    select_latest_credit_oas_raw_vintages,
    validate_raw_credit_oas_observation,
)
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import ProcessingPersistenceError, ProcessingValidationError
from cross_asset_market_intelligence.lineage import RawInputIdentity, processed_observation_id


IG = "BAMLC0A0CM"
HY = "BAMLH0A0HYM2"


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "credit_processing.duckdb")
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
    source: str = "fred",
) -> None:
    connection.execute(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source,
            series_id,
            observation_date,
            value,
            datetime(2026, 9, 16, tzinfo=timezone.utc),
            None,
            vintage,
            "{}",
        ),
    )


def test_only_approved_credit_series_map_to_their_respective_indicators() -> None:
    assert approved_credit_oas_indicator_for("fred", IG) == "us_investment_grade_oas"
    assert approved_credit_oas_indicator_for("fred", HY) == "us_high_yield_oas"
    with pytest.raises(ProcessingValidationError, match="Unsupported FRED Credit OAS"):
        approved_credit_oas_indicator_for("fred", "SP500")
    with pytest.raises(ProcessingValidationError, match="Unsupported source"):
        approved_credit_oas_indicator_for("frbny", IG)


def test_both_credit_oas_series_preserve_native_percentage_point_values_and_exact_lineage(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, IG, 0.78, _vintage(16))
        _insert_raw(connection, HY, 2.70, _vintage(16))
        result = process_credit_oas(connection)
        rows = connection.execute(
            """
            SELECT processed.indicator_id, processed.value, processed.processing_version,
                   processed.transformation, input.input_role, input.raw_source,
                   input.raw_series_id, input.raw_vintage
            FROM processed_observations AS processed
            JOIN processed_observation_inputs AS input USING (processed_observation_id)
            ORDER BY processed.indicator_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert result.inserted == 2
    assert result.skipped_missing == 0
    assert rows == [
        (
            "us_high_yield_oas",
            2.70,
            CREDIT_OAS_PROCESSING_VERSION,
            CREDIT_OAS_TRANSFORMATION,
            "source",
            "fred",
            HY,
            _vintage(16),
        ),
        (
            "us_investment_grade_oas",
            0.78,
            CREDIT_OAS_PROCESSING_VERSION,
            CREDIT_OAS_TRANSFORMATION,
            "source",
            "fred",
            IG,
            _vintage(16),
        ),
    ]


def test_processed_identity_uses_the_established_exact_raw_lineage_helper(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, IG, 0.78, _vintage(16))
        process_credit_oas_series(connection, "fred", IG)
        actual = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    assert actual == processed_observation_id(
        "us_investment_grade_oas",
        date(2026, 9, 15),
        CREDIT_OAS_PROCESSING_VERSION,
        [RawInputIdentity("source", "fred", IG, date(2026, 9, 15), _vintage(16))],
    )


def test_credit_processing_is_idempotent_and_does_not_mutate_raw_data(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, IG, 0.78, _vintage(16))
        raw_before = connection.execute("SELECT * FROM raw_observations").fetchall()
        assert process_credit_oas_series(connection, "fred", IG).inserted == 1
        assert process_credit_oas_series(connection, "fred", IG).inserted == 0
        raw_after = connection.execute("SELECT * FROM raw_observations").fetchall()
    finally:
        connection.close()

    assert raw_after == raw_before


def test_latest_fred_vintage_is_selected_immutably_without_changing_methodology(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, IG, 0.78, _vintage(16))
        first = process_credit_oas_series(connection, "fred", IG)
        original_id = connection.execute("SELECT processed_observation_id FROM processed_observations").fetchone()[0]
        _insert_raw(connection, IG, 0.80, _vintage(17))
        selected = select_latest_credit_oas_raw_vintages(connection, "fred", IG)
        second = process_credit_oas_series(connection, "fred", IG)
        rows = connection.execute(
            "SELECT processed_observation_id, value, processing_version FROM processed_observations ORDER BY value"
        ).fetchall()
    finally:
        connection.close()

    assert first.inserted == 1
    assert selected[0].vintage == _vintage(17)
    assert second.inserted == 1
    assert rows[0] == (original_id, 0.78, CREDIT_OAS_PROCESSING_VERSION)
    assert rows[1][1:] == (0.80, CREDIT_OAS_PROCESSING_VERSION)
    assert rows[0][0] != rows[1][0]


def test_source_missing_values_are_skipped_without_fabricating_processed_credit_data(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, HY, None, _vintage(16))
        result = process_credit_oas_series(connection, "fred", HY)
        count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
    finally:
        connection.close()

    assert result.inserted == 0
    assert result.skipped_missing == 1
    assert count == 0


@pytest.mark.parametrize(
    ("observation", "message"),
    [
        (RawCreditOasObservation("fred", IG, date(2026, 9, 15), 0.78, "bad"), "FRED vintage"),
        (RawCreditOasObservation("fred", IG, date(2026, 9, 15), float("nan"), _vintage(16)), "finite"),
        (RawCreditOasObservation("fred", IG, date(2026, 9, 15), True, _vintage(16)), "numeric"),
    ],
)
def test_invalid_credit_raw_contract_fails_explicitly(
    observation: RawCreditOasObservation, message: str
) -> None:
    with pytest.raises(ProcessingValidationError, match=message):
        validate_raw_credit_oas_observation(observation)


def test_parent_and_raw_lineage_persist_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, IG, 0.78, _vintage(16))

        def invalid_input(**_: object) -> RawInputIdentity:
            return RawInputIdentity("source", "fred", IG, date(2026, 9, 15), "missing")

        monkeypatch.setattr(credit_oas_processing, "RawInputIdentity", invalid_input)
        with pytest.raises(ProcessingPersistenceError, match="complete processed Credit OAS"):
            process_credit_oas_series(connection, "fred", IG)
        assert connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM processed_observation_inputs").fetchone()[0] == 0
    finally:
        connection.close()
