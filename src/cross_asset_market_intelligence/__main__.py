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
from .database import connect
from .dashboard.treasury_read_model import current_treasury_dashboard
from .dashboard.sofr_read_model import current_sofr_observation
from .dashboard.credit_read_model import current_credit_dashboard
from .logging_setup import configure_logging


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
        ],
    )
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    arguments = parser.parse_args()

    settings = load_settings()
    logger = configure_logging(settings)
    connection = connect(
        settings.database_path,
        read_only=arguments.command in {
            "show-treasury-dashboard-data",
            "show-sofr-dashboard-data",
            "show-credit-dashboard-data",
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
        else:
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
    finally:
        connection.close()


if __name__ == "__main__":
    main()
