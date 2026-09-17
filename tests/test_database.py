from pathlib import Path

from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema


def test_phase_0_schema_creates_foundational_tables(tmp_path: Path) -> None:
    connection = connect(tmp_path / "test.duckdb")
    try:
        initialize_phase_0_schema(connection)
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    finally:
        connection.close()

    assert {"raw_observations", "processed_observations", "signals"} <= tables
