"""Explicit, manual operational orchestration for approved Phase 1 pipelines."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import duckdb

from ..database import initialize_phase_0_schema
from .credit_oas_processing import process_credit_oas
from .fred import FredClient
from .frbny_sofr import FrbnySofrClient
from .ingestion import (
    APPROVED_CREDIT_OAS_FRED_SERIES,
    APPROVED_TREASURY_FRED_SERIES,
    ingest_approved_fred_series,
)
from .sofr_ingestion import ingest_sofr
from .sofr_processing import process_sofr
from .treasury_processing import process_approved_fred_treasuries
from .treasury_spread_processing import process_treasury_spread


SUPPORTED_REFRESH_PIPELINES = frozenset({"treasury", "sofr", "credit"})


@dataclass(frozen=True)
class RefreshRun:
    """Durable operational outcome for one explicitly requested pipeline attempt."""

    refresh_run_id: str
    pipeline_name: str
    started_timestamp: datetime
    completed_timestamp: datetime | None
    status: str
    stage: str
    records_inserted: int | None
    records_skipped: int | None
    error_type: str | None
    error_message: str | None


def refresh_market_data(
    connection: duckdb.DuckDBPyConnection,
    pipeline_name: str,
    *,
    observation_start: date | None = None,
    observation_end: date | None = None,
    fred_client: FredClient | None = None,
    sofr_client: FrbnySofrClient | None = None,
    logger: logging.Logger | None = None,
) -> RefreshRun:
    """Run one selected pipeline and persist its operational outcome.

    This function is deliberately manual: it does not schedule itself or invoke
    any governance-pending source. Existing source adapters and processors remain
    the sole owners of market-data retrieval and transformation.
    """
    if pipeline_name not in SUPPORTED_REFRESH_PIPELINES:
        raise ValueError(f"Unsupported refresh pipeline: {pipeline_name}")

    initialize_phase_0_schema(connection)
    started_at = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    _insert_running_run(connection, run_id, pipeline_name, started_at)
    counts = _RefreshCounts()
    stage = "ingestion"
    try:
        if pipeline_name == "treasury":
            stage = "ingestion"
            client = fred_client or FredClient.from_environment()
            for series_id in sorted(APPROVED_TREASURY_FRED_SERIES):
                counts.inserted += ingest_approved_fred_series(
                    client,
                    connection,
                    series_id,
                    observation_start=observation_start,
                    observation_end=observation_end,
                    logger=logger,
                )
            stage = "direct_processing"
            result = process_approved_fred_treasuries(connection, logger=logger)
            counts.inserted += result.inserted
            counts.skipped += result.skipped_missing
            stage = "spread_processing"
            result = process_treasury_spread(connection, logger=logger)
            counts.inserted += result.inserted
            counts.skipped += result.skipped_missing_input
        elif pipeline_name == "sofr":
            stage = "ingestion"
            counts.inserted += ingest_sofr(
                sofr_client or FrbnySofrClient(),
                connection,
                observation_start=observation_start,
                observation_end=observation_end,
                logger=logger,
            )
            stage = "processing"
            result = process_sofr(connection, logger=logger)
            counts.inserted += result.inserted
            counts.skipped += result.skipped_missing
        else:
            stage = "ingestion"
            client = fred_client or FredClient.from_environment()
            for series_id in sorted(APPROVED_CREDIT_OAS_FRED_SERIES):
                counts.inserted += ingest_approved_fred_series(
                    client,
                    connection,
                    series_id,
                    observation_start=observation_start,
                    observation_end=observation_end,
                    logger=logger,
                )
            stage = "processing"
            result = process_credit_oas(connection, logger=logger)
            counts.inserted += result.inserted
            counts.skipped += result.skipped_missing
    except Exception as error:
        return _complete_run(
            connection,
            run_id,
            pipeline_name,
            started_at,
            status="failed",
            stage=stage,
            counts=counts,
            error=error,
        )

    return _complete_run(
        connection,
        run_id,
        pipeline_name,
        started_at,
        status="succeeded",
        stage="complete",
        counts=counts,
        error=None,
    )


@dataclass
class _RefreshCounts:
    inserted: int = 0
    skipped: int = 0


def _insert_running_run(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    pipeline_name: str,
    started_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO refresh_runs (
            refresh_run_id, pipeline_name, started_timestamp, completed_timestamp,
            status, stage, records_inserted, records_skipped, error_type, error_message
        ) VALUES (?, ?, ?, NULL, 'running', 'starting', NULL, NULL, NULL, NULL)
        """,
        (run_id, pipeline_name, started_at),
    )


def _complete_run(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    pipeline_name: str,
    started_at: datetime,
    *,
    status: str,
    stage: str,
    counts: _RefreshCounts,
    error: Exception | None,
) -> RefreshRun:
    completed_at = datetime.now(timezone.utc)
    error_type = type(error).__name__ if error is not None else None
    error_message = _safe_error_message(error) if error is not None else None
    connection.execute(
        """
        UPDATE refresh_runs
        SET completed_timestamp = ?, status = ?, stage = ?, records_inserted = ?,
            records_skipped = ?, error_type = ?, error_message = ?
        WHERE refresh_run_id = ?
        """,
        (
            completed_at,
            status,
            stage,
            counts.inserted,
            counts.skipped,
            error_type,
            error_message,
            run_id,
        ),
    )
    return RefreshRun(
        refresh_run_id=run_id,
        pipeline_name=pipeline_name,
        started_timestamp=started_at,
        completed_timestamp=completed_at,
        status=status,
        stage=stage,
        records_inserted=counts.inserted,
        records_skipped=counts.skipped,
        error_type=error_type,
        error_message=error_message,
    )


def _safe_error_message(error: Exception) -> str:
    """Retain a concise diagnostic while excluding common secret-bearing fragments."""
    message = str(error).replace("\n", " ").replace("\r", " ").strip()
    message = re.sub(r"(?i)(api[_ -]?key|token|secret|password)\s*[=:]\s*[^\s,;&]+", r"\1=[redacted]", message)
    message = re.sub(r"(?i)([?&](?:api[_-]?key|token|secret|password)=)[^&#\s]+", r"\1[redacted]", message)
    for candidate in re.findall(r"https?://[^\s]+", message):
        parts = urlsplit(candidate)
        if parts.query or parts.username or parts.password:
            message = message.replace(candidate, urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))
    return message[:500] or type(error).__name__
