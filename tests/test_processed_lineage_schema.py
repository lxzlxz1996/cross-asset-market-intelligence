from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.database import (
    connect,
    initialize_phase_0_schema,
    migrate_processed_observation_lineage,
)
from cross_asset_market_intelligence.exceptions import SchemaMigrationError
from cross_asset_market_intelligence.lineage import RawInputIdentity, processed_observation_id


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "lineage.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _insert_raw(connection: duckdb.DuckDBPyConnection, vintage: str, series_id: str = "DGS2") -> None:
    connection.execute(
        """
        INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "fred",
            series_id,
            date(2026, 9, 15),
            4.25,
            datetime(2026, 9, 16, tzinfo=timezone.utc),
            None,
            vintage,
            "{}",
        ),
    )


def _input(vintage: str, series_id: str = "DGS2", role: str = "source") -> RawInputIdentity:
    return RawInputIdentity(role, "fred", series_id, date(2026, 9, 15), vintage)


def _insert_processed(
    connection: duckdb.DuckDBPyConnection,
    identifier: str,
    inputs: list[RawInputIdentity],
    *,
    indicator_id: str = "us_treasury_2y_yield",
    processing_version: str = "treasury_identity_v1",
) -> None:
    connection.execute(
        """
        INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identifier,
            indicator_id,
            date(2026, 9, 15),
            4.25,
            processing_version,
            "validated_identity_percent",
            datetime(2026, 9, 16, tzinfo=timezone.utc),
        ),
    )
    for input_ in inputs:
        connection.execute(
            """
            INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                input_.input_role,
                input_.raw_source,
                input_.raw_series_id,
                input_.raw_observation_date,
                input_.raw_vintage,
            ),
        )


def test_one_processed_output_can_reference_one_raw_input(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "v1")
        input_ = _input("v1")
        identifier = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v1", [input_])
        _insert_processed(connection, identifier, [input_])
        assert connection.execute("SELECT count(*) FROM processed_observation_inputs").fetchone()[0] == 1
    finally:
        connection.close()


def test_one_processed_output_can_reference_two_raw_inputs_with_roles(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "v1", "DGS10")
        _insert_raw(connection, "v1", "DGS2")
        inputs = [_input("v1", "DGS10", "ten_year"), _input("v1", "DGS2", "two_year")]
        identifier = processed_observation_id("example_spread", date(2026, 9, 15), "example_v1", inputs)
        _insert_processed(connection, identifier, inputs, indicator_id="example_spread", processing_version="example_v1")
        roles = {row[0] for row in connection.execute("SELECT input_role FROM processed_observation_inputs").fetchall()}
        assert roles == {"ten_year", "two_year"}
    finally:
        connection.close()


def test_exact_raw_vintage_is_preserved(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "fred_realtime:2026-09-16:2026-09-16")
        input_ = _input("fred_realtime:2026-09-16:2026-09-16")
        identifier = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v1", [input_])
        _insert_processed(connection, identifier, [input_])
        assert connection.execute("SELECT raw_vintage FROM processed_observation_inputs").fetchone()[0] == input_.raw_vintage
    finally:
        connection.close()


def test_source_vintage_change_creates_new_identity_without_changing_methodology() -> None:
    v1, v2 = _input("v1"), _input("v2")
    first = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v1", [v1])
    second = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v1", [v2])

    assert first != second


def test_processing_version_change_creates_new_identity() -> None:
    input_ = _input("v1")
    first = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v1", [input_])
    second = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v2", [input_])

    assert first != second


def test_identity_is_stable_and_input_order_is_canonicalized() -> None:
    inputs = [_input("v1", "DGS10", "ten_year"), _input("v1", "DGS2", "two_year")]
    first = processed_observation_id("example_spread", date(2026, 9, 15), "example_v1", inputs)
    second = processed_observation_id("example_spread", date(2026, 9, 15), "example_v1", list(reversed(inputs)))

    assert first == second


def test_lineage_joins_back_to_the_exact_raw_observation(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_raw(connection, "v1")
        input_ = _input("v1")
        identifier = processed_observation_id("us_treasury_2y_yield", date(2026, 9, 15), "treasury_identity_v1", [input_])
        _insert_processed(connection, identifier, [input_])
        joined_value = connection.execute(
            """
            SELECT raw.value FROM processed_observation_inputs input
            JOIN raw_observations raw ON (
                input.raw_source = raw.source
                AND input.raw_series_id = raw.series_id
                AND input.raw_observation_date = raw.observation_date
                AND input.raw_vintage = raw.vintage
            )
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert joined_value == 4.25


def test_orphan_lineage_is_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        with pytest.raises(duckdb.Error):
            connection.execute(
                """
                INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("missing", "source", "fred", "DGS2", date(2026, 9, 15), "v1"),
            )
    finally:
        connection.close()


def test_lineage_with_missing_raw_input_is_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        identifier = "proc_sha256:parent"
        connection.execute(
            """
            INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                "us_treasury_2y_yield",
                date(2026, 9, 15),
                4.25,
                "treasury_identity_v1",
                "validated_identity_percent",
                datetime(2026, 9, 16, tzinfo=timezone.utc),
            ),
        )
        with pytest.raises(duckdb.Error):
            connection.execute(
                """
                INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)
                """,
                (identifier, "source", "fred", "DGS2", date(2026, 9, 15), "missing"),
            )
    finally:
        connection.close()


def test_nonempty_legacy_processed_table_is_not_destroyed(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.duckdb"
    connection = connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE processed_observations (
                indicator_id VARCHAR NOT NULL,
                date DATE NOT NULL,
                value DOUBLE,
                processing_version VARCHAR NOT NULL,
                raw_source VARCHAR NOT NULL,
                raw_series_id VARCHAR NOT NULL,
                transformation VARCHAR NOT NULL,
                created_timestamp TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (indicator_id, date, processing_version)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_indicator",
                date(2026, 9, 15),
                1.0,
                "legacy_v1",
                "fred",
                "DGS2",
                "legacy",
                datetime(2026, 9, 16, tzinfo=timezone.utc),
            ),
        )
        with pytest.raises(SchemaMigrationError, match="nonempty legacy"):
            migrate_processed_observation_lineage(connection)
        assert connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0] == 1
    finally:
        connection.close()
