from __future__ import annotations

from datetime import date

from cross_asset_market_intelligence.dashboard import streamlit_app
from cross_asset_market_intelligence.dashboard.credit_read_model import CreditDashboardObservation
from cross_asset_market_intelligence.dashboard.presentation import (
    direct_lineage_rows,
    format_change,
    format_level,
    historical_chart_rows,
)
from cross_asset_market_intelligence.dashboard.read_model_common import DashboardChange
from cross_asset_market_intelligence.dashboard.treasury_read_model import (
    DirectDashboardLineage,
    RawLineageSummary,
)


def _observation(
    *,
    indicator_id: str = "us_investment_grade_oas",
    value: float = 0.78,
    observation_date: date = date(2026, 9, 16),
) -> CreditDashboardObservation:
    series_id = "BAMLC0A0CM" if indicator_id == "us_investment_grade_oas" else "BAMLH0A0HYM2"
    display_name = "Investment Grade OAS" if indicator_id == "us_investment_grade_oas" else "High Yield OAS"
    return CreditDashboardObservation(
        indicator_id=indicator_id,
        display_name=display_name,
        category="Credit",
        subcategory="Investment-grade spreads",
        observation_date=observation_date,
        value=value,
        unit="percentage_points",
        processing_version="fixture_v1",
        processed_observation_id=f"{indicator_id}-fixture",
        lineage=DirectDashboardLineage(
            RawLineageSummary("fred", series_id, observation_date, "fred_realtime:2026-09-17:2026-09-17")
        ),
        change_1d=DashboardChange(1, -0.02),
        change_5d=DashboardChange(5, -0.03),
        change_20d=DashboardChange(20, None),
    )


def test_credit_presentation_helpers_preserve_percentage_point_levels_history_and_lineage() -> None:
    observation = _observation()

    assert format_level(observation) == "0.78pp"
    assert format_change(observation.change_1d.value) == "-0.02 pp"
    assert format_change(observation.change_20d.value) == "N/A"
    assert historical_chart_rows((observation,), "Investment Grade OAS (pp)") == [
        {"date": "2026-09-16", "series": "Investment Grade OAS (pp)", "value": 0.78}
    ]
    lineage = direct_lineage_rows(observation)[0]
    assert lineage["raw_source"] == "fred"
    assert lineage["raw_series_id"] == "BAMLC0A0CM"
    assert lineage["raw_vintage"] == "fred_realtime:2026-09-17:2026-09-17"


class _Column:
    def __enter__(self) -> _Column:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


class _FakeStreamlit:
    def __init__(self) -> None:
        self.subheaders: list[str] = []
        self.markdowns: list[str] = []
        self.infos: list[str] = []

    def subheader(self, value: str) -> None:
        self.subheaders.append(value)

    def columns(self, count: int) -> list[_Column]:
        return [_Column() for _ in range(count)]

    def markdown(self, value: str) -> None:
        self.markdowns.append(value)

    def info(self, value: str) -> None:
        self.infos.append(value)


def test_credit_section_uses_distinct_read_model_histories_and_separate_charts(monkeypatch) -> None:
    investment_grade = _observation()
    high_yield = _observation(indicator_id="us_high_yield_oas", value=2.70)
    fake_streamlit = _FakeStreamlit()
    rendered_cards: list[CreditDashboardObservation] = []
    rendered_charts: list[tuple[list[dict[str, object]], str]] = []

    def fake_history(connection, indicator_id: str):
        assert connection == "read-only-connection"
        return (investment_grade,) if indicator_id == "us_investment_grade_oas" else (high_yield,)

    monkeypatch.setattr(streamlit_app, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_app, "credit_history", fake_history)
    monkeypatch.setattr(streamlit_app, "_render_observation_card", rendered_cards.append)
    monkeypatch.setattr(
        streamlit_app,
        "_render_chart",
        lambda rows, y_title: rendered_charts.append((rows, y_title)),
    )

    streamlit_app._render_credit(
        "read-only-connection",
        {
            "us_investment_grade_oas": investment_grade,
            "us_high_yield_oas": high_yield,
        },
    )

    assert fake_streamlit.subheaders == ["Credit"]
    assert fake_streamlit.markdowns == ["**Credit history**"]
    assert rendered_cards == [investment_grade, high_yield]
    assert rendered_charts == [
        ([{"date": "2026-09-16", "series": "Investment Grade OAS (pp)", "value": 0.78}], "OAS (pp)"),
        ([{"date": "2026-09-16", "series": "High Yield OAS (pp)", "value": 2.70}], "OAS (pp)"),
    ]
