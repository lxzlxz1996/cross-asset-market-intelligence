# Cross-Asset Market Intelligence & Portfolio Risk System

Local, research-first infrastructure for understanding cross-asset market conditions and improving portfolio risk decisions over time. It is not a short-term prediction or automated trading system.

## Current status

**Phase 0 — System Architecture & Foundation.** The repository currently contains the directory layout, documentation, configuration design, a minimal DuckDB utility, logging setup, and deterministic tests. No market-data ingestion, dashboard, signals, models, portfolio optimization, or backtesting has been implemented.

## Quick start (when Python is installed)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` only when a future data source requires credentials. Never commit `.env`.

See [the project blueprint](docs/PROJECT_BLUEPRINT.md), [architecture](docs/ARCHITECTURE.md), and [development roadmap](docs/DEVELOPMENT_ROADMAP.md).
