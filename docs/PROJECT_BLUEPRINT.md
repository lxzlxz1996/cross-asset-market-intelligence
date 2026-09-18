# Project Blueprint

The authoritative project blueprint is preserved verbatim in the project root as `Cross-Asset_Market_Intelligence_Blueprint.md`. This document is a stable in-repository reference point for future agents; consult the root source before material changes.

Current phase: **Phase 2.1B-11 — SOFR vertical-slice final review (complete); Phase 2.2 not started**.

Core chain: **Data → Information → Signal → Regime → Risk → Portfolio Decision → Review**.

Phases 0, 1.1–1.8C, **2.1A**, and **2.1B-1 through 2.1B-11** are complete. The frozen Phase 1 baseline remains **6 implemented / 3 deferred source integrations**: `spx`, `vix`, and `move_index` remain `source_pending` in the [Deferred Source Integrations](DEVELOPMENT_ROADMAP.md#deferred-source-integrations) record. Outer `sofr_rate_state/v1` remains immutable anomaly-only production; v2 adds frozen [SOFR direction methodology v1](SOFR_DIRECTION_METHODOLOGY_V1.md); v3 preserves both and adds frozen [SOFR Level methodology v1](SOFR_LEVEL_METHODOLOGY_V1.md) with exact expanding lineage. The [SOFR vertical-slice final review](SOFR_VERTICAL_SLICE_FINAL_REVIEW.md) approves this as the Phase 2 reference pattern with non-blocking follow-ups. All categorical states remain null; Phase 2.2 and Phase 3 are not started.
