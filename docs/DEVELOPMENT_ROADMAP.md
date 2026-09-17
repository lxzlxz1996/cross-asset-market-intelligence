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
- **Phase 2 — Signal Engine: explicitly out of scope.** No Z-scores, percentiles, trend/momentum states, signal classifications, or regime logic are authorized.

| Phase | Objective | Major components | Dependencies | Definition of done |
|---|---|---|---|---|
| 0 — Architecture | Build a reliable foundation. | Dictionary, schema, naming, config, tests. | Blueprint. | **Complete.** Core definitions and runnable foundation exist. |
| 1 — Market Dashboard MVP | Understand core market state in five minutes. | Nine core indicators, daily update, homepage. | Phase 0 definitions and verified source contracts. | **Authorized / in progress:** Treasury and SOFR read-only dashboard slices are complete; remaining Phase 1 indicators remain separately gated. |
| 2 — Signal Engine | Standardize market states and anomalies. | Z-scores, percentiles, trends, momentum. | Phase 1 history. | Traceable, configurable outputs for core indicators. |
| 3 — Cross-Asset Engine | Detect meaningful divergences. | Relationship and divergence rules. | Phases 1–2. | Four explainable divergence types with history. |
| 4 — Macro & Regime Engine | Identify economic and policy environment. | Growth, inflation, Fed pricing, regime logic. | Phases 1–3. | Regime, evidence, confidence, and change conditions. |
| 5 — Positioning & Flow | Identify crowding and unwind risk. | CFTC, OI, ETF flow, options data. | Data-source validation. | Joint price/position/flow interpretation. |
| 6 — Research & Backtest | Validate retained signals. | Event studies, OOS, walk-forward. | Versioned data/signals. | Robust, cost-aware results by regime. |
| 7 — Factor Model | Reduce duplicated information. | Correlation, clustering, PCA. | Validated feature history. | Stable, explainable conceptual factors. |
| 8 — Portfolio & Risk | Explain portfolio exposures and stress. | Holdings, risk contribution, VaR/CVaR, scenarios. | Factors and data integrity. | Traceable portfolio- and position-level risk. |
| 9 — Decision System | Turn evidence into conditional responses. | Rules, human confirmation, journal. | Phases 4, 6, 8. | Explainable actions with invalidation and recorded rationale. |
| 10 — Execution & Feedback | Close the decision-performance loop. | Costs, slippage, attribution, review. | Phase 9. | Gross/net performance and versioned feedback. |
