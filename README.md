# Cross-Asset Market Intelligence & Portfolio Risk System

Local, research-first infrastructure for understanding cross-asset market conditions and improving portfolio risk decisions over time. It is not a short-term prediction or automated trading system.

## Current status

**Phase 1 engineering baseline frozen (Phase 1.8C).** The local application presents read-only current and selected-history data, descriptive 1D/5D/20D observation-count changes, and inspectable lineage for Treasury (2Y, 10Y, 10Y−2Y), SOFR, and Credit (IG/HY OAS). It also exposes manual refresh-run status and Data Status without changing market data.

Phase 1 is **6 implemented / 3 deferred source integrations**. `spx`, `vix`, and `move_index` remain `source_pending`: their long-term data-source and usage-rights conditions are unresolved, so they are not implemented or represented as production-authorized. The durable conditions for resuming each integration are recorded in [Deferred Source Integrations](docs/DEVELOPMENT_ROADMAP.md#deferred-source-integrations). The Signal Engine, regime logic, risk/portfolio logic, and backtesting are future work; no Phase 2 functionality is implemented.

## Quick start (when Python is installed)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` only when a future data source requires credentials. Never commit `.env`.

See [the project blueprint](docs/PROJECT_BLUEPRINT.md), [architecture](docs/ARCHITECTURE.md), and [development roadmap](docs/DEVELOPMENT_ROADMAP.md).

## Local dashboard

After local raw ingestion and Treasury processing have populated `data/market_intelligence.duckdb`, launch the graphical dashboard with:

```powershell
streamlit run src/cross_asset_market_intelligence/dashboard/streamlit_app.py
```

The page is strictly read-only: opening or refreshing it does not call external sources, ingest data, process observations, initiate a refresh, or write to DuckDB. It shows Treasury, Funding / Liquidity, Credit, Data Status, and Data & Lineage. Unavailable metrics such as a 20D change with insufficient history display as `N/A`.

Manual refresh is explicit and limited to implemented pipelines:

```powershell
python -m cross_asset_market_intelligence refresh-market-data --pipeline treasury
python -m cross_asset_market_intelligence show-data-health
```

The refresh command is not scheduled and does not invoke governance-pending indicators.

## Phase 1.2 manual raw ingestion

Set `FRED_API_KEY` in your shell (or securely load it into the environment), then run:

```powershell
python -m cross_asset_market_intelligence ingest-fred-treasury --start 2026-01-01
```

This is limited to FRED `DGS2` and `DGS10`. It writes only to `data/market_intelligence.duckdb` → `raw_observations`; it does not create processed data, a yield-curve spread, or dashboard output. Inspect rows with a DuckDB client, for example: `SELECT * FROM raw_observations WHERE source = 'fred' ORDER BY series_id, observation_date;`.
