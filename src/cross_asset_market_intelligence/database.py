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


OPERATIONAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS refresh_runs (
    refresh_run_id VARCHAR PRIMARY KEY,
    pipeline_name VARCHAR NOT NULL,
    started_timestamp TIMESTAMPTZ NOT NULL,
    completed_timestamp TIMESTAMPTZ,
    status VARCHAR NOT NULL,
    stage VARCHAR NOT NULL,
    records_inserted INTEGER,
    records_skipped INTEGER,
    error_type VARCHAR,
    error_message VARCHAR
);
"""


SIGNAL_ENGINE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS signal_definitions (
    signal_id VARCHAR NOT NULL,
    signal_version VARCHAR NOT NULL,
    indicator_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    economic_question VARCHAR NOT NULL,
    economic_hypothesis VARCHAR,
    what_it_measures VARCHAR NOT NULL,
    what_it_does_not_mean VARCHAR NOT NULL,
    methodology_description VARCHAR NOT NULL,
    parameter_definition JSON NOT NULL,
    limitations VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    created_timestamp TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (signal_id, signal_version),
    CHECK (status IN ('draft', 'active', 'deprecated'))
);

CREATE TABLE IF NOT EXISTS signal_observations (
    signal_observation_id VARCHAR NOT NULL,
    signal_id VARCHAR NOT NULL,
    signal_version VARCHAR NOT NULL,
    indicator_id VARCHAR NOT NULL,
    as_of_observation_date DATE NOT NULL,
    information_available_at TIMESTAMPTZ,
    information_available_date DATE,
    availability_precision VARCHAR NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL,
    level_state VARCHAR,
    direction_state VARCHAR,
    anomaly_state VARCHAR,
    evidence_quality VARCHAR NOT NULL,
    evidence JSON NOT NULL,
    parameters_used JSON NOT NULL,
    explanation VARCHAR NOT NULL,
    quality_reasons JSON NOT NULL,
    PRIMARY KEY (signal_observation_id),
    FOREIGN KEY (signal_id, signal_version)
        REFERENCES signal_definitions(signal_id, signal_version),
    CHECK (availability_precision IN ('exact_timestamp', 'date_only', 'source_schedule', 'unknown')),
    CHECK (evidence_quality IN ('sufficient', 'limited', 'insufficient')),
    CHECK (
        (availability_precision = 'exact_timestamp'
            AND information_available_at IS NOT NULL
            AND information_available_date IS NULL)
        OR (availability_precision = 'date_only'
            AND information_available_at IS NULL
            AND information_available_date IS NOT NULL)
        OR (availability_precision IN ('source_schedule', 'unknown')
            AND information_available_at IS NULL
            AND information_available_date IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS signal_observation_inputs (
    signal_observation_id VARCHAR NOT NULL,
    processed_observation_id VARCHAR NOT NULL,
    input_role VARCHAR NOT NULL,
    window_position INTEGER,
    PRIMARY KEY (signal_observation_id, processed_observation_id, input_role),
    FOREIGN KEY (signal_observation_id)
        REFERENCES signal_observations(signal_observation_id),
    FOREIGN KEY (processed_observation_id)
        REFERENCES processed_observations(processed_observation_id),
    CHECK (window_position IS NULL OR window_position >= 0)
);
"""


def connect(database_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a local DuckDB database, creating parent directories when writable."""
    if not read_only:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database_path), read_only=read_only)


def initialize_phase_0_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the foundation, lineage, operational, and additive signal schemas."""
    connection.execute(PHASE_0_SCHEMA_SQL)
    migrate_processed_observation_lineage(connection)
    connection.execute(OPERATIONAL_SCHEMA_SQL)
    migrate_signal_engine_schema(connection)


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


def migrate_signal_engine_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Install additive Phase 2 signal contracts without changing the legacy placeholder."""
    connection.execute(SIGNAL_ENGINE_SCHEMA_SQL)
