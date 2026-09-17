from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.lineage import (
    ProcessedDependencyIdentity,
    RawInputIdentity,
    derived_processed_observation_id,
)


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "dependencies.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _insert_processed(
    connection: duckdb.DuckDBPyConnection, identifier: str, indicator_id: str
) -> None:
    connection.execute(
        """
        INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identifier,
            indicator_id,
            date(2026, 9, 15),
            1.0,
            "synthetic_fixture_v1",
            "synthetic_fixture_only",
            datetime(2026, 9, 16, tzinfo=timezone.utc),
        ),
    )


def _insert_dependency(
    connection: duckdb.DuckDBPyConnection, output: str, input_: str, role: str
) -> None:
    connection.execute(
        """
        INSERT INTO processed_observation_dependencies VALUES (?, ?, ?)
        """,
        (output, input_, role),
    )


def test_one_processed_output_can_depend_on_one_processed_observation(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_processed(connection, "input", "synthetic_input")
        _insert_processed(connection, "output", "synthetic_output")
        _insert_dependency(connection, "output", "input", "source")
        assert connection.execute("SELECT count(*) FROM processed_observation_dependencies").fetchone()[0] == 1
    finally:
        connection.close()


def test_derived_output_preserves_two_distinct_dependency_roles(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_processed(connection, "ten", "synthetic_ten_year")
        _insert_processed(connection, "two", "synthetic_two_year")
        _insert_processed(connection, "derived", "synthetic_derived")
        _insert_dependency(connection, "derived", "two", "two_year")
        _insert_dependency(connection, "derived", "ten", "ten_year")
        roles = connection.execute(
            """
            SELECT input_role, input_processed_observation_id
            FROM processed_observation_dependencies
            ORDER BY input_role
            """
        ).fetchall()
    finally:
        connection.close()

    assert roles == [("ten_year", "ten"), ("two_year", "two")]


def test_nonexistent_output_or_input_and_self_dependency_are_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_processed(connection, "existing", "synthetic_input")
        with pytest.raises(duckdb.Error):
            _insert_dependency(connection, "missing", "existing", "source")
        with pytest.raises(duckdb.Error):
            _insert_dependency(connection, "existing", "missing", "source")
        with pytest.raises(duckdb.Error):
            _insert_dependency(connection, "existing", "existing", "source")
    finally:
        connection.close()


def test_duplicate_dependency_role_for_one_output_is_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        _insert_processed(connection, "input_one", "synthetic_input")
        _insert_processed(connection, "input_two", "synthetic_input")
        _insert_processed(connection, "output", "synthetic_output")
        _insert_dependency(connection, "output", "input_one", "source")
        with pytest.raises(duckdb.Error):
            _insert_dependency(connection, "output", "input_two", "source")
    finally:
        connection.close()


def test_derived_identity_is_stable_and_dependency_order_is_canonicalized() -> None:
    dependencies = [
        ProcessedDependencyIdentity("ten_year", "proc_sha256:ten"),
        ProcessedDependencyIdentity("two_year", "proc_sha256:two"),
    ]
    first = derived_processed_observation_id(
        "synthetic_derived", date(2026, 9, 15), "synthetic_derived_v1", dependencies
    )
    second = derived_processed_observation_id(
        "synthetic_derived", date(2026, 9, 15), "synthetic_derived_v1", list(reversed(dependencies))
    )

    assert first == second


def test_upstream_identity_or_derived_methodology_change_changes_derived_identity() -> None:
    dependencies = [
        ProcessedDependencyIdentity("ten_year", "proc_sha256:ten_v1"),
        ProcessedDependencyIdentity("two_year", "proc_sha256:two_v1"),
    ]
    revised_dependencies = [
        ProcessedDependencyIdentity("ten_year", "proc_sha256:ten_v2"),
        ProcessedDependencyIdentity("two_year", "proc_sha256:two_v1"),
    ]
    first = derived_processed_observation_id(
        "synthetic_derived", date(2026, 9, 15), "synthetic_derived_v1", dependencies
    )
    revised_input = derived_processed_observation_id(
        "synthetic_derived", date(2026, 9, 15), "synthetic_derived_v1", revised_dependencies
    )
    revised_methodology = derived_processed_observation_id(
        "synthetic_derived", date(2026, 9, 15), "synthetic_derived_v2", dependencies
    )

    assert first != revised_input
    assert first != revised_methodology


def test_transitive_lineage_reaches_the_exact_raw_observation(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        connection.execute(
            """
            INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "fred",
                "DGS10",
                date(2026, 9, 15),
                4.5,
                datetime(2026, 9, 16, tzinfo=timezone.utc),
                None,
                "fred_realtime:2026-09-16:9999-12-31",
                "{}",
            ),
        )
        _insert_processed(connection, "upstream", "synthetic_ten_year")
        connection.execute(
            """
            INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "upstream",
                "source",
                "fred",
                "DGS10",
                date(2026, 9, 15),
                "fred_realtime:2026-09-16:9999-12-31",
            ),
        )
        _insert_processed(connection, "derived", "synthetic_derived")
        _insert_dependency(connection, "derived", "upstream", "ten_year")
        raw_series = connection.execute(
            """
            SELECT raw.series_id
            FROM processed_observation_dependencies AS dependency
            JOIN processed_observation_inputs AS input
                ON dependency.input_processed_observation_id = input.processed_observation_id
            JOIN raw_observations AS raw
                ON input.raw_source = raw.source
                AND input.raw_series_id = raw.series_id
                AND input.raw_observation_date = raw.observation_date
                AND input.raw_vintage = raw.vintage
            WHERE dependency.output_processed_observation_id = 'derived'
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert raw_series == "DGS10"


def test_schema_initialization_preserves_existing_processed_raw_lineage_and_raw_rows(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    try:
        raw_row = (
            "fred",
            "DGS2",
            date(2026, 9, 15),
            4.25,
            datetime(2026, 9, 16, tzinfo=timezone.utc),
            None,
            "fred_realtime:2026-09-16:9999-12-31",
            "{}",
        )
        connection.execute("INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", raw_row)
        _insert_processed(connection, "direct", "synthetic_direct")
        connection.execute(
            """
            INSERT INTO processed_observation_inputs VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "direct",
                "source",
                "fred",
                "DGS2",
                date(2026, 9, 15),
                "fred_realtime:2026-09-16:9999-12-31",
            ),
        )
        raw_before = connection.execute("SELECT * FROM raw_observations").fetchall()
        direct_before = connection.execute("SELECT * FROM processed_observations").fetchall()
        inputs_before = connection.execute("SELECT * FROM processed_observation_inputs").fetchall()
        initialize_phase_0_schema(connection)
        raw_after = connection.execute("SELECT * FROM raw_observations").fetchall()
        direct_after = connection.execute("SELECT * FROM processed_observations").fetchall()
        inputs_after = connection.execute("SELECT * FROM processed_observation_inputs").fetchall()
    finally:
        connection.close()

    assert raw_after == raw_before
    assert direct_after == direct_before
    assert inputs_after == inputs_before
