from __future__ import annotations

from contextlib import nullcontext
from datetime import date

from cross_asset_market_intelligence.dashboard.data_health_read_model import DataHealthRecord
from cross_asset_market_intelligence.dashboard import streamlit_app


class _StreamlitCapture:
    def __init__(self) -> None:
        self.subheaders: list[str] = []
        self.captions: list[str] = []
        self.dataframes: list[list[dict[str, object]]] = []
        self.expanders: list[str] = []

    def subheader(self, value: str) -> None:
        self.subheaders.append(value)

    def caption(self, value: str) -> None:
        self.captions.append(value)

    def dataframe(self, value: list[dict[str, object]], **_: object) -> None:
        self.dataframes.append(value)

    def expander(self, value: str):
        self.expanders.append(value)
        return nullcontext()


def test_data_status_rendering_is_read_only_and_exposes_failed_stage(monkeypatch) -> None:
    capture = _StreamlitCapture()
    records = (
        DataHealthRecord(
            indicator_id="sofr",
            display_name="SOFR",
            pipeline_name="sofr",
            source_identity="FRBNY / SOFR",
            availability="available",
            latest_observation_date=date(2026, 9, 16),
            latest_observation_value=3.62,
            latest_refresh_status="failed",
            latest_refresh_attempt_timestamp=None,
            latest_successful_refresh_timestamp=None,
            latest_refresh_stage="processing",
            latest_refresh_error_type="ValueError",
            latest_refresh_error_message="processing failure",
        ),
    )
    monkeypatch.setattr(streamlit_app, "st", capture)

    streamlit_app._render_data_health(records)

    assert capture.subheaders == ["Data status"]
    assert capture.dataframes[0][0]["Availability"] == "available"
    assert capture.expanders == ["Recent refresh failure details"]
    assert capture.dataframes[1][0]["Stage"] == "processing"
