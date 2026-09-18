# Phase 2.2D — Treasury 2s10s framework validation

Framework decision:

PHASE 2.2 FRAMEWORK VALIDATED WITH NON-BLOCKING FOLLOW-UPS

Curve research decision:

MORE_RESEARCH_REQUIRED

## Evidence and scope

The [research package](../notebooks/treasury_curve/outputs/README.md), [report](../notebooks/treasury_curve/outputs/report.md), [machine conclusions](../notebooks/treasury_curve/outputs/results.json), [independent checks](../notebooks/treasury_curve/outputs/validation.json), and [17-capability scorecard](../notebooks/treasury_curve/outputs/framework_scorecard.csv) validate a second family using current local Phase 1 DGS2/DGS10 inputs. Ten same-date curve observations (2026-09-01–09-15) have 20 exact processed leg inputs. Spreads range +32 to +43bp; all are positive. No source retrieval or database mutation was performed.

Same-date pairing, explicit percentage-point-to-bp conversion, direct sign semantics, leg attribution, snapshot/run/code identity and artifact finalization work without SOFR component schemas or windows. Merged positions enumerate date/role pairs; separate role sequences preserve each leg's time order and current endpoint. The generic chronological validator already allows equal dates. A multi-sequence extension is unnecessary for this bounded study.

Four observed illustrative cases and nine separately labeled synthetic cases exercise sign/direction interaction, zero boundary, crossing, round trips, common leg movement and sustained inversion. Synthetic data are excluded from selected market inputs and observed statistics. Research CDF bands, path/slope and reference sensitivity are exploratory; none is a production formula, horizon or state freeze.

## Defects and smallest corrections

Boundary fixtures demonstrated six failures before correction: dangling references, false passed validation, conflicting report outcome, never-null CSV violations, extra-field CSV crashes, and position/array mismatch when dates tie. Generic validator changes now enforce resolvable references, matching report outcome, truthful status/limitation handling, structured schema errors and CSV field/null mechanics. Ordered positions follow array order, with chronological direction separately declared. ISO full dates/timestamps are checked in their normative forms.

These corrections enforce the existing `research_artifacts_v1` ownership/mechanical requirements. No schema or semantic hash profile was changed, and no SOFR production calculator was edited. The valid alternate-order test now explicitly reindexes positions in its newly declared array order, rather than leaving conflicting ascending-chronology positions attached to a reversed array.

## Follow-ups and gates

Historical publication availability remains unknown; the study cannot establish historical event-time replay. Longer validated local Treasury history is required to study observed inversion/crossing, volatility changes and horizon sensitivity. This is blocking for curve methodology freeze, but does not reveal a foundational architecture defect. Package validity accepts an honest `MORE_RESEARCH_REQUIRED` result; it cannot grant methodology-freeze readiness.

Empirical rank/window abstractions, state objects, universal component payloads and automatic classifications remain deferred. Any historical expansion requires separate authorization through the Phase 1 workflow. No Curve production implementation starts here.

## Verification

Targeted tests cover Treasury normalization/derived lineage, research calculations, warm-up and future exclusion, the generic artifact package and corrected validator failures. The independent entrypoint checks all 170 observed date/candidate rows, every actual input pair, 13 cases and synthetic reference sensitivity using separate formulas and original-database SQL. Package CLI returns `passed_with_warnings` with no blocking errors; warnings retain unknown availability and bounded scope.

Targeted suite: **52 passed**. Final complete project suite: **223 passed**, zero failures/errors/skips, 252.92 seconds. The XML ledger is retained at `notebooks/treasury_curve/verification/full_suite.xml`; [test_summary.json](../notebooks/treasury_curve/outputs/test_summary.json) records counts and its raw-file hash. All 14 independent checks pass; generic package validation returns `passed_with_warnings`. SOFR regression coverage is included.
