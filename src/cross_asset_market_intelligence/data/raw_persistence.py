"""Small, source-neutral persistence primitive for validated raw records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb

from ..exceptions import PersistenceError


@dataclass(frozen=True)
class RawObservationRecord:
    """A validated raw observation ready for append-only storage."""

    source: str
    series_id: str
    observation_date: date
    value: float | None
    publication_timestamp: datetime | None
    vintage: str
    metadata: dict[str, object]


def persist_raw_observation_records(
    connection: duckdb.DuckDBPyConnection,
    records: Iterable[RawObservationRecord],
    *,
    retrieved_at: datetime | None = None,
    source_name: str,
) -> int:
    """Append source-validated records idempotently without replacing revisions."""
    timestamp = retrieved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")

    rows = [
        (
            record.source,
            record.series_id,
            record.observation_date,
            record.value,
            timestamp,
            record.publication_timestamp,
            record.vintage,
            json.dumps(record.metadata, sort_keys=True),
        )
        for record in records
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
        raise PersistenceError(f"Could not persist raw {source_name} observations") from error
