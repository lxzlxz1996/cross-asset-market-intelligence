"""DuckDB connection and Phase 0 schema utilities."""

from __future__ import annotations

from pathlib import Path

import duckdb


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

CREATE TABLE IF NOT EXISTS processed_observations (
    indicator_id VARCHAR NOT NULL,
    date DATE NOT NULL,
    value DOUBLE,
    processing_version VARCHAR NOT NULL,
    raw_source VARCHAR NOT NULL,
    raw_series_id VARCHAR NOT NULL,
    transformation VARCHAR NOT NULL,
    created_timestamp TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (indicator_id, date, processing_version)
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


def connect(database_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a local DuckDB database, creating parent directories when writable."""
    if not read_only:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database_path), read_only=read_only)


def initialize_phase_0_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Create only the raw, processed, and signal tables needed by the foundation."""
    connection.execute(PHASE_0_SCHEMA_SQL)
