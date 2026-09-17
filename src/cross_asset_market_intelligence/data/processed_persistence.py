"""Atomic persistence of direct processed observations and exact raw lineage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb

from ..exceptions import ProcessingPersistenceError
from ..lineage import RawInputIdentity


@dataclass(frozen=True)
class ProcessedRawRecord:
    """One complete direct processed observation and its sole raw input."""

    processed_observation_id: str
    indicator_id: str
    observation_date: date
    value: float
    input_identity: RawInputIdentity


def persist_processed_raw_records(
    connection: duckdb.DuckDBPyConnection,
    records: Iterable[ProcessedRawRecord],
    *,
    processing_version: str,
    transformation: str,
    subject: str,
) -> int:
    """Persist each parent and its exact raw lineage in one transaction."""
    rows = list(records)
    if not rows:
        return 0
    transaction_started = False
    try:
        connection.execute("BEGIN TRANSACTION")
        transaction_started = True
        inserted = 0
        for record in rows:
            existing = connection.execute(
                "SELECT 1 FROM processed_observations WHERE processed_observation_id = ?",
                (record.processed_observation_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO processed_observations (
                    processed_observation_id, indicator_id, date, value,
                    processing_version, transformation, created_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    record.processed_observation_id,
                    record.indicator_id,
                    record.observation_date,
                    record.value,
                    processing_version,
                    transformation,
                    datetime.now(timezone.utc),
                ),
            )
            input_identity = record.input_identity
            connection.execute(
                """
                INSERT INTO processed_observation_inputs (
                    processed_observation_id, input_role, raw_source, raw_series_id,
                    raw_observation_date, raw_vintage
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    record.processed_observation_id,
                    input_identity.input_role,
                    input_identity.raw_source,
                    input_identity.raw_series_id,
                    input_identity.raw_observation_date,
                    input_identity.raw_vintage,
                ),
            )
            if existing is None:
                inserted += 1
        connection.execute("COMMIT")
        return inserted
    except duckdb.Error as error:
        if transaction_started:
            connection.execute("ROLLBACK")
        raise ProcessingPersistenceError(
            f"Could not persist complete processed {subject} observation lineage"
        ) from error
