# Phase 2 signal research template

Package the completed research under the frozen [Signal Research Artifact Standard](SIGNAL_RESEARCH_ARTIFACT_STANDARD.md). This template defines research content; the artifact standard defines filenames, machine-readable envelopes, hashes, ownership, and finalization.

Use this template for a research package before methodology freeze. Replace instructions with project-specific content. `Not applicable` is valid only with a reason. Do not invent production behavior in implementation.

## 1. Signal / Component Identity

- Proposed research ID:
- Indicator/component:
- Research version:
- Workflow status: `PROPOSED | RESEARCHING | READY_FOR_METHODOLOGY_FREEZE | MORE_RESEARCH_REQUIRED | BLOCKED_BY_DATA_OR_ARCHITECTURE`
- Scope and explicit non-goals:

## 2. Economic Question

- Observable behavior being described:
- Exact question:

## 3. Economic Relevance

- Why this evidence could improve market awareness:
- Intended downstream use:

## 4. What It Measures

- Quantities and units:
- Descriptive/causal/forecast classification:

## 5. What It Does Not Mean

- Forbidden interpretations:
- Unresolved external context:
- No implied trade/portfolio action:

## 6. Input Data Contract

- Indicator/source series:
- Native and processed units:
- Frequency and valid-observation definition:
- Canonical selection:
- Revision/vintage behavior:
- Missing/non-publication treatment:
- Exact selected-input artifact:

## 7. Point-in-Time / Availability Semantics

- Observation date meaning:
- `information_available_at/date` and precision:
- Retrieval-time role:
- Unknown availability:
- Historical point-in-time limitation:

## 8. Candidate Evidence Methods

For each candidate: formula, output unit, inclusion/exclusion, precision, ties, missingness, fallback, and economic interpretation.

## 9. Candidate Windows / Reference Sets

For each: exact indexing, economic meaning, warm-up, responsiveness/lag, reasonable alternatives, regime exposure, and lineage cost.

## 10. Research Evaluation Criteria

- Mandatory core criteria selected:
- Indicator-specific criteria:
- Not-applicable criteria with rationale:

## 11. Regime / Structural-Break Analysis

- Relevant regimes/breaks:
- Full/rolling/recent/regime-relative implications:
- Source-methodology changes:

## 12. Failure Modes

- Misleading/degenerate cases:
- Missing/revision/outlier/denominator/tie behavior:
- Consequence for candidate inclusion:

## 13. Orthogonality / Redundancy Analysis

- Compared dimensions:
- Correlation/conditional/conflict evidence:
- Independent-confirmation claims allowed or forbidden:

## 14. Warm-Up

- Minimum inputs per candidate:
- Partial windows prohibited/allowed with rationale:
- Status/progress representation:

## 15. Missing Data

- Missing/non-publication semantics:
- Fill/interpolation policy:
- Valid unavailability versus structural failure:

## 16. Numeric Precision

- Decimal/float policy:
- Equality/tie policy:
- Rounding and serialization:
- Unit conversion:

## 17. Candidate State Logic

- State proposed or explicitly none:
- Evidence and economic meaning for any threshold:
- Boundary/conflict/quality behavior:

## 18. Evidence Quality Interaction

- Component availability versus outer quality:
- Deterministic reasons:
- Unknown-availability effect:

## 19. Exact Lineage Requirements

- Roles and ordered/unordered semantics:
- Positions/current input/overlap:
- Required reconstruction:
- Revision identity:
- Per-observation and backfill cost estimate:

## 20. Historical Golden Cases

- Named normal/extreme/conflict/failure/warm-up cases as relevant:
- Independent expected-value source:

## 21. Independent Validation

- Independent method and why independent:
- Formula/input/warm-up coverage:
- Counts/hashes/status:
- Unresolved limitations:

## 22. Recommended Evidence Contract

- Recommended fields and units:
- Fields deliberately excluded:
- Separate evidence dimensions:

## 23. Deterministic Explanation Semantics

- Mandatory facts/order if any:
- Unavailable/conflict/tie wording:
- Forbidden causal/classification language:

## 24. Methodology Versioning

- Proposed immutable methodology ID:
- Expected outer-version effect:
- Changes requiring a future bump:

## 25. Measured Facts

List observations only; do not embed recommendations.

## 26. Research Interpretation

Interpret the measured facts within the declared boundaries.

## 27. Design Recommendation

State the recommended production evidence and exclusions.

## 28. Deferred Questions

List questions that are not silently solved by this recommendation.

## 29. Artifact Map

Map the manifest, selected inputs, machine-readable results, comparisons, cases, validation, report, README, and code using `research_artifacts_v1`. Mark conditional artifacts present or `not_applicable` with rationale; do not create empty irrelevant artifacts.

## 30. Production Readiness Decision

Choose exactly one:

```text
READY_FOR_METHODOLOGY_FREEZE
MORE_RESEARCH_REQUIRED
BLOCKED_BY_DATA_OR_ARCHITECTURE
```
