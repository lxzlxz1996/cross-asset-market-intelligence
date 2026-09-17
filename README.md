# Cross-Asset Market Intelligence & Portfolio Risk System

Local, research-first infrastructure for understanding cross-asset market conditions and improving portfolio risk decisions over time. It is not a short-term prediction or automated trading system.

## Current status

**Phase 1.5C — Treasury dashboard vertical slice.** The local application displays read-only current and selected-history data for 2Y, 10Y, and 10Y−2Y Treasury indicators, including descriptive 1D/5D/20D changes and inspectable lineage. It is not a completed cross-asset dashboard; no signals, portfolio logic, or Phase 2 functionality is implemented.

## Quick start (when Python is installed)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` only when a future data source requires credentials. Never commit `.env`.

See [the project blueprint](docs/PROJECT_BLUEPRINT.md), [architecture](docs/ARCHITECTURE.md), and [development roadmap](docs/DEVELOPMENT_ROADMAP.md).

## Local Treasury dashboard

After local raw ingestion and Treasury processing have populated `data/market_intelligence.duckdb`, launch the graphical dashboard with:

```powershell
streamlit run src/cross_asset_market_intelligence/dashboard/streamlit_app.py
```

The page is strictly read-only: opening or refreshing it does not call FRED, ingest data, process Treasury observations, or write to DuckDB. It currently covers only 2Y, 10Y, and 10Y−2Y Treasury data; unavailable metrics such as a 20D change with insufficient history display as `N/A`.

## Phase 1.2 manual raw ingestion

Set `FRED_API_KEY` in your shell (or securely load it into the environment), then run:

```powershell
python -m cross_asset_market_intelligence ingest-fred-treasury --start 2026-01-01
```

This is limited to FRED `DGS2` and `DGS10`. It writes only to `data/market_intelligence.duckdb` → `raw_observations`; it does not create processed data, a yield-curve spread, or dashboard output. Inspect rows with a DuckDB client, for example: `SELECT * FROM raw_observations WHERE source = 'fred' ORDER BY series_id, observation_date;`.
