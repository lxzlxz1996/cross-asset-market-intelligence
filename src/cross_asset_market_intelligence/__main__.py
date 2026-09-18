"""Minimal manual entry point for approved Phase 1 raw-data workflows."""

from __future__ import annotations

import argparse
from datetime import date

from .config import load_settings
from .data.fred import FredClient
from .data.ingestion import (
    APPROVED_CREDIT_OAS_FRED_SERIES,
    APPROVED_TREASURY_FRED_SERIES,
    ingest_approved_fred_series,
)
from .data.frbny_sofr import FrbnySofrClient
from .data.credit_oas_processing import process_credit_oas
from .data.sofr_ingestion import ingest_sofr
from .data.sofr_processing import process_sofr
from .data.treasury_processing import process_approved_fred_treasuries
from .data.treasury_spread_processing import process_treasury_spread
from .data.refresh_orchestration import SUPPORTED_REFRESH_PIPELINES, refresh_market_data
from .database import connect
from .dashboard.treasury_read_model import current_treasury_dashboard
from .dashboard.sofr_read_model import current_sofr_observation
from .dashboard.credit_read_model import current_credit_dashboard
from .dashboard.data_health_read_model import current_data_health
from .logging_setup import configure_logging
from .signals.sofr_rate_state import generate_sofr_rate_state
from .signals.sofr_rate_state_v2 import generate_sofr_rate_state_v2
from .signals.sofr_rate_state_v3 import generate_sofr_rate_state_v3


def _format_change(value: float | None) -> str:
    return "N/A" if value is None else f"{value} percentage_points"


def main() -> None:
    parser = argparse.ArgumentParser(description="Approved Phase 1 raw-data workflows")
    parser.add_argument(
        "command",
        choices=[
            "ingest-fred-treasury",
            "ingest-credit-oas",
            "process-credit-oas",
            "ingest-sofr",
            "process-sofr",
            "process-fred-treasury",
            "process-treasury-spread",
            "show-treasury-dashboard-data",
            "show-sofr-dashboard-data",
            "show-credit-dashboard-data",
            "refresh-market-data",
            "show-data-health",
            "generate-sofr-rate-state",
        ],
    )
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--pipeline", choices=sorted(SUPPORTED_REFRESH_PIPELINES))
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--version", choices=("v1", "v2", "v3"), default="v1")
    arguments = parser.parse_args()
    if arguments.command == "refresh-market-data" and arguments.pipeline is None:
        parser.error("--pipeline is required for refresh-market-data")

    settings = load_settings()
    logger = configure_logging(settings)
    connection = connect(
        settings.database_path,
        read_only=arguments.command in {
            "show-treasury-dashboard-data",
            "show-sofr-dashboard-data",
            "show-credit-dashboard-data",
            "show-data-health",
        },
    )
    try:
        if arguments.command == "ingest-fred-treasury":
            client = FredClient.from_environment()
            for series_id in sorted(APPROVED_TREASURY_FRED_SERIES):
                ingest_approved_fred_series(
                    client,
                    connection,
                    series_id,
                    observation_start=arguments.start,
                    observation_end=arguments.end,
                    logger=logger,
                )
        elif arguments.command == "ingest-credit-oas":
            client = FredClient.from_environment()
            completed: list[str] = []
            try:
                for series_id in sorted(APPROVED_CREDIT_OAS_FRED_SERIES):
                    ingest_approved_fred_series(
                        client,
                        connection,
                        series_id,
                        observation_start=arguments.start,
                        observation_end=arguments.end,
                        logger=logger,
                    )
                    completed.append(series_id)
            except Exception as error:
                raise RuntimeError(
                    f"Credit OAS ingestion did not complete; persisted series: {completed}"
                ) from error
        elif arguments.command == "ingest-sofr":
            ingest_sofr(
                FrbnySofrClient(),
                connection,
                observation_start=arguments.start,
                observation_end=arguments.end,
                logger=logger,
            )
        elif arguments.command == "process-credit-oas":
            process_credit_oas(connection, logger=logger)
        elif arguments.command == "process-sofr":
            process_sofr(connection, logger=logger)
        elif arguments.command == "process-fred-treasury":
            process_approved_fred_treasuries(connection, logger=logger)
        elif arguments.command == "process-treasury-spread":
            process_treasury_spread(connection, logger=logger)
        elif arguments.command == "show-treasury-dashboard-data":
            for indicator_id, observation in current_treasury_dashboard(connection).items():
                if observation is None:
                    print(f"{indicator_id} unavailable")
                else:
                    print(
                        f"{observation.indicator_id} {observation.value} {observation.unit} "
                        f"as of {observation.observation_date}; "
                        f"1D {_format_change(observation.change_1d.value)}; "
                        f"5D {_format_change(observation.change_5d.value)}; "
                        f"20D {_format_change(observation.change_20d.value)}"
                    )
        elif arguments.command == "show-sofr-dashboard-data":
            observation = current_sofr_observation(connection)
            if observation is None:
                print("sofr unavailable")
            else:
                print(
                    f"{observation.indicator_id} {observation.value} {observation.unit} "
                    f"as of {observation.observation_date}; "
                    f"1D {_format_change(observation.change_1d.value)}; "
                    f"5D {_format_change(observation.change_5d.value)}; "
                    f"20D {_format_change(observation.change_20d.value)}"
                )
        elif arguments.command == "show-credit-dashboard-data":
            for indicator_id, observation in current_credit_dashboard(connection).items():
                if observation is None:
                    print(f"{indicator_id} unavailable")
                else:
                    print(
                        f"{observation.indicator_id} {observation.value} {observation.unit} "
                        f"as of {observation.observation_date}; "
                        f"1D {_format_change(observation.change_1d.value)}; "
                        f"5D {_format_change(observation.change_5d.value)}; "
                        f"20D {_format_change(observation.change_20d.value)}"
                    )
        elif arguments.command == "refresh-market-data":
            run = refresh_market_data(
                connection,
                arguments.pipeline,
                observation_start=arguments.start,
                observation_end=arguments.end,
                logger=logger,
            )
            print(
                f"{run.pipeline_name} {run.status} at {run.stage}; "
                f"inserted {run.records_inserted}; skipped {run.records_skipped}; "
                f"run {run.refresh_run_id}"
            )
            if run.error_type is not None:
                print(f"{run.error_type}: {run.error_message}")
        elif arguments.command == "generate-sofr-rate-state":
            generator = {
                "v1": generate_sofr_rate_state,
                "v2": generate_sofr_rate_state_v2,
                "v3": generate_sofr_rate_state_v3,
            }[arguments.version]
            result = generator(
                connection,
                as_of_observation_date=arguments.as_of,
            )
            action = "inserted" if result.observation_inserted else "replayed"
            print(
                f"{result.observation.signal_id}/{result.observation.signal_version} {action}; "
                f"as of {result.observation.as_of_observation_date}; "
                f"quality {result.observation.evidence_quality.value}; "
                f"observation {result.observation.signal_observation_id}"
            )
        else:
            for record in current_data_health(connection):
                latest_date = (
                    "N/A"
                    if record.latest_observation_date is None
                    else record.latest_observation_date.isoformat()
                )
                status = record.latest_refresh_status or "not_attempted"
                print(
                    f"{record.indicator_id} {record.availability}; "
                    f"latest data {latest_date}; latest refresh {status}; "
                    f"pipeline {record.pipeline_name or 'source_pending'}"
                )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
