"""DuckDB connection and Phase 0 schema utilities."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .exceptions import SchemaMigrationError


PHASE_0_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_observations (
    source VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    value DOUBLE,
    retrieval_timestamp TIMESTAMPTZ NOT NULL,
    publication_timestamp TIMESTAMPTZ,
    vintage VARCHAR NOT NULL DEFAULT 'latest',
    metadata JSON,
    PRIMARY KEY (source, series_id, observation_date, vintage)
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id VARCHAR NOT NULL,
    indicator_id VARCHAR NOT NULL,
    date DATE NOT NULL,
    signal_type VARCHAR NOT NULL,
    value DOUBLE,
    state VARCHAR,
    model_version VARCHAR NOT NULL,
    created_timestamp TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (signal_id, indicator_id, date, model_version)
);
"""

PROCESSED_LINEAGE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS processed_observations (
    processed_observation_id VARCHAR PRIMARY KEY,
    indicator_id VARCHAR NOT NULL,
    date DATE NOT NULL,
    value DOUBLE,
    processing_version VARCHAR NOT NULL,
    transformation VARCHAR NOT NULL,
    created_timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_observation_inputs (
    processed_observation_id VARCHAR NOT NULL,
    input_role VARCHAR NOT NULL,
    raw_source VARCHAR NOT NULL,
    raw_series_id VARCHAR NOT NULL,
    raw_observation_date DATE NOT NULL,
    raw_vintage VARCHAR NOT NULL,
    PRIMARY KEY (
        processed_observation_id,
        input_role,
        raw_source,
        raw_series_id,
        raw_observation_date,
        raw_vintage
    ),
    FOREIGN KEY (processed_observation_id)
        REFERENCES processed_observations(processed_observation_id),
    FOREIGN KEY (raw_source, raw_series_id, raw_observation_date, raw_vintage)
        REFERENCES raw_observations(source, series_id, observation_date, vintage)
);

CREATE TABLE IF NOT EXISTS processed_observation_dependencies (
    output_processed_observation_id VARCHAR NOT NULL,
    input_processed_observation_id VARCHAR NOT NULL,
    input_role VARCHAR NOT NULL,
    PRIMARY KEY (output_processed_observation_id, input_processed_observation_id),
    UNIQUE (output_processed_observation_id, input_role),
    CHECK (output_processed_observation_id != input_processed_observation_id),
    FOREIGN KEY (output_processed_observation_id)
        REFERENCES processed_observations(processed_observation_id),
    FOREIGN KEY (input_processed_observation_id)
        REFERENCES processed_observations(processed_observation_id)
);
"""


def connect(database_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a local DuckDB database, creating parent directories when writable."""
    if not read_only:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database_path), read_only=read_only)


def initialize_phase_0_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the foundation schema and safely evolve processed lineage."""
    connection.execute(PHASE_0_SCHEMA_SQL)
    migrate_processed_observation_lineage(connection)


def migrate_processed_observation_lineage(connection: duckdb.DuckDBPyConnection) -> None:
    """Replace the empty legacy processed table with immutable normalized lineage.

    Raw observations are never changed. A nonempty legacy table raises explicitly
    because its rows cannot be migrated without fabricating raw-vintage lineage.
    """
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    if "processed_observations" not in tables:
        connection.execute(PROCESSED_LINEAGE_SCHEMA_SQL)
        return

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info('processed_observations')").fetchall()
    }
    if "processed_observation_id" in columns:
        connection.execute(PROCESSED_LINEAGE_SCHEMA_SQL)
        return

    row_count = connection.execute("SELECT count(*) FROM processed_observations").fetchone()[0]
    if row_count:
        raise SchemaMigrationError(
            "Cannot migrate nonempty legacy processed_observations without raw-vintage lineage"
        )
    connection.execute("DROP TABLE processed_observations")
    connection.execute(PROCESSED_LINEAGE_SCHEMA_SQL)
