# Phase 2.2D — 2s10s research and framework compatibility

## MEASURED FACT

The local current-vintage sample is bounded. `aligned_levels.csv` preserves one spread per same economic date and the exact two-leg/derived IDs. `selected_observations.json` preserves actual processed leg values and availability/vintage identities. Observed summary, independently reconciled to these artifacts:

```json
{{DATASET}}
```

Every observed spread is positive. There are no observed inverted, exact-zero or strict sign-crossing cases. The largest sample one-step rise is +3bp and the largest fall is -6bp. The sample starts +40bp, reaches +43bp and ends +33bp. Its endpoint movement is -7bp; 10Y rose 21bp while 2Y rose 28bp, so the spread fell despite both legs rising. These statements describe this snapshot only.

The raw date union contains 11 dates; one date has both source values missing, and zero dates have only one available leg. Missing-leg frequency is therefore 0/11 one-leg dates, not a claim of complete business-day coverage. The source-missing date is 2026-09-07; no cause or holiday classification is inferred. Non-publication/weekend dates absent from both source series are not inserted. `alignment_audit.csv` distinguishes these facts from missing processed rows.

`method_comparison.csv` compares the declared research grid without an aggregate score. The 1/3/5-change endpoint candidates have 9/7/5 eligible rows; 10 changes has none. Complete 5-prior-change rarity has four eligible rows; 21/63 have none. Expanding rarity with minimum five prior changes also has four eligible rows. Their coarsest ranks and ties must remain visible. Complete 5-prior-level context has five eligible rows; 21 has none. These are warm-up counts, not empirical horizon endorsements.

## Economic question and contract

The primary question is the sign and bp distance of the same-date 10Y-minus-2Y spread from zero, the recent movement and its two-leg decomposition, and whether prior behavior can provide honest context. Relevance is descriptive curve awareness. The research brief explicitly excludes recession probabilities, Fed forecasts, equity direction, bond returns and trade recommendations.

Inputs are existing validated Phase 1 FRED DGS2/DGS10 direct processed observations in percent. Each leg selects the greatest valid FRED realtime-start/end/vintage tuple and requires the exact matching direct processing version and raw-vintage lineage. Revision creates a new immutable processed pair and derived identity; a latest null does not fall back to an older value. Same economic date is mandatory, missing legs cannot create a curve observation, and no filling or interpolation occurs. Exact subtraction converts a percentage-point difference to bp through the explicit Decimal primitive. Positive, zero and negative spreads are supported.

Publication timestamps are unknown in this snapshot. `information_available_at=null` and `availability_precision=unknown` remain explicit. Retrieval timestamps are normalized to UTC and remain retrieval only. FRED realtime dates identify vintage, not publication time. The research uses current selected vintages with economic-date prior-only calculations; it cannot replay the historical information available at an intraday decision timestamp.

## RESEARCH INTERPRETATION

### Shape, movement and attribution

Raw signed spread already gives signed distance from zero. Negative means the 2Y yield exceeds the 10Y yield; zero means exact equality; positive means the reverse. `positive` is not a macroeconomic "normal" state. Exact zero does not define a near-flat interval.

An increase in DGS10-minus-DGS2 is a spread rise/steepening; a decline is spread decline, with sign/start/end retained to distinguish positive flattening from deeper inversion. Movement is always reported quantitatively. Two-leg changes matter: an equal common shift leaves the spread unchanged while both yields move. No bullish/bearish causal label is inferred from the spread alone.

Endpoint net movement is transparent but hides a round trip. Gross absolute path and `abs(net)/gross` describe retained movement, with null when gross path is zero. A separate least-squares slope over h+1 levels weights path shape differently; it is only a research comparator. Synthetic round-trip evidence demonstrates slope versus endpoint conflict. No sign-composition method or SOFR horizon is assumed. Current movement includes the current pair; contextual reference distributions exclude current level/current change.

### Rarity and context

Change rarity uses strict/weak empirical CDF endpoints for current absolute one-step movement against preceding changes. The interval and less/equal/greater counts expose ties rather than impose a point estimate. Signed/absolute bp magnitude remains separate. Four eligible short-reference rows cannot calibrate tails, materiality or an anomaly state. The observed -6bp move exceeds its small available prior reference, without establishing economic stress.

Prior median distance and level CDF answer reference-dependent questions. The available five-level sample is too narrow for long-history contextual authority. A synthetic zero spread has strict rank 100% against three inverted references and 0% against three positive references; its actual shape is identical. Prolonged inversion, prolonged positive curves, rapid crossing and volatility changes require broader observed history. No multi-regime or policy-transition inference is supported here.

### Orthogonality and states

Shape and movement have different economic meanings even when correlated. Sign coarsens spread and is redundant evidence, not independent confirmation. Signed distance from zero duplicates spread; absolute distance adds only magnitude framing. Net change and slope summarize the same path with different weights, and cannot count as independent confirmations. Rarity is conditioned on the reference; it does not replace magnitude. No arbitrary correlation threshold or score is used.

The framework supports a directly defined sign descriptor and separately governed empirical states. Research-only `inverted/zero/positive` has an exact zero boundary, equality behavior and explicit missingness. Inversion creates no recession/trading claim. `unusually steep`, `near flat`, `anomaly` and materiality classifications need threshold research and remain deferred. Production terminology, conflict/quality rules and explanations are not frozen by this package.

## Historical and exact synthetic cases

`case_studies.csv` names the actual latest positive curve, closest observed distance to zero (which is not labeled near-flat), and largest sample steepening/flattening. The small data-driven case selections are descriptive illustrations, not event-study evidence or out-of-sample testing. `synthetic_fixtures.json` and labeled synthetic rows cover inversion deepening/easing, exact zero, +/-1bp near zero, crossing, round trip, common-leg shift and sustained inversion. Synthetic anchors are labels; these records never enter observed frequencies, selected snapshots or normalization references. Causal macro stories are absent.

## Framework validation and generic corrections

`framework_scorecard.csv` records every requested capability using PASS / PASS WITH FOLLOW-UP. Multi-input derived data, exact lineage, snapshot/run identities, bp conversion and ordered primitives work without a single-series assumption. Global input positions enumerate `(date, role)`; chronological checks allow equal dates. Each leg separately validates `role_position` and its current endpoint. The merged sequence has no single current leg; the current curve remains an explicit pair. There is no need for a multi-sequence extension to represent this study.

Dogfooding uncovered mechanical gaps in the earlier validator: dangling references, false passed validation records, report/decision disagreement, never-null CSV values and extra CSV fields. The ordered validator also permitted array/position disagreement on equal dates; full-date parsing accepted non-normative basic forms. Minimal corrections enforce the already frozen contract. Regression fixtures first demonstrated six failures, then passed. Schema/profile names remain unchanged because these corrections reject malformed packages, rather than redefine valid identity semantics. Original SOFR calculation functions are not touched.

Passing `validate-research-artifacts` proves the declared package is internally valid. It does not prove an empirical recommendation is sufficiently researched. `MORE_RESEARCH_REQUIRED` remains an allowed, matching package outcome. Runtime validation retains non-blocking warnings for unknown event-time availability and bounded validation scope. The short-history failure is blocking for curve methodology research, not for demonstrating framework compatibility.

## Independent validation

`notebooks/treasury_curve/validate.py` never imports research calculators. It checks original selected IDs/vintages/timestamps with independent SQL, recomputes spread in decimal SQL, resolves existing derived dependency pairs, and recalculates all candidate rows with separate closed-form slope, sorted median, CDF and indexing paths. Snapshot identity is recomputed with a separate standard-library implementation of the frozen projection. Exact synthetic expectations, observed cases, warm-up, prior-only boundaries and result facts are checked. Generic package validation is then run through the public CLI. The check ledger and independence statement are in `validation.json`.

## DESIGN RECOMMENDATION

Propose raw spread bp, exact pair identity, direct sign descriptor, signed/absolute movement and leg decomposition for later freeze consideration. Retain path reversal diagnostics as candidate secondary context. Do not select a movement/reference horizon or authorize empirical normalized states from this history. Research arithmetic uses Decimal strings from retained percent values; the existing Phase 1 binary-float percentage-point value is preserved, with a validation-only 1e-10 percentage-point tolerance when comparing that stored derived value. Sign/ties have no epsilon or rounding.

Warm-up is candidate-specific: raw shape needs one aligned pair; h-change movement needs h+1 pairs; a w-prior-change reference plus current change needs w+2 pairs; a w-prior-level context needs w+1 pairs. No partial-window fallback. Structural identity/lineage corruption fails rather than becomes a low-quality observation. Unknown availability would bound future outer quality; exact quality mapping requires indicator-specific freeze.

Exact lineage cost is finite when research horizons are bounded: raw shape needs 2 leg links, h-change movement 2(h+1), and w-prior-change rarity 2(w+2). The maximum 63-reference candidate would need 130 unique leg records for one as-of, including overlaps deduplicated by exact ID/role under a future explicit freeze. A full expanding research comparator is not proposed as an unbounded production default. Ten observed curve rows resolve 20 leg records; the source/derived links already exist and are not replaced by hashes.

Future freeze must use the 15-decision template: field names/formulas/precision, input selection, windows, warm-up/fallback, state nomenclature, quality, role overlap/scope, deterministic wording, methodology identity/version rules and failures remain explicit decisions. Semantic changes need a new research version, component methodology or outer version at the appropriate gate. No production curve ID is registered and no signal observations are persisted.

## DEFERRED QUESTION

The next data prerequisite is a separately authorized expansion through the established Phase 1 pipeline, covering observed inversion, crossing, positive and differing volatility environments. More than a minimum window count is necessary: long-history coverage and sensitivity must support the selected descriptive purpose. Historical publication-time reconstruction remains separate. Empirical-rank/window/component/state abstractions are not automatically authorized by this second-family study.

Framework outcome:

PHASE 2.2 FRAMEWORK VALIDATED WITH NON-BLOCKING FOLLOW-UPS

Curve research outcome:

MORE_RESEARCH_REQUIRED
