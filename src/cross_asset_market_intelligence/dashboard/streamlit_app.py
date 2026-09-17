"""Local, read-only Streamlit Treasury and SOFR dashboard vertical slice."""

from __future__ import annotations

import streamlit as st

from cross_asset_market_intelligence.config import load_settings
from cross_asset_market_intelligence.database import connect
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
    TreasuryDashboardObservation,
    current_treasury_dashboard,
    treasury_history,
)
from cross_asset_market_intelligence.dashboard.sofr_read_model import (
    SofrDashboardObservation,
    current_sofr_observation,
    sofr_history,
)
from cross_asset_market_intelligence.exceptions import DashboardLineageError, DashboardReadError


def main() -> None:
    """Render validated local Treasury and SOFR observations without mutation."""
    st.set_page_config(page_title="Cross-Asset Market Intelligence", layout="wide")
    st.title("Cross-Asset Market Intelligence")
    st.caption("Read-only local view of validated Treasury and SOFR observations.")
    try:
        settings = load_settings()
        connection = connect(settings.database_path, read_only=True)
        try:
            dashboard = current_treasury_dashboard(connection)
            sofr = current_sofr_observation(connection)
            _render_current_cards(dashboard)
            _render_history(connection)
            _render_sofr(connection, sofr)
            _render_lineage(dashboard, sofr)
        finally:
            connection.close()
    except DashboardLineageError:
        st.error("Data lineage validation failed. No replacement value has been shown.")
    except DashboardReadError:
        st.error("Data unavailable: the local dashboard data could not be read.")
    except FileNotFoundError:
        st.error("Data unavailable: the local DuckDB database does not exist yet.")


def _render_current_cards(
    dashboard: dict[str, TreasuryDashboardObservation | None],
) -> None:
    st.subheader("Treasury market")
    columns = st.columns(3)
    for column, indicator_id in zip(columns, dashboard):
        observation = dashboard[indicator_id]
        with column:
            if observation is None:
                st.info(f"{indicator_id}: no validated observation available.")
            else:
                _render_observation_card(observation)


def _render_history(connection) -> None:
    st.subheader("Historical Treasury observations")
    two_year = treasury_history(connection, "us_treasury_2y_yield")
    ten_year = treasury_history(connection, "us_treasury_10y_yield")
    spread = treasury_history(connection, "us_treasury_10y_minus_2y")
    if two_year or ten_year:
        st.markdown("**Treasury yields**")
        _render_chart(yield_chart_rows(two_year, ten_year), "Yield (%)")
    else:
        st.info("No validated 2Y or 10Y history is available.")
    if spread:
        st.markdown("**10Y − 2Y spread**")
        _render_chart(historical_chart_rows(spread, "10Y − 2Y (pp)"), "Spread (pp)")
    else:
        st.info("No validated 10Y − 2Y history is available.")


def _render_sofr(connection, observation: SofrDashboardObservation | None) -> None:
    """Keep funding data distinct from the Treasury market presentation."""
    st.subheader("Funding / Liquidity")
    if observation is None:
        st.info("SOFR: no validated observation available.")
    else:
        _render_observation_card(observation)
    st.markdown("**SOFR history**")
    history = sofr_history(connection)
    if history:
        _render_chart(historical_chart_rows(history, "SOFR (%)"), "SOFR (%)")
    else:
        st.info("No validated SOFR history is available.")


def _render_observation_card(observation: TreasuryDashboardObservation | SofrDashboardObservation) -> None:
    """Render direct-indicator values without adding interpretation."""
    st.metric(observation.display_name, format_level(observation))
    change_columns = st.columns(3)
    for change_column, label, change in zip(
        change_columns,
        ("1D", "5D", "20D"),
        (observation.change_1d, observation.change_5d, observation.change_20d),
    ):
        with change_column:
            st.caption(label)
            st.write(format_change(change.value))
    st.caption(f"As of {observation.observation_date.isoformat()}")


def _render_chart(rows: list[dict[str, object]], y_title: str) -> None:
    """Render date-only ordered data with a compact, non-rebased value axis."""
    st.vega_lite_chart(
        rows,
        {
            "mark": {"type": "line", "point": True},
            "encoding": {
                "x": {
                    "field": "date",
                    "type": "ordinal",
                    "title": None,
                    "axis": {"labelAngle": 0},
                },
                "y": {
                    "field": "value",
                    "type": "quantitative",
                    "title": y_title,
                    "scale": {"domain": chart_y_domain(rows), "zero": False},
                },
                "color": {"field": "series", "type": "nominal", "title": None},
                "tooltip": [
                    {"field": "date", "type": "ordinal", "title": "Date"},
                    {"field": "series", "type": "nominal", "title": "Series"},
                    {"field": "value", "type": "quantitative", "title": y_title},
                ],
            },
        },
        use_container_width=True,
    )


def _render_lineage(
    dashboard: dict[str, TreasuryDashboardObservation | None],
    sofr: SofrDashboardObservation | None,
) -> None:
    with st.expander("Data and lineage inspection"):
        for indicator_id, observation in dashboard.items():
            if observation is None:
                st.write(f"{indicator_id}: no validated observation available.")
            elif indicator_id == "us_treasury_10y_minus_2y":
                st.write(observation.display_name)
                st.dataframe(spread_lineage_rows(observation), hide_index=True)
            else:
                st.write(observation.display_name)
                st.dataframe(direct_lineage_rows(observation), hide_index=True)
        if sofr is None:
            st.write("SOFR: no validated observation available.")
        else:
            st.write(sofr.display_name)
            st.dataframe(direct_lineage_rows(sofr), hide_index=True)


if __name__ == "__main__":
    main()
