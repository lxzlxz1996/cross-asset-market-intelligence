"""Approved Phase 1 raw-ingestion orchestration and persistence."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import PersistenceError
from .fred import FredClient, FredObservation

APPROVED_FRED_SERIES = frozenset({"DGS2", "DGS10"})


def ingest_approved_fred_series(
    client: FredClient,
    connection: duckdb.DuckDBPyConnection,
    series_id: str,
    *,
    observation_start: date | None = None,
    observation_end: date | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """Retrieve and persist one explicitly approved Phase 1 FRED series."""
    if series_id not in APPROVED_FRED_SERIES:
        raise ValueError(f"FRED series is not approved for Phase 1.2: {series_id}")

    observations = client.fetch_observations(
        series_id, observation_start=observation_start, observation_end=observation_end
    )
    initialize_phase_0_schema(connection)
    inserted = persist_fred_observations(connection, observations)
    if logger is not None:
        logger.info("Persisted %s new raw FRED observations for %s", inserted, series_id)
    return inserted


def persist_fred_observations(
    connection: duckdb.DuckDBPyConnection,
    observations: Iterable[FredObservation],
    *,
    retrieved_at: datetime | None = None,
) -> int:
    """Append raw FRED records idempotently, preserving every real-time period."""
    timestamp = retrieved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")

    rows = [
        (
            "fred",
            observation.series_id,
            observation.observation_date,
            observation.value,
            timestamp,
            None,
            observation.vintage_key,
            json.dumps(
                {
                    "fred_realtime_start": observation.realtime_start,
                    "fred_realtime_end": observation.realtime_end,
                    "fred_raw_value": observation.raw_value,
                    "is_missing": observation.value is None,
                }
            ),
        )
        for observation in observations
    ]
    if not rows:
        return 0

    transaction_started = False
    try:
        connection.execute("BEGIN TRANSACTION")
        transaction_started = True
        inserted = 0
        for row in rows:
            existing = connection.execute(
                """
                SELECT 1 FROM raw_observations
                WHERE source = ? AND series_id = ? AND observation_date = ? AND vintage = ?
                """,
                (row[0], row[1], row[2], row[6]),
            ).fetchone()
            if existing is not None:
                continue
            connection.execute(
                """
                INSERT INTO raw_observations (
                    source, series_id, observation_date, value, retrieval_timestamp,
                    publication_timestamp, vintage, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            inserted += 1
        connection.execute("COMMIT")
        return inserted
    except duckdb.Error as error:
        if transaction_started:
            connection.execute("ROLLBACK")
        raise PersistenceError("Could not persist raw FRED observations") from error
