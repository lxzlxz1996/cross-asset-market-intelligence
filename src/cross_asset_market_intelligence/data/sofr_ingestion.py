"""Phase 1.6A orchestration for official FRBNY SOFR raw ingestion only."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

import duckdb

from ..database import initialize_phase_0_schema
from .frbny_sofr import FRBNY_SOFR_SERIES_ID, FRBNY_SOURCE, FrbnySofrClient, FrbnySofrObservation
from .raw_persistence import RawObservationRecord, persist_raw_observation_records


def ingest_sofr(
    client: FrbnySofrClient,
    connection: duckdb.DuckDBPyConnection,
    *,
    observation_start: date | None = None,
    observation_end: date | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """Retrieve and append only official FRBNY SOFR raw observations."""
    observations = client.fetch_observations(
        observation_start=observation_start,
        observation_end=observation_end,
    )
    initialize_phase_0_schema(connection)
    inserted = persist_sofr_observations(connection, observations)
    if logger is not None:
        logger.info("Persisted %s new raw FRBNY SOFR observations", inserted)
    return inserted


def persist_sofr_observations(
    connection: duckdb.DuckDBPyConnection,
    observations: Iterable[FrbnySofrObservation],
    *,
    retrieved_at: datetime | None = None,
) -> int:
    """Persist native-percent official SOFR records with no invented publication time."""
    records = [
        RawObservationRecord(
            source=FRBNY_SOURCE,
            series_id=FRBNY_SOFR_SERIES_ID,
            observation_date=observation.effective_date,
            value=observation.percent_rate,
            publication_timestamp=None,
            vintage=observation.vintage_key,
            metadata={
                "frbny_effective_date": observation.effective_date.isoformat(),
                "frbny_percent_rate": observation.percent_rate,
                "frbny_revision_indicator": observation.revision_indicator,
                "frbny_source_record": observation.source_record,
            },
        )
        for observation in observations
    ]
    return persist_raw_observation_records(
        connection,
        records,
        retrieved_at=retrieved_at,
        source_name="FRBNY SOFR",
    )
