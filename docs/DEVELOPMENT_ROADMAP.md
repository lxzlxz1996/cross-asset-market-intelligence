# Development Roadmap

## Current authorization

- **Phase 0 — Architecture: complete.**
- **Phase 1.1 — Phase gate and market-data source verification: complete.**
- **Phase 1.2 — FRED raw ingestion for DGS2 and DGS10: complete.**
- **Phase 1.3A — Processed-observation lineage schema evolution: complete.**
- **Phase 1.3B — Direct Treasury raw → processed normalization: complete.** This subphase authorizes only `fred`/`DGS2` and `fred`/`DGS10` direct, percent-preserving processed observations and immutable source lineage. It does not authorize derived spreads.
- **Phase 1.4A — Processed-to-processed dependency lineage: complete.** This subphase authorizes only additive dependency schema, derived-identity support, and synthetic tests; it does not authorize spread values or real derived observations.
- **Phase 1.4B — Treasury 10Y−2Y derivation: complete.** This subphase authorizes only same-date, percentage-point spread processing from validated processed Treasury inputs and transitive lineage.
- **Phase 1.5A — Treasury dashboard read model: complete.** This subphase authorizes only read-only deterministic projections, history access, and lineage inspection; it does not authorize dashboard UI or change metrics.
- **Phase 1.5B — Descriptive Treasury dashboard changes: complete.** This subphase authorizes only read-only 1D/5D/20D observation-count differences; it does not authorize UI, returns, classifications, or persistence.
- **Phase 1.5C — Graphical Treasury dashboard vertical slice: complete.** This subphase authorizes only a local, read-only Streamlit presentation of the established Treasury read model.
- **Phase 1.5C.1 — Treasury dashboard presentation polish: complete.** This subphase authorizes only compact card layout and clearer, date-only historical chart presentation; it does not change the read model, data, or lineage.
- **Phase 1.6A — Official SOFR raw ingestion: complete.** This subphase authorizes only official FRBNY `SOFR` retrieval and append-only raw storage, including source revision metadata; it does not authorize SOFR processing or dashboard presentation.
- **Phase 1.6B — Validated SOFR raw → processed normalization: complete.** This subphase authorizes only local, percent-preserving normalization of selected FRBNY SOFR raw observations with immutable exact raw-vintage lineage; it does not authorize SOFR dashboard presentation.
- **Phase 1.6C — SOFR read model and dashboard integration: complete.** This subphase authorizes only read-only, revision-aware selected SOFR history, descriptive observation-count changes, exact lineage inspection, and a separate local SOFR dashboard section. It does not authorize backfill, another source, classifications, or signals.
- **Phase 1.6D — Bounded official SOFR historical backfill: complete.** This subphase used the existing official FRBNY range ingestion and existing processing flow for 2026-06-19 through 2026-09-16. It did not change source, revision, processing, or dashboard-metric semantics; the resulting selected history supports 5D and 20D descriptive changes.
- **Phase 1.7A — Credit OAS raw ingestion: complete.** This subphase authorizes only local/internal FRED raw ingestion of ICE BofA series `BAMLC0A0CM` and `BAMLH0A0HYM2`, preserving native percentage-point values, source missingness, and FRED realtime vintages.
- **Phase 1.7B — Validated Credit OAS raw → processed normalization: complete.** This subphase authorizes only local, percentage-point-preserving normalization of selected FRED Credit OAS observations and immutable exact raw-vintage lineage. Credit read models and presentation remain separately gated.
- **Phase 1.7C — Credit read model and descriptive changes: complete.** This subphase authorizes only read-only, revision-aware Credit OAS current/history projections, exact lineage inspection, and 1D/5D/20D observation-count differences in percentage points. Graphical Credit presentation remains separately gated.
- **Phase 1.7D — Credit dashboard presentation integration: complete.** This subphase authorizes only a separate local, read-only Credit section using the established Credit read model: current Investment Grade and High Yield OAS cards, separate selected-history charts, and collapsed exact raw-vintage lineage. It does not authorize data retrieval, processing, selection-rule changes, signals, classifications, or Phase 2.
- **Phase 1.8A — Remaining source implementation gate: complete.** This subphase verified the official-source, automation, schema, and usage-rights constraints for MOVE, VIX, and SPX. No public-source persistence path is authorized under the reviewed terms; each requires explicit, source-specific user-supplied entitlement or written permission before implementation. It does not authorize ingestion, storage, processing, dashboard work, or Phase 2.
- **Phase 1.8B — Market refresh orchestration and data-health / failure visibility: complete.** This subphase adds explicit manual Treasury, SOFR, and Credit refresh-run records, stage-specific success/failure visibility, and read-only health projections/dashboard status. It does not add scheduling, sources, backfills, indicator logic, financial signals, or classifications; SPX, VIX, and MOVE remain source-pending.
- **Phase 1.8C — Phase 1 stabilization, audit, and freeze: complete.** The implemented paths, schema/lineage, read-only presentation, operational health, local database integrity, source-pending status, and repository hygiene were audited. The frozen engineering baseline includes Treasury, SOFR, Credit, manual refresh records, and Data Status; it does not authorize new sources, scheduling, signals, or any Phase 2 behavior.
- **Phase 2 — Signal Engine: future work, not implemented.** No Z-scores, percentiles, trend/momentum states, signal classifications, or regime logic exist in the frozen Phase 1 baseline.

## Deferred Source Integrations

This is the canonical Phase documentation record for deferred source integrations. It remains part of the Phase 1 freeze record when later phases begin. Phase 1 is **6 implemented / 3 deferred source integrations**, not 9/9 indicators complete.

| Intended indicator ID | Current status | Intended authoritative provider | Reason for deferral | Exact condition before implementation may resume |
|---|---|---|---|---|
| `spx` | `source_pending` | S&P Dow Jones Indices LLC; conditional FRED distribution series `SP500` | Reviewed FRED and S&P terms do not establish a right to persist the distributed S&P 500 data locally merely by obtaining a FRED API key. | The user supplies an arrangement that expressly permits automated local research storage of the FRED distribution and written S&P rights for the intended use. |
| `vix` | `source_pending` | Cboe | The public historical download lacks a stable documented API/correction-vintage contract, and reviewed Cboe terms require approval and a signed data license for database storage/use. | The user supplies a Cboe agreement covering automated retrieval, local research storage, internal use, any intended redistribution, and the supported delivery schema plus revision treatment. |
| `move_index` | `source_pending` | ICE Data Indices | The public ICE material does not provide a free production historical endpoint or disclose the contracted delivery identifier, fields, timing, revision, and storage-rights terms. | The user supplies an ICE agreement and credential that establish the exact identifier, delivered fields/unit, EOD convention/timezone, publication/revision behavior, retention/local-storage rights, and redistribution limits. |

| Phase | Objective | Major components | Dependencies | Definition of done |
|---|---|---|---|---|
| 0 — Architecture | Build a reliable foundation. | Dictionary, schema, naming, config, tests. | Blueprint. | **Complete.** Core definitions and runnable foundation exist. |
| 1 — Market Dashboard MVP | Understand core market state in five minutes. | Read-only Treasury, SOFR, and Credit observations; explicit manual refresh and data health. | Phase 0 definitions and verified source contracts. | **Engineering baseline frozen: 6 implemented / 3 deferred source integrations.** See [Deferred Source Integrations](#deferred-source-integrations). |
| 2 — Signal Engine | Standardize market states and anomalies. | Z-scores, percentiles, trends, momentum. | Phase 1 history. | Traceable, configurable outputs for core indicators. |
| 3 — Cross-Asset Engine | Detect meaningful divergences. | Relationship and divergence rules. | Phases 1–2. | Four explainable divergence types with history. |
| 4 — Macro & Regime Engine | Identify economic and policy environment. | Growth, inflation, Fed pricing, regime logic. | Phases 1–3. | Regime, evidence, confidence, and change conditions. |
| 5 — Positioning & Flow | Identify crowding and unwind risk. | CFTC, OI, ETF flow, options data. | Data-source validation. | Joint price/position/flow interpretation. |
| 6 — Research & Backtest | Validate retained signals. | Event studies, OOS, walk-forward. | Versioned data/signals. | Robust, cost-aware results by regime. |
| 7 — Factor Model | Reduce duplicated information. | Correlation, clustering, PCA. | Validated feature history. | Stable, explainable conceptual factors. |
| 8 — Portfolio & Risk | Explain portfolio exposures and stress. | Holdings, risk contribution, VaR/CVaR, scenarios. | Factors and data integrity. | Traceable portfolio- and position-level risk. |
| 9 — Decision System | Turn evidence into conditional responses. | Rules, human confirmation, journal. | Phases 4, 6, 8. | Explainable actions with invalidation and recorded rationale. |
| 10 — Execution & Feedback | Close the decision-performance loop. | Costs, slippage, attribution, review. | Phase 9. | Gross/net performance and versioned feedback. |
