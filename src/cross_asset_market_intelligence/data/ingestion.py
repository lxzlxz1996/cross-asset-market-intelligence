"""Approved Phase 1 raw-ingestion orchestration and persistence."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb

from ..database import initialize_phase_0_schema
from .fred import FredClient, FredObservation
from .raw_persistence import RawObservationRecord, persist_raw_observation_records

APPROVED_TREASURY_FRED_SERIES = frozenset({"DGS2", "DGS10"})
APPROVED_CREDIT_OAS_FRED_SERIES = frozenset({"BAMLC0A0CM", "BAMLH0A0HYM2"})
APPROVED_FRED_SERIES = APPROVED_TREASURY_FRED_SERIES | APPROVED_CREDIT_OAS_FRED_SERIES


def ingest_approved_fred_series(
    client: FredClient,
    connection: duckdb.DuckDBPyConnection,
    series_id: str,
    *,
    observation_start: date | None = None,
    observation_end: date | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """Retrieve and persist one explicitly approved Phase 1 FRED raw series."""
    if series_id not in APPROVED_FRED_SERIES:
        raise ValueError(f"FRED series is not approved for Phase 1 raw ingestion: {series_id}")

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

    records = [
        RawObservationRecord(
            source="fred",
            series_id=observation.series_id,
            observation_date=observation.observation_date,
            value=observation.value,
            publication_timestamp=None,
            vintage=observation.vintage_key,
            metadata={
                "fred_realtime_start": observation.realtime_start,
                "fred_realtime_end": observation.realtime_end,
                "fred_raw_value": observation.raw_value,
                "is_missing": observation.value is None,
            },
        )
        for observation in observations
    ]
    return persist_raw_observation_records(
        connection,
        records,
        retrieved_at=timestamp,
        source_name="FRED",
    )
