"""Pure formatting and chart-shaping helpers for the Treasury Streamlit page."""

from __future__ import annotations

from .treasury_read_model import TreasuryDashboardObservation


def format_level(observation: TreasuryDashboardObservation) -> str:
    """Format a dashboard level without changing its underlying unit contract."""
    suffix = "%" if observation.unit == "percent" else "pp"
    return f"{observation.value:.2f}{suffix}"


def format_change(value: float | None) -> str:
    """Format a descriptive change, preserving explicit unavailable state."""
    return "N/A" if value is None else f"{value:+.2f} pp"


def historical_chart_rows(
    observations: tuple[TreasuryDashboardObservation, ...],
    column_name: str,
) -> list[dict[str, object]]:
    """Shape deterministic selected history for a native Streamlit chart."""
    return [{"date": item.observation_date, column_name: item.value} for item in observations]


def direct_lineage_rows(observation: TreasuryDashboardObservation) -> list[dict[str, object]]:
    """Return concise direct raw-lineage fields for display."""
    lineage = observation.lineage
    if not hasattr(lineage, "raw_input"):
        return []
    raw = lineage.raw_input
    return [
        {
            "processed_observation_id": observation.processed_observation_id,
            "processing_version": observation.processing_version,
            "raw_source": raw.source,
            "raw_series_id": raw.series_id,
            "raw_observation_date": raw.observation_date,
            "raw_vintage": raw.vintage,
        }
    ]


def spread_lineage_rows(observation: TreasuryDashboardObservation) -> list[dict[str, object]]:
    """Return concise immediate and transitive spread lineage fields for display."""
    lineage = observation.lineage
    if not hasattr(lineage, "ten_year_processed_observation_id"):
        return []
    return [
        {
            "spread_processed_observation_id": observation.processed_observation_id,
            "spread_processing_version": observation.processing_version,
            "ten_year_processed_observation_id": lineage.ten_year_processed_observation_id,
            "ten_year_raw_series_id": lineage.ten_year_raw_input.series_id,
            "ten_year_raw_observation_date": lineage.ten_year_raw_input.observation_date,
            "ten_year_raw_vintage": lineage.ten_year_raw_input.vintage,
            "two_year_processed_observation_id": lineage.two_year_processed_observation_id,
            "two_year_raw_series_id": lineage.two_year_raw_input.series_id,
            "two_year_raw_observation_date": lineage.two_year_raw_input.observation_date,
            "two_year_raw_vintage": lineage.two_year_raw_input.vintage,
        }
    ]
