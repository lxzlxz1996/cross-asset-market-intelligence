# Development Roadmap

## Current authorization

- **Phase 0 — Architecture: complete.**
- **Phase 1.1 — Phase gate and market-data source verification: complete.**
- **Phase 1.2 — FRED raw ingestion for DGS2 and DGS10: complete.**
- **Phase 1.3A — Processed-observation lineage schema evolution: complete.**
- **Phase 1.3B — Direct Treasury raw → processed normalization: complete.** This subphase authorizes only `fred`/`DGS2` and `fred`/`DGS10` direct, percent-preserving processed observations and immutable source lineage. It does not authorize derived spreads.
- **Phase 1.4A — Processed-to-processed dependency lineage: complete.** This subphase authorizes only additive dependency schema, derived-identity support, and synthetic tests; it does not authorize spread values or real derived observations.
- **Phase 1.4B — Treasury 10Y−2Y derivation: complete.** This subphase authorizes only same-date, percentage-point spread processing from validated processed Treasury inputs and transitive lineage.
- **Phase 2 — Signal Engine: explicitly out of scope.** No Z-scores, percentiles, trend/momentum states, signal classifications, or regime logic are authorized.

| Phase | Objective | Major components | Dependencies | Definition of done |
|---|---|---|---|---|
| 0 — Architecture | Build a reliable foundation. | Dictionary, schema, naming, config, tests. | Blueprint. | **Complete.** Core definitions and runnable foundation exist. |
| 1 — Market Dashboard MVP | Understand core market state in five minutes. | Nine core indicators, daily update, homepage. | Phase 0 definitions and verified source contracts. | **Authorized / in progress:** Phases 1.3A, 1.3B, 1.4A, and 1.4B are complete. No further Phase 1 scope is authorized by this update. |
| 2 — Signal Engine | Standardize market states and anomalies. | Z-scores, percentiles, trends, momentum. | Phase 1 history. | Traceable, configurable outputs for core indicators. |
| 3 — Cross-Asset Engine | Detect meaningful divergences. | Relationship and divergence rules. | Phases 1–2. | Four explainable divergence types with history. |
| 4 — Macro & Regime Engine | Identify economic and policy environment. | Growth, inflation, Fed pricing, regime logic. | Phases 1–3. | Regime, evidence, confidence, and change conditions. |
| 5 — Positioning & Flow | Identify crowding and unwind risk. | CFTC, OI, ETF flow, options data. | Data-source validation. | Joint price/position/flow interpretation. |
| 6 — Research & Backtest | Validate retained signals. | Event studies, OOS, walk-forward. | Versioned data/signals. | Robust, cost-aware results by regime. |
| 7 — Factor Model | Reduce duplicated information. | Correlation, clustering, PCA. | Validated feature history. | Stable, explainable conceptual factors. |
| 8 — Portfolio & Risk | Explain portfolio exposures and stress. | Holdings, risk contribution, VaR/CVaR, scenarios. | Factors and data integrity. | Traceable portfolio- and position-level risk. |
| 9 — Decision System | Turn evidence into conditional responses. | Rules, human confirmation, journal. | Phases 4, 6, 8. | Explainable actions with invalidation and recorded rationale. |
| 10 — Execution & Feedback | Close the decision-performance loop. | Costs, slippage, attribution, review. | Phase 9. | Gross/net performance and versioned feedback. |
