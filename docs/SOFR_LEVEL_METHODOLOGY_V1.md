# SOFR Level methodology v1 decision record

## Scope and status

This document freezes the evidence-only Level component methodology derived from the completed [SOFR Level Research](../notebooks/sofr_level/outputs/report.md). Phase 2.1B-10 subsequently implemented this unchanged contract in outer `sofr_rate_state/v3` without a schema change.

**Production readiness:** **METHODOLOGY FROZEN — READY FOR LEVEL IMPLEMENTATION**

**Implementation status:** Phase 2.1B-10 complete in outer `sofr_rate_state/v3`; v1 and v2 remain immutable.

**Component methodology identity:** `sofr_level_evidence_v1`

**Outer implementation identity:** `signal_id=sofr_rate_state`, `signal_version=v3`

Existing outer `sofr_rate_state/v1` and `sofr_rate_state/v2` remain active, immutable production definitions. V1 contains anomaly evidence only. V2 contains unchanged anomaly evidence plus Direction evidence. V3 preserves both and adds the frozen Level component.

## Production implementation

- Implementation: `cross_asset_market_intelligence.signals.sofr_rate_state_v3`.
- Interface: `generate_sofr_rate_state_v3(connection, as_of_observation_date=...)`; omission of as-of safely selects the latest canonical valid observation.
- CLI: `python -m cross_asset_market_intelligence generate-sofr-rate-state --version v3 --as-of YYYY-MM-DD`. The historical default remains v1.
- V3 delegates the unchanged anomaly and Direction calculations to the frozen v2 builder, then adds Level evidence and replaces the truncated v2 lineage with the exact expanding sequence.
- Registration and observation persistence use the existing Phase 2.1A APIs. No schema change is required.

## Economic question and boundary

Level asks:

> Where does the current SOFR level sit relative to broad historical experience and relative to its recent local environment?

It reports descriptive sample position and level distance. It does not identify funding-market stress, system liquidity, tight/easy or hawkish/dovish policy, likely Federal Reserve action, valuation, expected returns, asset direction, or a portfolio action. SOFR is strongly policy-regime dependent; a historically high SOFR level is not evidence of funding stress by itself.

## Evidence basis

### MEASURED FACT

- The validated research snapshot contains 2,112 canonical selected SOFR observations from 2018-04-03 through 2026-09-16. Independent recomputation validated 83,353 calculations. Snapshot SHA-256: `bef72683a3fe8fe0da76518ca325a19867fbb9249a7a69a76c510f65d167792d`.
- Full-history prior-only midrank was eligible on 2,111 dates. Its mean/median strict-to-weak tie bracket was approximately 2.51/0.92 percentile points, with a maximum of 60 points.
- Rolling 60/120/252/504 level percentiles saturated near 0 or 100 around level shifts, adapted mechanically to policy environments, and retained tie brackets. The 60-observation mean bracket was approximately 18.85 points.
- Distance from the prior-60 median had a zero median revision on unchanged-level comparisons and approximately 0.823 correlation with 20-change Direction net displacement.
- Level Z became transition-sensitive and scale-dependent. The 60-observation version had 35 zero-scale cases; longer windows generated increasing frequencies of absolute Z at least 2 as regimes moved.
- MAD was zero in approximately 19.54%, 16.67%, and 9.46% of eligible 60/120/252-level windows.

### RESEARCH INTERPRETATION

The raw level is indispensable primary evidence. Expanding prior-only empirical rank provides a transparent broad sample location when its tie bracket remains visible. The prior-60 median supplies a stable, directly interpretable local reference in rate and basis-point units. These two contexts answer different questions and must not be collapsed. Rolling percentiles, Level Z, and robust Z add transition mechanics, tie/scale problems, or evidence duplication without enough independent economic meaning for production.

## Frozen decisions D1–D14

| ID | FROZEN PRODUCTION DECISION |
|---|---|
| D1 | `current_level_percent` is mandatory production evidence. It is the canonical selected processed SOFR observation in percentage points/percent per annum, without normalization. |
| D2 | Expanding full-history prior-only empirical percentile is mandatory broad-context production evidence. It is descriptive sample position only. |
| D3 | `midrank_percentile` is the primary displayed broad-rank value. It is calculated from exact decimal comparisons and is not a library percentile convention. |
| D4 | Strict and weak percentiles plus exact less/equal/greater counts are mandatory audit fields. The tie bracket is never hidden in stored evidence. |
| D5 | The broad baseline contains one canonical valid selected processed SOFR observation for every eligible economic date strictly before the current as-of observation, under active frozen Phase 1 selection rules. There is no calendar filling. |
| D6 | The median of exactly the prior 60 valid selected levels and the current-minus-median distance in bp are mandatory recent-context production evidence. The current level is excluded and the window is never shortened. |
| D7 | Rolling 60/120/252/504 level percentiles are excluded from production and remain research diagnostics only. |
| D8 | All Level Z variants are excluded from production and remain research evidence only. |
| D9 | Robust Level Z/MAD variants are excluded from production. No epsilon, fallback, or hidden scale repair is permitted. |
| D10 | `level_state` remains null. No low/normal/high boundary, policy-regime label, score, vote, or classifier is defined. |
| D11 | The raw level is available immediately. Broad rank is unavailable with zero prior observations and mathematically available with at least one. Recent context is unavailable until exactly 60 prior valid levels exist. Context statuses expose warm-up; no top-level Level status enum is added. |
| D12 | Exact lineage is one ordered `sofr_level_history` sequence containing the current processed observation and every eligible prior processed observation used by the expanding rank. The prior-60 median uses the final 60 prior members of that same sequence; duplicate lineage rows are prohibited. |
| D13 | Production integration requires new outer `sofr_rate_state/v3`. V1 and v2 must not be mutated, reinterpreted, or backfilled with Level evidence. |
| D14 | Any semantic change listed under Versioning requires a new Level methodology ID and, once integrated, a new outer signal version. |

## Raw current-level contract

`current_level_percent` is the actual selected Phase 1 processed value for `indicator_id=sofr`. The source and canonical processed unit is percent per annum: source value `3.62` means `3.62%`, not `0.0362`, 362bp, or a percentage return.

Calculations must construct decimal-safe values from the canonical stored representation. Do not round before equality, ordering, median, subtraction, or invariant checks. Persist the numeric evidence at the canonical processed precision. A standard explanation displays two decimal places, matching the official SOFR quotation convention; display formatting does not change stored evidence or calculations. If a future authorized source contract changes canonical precision, that is a methodology/version review, not a silent display or calculation change.

The raw current level has no history requirement. Outer v3 inherits the anomaly component's requirement for a current and previous valid selected level before an outer signal observation can exist; that outer rule does not change the Level component's mathematical availability.

## Broad historical-context calculation

For current level `L_t`, let the ordered broad baseline be `B_t`, containing all and only eligible canonical selected SOFR levels with economic observation date strictly before `t`. Let `N = len(B_t)`.

```text
less_count    = count(level in B_t where level < L_t)
equal_count   = count(level in B_t where level == L_t)
greater_count = count(level in B_t where level > L_t)

strict_percentile  = 100 × less_count / N
weak_percentile    = 100 × (less_count + equal_count) / N
midrank_percentile = 100 × (less_count + 0.5 × equal_count) / N
```

Normative invariants when available:

- `N >= 1`.
- `less_count + equal_count + greater_count == N`.
- `strict_percentile <= midrank_percentile <= weak_percentile`.
- `midrank_percentile == (strict_percentile + weak_percentile) / 2`.
- The current observation is not a member of `B_t`; no later observation is a member of `B_t`.
- Exact canonical decimal equality defines ties; display rounding never defines them.

The midrank is a 0–100 empirical rank, not a probability, forecast, policy state, stress score, or valuation measure.

## Full-history baseline semantics

“Expanding full history” means every canonical valid processed SOFR observation strictly before the current as-of observation under the active Phase 1 revision/vintage-selection rules:

- The presently validated history begins on 2018-04-03. Methodologically, the baseline begins with the earliest eligible canonical observation present under the authorized source/history contract; no hard-coded later start date is allowed.
- Each economic date contributes at most one selected processed observation. Duplicate processed vintages for one date are resolved only by the frozen Phase 1 rule: selected revised `r` when present, otherwise selected `original`. Arbitrary ID, insertion, or retrieval ordering is prohibited.
- Missing/non-publication dates remain absent. Do not fill weekends, holidays, or missing dates, and do not interpolate.
- A current date cannot select two vintages or two values. Ambiguous/invalid canonical selection is a structural failure.
- A newly selected source revision creates a different processed input identity and therefore a different deterministic signal identity. Existing persisted observations are never overwritten.
- The current date and all future economic dates are excluded.

The expanding baseline applies independently at each as-of date. A stored result for date `t` is reconstructed from its exact recorded inputs; later future-dated observations never enter or revise that result. Recomputing an old date against today's full dataset is prohibited unless the calculation first enforces `observation_date < t` and records the exact then-selected canonical inputs. A later ingested revision to a pre-`t` input may produce a new immutable signal observation with new lineage; it does not mutate the old record and does not imply point-in-time publication reconstruction.

## Full-history lineage and operational cost

The existing Phase 2.1A exact-lineage principle remains normative:

```text
signal observation
→ every exact selected processed SOFR observation used
→ each processed observation's exact Phase 1 raw lineage
```

For a mature Level observation, record one ordered `sofr_level_history` sequence, oldest first, containing all broad-baseline inputs followed by the current level. `window_position=0` is the earliest input and the final position is current. The final 61 members reconstruct the prior-60 median and current distance when recent context is available. Do not add duplicate recent-window roles, and do not substitute baseline dates, counts, a checksum, an untracked aggregate, or an opaque cache for exact inputs.

This cost is accepted for `sofr_level_evidence_v1`. At the validated 2026-09-16 as-of date it means 2,111 prior processed levels plus the current level, or 2,112 persisted v3 input links. The number grows by approximately one per newly eligible SOFR observation. Storage and backfill volume must be planned operationally, but optimization may not weaken reproducibility. A future transparent, versioned aggregation architecture would require separate research and a methodology/version change.

## Recent-context calculation

Let `R_t` be exactly the last 60 valid selected levels in `B_t`, ordered oldest to newest. It is available only when `N >= 60`.

```text
prior_60_median_level_percent = median(R_t)

distance_from_prior_60_median_bp =
    100 × (current_level_percent - prior_60_median_level_percent)
```

For the even 60-member window, the median is the arithmetic mean of the 30th and 31st ordered values. Use exact decimal arithmetic. The current observation is not in `R_t`. The window is based on valid observations, not calendar days, and is never shortened. Its baseline dates are the dates of the oldest and newest members of `R_t`.

Median is selected for this specific role because the research found that it responds appropriately to the recent environment, remains stable on plateaus, is less dragged by policy-level transitions than the rolling mean, and produces an interpretable rate/bp distance. This is not a general claim that median is statistically superior in every application.

The approximately 0.823 correlation with Direction net displacement means recent Level distance is not independent confirmation of Direction. Recent Level describes the current rate relative to a local level reference; Direction describes the path over the latest 20 changes. They may agree during trends. Never average them, vote them together, treat agreement as two independent signals, or use one to promote the other.

## Broad and recent contexts remain separate

- Broad historical context answers: “Where is current SOFR relative to all eligible historical observations available before this as-of date?”
- Recent context answers: “How far is current SOFR from the median of its prior 60 valid observations?”

Neither is authoritative over the other. Do not combine them into a composite Level score, state, confidence, or conflict-resolution rule.

## Excluded methods

### Rolling percentiles

Rolling 60/120/252/504 level percentiles remain research diagnostics and are absent from production evidence. They saturate around level shifts, generate wide tie brackets on plateaus, and adapt mechanically to policy environments. Including them would add overlapping evidence without a distinct frozen economic question.

### Level Z

Level Z is absent from production evidence. Transition amplification, zero/near-zero scale, and scale dependence make it behave partly as a transition detector rather than stable Level context. Anomaly v1's secondary Z does not establish a reason to retain Level Z; the components answer different questions.

### Robust Z / MAD

Robust Level Z and MAD are absent. Discrete SOFR plateaus create structural zero-scale cases. No epsilon, hidden repair, alternate denominator, or fallback is allowed.

## Final Level v1 component evidence contract

Percent values are percentage points/percent per annum; bp values are basis points. Counts are integers. Percentiles use the 0–100 scale.

```text
level_evidence:
  methodology_id: sofr_level_evidence_v1
  current_level_percent

  broad_historical_context:
    status                         # available | insufficient_history
    prior_observation_count
    baseline_start_date            # null unless available
    baseline_end_date              # null unless available
    less_count                     # null unless available
    equal_count                    # null unless available
    greater_count                  # null unless available
    strict_percentile              # null unless available
    midrank_percentile             # null unless available; primary display rank
    weak_percentile                # null unless available

  recent_context:
    status                         # available | insufficient_history
    required_prior_level_count: 60
    available_prior_level_count    # min(prior_observation_count, 60)
    baseline_start_date            # null unless available
    baseline_end_date              # null unless available
    prior_60_median_level_percent  # null unless available
    distance_from_prior_60_median_bp # null unless available
```

No top-level Level status is persisted. The mandatory raw level and the two context statuses express availability without a redundant `partial` enum. The broad object's name and methodology ID fix its expanding-prior-history reference; the recent object's field names and required count fix its reference, so separate repeated `reference_type` strings are unnecessary.

Fields deliberately absent include rolling percentiles, rolling means, Level Z, robust Z/MAD, composite scores, policy adjustment, calendar adjustment, stress/liquidity labels, confidence, and categorical `level_state`.

## Warm-up and outer evidence quality

### FROZEN PRODUCTION DECISION

- Current selected level: always present in a persisted outer observation and requires no Level history.
- Zero prior valid levels: broad context has `status=insufficient_history`, `prior_observation_count=0`, and all dates/counts/percentiles null.
- At least one prior valid level: broad context has `status=available`. Very small baselines remain valid but their exact count and tie bracket expose limited sample depth; no arbitrary minimum or adjective is imposed.
- Fewer than 60 prior valid levels: recent context has `status=insufficient_history`, exact `available_prior_level_count`, and null dates/median/distance.
- At least 60 prior valid levels: recent context has `status=available` and all mandatory fields validate.

Level availability does not promote, downgrade, or redefine outer `evidence_quality`. V3 inherits the anomaly/availability quality mapping: anomaly warm-up and honest information availability remain authoritative. Level adds no component confidence score and no duplicate quality reasons for valid warm-up; its context statuses provide exact progress. Unknown publication availability continues to cap outer quality at `limited` under the existing contract. Structural Level corruption is never represented as `limited` or `insufficient_history`; it prevents persistence.

## Exact lineage and availability

Outer v3 records one ordered, deduplicated `sofr_level_history` sequence sufficient for all anomaly, Direction, and Level evidence. Because Level uses every eligible prior level, anomaly and Direction inputs are suffixes of this sequence. Every required processed ID must resolve through Phase 1 lineage.

Availability precision is derived honestly from the complete selected lineage under the existing Phase 2.1A rules. Retrieval time is not publication time. This Level methodology does not claim point-in-time historical publication reconstruction.

## Deterministic explanation contract

The v3 formatter uses named evidence fields and factual branching only. When both contexts are available, it reports:

```text
SOFR is currently 3.62%.

Relative to all eligible prior SOFR observations, the current level has a
midrank of X on a 0–100 scale (strict Y; weak Z) across N prior observations.

The current level is D bp above/below/equal to the median of the prior 60
valid SOFR observations.

The broad historical rank describes sample position only and does not imply
funding stress or monetary-policy state. No categorical Level state is assigned
under sofr_level_evidence_v1.
```

Strict and weak percentiles are always included when broad rank is available. This exposes every tie bracket without inventing a material-width threshold. The standard explanation need not repeat `equal_count`, but the count remains stored and may be shown in an audit view. For unavailable context, report the exact available/required count rather than estimating a rank or shortening the window.

Use `above`, `below`, or `equal to` from the exact signed bp distance. Forbidden Level-only wording includes `stressed`, `liquidity is poor`, `tight`, `easy`, `hawkish`, `dovish`, `dangerously high`, `bullish`, `bearish`, `normal`, and `unusual`.

## Structural failures

Any of the following prevents persistence and must fail visibly:

- missing/non-finite current processed level or invalid current processed ID;
- current observation included in a prior baseline;
- future-dated observation included in a baseline;
- duplicate, ambiguous, or nonchronological economic-date selection;
- selection that violates Phase 1 canonical vintage rules;
- broad counts that do not sum to `prior_observation_count`;
- percentile ordering or midrank invariant failure;
- an available recent window containing other than exactly 60 prior valid levels;
- incorrect even-count median or inconsistent bp distance;
- a status marked available with missing required fields, or insufficient with non-null calculated fields/dates;
- incomplete, duplicated, misordered, or unresolvable lineage;
- any use of calendar filling, hidden rounding, future observations, or opaque untracked aggregates.

Valid insufficient history is not a failure. Tie concentration is not a failure because exact tie evidence remains visible.

## Signal identity and frozen parameters

The immutable outer v3 definition and each observation's `parameters_used` encode at least:

```text
level_methodology_id: sofr_level_evidence_v1
level_current_unit: percent_per_annum
level_current_normalization: none_canonical_processed_value
level_broad_reference: all_canonical_valid_prior_observations
level_broad_current_excluded: true
level_broad_future_excluded: true
level_broad_percentile_primary: midrank
level_broad_percentile_audit: [strict, weak, less_count, equal_count, greater_count]
level_tie_equality: exact_decimal_percent_no_prerounding
level_recent_reference: prior_60_valid_level_median
level_recent_required_level_count: 60
level_recent_current_excluded: true
level_recent_distance_unit: basis_points
level_missing_observation_policy: valid_observations_no_fill_no_interpolation
level_rolling_percentile_policy: excluded
level_z_policy: excluded
level_robust_z_policy: excluded
level_state_policy: null_evidence_only
level_lineage_policy: exact_expanding_ordered_processed_inputs
```

## Outer versioning

Adding Level changes the outer economic question, measured evidence, parameter contract, explanation, payload, and exact input sequence. It is therefore implemented as `sofr_rate_state/v3`. V3 contains unchanged `sofr_change_rarity_v1`, unchanged `sofr_direction_evidence_v1`, and `sofr_level_evidence_v1`. All three categorical state fields remain null.

The methodology-freeze phase itself did not authorize implementation. The separately authorized Phase 2.1B-10 added v3 registration, generation, CLI routing, and persistence without a schema migration or historical backfill. V1 and v2 remain active and immutable.

## Versioning

After integration, each of the following requires both a new Level component methodology ID and a new outer signal version:

- replacing expanding full history with any rolling, bounded, weighted, decayed, or policy-adjusted history;
- changing canonical vintage selection, valid-observation semantics, current/future exclusion, earliest-history policy, missing-date treatment, or historical replay semantics;
- changing strict/midrank/weak formulas, primary percentile convention, exact tie equality, or mandatory tie audit fields;
- changing recent window length, observation indexing, median definition, median-to-mean reference, bp conversion, or window-shortening policy;
- adding/removing production Level measures, a composite score, multi-window vote, calendar adjustment, standard/robust Z, or an opaque aggregate;
- adding Level thresholds, `level_state`, policy regimes, stress/liquidity meaning, conflict precedence, confidence, or causal/economic claims;
- weakening exact lineage or changing its order, deduplication, revision behavior, or identity role;
- changing warm-up availability semantics, integrity failures, outer-quality interaction, or deterministic explanation meaning.

Pure spelling/layout corrections that do not change persisted fields, calculations, parameters, lineage, availability, failures, or economic claims do not require a version bump.

## Deferred questions

### DEFERRED QUESTION

- Economically defensible Low/Normal/High thresholds and any future `level_state`.
- Policy-relative Level interpretation or a formal policy/macro regime model.
- External spreads such as SOFR versus IORB or EFFR.
- Funding-stress and liquidity interpretation using additional evidence.
- Point-in-time publication/revision reconstruction for historical backtesting.
- Transparent scalability or backfill optimization if exact expanding lineage becomes operationally expensive.

These items require separate research and authorization. They must not be solved by silently changing `sofr_level_evidence_v1`.

## Explicit boundary confirmation

Phase 2.1B-10 implements only the frozen v3 contract. It leaves outer v1 and v2 definitions, code, and observations unchanged; keeps `level_state`, `direction_state`, and `anomaly_state` null; introduces no thresholds; adds no Phase 3 behavior; and preserves all Phase 1 selection, processing, unit, revision, missing-data, and lineage semantics.
