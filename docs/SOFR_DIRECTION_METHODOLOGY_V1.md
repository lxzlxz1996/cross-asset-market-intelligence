# SOFR direction methodology v1 decision record

## Scope and status

This document freezes the evidence-only Direction component methodology derived from the completed [SOFR Direction Research](../notebooks/sofr_direction/outputs/report.md). Phase 2.1B-7 implements this contract without populating `direction_state`, altering anomaly v1, adding level methodology, or adding Phase 3 interpretation.

**Production readiness:** **METHODOLOGY FROZEN — READY FOR DIRECTION IMPLEMENTATION**

**Implementation status:** Phase 2.1B-7 complete in outer `sofr_rate_state/v2`; v1 remains anomaly-only and immutable.

**Component methodology identity:** `sofr_direction_evidence_v1`

**Required outer implementation identity:** `signal_id=sofr_rate_state`, `signal_version=v2`

The outer version is normative. The existing active `sofr_rate_state/v1` definition and its persisted observation are immutable and describe only `sofr_change_rarity_v1`. Adding Direction changes the economic question, measured evidence, parameter definition, explanation, and evidence payload. Reusing or mutating outer v1 would violate the Phase 2.1A immutable-definition contract. Outer v1 therefore remains the frozen anomaly-only record; Phase 2.1B-7 registers the combined anomaly-plus-Direction implementation as v2.

## Economic question and boundary

Direction asks:

> Over the most recent 20 valid SOFR changes, what were the endpoint displacement, sign composition, and concentration of the observed path?

It measures recent SOFR path evidence. It does not identify funding or liquidity stress, monetary-policy cause, anomaly, market risk-on/risk-off, an asset-return direction, or a portfolio action. Direction and anomaly remain orthogonal components.

## Evidence basis

### MEASURED FACT

- The validated research snapshot contains 2,112 selected SOFR levels and 2,111 consecutive-valid-observation changes from 2018-04-03 through 2026-09-16.
- At 20 changes, adjacent nonzero sign-flip rates were 10.10% for net change and 3.45% for sign balance. Twenty-level slope had a 7.75% rate. Five/ten windows were noisier; 60 was slower and more prone to stale direction.
- `net_change_20=0` did not imply a quiet path: on 2019-10-21 the total absolute 20-change path was 184bp.
- Median change was exactly zero in 77.92% of eligible 20-change windows.
- Completed steps produced large net displacement but weak or contrary sign composition; slope temporarily represented a completed step as a smooth trend.
- Correlations of recent anomaly rarity with signed net20, absolute net20, and slope20 were approximately 0.046, 0.059, and 0.060.

### RESEARCH INTERPRETATION

No single scalar distinguishes gradual movement, a completed step, and a volatile round trip. Net displacement supplies magnitude, exact sign counts supply persistence evidence, and path concentration exposes whether movement is distributed or dominated by one observation. Linear slope is useful only as a labeled diagnostic. The research does not establish defensible magnitude, persistence, or stability thresholds.

## Frozen decisions

| ID | FROZEN PRODUCTION DECISION |
|---|---|
| D1 | The primary horizon is exactly the most recent 20 consecutive valid SOFR changes. It uses 21 selected processed SOFR levels and never uses calendar days or a shortened window. The 5/10/60 candidates remain research-only and do not vote in production. |
| D2 | `net_change_20_bp` is mandatory primary magnitude evidence. It is not a classifier by itself. |
| D3 | `positive_change_count_20`, `zero_change_count_20`, and `negative_change_count_20` are mandatory persistence evidence. Shares and `direction_balance_20` are not persisted because they are exactly derivable from the counts and add no lineage or audit information. |
| D4 | `path_total_abs_20_bp`, `largest_change_abs_20_bp`, and `largest_change_share_20` are mandatory path-concentration evidence. The share is null when the total absolute path is zero; otherwise it is on the 0–1 scale. |
| D5 | `linear_slope_20_bp_per_valid_observation` is retained as a nullable secondary diagnostic over the latest 20 levels. It cannot determine or override state, magnitude, persistence, or concentration evidence. No p-value or residual-distribution claim is produced. |
| D6 | Rolling median change is excluded from production evidence. It remains research-only. |
| D7 | `direction_state` is always null under this component methodology. No rising/stable/falling thresholds or conflict precedence are defined. Production persists transparent evidence and deterministic factual explanation instead. |
| D8 | A completed step is represented numerically as endpoint displacement, exact sign counts, total path, largest move, and concentration share. It is not automatically labeled rising or falling. |
| D9 | Magnitude/persistence conflicts remain explicit; they are not collapsed into a score. Explanation reports endpoint sign/magnitude and sign counts, then reports concentration. |
| D10 | Direction evidence is unavailable until exactly 20 valid changes exist. Windows are never shortened. Valid warm-up is represented inside `direction_evidence`; integrity failures prevent persistence. |
| D11 | Exact reconstruction requires all 21 ordered processed SOFR levels for the Direction suffix. In the combined signal, these are the final 21 members of the existing ordered `sofr_level_history` lineage sequence. |
| D12 | Implementing this component requires outer `sofr_rate_state/v2`. Later semantic changes listed under Versioning require another outer version and a new component methodology ID. |

## Frozen calculation contract

Let the selected valid SOFR levels ending at the as-of observation be `L_0, ..., L_20`, in percentage points and strictly increasing observation-date order. For `i=1,...,20`:

```text
change_i_bp = 100 × (L_i - L_(i-1))
```

Use decimal-safe selected values. Do not round before sign, equality, sum, maximum, or invariant evaluation. A valid observation is the preceding/current canonical selected processed observation; it need not be a consecutive calendar date. Do not fill or interpolate missing dates.

### Magnitude

```text
net_change_20_bp = 100 × (L_20 - L_0)
                 = sum(change_i_bp for i=1..20)
```

Both expressions must agree before serialization. A mismatch is an integrity failure.

### Sign composition

```text
positive_change_count_20 = count(change_i_bp > 0)
zero_change_count_20     = count(change_i_bp == 0)
negative_change_count_20 = count(change_i_bp < 0)
```

Normative invariant:

```text
positive_change_count_20
+ zero_change_count_20
+ negative_change_count_20
= 20
```

Shares and balance may be computed by a consumer as views, but they are not part of the persisted v1 component evidence contract:

```text
positive_share_20 = positive_change_count_20 / 20
zero_share_20 = zero_change_count_20 / 20
negative_share_20 = negative_change_count_20 / 20
direction_balance_20 = positive_change_count_20 - negative_change_count_20
```

### Path concentration

```text
path_total_abs_20_bp = sum(abs(change_i_bp) for i=1..20)
largest_change_abs_20_bp = max(abs(change_i_bp) for i=1..20)

largest_change_share_20 =
    null, when path_total_abs_20_bp == 0
    largest_change_abs_20_bp / path_total_abs_20_bp, otherwise
```

Normative invariants:

- `path_total_abs_20_bp >= abs(net_change_20_bp)`.
- `0 <= largest_change_abs_20_bp <= path_total_abs_20_bp`.
- When non-null, `0 < largest_change_share_20 <= 1` and it must equal the stated ratio without a hidden threshold.
- A null share means only that all 20 changes are exactly zero; it is not missing data.

### Secondary slope diagnostic

Use the latest 20 levels `L_1, ..., L_20`, indexed `x=0,...,19`. Fit ordinary least squares descriptively:

```text
SOFR_x = alpha + beta × x + error_x
linear_slope_20_bp_per_valid_observation = 100 × beta
```

The slope uses 20 levels (19 changes), while the primary Direction horizon uses 20 changes (21 levels). Both end at the current level. The Direction lineage already contains every required slope input. No intercept, residual statistic, p-value, normality claim, or regression-based state is persisted.

Slope is null whenever the enclosing Direction evidence is unavailable. It does not become available one observation early even though 20 levels would mathematically exist after 19 changes.

## Final Direction v1 component evidence contract

The following object is implemented by outer `sofr_rate_state/v2`. Counts are integers, bp fields use basis points, and the concentration share uses the 0–1 scale.

```text
direction_evidence:
  methodology_id: sofr_direction_evidence_v1
  status                         # available | insufficient_history
  horizon_change_count: 20
  available_change_count         # min(total available valid changes, 20)
  baseline_start_date            # date of L_0; null unless available
  baseline_end_date              # date of L_20/current; null unless available

  net_change_20_bp               # null unless available

  positive_change_count_20       # null unless available
  zero_change_count_20           # null unless available
  negative_change_count_20       # null unless available

  path_total_abs_20_bp           # null unless available
  largest_change_abs_20_bp       # null unless available
  largest_change_share_20        # null if unavailable or zero path

  secondary_diagnostics:
    linear_slope_20:
      role: secondary_only
      level_count: 20
      baseline_start_date        # date of L_1; null unless available
      baseline_end_date          # date of L_20/current; null unless available
      value_bp_per_valid_observation
```

Fields deliberately absent: persisted shares, persisted direction balance, median change, 5/10/60 evidence, a combined score, a persistence threshold, a stable band, a step threshold/state, a reversal state, calendar adjustment, policy-event cause, and categorical `direction_state`.

## Magnitude, persistence, step, and reversal semantics

### FROZEN PRODUCTION DECISION

The component reports independent facts rather than an opaque score:

- Positive/negative net displacement with neutral or opposite sign composition remains an explicit magnitude/persistence conflict. It may be consistent with a step or reversal, but production does not assign that cause.
- Small net displacement with many same-sign changes remains explicit evidence of repeated small movement. “Small” is not a production label until a future threshold is researched and versioned.
- Zero net displacement with nonzero total path is a round-trip-shaped numeric pattern, not proof of stability. Explanation reports both exact values.
- Net displacement and sign composition pointing the same way are reported together without upgrading the observation to a categorical state.
- A completed step is not automatically rising/falling. The largest-change share quantifies concentration; no concentration boundary is applied.
- No fourth `reversing` state is introduced. A reversal-shaped conflict is explained through the net sign and exact counts.

## Deterministic explanation contract

Do not implement the formatter in this freeze phase. The later implementation must use named evidence fields and deterministic branching only.

When Direction is available, report in this order:

1. Exact 20-change endpoint displacement (`higher`, `lower`, or `unchanged`).
2. Exact positive, unchanged, and negative counts.
3. Exact total absolute path and largest single absolute change; report the share when non-null, otherwise state that all 20 changes were unchanged.
4. If net displacement is positive while positive count does not exceed negative count, state: “The endpoint is higher, while positive changes do not outnumber negative changes in the window.” Use the sign-symmetric sentence for negative displacement. This is a factual conflict rule, not a state or threshold.
5. State: “No categorical direction state is assigned under `sofr_direction_evidence_v1`."

Example:

```text
SOFR is 7bp higher than 20 valid changes ago. Within those 20 changes,
9 were positive, 8 were unchanged, and 3 were negative. Total absolute
path movement was 15bp; the largest single change was 3bp and accounted
for 20.0% of that path. No categorical direction state is assigned under
sofr_direction_evidence_v1.
```

An unavailable component states the exact progress: “Direction evidence is unavailable because X of 20 required valid changes are available.”

Forbidden causal or interpretive wording includes `hawkish`, `dovish`, `stress`, `liquidity tightening/deterioration`, `bullish`, `bearish`, `normal`, and `unusual`. The existing anomaly explanation remains authoritative for anomaly evidence.

## Calendar contract

Direction adds no calendar field, adjustment, exclusion, reweighting, threshold, or quality rule. Existing anomaly `calendar_context` may be shown beside Direction facts but cannot alter Direction calculations or state. Policy/FOMC causes are not inferred.

## Warm-up, failures, and shared evidence quality

### FROZEN PRODUCTION DECISION

- Fewer than 20 valid changes: `direction_evidence.status=insufficient_history`; `available_change_count` shows exact progress; dates and computed metrics are null. The window is not shortened and the slope is not exposed early.
- At least 20 valid changes: Direction evidence is available and all mandatory fields/invariants must validate.
- Missing current or previous selected SOFR levels retains the anomaly v1 behavior: persist no combined signal observation.
- A missing/duplicate/nonchronological required level, broken processed lineage, count mismatch, non-finite output, endpoint/sum mismatch, or concentration invariant failure is an integrity error: persist no combined observation.
- Do not add component-specific `EvidenceQuality`. `direction_evidence.status` describes warm-up only. The outer shared quality remains governed by the existing combined information set: anomaly recent/broad warm-up and honest availability. Thus Direction may be available after 20 changes while the combined signal remains `insufficient` before 60 prior anomaly changes, `limited` before 252, and capped at `limited` when availability is unknown.
- Do not fabricate publication timestamps. Reuse the exact availability derivation from the complete selected lineage.

## Exact lineage

The combined v2 observation records one ordered `sofr_level_history` sequence, oldest first, using the existing Phase 2.1A input contract. It does not add duplicate Direction input rows or start/end-only lineage.

- When broad anomaly evidence is available, the sequence remains the latest 254 unique selected processed SOFR levels required by anomaly v1. Direction uses its final 21 levels; slope uses the final 20.
- During warm-up, include all available selected levels up to the same 254-level cap. Once Direction is available, its exact 21-level suffix must exist.
- `window_position=0` is the oldest stored input and positions increase toward the current observation.
- Phase 1 canonical revision/vintage selection remains authoritative. A changed selected processed identity creates a distinct signal observation; no historical record is overwritten.

## Signal identity and parameters

The immutable outer v2 definition and every observation's `parameters_used` include at least:

```text
direction_methodology_id: sofr_direction_evidence_v1
direction_horizon_change_count: 20
direction_window_unit: consecutive_valid_changes
direction_required_level_count: 21
direction_net_change_unit: basis_points
direction_sign_equality: exact_decimal_bp_no_prerounding
direction_persisted_sign_fields: [positive_count, zero_count, negative_count]
direction_derived_not_persisted: [positive_share, zero_share, negative_share, direction_balance]
direction_path_total: sum_absolute_changes
direction_largest_change: max_absolute_change
direction_zero_path_share_policy: null
direction_slope_role: secondary_only
direction_slope_level_count: 20
direction_state_policy: null_evidence_only
direction_calendar_policy: no_adjustment_no_direction_fields
direction_missing_observation_policy: previous_valid_no_fill_no_interpolation
```

The outer v2 definition must also preserve the anomaly v1 parameter contract unchanged and describe both orthogonal components in its economic question, measured evidence, limitations, and explanation semantics.

## Versioning

### FROZEN PRODUCTION DECISION

Adding Direction is itself an outer-version change: it is implemented as `sofr_rate_state/v2`; never mutate or backfill outer v1 with Direction fields.

After v2 exists, any of the following requires a new outer signal version and a new Direction component methodology ID:

- changing the 20-change horizon, valid-observation indexing, required level count, or missing-observation policy;
- changing bp conversion, decimal/sign equality, net-change definition, or sign-count treatment;
- adding/removing persisted sign or path fields, or changing zero-path share semantics;
- changing slope level count, formula, units, inclusion, or authority;
- adding median, 5/10/60 evidence, multi-window voting, or an opaque combined score;
- adding any rising/stable/falling threshold, conflict precedence, step/reversal state, or magnitude/persistence band;
- allowing anomaly or calendar context to alter Direction;
- changing warm-up, integrity-failure, shared-quality, lineage, or deterministic claim semantics.

Purely cosmetic presentation that does not alter a persisted claim, additional selected observations under unchanged Phase 1 rules, and a new raw vintage selected under the unchanged canonical rule do not change methodology. New input identity still produces a distinct immutable observation.

## DEFERRED QUESTION

- Economically and empirically defensible thresholds for rising, stable, and falling.
- Whether a later state design needs a separately researched magnitude band, persistence boundary, and concentration rule.
- Whether the secondary slope materially improves downstream use enough to retain in a future version.
- Any formal step or reversal classifier.
- Policy-event context from an independently approved dataset.
- Historical publication-time reconstruction and point-in-time backtesting.

These questions do not block implementation of the frozen evidence-only component.
