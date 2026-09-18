# Phase 2.2A — Signal Research Framework contract

## Status, authority, and scope

**Framework status:** **PHASE 2.2A FRAMEWORK CONTRACT FROZEN — READY FOR 2.2B**

This document is the authoritative Phase 2 research and methodology-governance lifecycle contract. It applies to future Rates, Curve, Funding, and Credit signal families while allowing each indicator to choose different economics, transformations, windows, reference sets, diagnostics, evidence shapes, state logic, and lineage scope.

The completed [SOFR vertical-slice final review](SOFR_VERTICAL_SLICE_FINAL_REVIEW.md) is evidence for these governance rules, not a universal statistical template. The framework standardizes discipline and phase gates. It does not define a universal signal formula, component payload, state engine, or indicator library.

Phase 2.2A is documentation governance. Lifecycle values in this document are required workflow metadata in research and decision artifacts, not database enums or new production state machinery. The frozen [Phase 2.2B Signal Research Artifact Standard](SIGNAL_RESEARCH_ARTIFACT_STANDARD.md) owns detailed artifact schemas and package validation rules; reusable code belongs to 2.2C; proof with a second materially different indicator belongs to 2.2D.

## Core lifecycle principle

Every production signal component must preserve this chain:

```text
Economic Question
→ Validated Inputs
→ Candidate Evidence Methods
→ Historical Research
→ Failure-Mode Analysis
→ Methodology Freeze
→ Immutable Methodology Identity
→ Production Implementation
→ Exact Lineage
→ Deterministic Explanation
→ Versioned Signal Observation
→ Final Review
```

Production code must implement a frozen economic contract. It must not invent windows, thresholds, fallbacks, quality meanings, or causal claims.

## Minimal generic signal contract

Every Phase 2 signal/component must document and preserve:

1. A precise economic question and relevance.
2. What the evidence measures and explicitly does not measure.
3. Intended downstream use and interpretation boundaries.
4. Exact input universe, canonical selection, units, observation semantics, missingness, revisions/vintages, and availability.
5. Exact transformations, reference sets, current/future inclusion, numeric policy, and warm-up.
6. Candidate-method research, failure cases, regime dependence, and redundancy analysis proportionate to the question.
7. A machine-readable research package with exact selected-input identity and independent validation.
8. A frozen evidence contract, state decision (including explicitly none), quality interaction, lineage contract, explanation semantics, and version rules.
9. An immutable component methodology ID and, when composition changes, a new immutable outer signal version.
10. Exact processed-input lineage for each persisted observation.
11. Deterministic canonical explanation and explicit structural failures.
12. Golden historical cases and implementation regression protection.

Indicator-specific evidence payloads remain allowed. Level, Direction, and Anomaly are not mandatory universal components.

## Mandatory indicator-specific decisions

The framework does not choose these for a signal:

- economic hypothesis and relevant market behavior;
- raw variables and units;
- transformation (level, change, spread, slope, rank, ratio, volatility, acceleration, or another justified method);
- evidence dimensions and payload shape;
- window lengths or unbounded/bounded reference sets;
- tie and discreteness treatment;
- scale/normalization and diagnostic methods;
- calendar/session/event treatment;
- missing-observation and revision behavior beyond the prohibition on fabrication;
- state labels and thresholds, if any;
- quality effects of component-specific limitations;
- exact lineage scope and ordering;
- explanation content and ordering;
- downstream claims that the evidence may support.

No conventional `20D`, `60D`, `252D`, Z-score, percentile, moving average, or state band receives default authority.

## Research lifecycle and status contract

The conceptual lifecycle is:

```text
PROPOSED
→ RESEARCHING
→ READY_FOR_METHODOLOGY_FREEZE
→ METHODOLOGY_FROZEN
→ READY_FOR_IMPLEMENTATION
→ IMPLEMENTED
→ REVIEWED_APPROVED
```

These are documentation workflow states in 2.2A. Do not persist them in signal-observation tables or introduce a software enum until 2.2D demonstrates a need across distinct signal families.

Each phase must end with exactly one machine-readable decision:

### Research phase

```text
READY_FOR_METHODOLOGY_FREEZE
MORE_RESEARCH_REQUIRED
BLOCKED_BY_DATA_OR_ARCHITECTURE
```

### Methodology-freeze phase

```text
METHODOLOGY_FROZEN_READY_FOR_IMPLEMENTATION
MORE_METHODOLOGY_RESEARCH_REQUIRED
BLOCKED_BY_DATA_OR_ARCHITECTURE
```

### Production-implementation phase

```text
COMPLETE_READY_FOR_REVIEW
BLOCKED_BY_METHOD_OR_ARCHITECTURE
```

### Final-review phase

```text
APPROVED
APPROVED_WITH_NON_BLOCKING_FOLLOW_UPS
REQUIRES_FIXES
BLOCKED_BY_FOUNDATIONAL_ARCHITECTURE
```

Status transitions require their gates below. A status cannot be inferred merely because code or a report exists.

## Economic-question contract

Before research begins, document:

```text
economic_question
economic_relevance
what_it_measures
what_it_does_not_measure
downstream_intended_use
known_interpretation_boundaries
```

The question must identify observable behavior. It must separate descriptive evidence from causal interpretation, forecasts, state classification, and trade/portfolio implications. A vague question such as “is this indicator bullish?” cannot enter methodology freeze.

## Input and point-in-time contract

Every research project declares:

```text
indicator_id and source series
native and processed units
observation semantics and frequency
valid-observation definition
canonical selection rules
revision/vintage behavior
observation_date
information_available_at / information_available_date
availability_precision
retrieved_at
missing-value and non-publication treatment
```

Rules:

- Unknown availability remains unknown.
- Retrieval time is never substituted for publication/availability time.
- Observation date and information availability are distinct.
- Revisions/vintages remain identifiable through the input chain.
- A mathematically valid economic-date result is not automatically valid for event-time historical backtesting.
- Research must identify whether current data can reconstruct what was actually known at the proposed decision timestamp.

## Transformation contract

Every candidate evidence method declares:

```text
raw variable(s)
exact transformation/formula
input and output units
window or reference-set definition
current inclusion/exclusion
future exclusion
valid-observation/calendar/session policy
missing-observation behavior
revision behavior
tie/equality behavior when applicable
numeric precision and serialization policy
fallback behavior, explicitly none when absent
```

No future observation may affect a historical as-of result. No fill, interpolation, epsilon, clipping, winsorization, calendar adjustment, or alternate denominator may appear without being explicit research and frozen methodology.

## Evidence dimensions and state governance

A component exposes only dimensions justified by its economic question. A future signal may have Level and Direction but no Anomaly, a spread-state dimension plus change rarity, or another indicator-specific structure.

Quantitative evidence is not categorical state. A schema field does not justify a label. `null` is a valid deliberate state policy meaning “not classified under this methodology”; it is not synonymous with missing evidence. Component availability/status must carry missing or warm-up meaning separately.

Before any categorical state is frozen, research must establish:

- the economic meaning of every label;
- exact thresholds and boundary equality;
- empirical and historical-case behavior;
- sensitivity and error trade-offs;
- conflict/precedence rules;
- interaction with missingness and quality;
- deterministic explanation semantics;
- version-bump consequences.

The framework prohibits automatic percentile-to-state, Z-to-anomaly, trend-to-direction, materiality, stress, or confidence mappings.

## Candidate-method research criteria

Mandatory core criteria, when meaningful to the question, are:

- economic interpretability and unit transparency;
- prior-only/availability discipline;
- responsiveness versus lag/stability;
- warm-up and missing-data behavior;
- failure modes and structural breaks;
- regime/reference-set dependence;
- outlier, denominator, discreteness, and tie behavior;
- window/reference-set sensitivity;
- redundancy with other proposed evidence;
- downstream usefulness without overclaiming.

Indicator-specific optional criteria may include calendar effects, microstructure, liquidity, seasonality, vendor methodology shifts, residual behavior, or event conditioning. `not applicable` with rationale is valid; meaningless statistical comparisons are not required.

When genuine ambiguity exists, compare reasonable alternatives. When only one method answers the economic question, document why alternatives are inapplicable rather than manufacture a tournament.

## Window and reference-set research

Every production window/reference set requires:

- economic interpretation;
- exact observation/indexing semantics;
- empirical responsiveness/lag behavior;
- minimum history and warm-up;
- comparison with reasonable alternatives;
- known failure cases;
- regime and structural-break analysis;
- lineage and backfill cost.

Long history is not automatically better. Research must distinguish what full-history, rolling-history, recent-relative, and regime-relative references would mean. No universal window defaults exist.

## Rarity, materiality, regime contamination, and redundancy

An anomaly-like project must separately ask what makes an observation statistically rare and what makes it economically large. Store them separately when they answer different questions. A materiality state is optional and requires its own evidence.

Historical normalization research must examine policy eras, volatility/credit regimes, market-structure and source-methodology changes, and other relevant structural breaks. The report must state what reference-distribution contamination means for interpretation.

Multiple metrics require redundancy analysis using suitable tools such as correlation, conditional behavior, conflict cases, and historical comparisons. No universal correlation threshold exists. Correlated measures may remain if their economic questions differ, but must not be described as independent confirmations.

## Failure-mode research and golden historical cases

Research must seek cases where a candidate metric misleads or degenerates. Relevant examples may include a single step, round trip, plateau, zero-heavy sample, wide ties, denominator collapse, extreme outlier, missing observations, source revision, structural break, or methodology change.

Before methodology freeze, name historical or exact synthetic cases that demonstrate the important semantics. Include normal, extreme, conflict, failure-mode, and warm-up-boundary cases when relevant, but do not force inappropriate categories. Golden expected values must come from an independent calculation path or frozen fixture, not the production function under test.

## Minimum research artifact package

Phase 2.2A freezes logical artifact roles and purposes. The frozen [Phase 2.2B artifact standard](SIGNAL_RESEARCH_ARTIFACT_STANDARD.md) defines filenames, generic envelope schemas, hashing, serialization, ownership, consistency, and finalization rules.

### Mandatory logical artifacts

| Artifact role | Purpose |
|---|---|
| Research brief / README | Scope, question, inputs, how to reproduce, artifact map, and explicit non-goals. |
| Selected-input snapshot or exact input manifest | Exact canonical IDs/values/dates/vintages used, or an equivalent reconstructable selection record. |
| `manifest.json` concept | Research identity and provenance, separate from conclusions. |
| Machine-readable primary results | Row-level or case-level candidate outputs needed for audit; format depends on method. |
| Method comparison | Machine-readable alternatives/trade-offs when multiple candidates exist; otherwise a documented not-applicable rationale. |
| Golden/case-study evidence | Machine-readable named cases when historical/synthetic cases are relevant; otherwise rationale. |
| `results.json` concept | Findings and final research decision, separate from provenance. |
| Independent validation record | Method, coverage, hashes/counts, status, and failures. |
| Human review report | Measured facts, interpretation, recommendation, limitations, and decision. |
| Reproducible analysis/validation code | Versioned code that creates and independently checks critical outputs. |

Do not create meaningless empty CSVs. A logical role may be embedded in another artifact only when the manifest declares the mapping and machine readability/reproducibility are preserved. Mandatory, conditional, and optional file rules are authoritative in the Phase 2.2B artifact standard.

## Research manifest contract boundary

Use a distinct `manifest.json` rather than overloading `results.json`:

- `manifest.json` answers “what research run, inputs, code, parameters, and artifacts produced this package?”
- `results.json` answers “what was measured and what decision resulted?”

The Phase 2.2B artifact standard and schemas cover:

```text
research_id
indicator_id and component
research_version
observation count / first date / last date
selected-input snapshot hash
source/vintage summary
analysis timestamp
code revision / Git commit or explicit unavailable reason
research and validation script hashes when available
candidate methods and parameter grid
validation status
decision status
artifact references and hashes
```

2.2A itself does not implement a schema, serializer, validator, or repository convention. Phase 2.2B supplies documentation schemas and examples only; executable validator/helper implementation remains gated to 2.2C.

## Measured fact and interpretation discipline

Research reports distinguish:

```text
MEASURED FACT
RESEARCH INTERPRETATION
DESIGN RECOMMENDATION
```

Methodology freeze records distinguish:

```text
MEASURED FACT
RESEARCH INTERPRETATION
FROZEN PRODUCTION DECISION
DEFERRED QUESTION
```

Observed values must not be presented as economic meaning without an interpretation step, and recommendations must not be presented as measured facts.

## Independent validation

Every quantitative research package independently validates critical calculations. Calling the same implementation twice is not independent. Acceptable paths include separate SQL, a separate Python implementation that does not import the analyzed calculator, small exact fixtures, manual/golden calculations, or another method appropriate to the contract.

Validation must cover formula-critical behavior, current/future exclusion, warm-up boundaries, missingness, ordering, units, and selected-input identity. The validation artifact records its independence, scope, counts/hashes, result, and unresolved limitations.

## Methodology-freeze gate

A component may enter `METHODOLOGY_FROZEN` only when the decision record freezes:

1. economic question, relevance, measured meaning, and explicit non-meaning;
2. production evidence fields and exact formulas;
3. input/output units and numeric precision;
4. windows/reference sets and indexing;
5. current/future inclusion and point-in-time limitations;
6. warm-up and component status behavior;
7. missing observations, revisions, ties, zero scales, and fallbacks;
8. structural failures and invariants;
9. evidence-quality interaction;
10. categorical-state decision, including explicitly none;
11. exact lineage roles, ordering, overlap, and scope;
12. deterministic explanation semantics and forbidden claims;
13. immutable methodology ID and outer-version impact;
14. version-bump rules;
15. known limitations and deferred questions.

Research evidence and independent validation must support the choices. If implementation must choose an economic behavior, the methodology is not frozen.

Use the reusable [methodology-freeze template](SIGNAL_METHODOLOGY_FREEZE_TEMPLATE.md).

## Production implementation-readiness gate

Before `READY_FOR_IMPLEMENTATION`, answer every item deterministically:

```text
formula exact?
inputs and canonical selection exact?
units and numeric policy exact?
window/reference set and indexing exact?
current/future exclusion exact?
warm-up and component status exact?
missing/revision/tie behavior exact?
fallback exact or explicitly none?
state logic exact or explicitly none?
quality interaction exact?
lineage roles/order/scope exact?
explanation meaning and forbidden claims exact?
methodology and outer version identity exact?
failure conditions and invariants exact?
golden cases and independent expected values available?
```

Any “developer decides” answer returns the work to methodology. Implementation may choose ordinary internal code structure only when it cannot alter persisted semantics, identity, lineage, or explanation meaning.

## Component-status semantics

2.2A freezes meanings, not a software enum:

- `available`: the frozen component's mandatory evidence exists and validates.
- `insufficient_history`: inputs are valid but the frozen minimum history is not yet present; expose exact progress when useful and do not shorten the method.
- `unavailable`: optional methodology-specific valid absence for a non-history reason (for example a required benchmark is legitimately unavailable). It must include a deterministic reason and must be frozen before implementation.

Only `available` and `insufficient_history` are mandatory shared concepts. Do not use `unavailable` as a catch-all. Structural corruption, ambiguous selection, invalid values, broken lineage, or invariant failure raises/fails; `structural_failure` is not a normal component status.

`not_classified` is not a component-availability status. A deliberate null state is expressed through the methodology's state policy and explanation while evidence may remain available.

## Evidence-quality semantics

`evidence_quality` means completeness, availability, and trustworthiness of the valid input information set. It is not statistical confidence, forecast probability, model accuracy, or confidence in an economic interpretation.

The existing outer vocabulary remains:

```text
sufficient
limited
insufficient
```

Each outer methodology freezes the mapping from component status and availability limitations to these labels and supplies deterministic quality reasons. Component availability does not silently promote outer quality. Unknown availability remains visible. No numeric confidence percentage is introduced.

Invalid evidence cannot receive a low-quality label; it fails.

## Exact-lineage contract

Every persisted signal observation links every exact processed observation required by its frozen methodology. The methodology declares:

```text
input roles
ordered vs unordered roles
ordering key and direction
window_position semantics
current input role/location
reference inputs
overlap/deduplication policy
required suffix/window reconstruction
revision/vintage identity behavior
lineage scope and expected cost
```

Start/end dates, counts, hashes, or aggregate state do not replace exact inputs. Lineage scope is methodology-specific; expanding full history is never a framework default. Opaque caches that prevent exact reconstruction are prohibited unless a future separately versioned architecture preserves equivalent auditable identity.

## Ordered-lineage validation convention

For every role declared ordered, production must validate the generally applicable invariants:

1. Every referenced processed ID exists and has reachable required upstream lineage.
2. No accidental duplicate `(processed ID, semantic role)` exists.
3. Positions are non-null, unique within the ordered role, and contiguous `0..N-1`.
4. The methodology declares what position order means; if it means time, observations follow its explicit chronological/tie-break rule.
5. No input date is after the signal as-of date.
6. Current input location is deterministic when a current input exists.
7. Required windows/suffixes are reconstructable from the sequence.
8. Intentional overlap between component inputs is deduplicated or repeated according to an explicitly frozen policy.

Strictly increasing dates are not universal: cross-series inputs may share dates. “Current is final” is not universal: it is required only when the methodology declares oldest-to-current ordering. Unordered roles normally use null positions and stable semantic role names.

## Deterministic explanation contract

Same frozen evidence produces the same canonical stored explanation. Canonical explanation logic:

- uses named evidence fields and deterministic branches;
- states units, unavailable/warm-up facts, and relevant tie/conflict evidence;
- respects what the methodology does not mean;
- does not convert rarity into probability/materiality or evidence into state;
- reports deliberate null classification where relevant;
- remains independent of an LLM.

Composition follows:

```text
validated component evidence
→ deterministic component fragments
→ deterministic outer canonical explanation
```

No universal component set or sentence order is frozen. A later UI may rephrase, including through an LLM, but cannot change persisted evidence/state or become the canonical explanation source.

## Versioning rules

Normally requires a new component methodology ID:

- formula, unit, transformation, window/reference set, or indexing change;
- current/future inclusion, missingness, revision, tie, precision, or fallback change;
- warm-up/status, state threshold, quality interaction, or failure change;
- lineage role/order/scope change;
- deterministic economic meaning or allowed claim change.

Normally requires a new outer signal version:

- component addition/removal/replacement;
- outer evidence payload or composition change;
- outer state/quality/explanation contract change;
- outer input identity semantics change.

Both may be required. Old definitions and observations remain resolvable and are never rewritten. Pure spelling/layout changes do not require a bump unless exact explanation text is explicitly a compatibility surface.

## Scaling and lineage-cost review

Before authorizing a large-reference method or historical backfill, estimate:

```text
input links per observation
expected observation/backfill count
total-link growth and worst case
storage and generation latency
reconstruction/query requirements
revision amplification
```

Document why the cost is acceptable. Do not optimize prematurely, but do not authorize an unbounded backfill without an estimate. 2.2A creates no aggregate cache or storage optimization.

## Blocking versus non-blocking

Blocking conditions include an ambiguous formula/unit/reference set, future leakage, unresolvable lineage, unfrozen state threshold/fallback, data incapable of answering the economic question, invalid point-in-time claim, missing critical validation, or an implementation that must invent economic behavior.

Non-blocking follow-ups may include presentation simplification, an experimental secondary diagnostic excluded from authority, future performance optimization after current scope is viable, deferred external context that is not required for the stated question, or additional UI views.

A non-blocking limitation must still be documented and must bound downstream claims.

## Candidate reusable primitives for Phase 2.2C

| Candidate | Classification | 2.2A rationale |
|---|---|---|
| Canonical JSON and selected-snapshot hashing | READY TO ABSTRACT | Already used across identities and independent research snapshots; semantics are content-addressing, not SOFR statistics. |
| Prior/future input-date validation | READY TO ABSTRACT | No-future-input discipline is universal; exact availability rules remain methodology-specific. |
| Ordered-lineage position validation | READY TO ABSTRACT | Existence, uniqueness, contiguity, and declared-order checks are generic. |
| Decimal-safe percent/percentage-point-to-bp conversion | READY TO ABSTRACT | Reusable opt-in unit conversion for rate/spread families when units are explicitly declared. |
| Strict named-field explanation rendering | READY TO ABSTRACT | Already generic and deterministic; component composition API remains separate. |
| Empirical rank with explicit ties | WAIT FOR SECOND FAMILY | Demonstrated twice inside one SOFR family; another indicator must confirm the API and precision needs. |
| Valid-observation fixed-window selection | WAIT FOR SECOND FAMILY | Likely reusable, but cross-series/session/missingness semantics may alter the abstraction. |
| Component status object/schema | WAIT FOR SECOND FAMILY | Meanings are frozen, but one nested payload is not yet justified. |
| Component explanation-fragment composition API | WAIT FOR SECOND FAMILY | The principle is generic; fragment ordering/metadata needs another family. |
| Full-history expanding percentile | SOFR-SPECIFIC | It answers the frozen SOFR Level question and carries regime/storage costs. |
| 60/252 anomaly windows | SOFR-SPECIFIC | Empirically selected for SOFR changes. |
| 20-change Direction and slope20 | SOFR-SPECIFIC | Selected from SOFR path research. |
| Prior-60 Level median | SOFR-SPECIFIC | SOFR local-level reference choice. |
| Gregorian SOFR calendar flags | SOFR-SPECIFIC | Source/instrument context, not a general signal primitive. |

Classification does not authorize implementation. READY items are candidates for 2.2C design and tests.

## Explicit SOFR non-generalizations

Phase 2.2 must not make these defaults or required fields:

```text
Level / Direction / Anomaly component trio
60/252 anomaly windows
20-change Direction horizon
60-level recent median
full-history empirical Level percentile
standard or robust Z
SOFR calendar flags
SOFR explanation order
expanding full-history lineage
SOFR categorical-state absence for every future indicator
```

Only the evidence for or against a future indicator's method can authorize it.

## Phase boundaries

### Phase 2.2B — Research Artifact Standard (complete / frozen)

The [authoritative standard](SIGNAL_RESEARCH_ARTIFACT_STANDARD.md) freezes detailed artifact filenames/schemas, manifest/results/validation ownership, hashes/references, serialization, consistency, and package-finalization checks. It chooses no signal method and implements no calculation helper.

### Phase 2.2C — Proven Reusable Primitives

Implement and test only primitives justified by this contract and 2.2B. Do not add an indicator, universal evidence payload, or universal state engine.

### Phase 2.2D — Framework Validation

Validate that a second materially different indicator can follow the lifecycle and artifacts without being forced into SOFR formulas, component structure, or lineage scope. Actual indicator selection and implementation require separate authorization. Successful validation must show both reusable discipline and preserved indicator-specific freedom.

The authorized Treasury 2s10s research now supplies this scoped validation: see [Phase 2.2D assessment](PHASE_22D_FRAMEWORK_VALIDATION.md). Framework outcome is `PHASE 2.2 FRAMEWORK VALIDATED WITH NON-BLOCKING FOLLOW-UPS`; Curve outcome is independently `MORE_RESEARCH_REQUIRED`. Artifact integrity and lifecycle exercise do not authorize methodology freeze, software workflow enums, production Curve states, or Phase 3. Ten aligned dates validate mechanics but cannot validate broad-history economics.

## Final review questions Q1–Q10

**Q1 — Minimal generic contract.** Economic question; validated point-in-time inputs; exact transformation/reference/warm-up/failure semantics; evidence/state/quality separation; research and validation artifacts; frozen methodology/version identities; exact lineage; deterministic explanation; golden regression and review.

**Q2 — Always indicator-specific.** Economic hypothesis, evidence dimensions/payload, units/transforms, windows/reference sets, diagnostics, states/thresholds, calendar/session behavior, quality mapping details, lineage scope, and allowed downstream interpretation.

**Q3 — Mandatory artifacts before freeze.** Research brief, exact selected inputs and manifest, machine-readable primary results, justified method comparison, relevant golden cases, results/decision JSON, independent validation record, human report, and reproducible code. Empty irrelevant files are prohibited.

**Q4 — Decisions frozen before implementation.** All 15 methodology-gate items: meaning, evidence/formulas, units, reference sets, inclusion, warm-up, missingness/fallbacks, failures, quality, state, lineage, explanation, identity, versioning, and limitations.

**Q5 — Generic component status.** Mandatory meanings are `available` and `insufficient_history`; methodology may freeze reasoned `unavailable`. Structural failure raises. Deliberate null classification is separate.

**Q6 — Standard lineage invariants.** Exact resolvable IDs, no future inputs, no accidental duplicates, explicit roles/order, unique contiguous positions for ordered roles, deterministic current placement when applicable, reconstructable required windows, and frozen overlap/revision policy.

**Q7 — Point-in-time metadata.** Observation date, actual availability timestamp/date and precision, retrieval time, and exact revision/vintage chain; unknown is never fabricated.

**Q8 — Implemented generic helpers.** Phase 2.2C provides canonical hashing, future-input validation, ordered-position validation, explicit rate-unit bp conversion, strict named-field rendering, and artifact-package validation. It does not choose indicator methodology.

**Q9 — Wait for a second family.** Universal component schema/status object, empirical-rank API, window API, explanation-fragment API, methodology registry service, automatic state/confidence engine, and any generic large-reference cache.

**Q10 — Gate readiness.** Research proceeds only with the exact research terminal status; freeze requires all methodology decisions and independent evidence; implementation requires no economic invention; final approval requires preserved identity/lineage/semantics, regression/golden evidence, honest limitations, and no blocking defect.

## Final outcome

**PHASE 2.2A FRAMEWORK CONTRACT FROZEN — READY FOR 2.2B**

No new indicator, production methodology, state threshold, Phase 3 interpretation, trade logic, database lifecycle machinery, artifact schema implementation, or reusable calculation helper is authorized by this document.
