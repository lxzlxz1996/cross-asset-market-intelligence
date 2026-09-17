"""Local, read-only Streamlit Treasury dashboard vertical slice."""

from __future__ import annotations

import streamlit as st

from cross_asset_market_intelligence.config import load_settings
from cross_asset_market_intelligence.database import connect
from cross_asset_market_intelligence.dashboard.presentation import (
    direct_lineage_rows,
    format_change,
    format_level,
    historical_chart_rows,
    spread_lineage_rows,
)
from cross_asset_market_intelligence.dashboard.treasury_read_model import (
    TreasuryDashboardObservation,
    current_treasury_dashboard,
    treasury_history,
)
from cross_asset_market_intelligence.exceptions import DashboardLineageError, DashboardReadError


def main() -> None:
    """Render the page using the existing read-only Treasury dashboard model."""
    st.set_page_config(page_title="Treasury Dashboard", layout="wide")
    st.title("Treasury dashboard")
    st.caption("Read-only local projection of validated Treasury observations.")
    try:
        settings = load_settings()
        connection = connect(settings.database_path, read_only=True)
        try:
            dashboard = current_treasury_dashboard(connection)
            _render_current_cards(dashboard)
            _render_history(connection)
            _render_lineage(dashboard)
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
                st.metric(observation.display_name, format_level(observation))
                st.caption(f"As of {observation.observation_date}")
                st.caption(
                    f"1D {format_change(observation.change_1d.value)} · "
                    f"5D {format_change(observation.change_5d.value)} · "
                    f"20D {format_change(observation.change_20d.value)}"
                )


def _render_history(connection) -> None:
    st.subheader("Historical Treasury observations")
    two_year = treasury_history(connection, "us_treasury_2y_yield")
    ten_year = treasury_history(connection, "us_treasury_10y_yield")
    spread = treasury_history(connection, "us_treasury_10y_minus_2y")
    if two_year or ten_year:
        yield_rows = [
            {"date": item.observation_date, "2Y yield (%)": item.value}
            for item in two_year
        ] + [
            {"date": item.observation_date, "10Y yield (%)": item.value}
            for item in ten_year
        ]
        st.line_chart(yield_rows, x="date")
    else:
        st.info("No validated 2Y or 10Y history is available.")
    if spread:
        st.line_chart(historical_chart_rows(spread, "10Y − 2Y (pp)"), x="date")
    else:
        st.info("No validated 10Y − 2Y history is available.")


def _render_lineage(dashboard: dict[str, TreasuryDashboardObservation | None]) -> None:
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


if __name__ == "__main__":
    main()
