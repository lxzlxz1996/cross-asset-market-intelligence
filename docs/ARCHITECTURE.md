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

### Phase 1.2 FRED mapping

For FRED `DGS2` and `DGS10`, `source` is `fred`, `series_id` is the FRED ID, `observation_date` and `value` come from the source `date` and `value`, and `retrieval_timestamp` is the system's UTC retrieval time. FRED does not provide an observation-level publication timestamp for these series, so `publication_timestamp` remains null. The `vintage` key is `fred_realtime:<realtime_start>:<realtime_end>`: it is a lossless identifier for FRED's date-level real-time availability interval, not a claimed intraday publication time or a fabricated vendor vintage. The same FRED fields and raw source value are retained in JSON metadata. A source `value` of `.` is stored as a row with null numeric `value` and explicit missing-value metadata.

### `processed_observations`

Immutable processed outputs keyed by `processed_observation_id`. The ID is a SHA-256 digest of a canonical JSON representation of `indicator_id`, date, `processing_version`, and the complete selected raw-input identities. It does not include execution time or output value. `processing_version` identifies methodology only; a changed raw vintage produces a new output identity without changing that methodology version.

### `processed_observation_inputs`

One row per raw observation used by a processed output. Its foreign keys identify the exact raw primary key: source, series ID, observation date, and vintage. `input_role` records the stable semantic role of the input. Direct source normalization will use `source`; a future 10Y−2Y calculation can use `ten_year` and `two_year`. This one-to-many relationship is authoritative lineage; `processed_observations` intentionally has no singular raw-source fields.

### Phase 1.3A migration

The former processed key, `(indicator_id, date, processing_version)`, could not retain an immutable result when the same raw observation gained a new vintage. The schema initializer replaces that legacy table only if it is empty. If any legacy processed rows exist, initialization raises an explicit migration error and leaves all tables unchanged; migration would otherwise fabricate missing raw-vintage lineage. `raw_observations` is never altered.

### Phase 1.3B direct Treasury normalization

Only `fred`/`DGS2` → `us_treasury_2y_yield` and `fred`/`DGS10` → `us_treasury_10y_yield` are approved. They are validated identity normalizations: a finite raw value remains a percent-per-annum value (for example, `4.25` remains `4.25`), using processing version `fred_treasury_direct_percent_identity_v1` and transformation `validated_identity_percent_per_annum`. A null FRED raw value is an expected missing observation and produces no processed row; it is never filled, interpolated, or replaced with zero.

For each source, series, and observation date, processing chooses the valid Phase 1.2 FRED vintage with the greatest `(realtime_start, realtime_end, vintage)` tuple parsed from `fred_realtime:<start>:<end>`. ISO-date lexical order is chronological. Processing inserts a separate immutable result for a newer selected vintage, without deleting older raw or processed rows and without changing methodology version. Every output has exactly one `source` lineage row identifying the selected raw primary key. The manual command `python -m cross_asset_market_intelligence process-fred-treasury` reads local raw rows only; it never calls FRED.

To inspect the resulting lineage locally:

```sql
SELECT processed.indicator_id, processed.date, processed.value,
       processed.processing_version, processed.processed_observation_id,
       input.raw_source, input.raw_series_id, input.raw_observation_date,
       input.raw_vintage, input.input_role
FROM processed_observations AS processed
JOIN processed_observation_inputs AS input USING (processed_observation_id)
ORDER BY processed.indicator_id, processed.date, input.raw_vintage;
```

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
