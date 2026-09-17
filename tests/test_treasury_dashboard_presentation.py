from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Literal

from cross_asset_market_intelligence.dashboard.presentation import (
    direct_lineage_rows,
    chart_y_domain,
    format_change,
    format_level,
    historical_chart_rows,
    spread_lineage_rows,
    yield_chart_rows,
)
from cross_asset_market_intelligence.dashboard.treasury_read_model import (
    DashboardChange,
    DirectDashboardLineage,
    RawLineageSummary,
    SpreadDashboardLineage,
    TreasuryDashboardObservation,
)


def _observation(
    *, unit: Literal["percent", "percentage_points"] = "percent", value: float = 4.67
) -> TreasuryDashboardObservation:
    return TreasuryDashboardObservation(
        indicator_id="us_treasury_2y_yield",
        display_name="2-Year Treasury Yield",
        category="Rates",
        subcategory="Treasury yield curve",
        observation_date=date(2026, 9, 15),
        value=value,
        unit=unit,
        processing_version="fixture_v1",
        processed_observation_id="fixture",
        lineage=DirectDashboardLineage(RawLineageSummary("fred", "DGS2", date(2026, 9, 15), "v1")),
        change_1d=DashboardChange(1, 0.02),
        change_5d=DashboardChange(5, -0.03),
        change_20d=DashboardChange(20, None),
    )


def test_levels_and_changes_use_display_only_unit_formatting() -> None:
    assert format_level(_observation()) == "4.67%"
    assert format_level(_observation(unit="percentage_points", value=0.33)) == "0.33pp"
    assert format_change(0.02) == "+0.02 pp"
    assert format_change(-0.03) == "-0.03 pp"
    assert format_change(None) == "N/A"


def test_chart_rows_preserve_selected_history_with_date_only_labels() -> None:
    observations = (
        _observation(value=4.50),
        replace(_observation(value=4.67), observation_date=date(2026, 9, 16)),
    )
    assert historical_chart_rows(observations, "2Y yield (%)") == [
        {"date": "2026-09-15", "series": "2Y yield (%)", "value": 4.50},
        {"date": "2026-09-16", "series": "2Y yield (%)", "value": 4.67},
    ]


def test_yield_chart_rows_are_chronological_and_preserve_unmodified_values() -> None:
    two_year = (
        replace(_observation(value=4.67), observation_date=date(2026, 9, 16)),
        _observation(value=4.50),
    )
    ten_year = (replace(_observation(value=5.00), observation_date=date(2026, 9, 15)),)

    rows = yield_chart_rows(two_year, ten_year)

    assert [row["date"] for row in rows] == ["2026-09-15", "2026-09-15", "2026-09-16"]
    assert [(row["series"], row["value"]) for row in rows] == [
        ("10Y yield (%)", 5.00),
        ("2Y yield (%)", 4.50),
        ("2Y yield (%)", 4.67),
    ]
    assert chart_y_domain(rows) == [4.425, 5.075]


def test_direct_and_spread_lineage_rows_preserve_exact_identifiers() -> None:
    direct = _observation()
    direct_row = direct_lineage_rows(direct)[0]
    spread = replace(
        _observation(unit="percentage_points", value=0.33),
        indicator_id="us_treasury_10y_minus_2y",
        lineage=SpreadDashboardLineage(
            "ten_processed",
            "two_processed",
            RawLineageSummary("fred", "DGS10", date(2026, 9, 15), "ten_vintage"),
            RawLineageSummary("fred", "DGS2", date(2026, 9, 15), "two_vintage"),
        ),
    )
    spread_row = spread_lineage_rows(spread)[0]

    assert direct_row["raw_vintage"] == "v1"
    assert direct_row["raw_series_id"] == "DGS2"
    assert spread_row["ten_year_processed_observation_id"] == "ten_processed"
    assert spread_row["two_year_processed_observation_id"] == "two_processed"
    assert spread_row["ten_year_raw_vintage"] == "ten_vintage"
    assert spread_row["two_year_raw_vintage"] == "two_vintage"
