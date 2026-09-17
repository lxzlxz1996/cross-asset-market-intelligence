# Architecture

## Intended flow

```text
Data Sources
  → Data Ingestion
  → Raw Storage
  → Validation / Cleaning
  → Derived Indicators
  → Signal Engine
  → Regime / Cross-Asset Analysis
  → Risk Engine
  → Portfolio Engine
  → Dashboard / Journal
  → Backtesting & Feedback
```

The arrows describe data lineage, not an authorization to automate investment decisions. Each downstream layer must retain enough identifiers, timestamps, and version information to trace an output back to its inputs.

## Phase 0: implemented foundation

- A local, conventional Python package with isolated configuration, database, logging, and exception modules.
- A DuckDB database utility and explicit DDL for `raw_observations`, `processed_observations`, and `signals`.
- File paths for raw and processed data, database, logs, and non-committed environment variables.
- An initial data dictionary and deterministic tests. No connection, table, or data is created until future code explicitly calls the relevant utility.
- One pure, unit-tested 10Y–2Y calculation establishes the convention that rate spreads are expressed in percentage points; it does not retrieve or process market data.

## Future layers: design only

| Layer | Responsibility | Phase introduced |
|---|---|---|
| Data ingestion | Retrieve source data with source-specific metadata and retry/quality handling. | 1 |
| Validation / cleaning | Validate units, dates, frequency, missingness, revisions, and outliers without mutating raw data. | 1 |
| Derived indicators | Apply documented transformations and record a processing version. | 1–2 |
| Signal engine | Create explainable descriptive, confirmation, leading, predictive, or allocation research outputs. | 2 |
| Cross-asset and regime engines | Reconcile evidence and flag divergences/regimes. | 3–4 |
| Risk and portfolio engines | Map validated research to risk exposures and conditional portfolio responses. | 8–9 |
| Dashboard, journal, backtesting | Present data, record decisions, and validate methods without look-ahead bias. | 1, 6, 9–10 |

## Storage and data lineage

### `raw_observations`

Append-only source observations keyed by `(source, series_id, observation_date, vintage)`. `retrieval_timestamp` records when this system received the observation; `publication_timestamp` records when it became publicly available when supplied by the source. `metadata` is source-specific JSON, reserved for items such as native units, payload identifiers, or release details.

### `processed_observations`

Cleaned or transformed values keyed by `(indicator_id, date, processing_version)`. Each row cites `raw_source`, `raw_series_id`, and `transformation`, giving a direct lineage pointer. A future processing-run identifier may be added only when multi-step pipelines warrant it.

### `signals`

Versioned, explainable rule outputs keyed by `(signal_id, indicator_id, date, model_version)`. A signal is not a decision. The table intentionally does not add portfolio fields.

### Deferred tables

`regimes`, `portfolio_positions`, `decisions`, and `backtest_results` are deferred until their phases. Their eventual links should be explicit: regimes cite signal/model versions; positions cite portfolio snapshots; decisions cite supporting signals/regimes and an availability timestamp; backtest results cite dataset, strategy/rule, and cost-model versions. This prevents premature schemas from locking in untested financial definitions.

## Architectural decisions

1. **DuckDB first.** It supports local analytical workflows with no service operation, matching the blueprint's local-first requirement.
2. **Explicit schema initialization.** Opening a connection has no hidden side effect beyond DuckDB's normal file creation; table creation is deliberate and testable.
3. **Raw values are source- and vintage-aware.** This supports reproducibility and later revision-aware, no-look-ahead research.
4. **Versioned derivatives and signals.** An output can coexist with a revised formula instead of silently rewriting research history.
5. **Minimal dependencies.** The foundation requires DuckDB; pytest is a development-only dependency. pandas and other analytical libraries are intentionally deferred until implementation requires them.

## Naming conventions

- Python: `snake_case`; package name: `cross_asset_market_intelligence`.
- Database tables and fields: `snake_case` and singularly scoped concepts.
- Indicator IDs: stable lowercase identifiers, for example `us_treasury_10y_yield`; source IDs remain separate.
- Dates: ISO 8601 calendar dates; timestamps: timezone-aware UTC timestamps whenever the source provides a timestamp.
- Definitions: changes require a new transformation or model version and documentation update.
