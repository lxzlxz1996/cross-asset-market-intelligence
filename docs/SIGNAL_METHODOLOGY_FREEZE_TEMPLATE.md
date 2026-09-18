# Phase 2 signal methodology-freeze template

Use this record only after the research package reaches `READY_FOR_METHODOLOGY_FREEZE`. Clearly label measured facts, interpretation, frozen decisions, and deferred questions.

## Scope and evidence basis

- Research ID/version and artifact links:
- Selected-input snapshot hash:
- Validation status:
- Scope and non-goals:

## MEASURED FACT

Record only validated empirical findings.

## RESEARCH INTERPRETATION

Explain what the facts imply within the economic boundaries.

## FROZEN PRODUCTION DECISIONS

### D1 — Economic question and boundaries

- Exact question:
- Measures:
- Does not mean:
- Intended downstream use:

### D2 — Production evidence

- Mandatory evidence fields:
- Secondary fields and authority:
- Fields deliberately excluded:

### D3 — Exact formulas and invariants

- Formula per field:
- Equality/tie/zero-scale behavior:
- Hard validation invariants:

### D4 — Units and numeric precision

- Input/output units:
- Conversion:
- Decimal, rounding, serialization:

### D5 — Windows / reference sets

- Exact count/indexing:
- Economic meaning:
- Alternatives rejected and why:

### D6 — Current/future inclusion and point-in-time semantics

- Current inclusion/exclusion:
- Future exclusion:
- Availability and revision limitations:

### D7 — Warm-up and component status

- Exact minimum inputs:
- `available` / `insufficient_history` / justified `unavailable` behavior:
- Exact progress/null fields:

### D8 — Missing values, revisions, ties, and fallbacks

- Missing/non-publication handling:
- Vintage selection:
- Fill/interpolation/fallback explicitly none or exact:

### D9 — Evidence-quality behavior

- Component-to-outer mapping:
- Quality reasons:
- Unknown availability:

### D10 — State decision

- Exact labels/thresholds/conflict rules, or deliberate null state:
- Interpretation and forbidden claims:

### D11 — Exact lineage

- Roles, ordering, positions, current location:
- Overlap/deduplication:
- Reconstructable windows:
- Cost estimate:

### D12 — Deterministic explanation semantics

- Required facts and branches:
- Tie/conflict/unavailability wording:
- Forbidden wording:

### D13 — Immutable methodology identity and outer version

- Component methodology ID:
- Required outer signal version:
- Frozen parameter definition:

### D14 — Version-bump rules

- Component-ID bump conditions:
- Outer-version bump conditions:
- Non-semantic changes that do not bump:

### D15 — Limitations and deferred questions

- Accepted limitations:
- Blocking conditions:
- Explicitly deferred work:

## Structural failures

List every condition that must fail rather than become low quality or normal unavailability.

## Final evidence contract

Provide exact field names, nesting, types/units, statuses, nullability, and invariants. Indicator-specific payloads are permitted.

## Golden cases and expected behavior

Link independently calculated cases that production tests must preserve.

## Implementation-readiness checklist

Every item must be `YES`; otherwise return to methodology work.

```text
[ ] Formula exact?
[ ] Inputs and canonical selection exact?
[ ] Units and numeric policy exact?
[ ] Window/reference set and indexing exact?
[ ] Current/future exclusion exact?
[ ] Warm-up and component status exact?
[ ] Missing/revision/tie behavior exact?
[ ] Fallback exact or explicitly none?
[ ] State logic exact or explicitly none?
[ ] Quality interaction exact?
[ ] Lineage roles/order/scope exact?
[ ] Explanation meaning and forbidden claims exact?
[ ] Methodology ID and outer version exact?
[ ] Structural failures and invariants exact?
[ ] Golden fixtures and independent expectations available?
```

## DEFERRED QUESTIONS

Deferred work must not be silently implemented under this methodology identity.

## Production readiness decision

Choose exactly one:

```text
METHODOLOGY_FROZEN_READY_FOR_IMPLEMENTATION
MORE_METHODOLOGY_RESEARCH_REQUIRED
BLOCKED_BY_DATA_OR_ARCHITECTURE
```
