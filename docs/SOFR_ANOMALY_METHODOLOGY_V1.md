# SOFR anomaly methodology v1 decision record

## Scope and status

This document freezes the anomaly-evidence component of `sofr_rate_state/v1`. Phase 2.1B-4 implements this component without adding a state classifier, level/direction methodology, or downstream interpretation.

**Production readiness:** **METHODOLOGY FROZEN — READY FOR IMPLEMENTATION**

**Implementation status:** Phase 2.1B-4 complete; production definition, generator, persistence, exact lineage, deterministic explanation, and CLI are implemented.

Evidence sources are the [Phase 2.1B-1 report](../notebooks/sofr_daily_change_anomaly/outputs/report.md), [Phase 2.1B-2 delta report](../notebooks/sofr_daily_change_anomaly/outputs_phase_2_1b_2/delta_report.md), and the validated structured artifacts beside that delta report.

## Production implementation

- Implementation: `cross_asset_market_intelligence.signals.sofr_rate_state`.
- Interface: `generate_sofr_rate_state(connection, as_of_observation_date=...)`; omission of as-of safely selects the latest canonical valid observation.
- CLI: `python -m cross_asset_market_intelligence generate-sofr-rate-state --as-of YYYY-MM-DD`.
- Persistence uses the Phase 2.1A immutable definition/observation APIs. No schema extension is required.
- Exact lineage uses one `sofr_level_history` sequence, oldest first. With broad evidence it contains 254 unique processed levels: the final item is current, the penultimate is previous, and the preceding 252 changes reconstruct the broad baseline. Recent-60 is the suffix of the same sequence, avoiding duplicated lineage roles.
- Publication time is derived only from exact raw publication metadata when every selected input supplies it. It never uses retrieval time as publication time. The current backfilled snapshot therefore persists `availability_precision=unknown` and quality reason `information_availability_unknown`.

## Evidence basis

### MEASURED FACT

- The frozen expanded snapshot contains 2,112 selected SOFR levels and 2,111 consecutive-valid-observation changes from 2018-04-03 through 2026-09-16. Independent SQL reproduced 7,992 rolling score rows.
- Robust-Z MAD is zero in 34.15%, 38.08%, 40.73%, and 48.36% of 20/60/120/252-change windows.
- One prior extreme inflates standard-deviation scale by as much as 29.57x, 11.42x, 5.63x, and 4.27x over those windows.
- Longer percentile windows reduce resolution and saturation problems but do not remove ties: mean strict-to-weak brackets remain about 36 percentage points.
- The archived `results.json` values 0.877 correlation, 10.37-point mean absolute difference, and 6.35% spreads of at least 25 points compare **20 versus 252** (`midrank_20_252`). They use the same 1,859 common eligible dates and midrank field as the later check; the discrepancy is the window pair, not sample filtering or a calculation bug. A targeted methodology-freeze check of the same validated `rolling_scores.csv` gives 60-versus-252 correlation 0.936, mean/median absolute differences 7.39/6.11 points, and one of 1,859 common dates (0.054%) at or above a 25-point difference; the maximum is 25.52 points on 2020-02-28.
- High rarity occurs on movements of 2bp or less, so rarity is not economic materiality.
- Calendar-boundary observations have larger average absolute changes, but the project has no authoritative holiday calendar and no evidence supporting a calendar adjustment.

### RESEARCH INTERPRETATION

Absolute-change empirical rank directly answers the economic question without an unstable volatility denominator. The 60 and 252 outputs are highly related, so they must not be presented as independent confirmations or combined into a stronger score. They still have distinct reference-set semantics, and observed differences approaching 25 points show that the broader context can materially qualify the recent rank in some episodes. Signed and absolute bp movement must remain visible because a rare move can still be economically small. The evidence does not justify a binary anomaly label or a materiality cutoff.

## Frozen decisions

| ID | FROZEN PRODUCTION DECISION |
|---|---|
| D1 | The primary rarity measure is empirical percentile rank of the current absolute consecutive-valid-observation SOFR change. Midrank is the principal displayed/stored percentile. |
| D2 | Production v1 has two named contextual horizons: 60 prior valid changes (`recent_rarity_60`) and 252 prior valid changes (`broad_rarity_252`). They are not independent signals, votes, confirmations, or inputs to an aggregate; the broad view qualifies the recent view against a different reference set. |
| D3 | Midrank is the principal rarity value. Strict and weak percentiles plus less/equal/greater counts are mandatory audit evidence. |
| D4 | Standard Z is retained only as nullable secondary diagnostic evidence for both production horizons. It cannot determine a state or change the percentile. |
| D5 | Robust Z/MAD is excluded from the production v1 evidence contract. It remains research-only; no epsilon, repair, or fallback is permitted. |
| D6 | Persist both signed `change_1obs_bp` and derived non-negative `absolute_change_1obs_bp`; the latter must equal `abs(change_1obs_bp)`. |
| D7 | Production v1 has no materiality state, threshold, or gating rule. Materiality remains quantitative bp evidence only. |
| D8 | `anomaly_state` is always `null` in v1. The anomaly component is evidence-only because no economically defensible rarity/materiality classification boundary has been established. |
| D9 | Month/quarter/year-end flags are persisted as context metadata. They do not alter rarity, Z, quality, or state. |
| D10 | A horizon is null until its exact required count exists: 60 for recent and 252 for broad. Windows are never shortened. |
| D11 | Any semantic change listed under Versioning requires a new outer signal version. |

## Frozen calculation contract

### Change

Let `SOFR_t` and `SOFR_previous_valid` be canonical selected processed SOFR levels in percentage points:

```text
change_1obs_bp = 100 × (SOFR_t - SOFR_previous_valid)
absolute_change_1obs_bp = abs(change_1obs_bp)
```

Use decimal-safe source values. Do not round before equality/tie comparisons. The preceding observation is the preceding valid selected observation, not necessarily the preceding calendar day. Preserve its date and the calendar gap. Do not fill, interpolate, annualize, or manufacture weekends/holidays.

### Rarity for horizon N

For `N in {60, 252}`, compare `a = absolute_change_1obs_bp` with the absolute magnitudes of exactly the prior `N` valid changes. The current change is excluded.

```text
less_count    = count(prior_abs < a)
equal_count   = count(prior_abs == a)
greater_count = count(prior_abs > a)

strict_percentile  = 100 × less_count / N
midrank_percentile = 100 × (less_count + 0.5 × equal_count) / N
weak_percentile    = 100 × (less_count + equal_count) / N
```

Normative invariants:

- `less_count + equal_count + greater_count == N`.
- `strict_percentile <= midrank_percentile <= weak_percentile`.
- `midrank_percentile == (strict_percentile + weak_percentile) / 2`.
- A percentile is an empirical historical rank, not a probability or forecast.
- The 60-change window is the most recent 60-change suffix of the 252-change history when both are available.

`baseline_start_date` and `baseline_end_date` are the effective dates of the oldest and newest prior changes included. Exact processed level inputs are normative lineage; dates alone are not lineage.

### Secondary standard Z

For each available horizon, compute the signed diagnostic using the same prior-only window and sample standard deviation (`ddof=1`):

```text
standard_z = (change_1obs_bp - prior_mean_bp) / prior_sample_std_bp
```

Persist the Z value, prior mean, and prior sample standard deviation. If the horizon is unavailable or the sample standard deviation is zero, Z is null with an explicit status/reason. It is not a classifier, probability, fallback percentile, or explanation adjective.

## Final v1 evidence contract

The field names and nesting below are frozen. Percentages use the 0–100 scale; bp fields use basis points.

```text
methodology_id: sofr_change_rarity_v1

change:
  previous_observation_date
  calendar_gap_days
  change_1obs_bp
  absolute_change_1obs_bp

recent_rarity_60:
  status                         # available | insufficient_history
  window_count                   # always 60
  available_prior_change_count
  strict_percentile              # null unless available
  midrank_percentile             # null unless available
  weak_percentile                # null unless available
  less_count                     # null unless available
  equal_count                    # null unless available
  greater_count                  # null unless available
  baseline_start_date            # null unless available
  baseline_end_date              # null unless available

broad_rarity_252:
  status                         # available | insufficient_history
  window_count                   # always 252
  available_prior_change_count
  strict_percentile              # null unless available
  midrank_percentile             # null unless available
  weak_percentile                # null unless available
  less_count                     # null unless available
  equal_count                    # null unless available
  greater_count                  # null unless available
  baseline_start_date            # null unless available
  baseline_end_date              # null unless available

calendar_context:
  rule_id: gregorian_last_weekday_v1
  month_end
  quarter_end
  year_end

secondary_diagnostics:
  standard_z_60:
    status                       # available | insufficient_history | zero_scale
    value
    prior_mean_bp
    prior_sample_std_bp
  standard_z_252:
    status                       # available | insufficient_history | zero_scale
    value
    prior_mean_bp
    prior_sample_std_bp
```

`available_prior_change_count` is `min(total prior valid changes, window_count)`. It therefore equals the required window when `status=available` and shows exact warm-up progress otherwise.

Fields deliberately absent from v1: robust Z/MAD, materiality state, materiality threshold, combined rarity score, categorical rarity band, anomaly threshold, and calendar-adjusted score.

### Field purposes

- `change` provides direction, material magnitude, gap transparency, and deterministic explanation inputs.
- Both rarity objects provide distinct recent/broad rank evidence and complete tie auditability.
- Calendar context supports explanation only; it is not a model input.
- Standard Z preserves a scale-sensitive comparison for audit/research without classification authority.
- Exact input IDs belong in `signal_observation_inputs`, not duplicated in evidence JSON.

## Signal identity, parameters, and lineage

- Outer production identity: `signal_id = sofr_rate_state`, `signal_version = v1`, `indicator_id = sofr`.
- Component identity: `methodology_id = sofr_change_rarity_v1`. It identifies this frozen anomaly component inside the broader signal definition; it does not create a second persistence/version lifecycle.
- Definition name: `SOFR Rate State`. Its economic question is whether the latest SOFR movement is unusual relative to recent and broader prior SOFR behavior. It measures descriptive self-history rarity and movement magnitude. It does not mean liquidity stress, crisis, financial-conditions direction, asset-return direction, or a portfolio action. The hypothesis is descriptive: recent and broad self-history ranks can provide distinct, auditable context for the current movement. The definition may become `active` only when Phase 2.1B-4 implements and verifies this contract.
- The immutable definition and each observation's `parameters_used` must encode the following exact semantic parameters:

```text
anomaly_methodology_id: sofr_change_rarity_v1
recent_window_count: 60
broad_window_count: 252
window_unit: prior_valid_changes
current_change_excluded: true
percentile_basis: absolute_change_1obs_bp
primary_percentile_convention: midrank
audit_percentile_conventions: [strict, weak]
tie_equality: exact_decimal_bp_no_prerounding
standard_z_role: secondary_only
standard_z_scale: sample_std_ddof1
missing_observation_policy: previous_valid_no_fill_no_interpolation
calendar_rule_id: gregorian_last_weekday_v1
anomaly_state_policy: null_evidence_only
materiality_policy: quantitative_bp_only_no_threshold
```
- Record one ordered input sequence with `input_role = sofr_level_history`, oldest first. Include the latest 254 canonical selected processed SOFR levels when broad rarity is available; otherwise include all available levels up to that maximum. `window_position=0` is oldest. The current and previous levels plus the required prior changes are thereby exactly reconstructible without duplicate input rows.
- Phase 1 canonical revision/vintage selection remains authoritative. A newly selected vintage produces different processed input identity; historical signal records are not overwritten.

## Warm-up, failures, and evidence quality

### FROZEN PRODUCTION DECISION

- No current selected SOFR level, or fewer than two valid selected levels: do not persist a signal observation; surface a deterministic missing-current-or-previous-input failure. A signal observation cannot truthfully represent a change without both levels.
- Current change available but fewer than 60 prior valid changes: both rarity objects null; `evidence_quality=insufficient`; reason `recent_history_warmup`.
- At least 60 but fewer than 252 prior valid changes: recent rarity available, broad rarity null; `evidence_quality=limited`; reason `broad_history_warmup`.
- At least 252 prior valid changes and complete exact lineage: both rarity objects available. Primary-method evidence may be `sufficient` if availability is represented honestly and no primary invariant fails.
- `availability_precision=unknown` adds reason `information_availability_unknown` and caps quality at `limited`.
- A zero standard deviation makes only that secondary Z null (`zero_scale`); it does not downgrade otherwise valid percentile evidence.
- Tie concentration does not make the primary method undefined because the strict/weak bracket and counts expose it explicitly.
- Any missing required processed input, broken lineage, count inconsistency, non-finite primary output, or percentile invariant failure is an integrity error: persist no observation and fail visibly. Evidence quality labels describe valid-but-incomplete evidence, not corrupted calculations.

The exact system receipt time may be represented from preserved retrieval lineage when genuinely known. It must not be described as the historical publication time. The backfilled economic-date snapshot validates methodology but does not establish point-in-time historical replay or Phase 7 backtesting readiness.

## Calendar contract

`gregorian_last_weekday_v1` means the final Monday–Friday calendar date of the month, without holiday adjustment. `quarter_end` requires `month_end` in March/June/September/December; `year_end` requires December `month_end`. The rule is deterministic and source-free, but imperfect around holidays; that limitation must remain documented.

Changing to an authoritative business calendar is a future methodology change, not a silent correction. No `around_*` flags enter production v1.

## Deterministic explanation contract

The persisted explanation reports facts without classification adjectives:

```text
SOFR declined 2bp from the previous valid observation. The absolute move has
a midrank of 91.7 on a 0–100 scale relative to the prior 60 valid changes
(strict 80.0; weak 100.0), and 74.0 relative to the prior 252 valid changes
(strict 68.0; weak 80.0). The observation matches the quarter-end context
rule; calendar context does not alter either rarity measure.
```

Rules:

- Use `rose`, `declined`, or `was unchanged` from the signed change; this wording does not set `direction_state`.
- Report only available horizons; state the exact missing-history reason for an unavailable horizon.
- Do not use `normal`, `unusual`, `highly unusual`, `material`, `stress`, `liquidity deterioration`, market-direction, return, or portfolio claims.
- Calendar text states the matched rule and non-adjustment; it does not normalize or excuse the move.

## Versioning

The following require a new outer `signal_version` (normally `v2`) and a new component methodology ID:

- changing the consecutive-valid-observation change definition, unit, or decimal/tie handling;
- changing either 60/252 window or combining the horizons;
- changing absolute versus signed ranking, strict/midrank/weak formulas, or the primary displayed measure;
- adding a materiality threshold/state/gate or any anomaly classification rule;
- adding/removing a production diagnostic or allowing a diagnostic to affect classification;
- calendar-adjusting, excluding, or reweighting observations, or changing the calendar rule;
- changing warm-up behavior, missing-data policy, primary evidence-quality mapping, or input-selection semantics;
- changing persisted explanation semantics in a way that alters the claim made.

More observations, new canonical vintages under unchanged Phase 1 selection, refreshed retrieval metadata, and purely cosmetic UI formatting do not require a methodology version change.

## DEFERRED QUESTION

- A defensible absolute-bp materiality threshold or materiality state.
- Any categorical `anomaly_state` mapping and its joint rarity/materiality rule.
- An authoritative holiday/business calendar and whether adjustment is economically warranted.
- Policy-event/FOMC context from a separately approved source.
- Level and direction methodologies for the full SOFR Rate State.
- Historical publication-time reconstruction and valid point-in-time backtesting.
