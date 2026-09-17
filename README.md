# Cross-Asset Market Intelligence & Portfolio Risk System

Local, research-first infrastructure for understanding cross-asset market conditions and improving portfolio risk decisions over time. It is not a short-term prediction or automated trading system.

## Current status

**Phase 1.2 — FRED Raw Ingestion for DGS2 and DGS10.** Phases 0 and 1.1 are complete. This subphase authorizes raw FRED ingestion for those two series only: no processed observations, yield-curve calculation, dashboard, signals, models, portfolio optimization, or backtesting is implemented. Phase 2 remains out of scope.

## Quick start (when Python is installed)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` only when a future data source requires credentials. Never commit `.env`.

See [the project blueprint](docs/PROJECT_BLUEPRINT.md), [architecture](docs/ARCHITECTURE.md), and [development roadmap](docs/DEVELOPMENT_ROADMAP.md).

## Phase 1.2 manual raw ingestion

Set `FRED_API_KEY` in your shell (or securely load it into the environment), then run:

```powershell
python -m cross_asset_market_intelligence ingest-fred-treasury --start 2026-01-01
```

This is limited to FRED `DGS2` and `DGS10`. It writes only to `data/market_intelligence.duckdb` → `raw_observations`; it does not create processed data, a yield-curve spread, or dashboard output. Inspect rows with a DuckDB client, for example: `SELECT * FROM raw_observations WHERE source = 'fred' ORDER BY series_id, observation_date;`.
