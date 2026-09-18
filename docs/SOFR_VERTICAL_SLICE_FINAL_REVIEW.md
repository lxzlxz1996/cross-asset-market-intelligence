# SOFR Rate State vertical-slice final review

## A. Executive assessment

**Review outcome:** **SOFR VERTICAL SLICE APPROVED WITH NON-BLOCKING FOLLOW-UPS**

**PASS — methodological correctness.** Level, Direction, and Anomaly answer distinct descriptive questions, retain the quantities needed to audit those answers, and explicitly refuse stress, policy, regime, return, trade, or portfolio conclusions. The absence of categorical states is a deliberate methodology result, not unfinished persistence.

**PASS — engineering correctness.** V1/v2/v3 are immutable, independently queryable definitions with stable observation identities; exact processed inputs and Phase 1 raw lineage are reachable; calculations are deterministic and prior-only by economic observation date; persistence is idempotent; structural failures are not converted into quality labels; and the 189-test project suite passes.

**BLOCKING ISSUE:** none.

**NON-BLOCKING FOLLOW-UP:** Phase 2.2 should extract only demonstrated reusable primitives, add explicit conventions for component status and ordered-lineage validation, standardize research artifacts, and evaluate scaling before any broad historical backfill. It should not copy SOFR windows, diagnostics, calendar rules, or expanding lineage into other indicators.

The slice is suitable as a reference implementation for workflow and contract discipline, not as a universal statistical template.

## B. Version-chain integrity

**PASS.** The persisted chain is:

| Outer version | Frozen composition | Persisted observation ID |
|---|---|---|
| `sofr_rate_state/v1` | `sofr_change_rarity_v1` only | `signal_sha256:608e2c405d933340bce628620c2964b23611be053d3e45e0df2c0dfaec57b793` |
| `sofr_rate_state/v2` | unchanged anomaly + `sofr_direction_evidence_v1` | `signal_sha256:59898db5c5231b2d882d1a55e4c1b0280c3607a453130b7a61ff68d2dd1c4a43` |
| `sofr_rate_state/v3` | unchanged anomaly and Direction + `sofr_level_evidence_v1` | `signal_sha256:e5f25533033535ad725c7a044af5417d97549f6e0b79b50e2a72a7b603151f1d` |

All definitions are active and keyed immutably by `(signal_id, signal_version)`. V1 has neither Direction nor Level evidence; v2 has no Level evidence; v3 preserves every v2 evidence object before adding `level_evidence`. The production database retains one observation for each version. Version bumps correspond to changes in economic question, component composition, parameter contract, explanation, and lineage—not software-release numbering.

Definition replay is a no-op; incompatible reuse of an existing version fails. The v3 test now locks the canonical golden ID in addition to replay equality, matching the v1/v2 regression discipline.

## C. Economic semantics

**PASS.** The persisted definition metadata and explanations preserve three distinct questions:

- Level: current rate position relative to broad prior history and a recent local level reference.
- Direction: recent endpoint displacement, sign composition, and path concentration.
- Anomaly: rarity of the latest absolute change relative to prior changes, with signed bp materiality kept separate.

No component claims funding/liquidity stress, policy stance or cause, expected return, asset direction, or a trade. Rarity is not called probability or materiality. A high historical Level rank is not called restrictive policy or stress. A completed step is not labeled a continuing trend.

**PASS — orthogonality.** Quantitative correlation does not become semantic substitution. Recent Level median distance and 20-change Direction can co-move, but remain separate fields, methodologies, explanation clauses, and state dimensions. They are not averaged, voted, scored, or described as independent confirmations.

## D. Level review

**PASS.** `sofr_level_evidence_v1` exposes:

- the unnormalized canonical current SOFR value in percent per annum;
- expanding prior-only broad rank with exact less/equal/greater counts and strict/midrank/weak percentiles;
- exact prior-60-level median and current-minus-median bp distance.

Current/future exclusion, exact tie equality, median indexing, baseline dates, count sums, percentile ordering, finite values, and bp-distance equality are validated. Rolling Level percentiles, Level Z, robust Z/MAD, state thresholds, policy labels, and combined Level scores are absent.

The broad rank remains regime-dependent descriptive sample position. The recent context is a local reference, not an independent Direction confirmation.

## E. Direction review

**PASS.** `sofr_direction_evidence_v1` retains 20-change endpoint displacement, exact positive/zero/negative counts, total absolute path, largest absolute change and path share, plus a labeled secondary 20-level slope. It exposes magnitude/persistence conflicts rather than resolving them into a state.

The 2022-06-16 step has +66bp endpoint displacement but only 4 positive changes versus 8 negative and 8 unchanged changes. The explanation explicitly reports the conflict and does not call the state rising. The 2019-10-21 round trip has 0bp net displacement with 184bp total path and is not called stable.

Slope is a useful secondary diagnostic, not a state input. Its presence should not be generalized without indicator-specific evidence.

## F. Anomaly review

**PASS.** `sofr_change_rarity_v1` compares the latest absolute consecutive-valid-observation change with exact prior-60 and prior-252 change windows. Midrank is primary; strict/weak/count audit fields expose ties. Signed and absolute bp changes preserve materiality evidence separately.

Current change exclusion, exact ties, window sizes, sample-standard-deviation diagnostics (`ddof=1`), zero-scale nulls, calendar-context non-interference, and warm-up are tested. Robust Z, anomaly thresholds, materiality states, combined rarity scores, and calendar adjustment remain absent.

## G. Evidence-quality review

**PASS.** `EvidenceQuality` describes the validity/completeness of the combined information set, not confidence in an economic conclusion. Component availability remains separate from outer quality.

The latest v3 Level, Direction, recent anomaly, and broad anomaly calculations are all available, but publication timestamps are unknown, so outer quality is correctly `limited` with `information_availability_unknown`. Level availability does not promote the outer label. Secondary Z zero scale does not downgrade valid primary rank evidence.

No current component-specific limitation is silently lost: warm-up is represented inside Level/Direction/anomaly objects; policy/regime dependence and diagnostic limitations are recorded in definitions and methodology documents; publication availability is represented by the outer availability/quality contract.

## H. Point-in-time discipline

**PASS — economic-date discipline.** Anomaly excludes the current change from both reference distributions. Direction uses only the current and prior valid levels. Broad Level rank uses only dates before the as-of date. Recent Level median uses exactly the prior 60 levels. Signal persistence rejects processed inputs after the as-of date.

The historical reproducibility test generates a 2024-06-14 v3 observation, adds later observations through 2026-09-16, and confirms identical evidence, identity, and historical lineage length on replay.

**ACCEPTABLE CURRENT LIMITATION — publication-time discipline.** Phase 1 preserves retrieval time and raw revision identity but lacks per-observation historical publication timestamps for this backfilled SOFR history. Therefore the system establishes prior-only economic-date calculation, not complete historical “known at that instant” replay. Phase 7 must not treat the current history as bias-free intraday/event-time backtest data. A backtest must either reconstruct authoritative availability/vintages, operate at a decision timestamp safely after known release, or explicitly bound conclusions to economic-date history.

## I. Exact lineage

**PASS.** The persisted latest v3 observation has:

```text
2,112 input rows
2,112 unique processed IDs
2,112 unique reachable raw identities
0 broken raw joins
window positions 0..2111
dates 2018-04-03..2026-09-16
```

The current input is final. The ordered sequence reconstructs broad Level rank; its final 61 levels reconstruct recent Level context; its suffixes reconstruct Direction, slope, latest change, and both anomaly windows. There are no duplicate component-specific lineage rows.

The cost is acceptable for the latest SOFR reference slice because the method explicitly prioritizes exact reconstruction. A full historical backfill would grow approximately quadratically in input links and requires a storage/performance study before authorization.

**PHASE 2.2 DESIGN LESSON:** exact lineage is general; expanding full-history lineage is not. Other signals should record every exact input their own frozen method needs, without assuming that input set must be an expanding history.

## J. Numeric correctness

**PASS.** Reviewed conventions are internally consistent:

- canonical SOFR `3.62` means `3.62%` per annum;
- rate differences multiply by 100 to produce bp;
- decimal-safe `Decimal(str(canonical_value))` comparisons occur before serialization;
- percentile ties use explicit strict/midrank/weak formulas;
- the 60-member median averages ordered positions 30 and 31;
- anomaly standard Z uses the prior-only sample standard deviation;
- Direction slope is bp per valid observation;
- zero total path produces a null largest-change share;
- nonzero share equals largest absolute change divided by total absolute path.

Evidence JSON serializes numeric results as finite JSON numbers. Canonical JSON sorts mapping keys and uses fixed separators. Observation identity does not include evidence floats, but parameters and exact input identities determine the calculation; persistence rejects a replay whose derived evidence differs. This avoids incidental float formatting changing identity while still detecting inconsistent output.

**NON-BLOCKING FOLLOW-UP:** future reusable numeric helpers should preserve this decimal-before-serialization rule and should define serialization tests across supported Python/runtime versions. No observed SOFR identity instability exists.

## K. Identity / idempotency

**PASS.** Observation identity includes signal/version, indicator, as-of and availability semantics, frozen parameters, and complete positioned inputs. `calculated_at`, evidence output, and explanation are deliberately excluded. Thus execution time cannot create duplicates, while different versions, parameters, vintages, or input positions create different IDs.

V1/v2/v3 production replays are idempotent. V3 insert followed by replay returned the same canonical ID. The generic persistence test proves that same identity with different evidence/states fails. Definitions are likewise idempotent for exact replay and immutable for conflicting metadata.

## L. Deterministic explanations

**PASS.** Explanations are named-field templates with no LLM dependency. Production examples are deterministic and bounded:

- Level includes current percent, tie-aware midrank plus strict–weak range, recent median distance, and an explicit no-stress/no-policy caveat.
- Anomaly says “midrank on a 0–100 scale,” not probability or risk probability.
- Direction reports exact counts and path concentration; conflicts and round trips remain visible.
- Calendar language is descriptive and states that it does not alter evidence.
- Each version explicitly says its categorical states are unassigned.

No reviewed wording implies trade direction, funding stress, policy stance, or expected return. Persisted explanations are verbose but appropriate as auditable canonical text; presentation layers may summarize them without changing stored meaning.

## M. Warm-up / failure semantics

**PASS.** Independent mathematical requirements are preserved:

| Component | Requirement |
|---|---|
| Raw current Level | first valid level |
| Broad Level rank | at least 1 prior level |
| Direction | 20 changes / 21 levels |
| Recent Level median | 60 prior levels |
| Recent anomaly | current change plus 60 prior changes |
| Broad anomaly | current change plus 252 prior changes |

The Level calculator can represent first-observation evidence, but composite outer v3 inherits the frozen anomaly requirement for current plus previous before persistence. This is an intentional outer-component constraint, documented by the Level methodology; it does not expose a partial anomaly payload.

**PASS — invalid versus insufficient.** Valid warm-up produces `insufficient_history` and null calculated fields. Missing lineage, future inputs, invalid canonical selection, count mismatches, median/distance mismatch, Direction net/path/sign inconsistency, non-finite values, identity-content conflict, and definition mutation fail explicitly. Structural corruption is never converted into `limited` or `insufficient` quality.

## N. Test coverage

**PASS.** The 189-test suite covers the foundation, Phase 1 dependencies, v1/v2/v3 isolation, golden IDs, exact formulas, ties, zero scale, warm-up boundaries, quality, historical future exclusion, lineage, idempotency, immutable definitions, explanations, CLI routing/default, and historical golden cases.

This review added one high-value frozen-behavior assertion: v3 now has a canonical golden observation-ID regression alongside v1 and v2.

**NON-BLOCKING FOLLOW-UPS:**

- Add a performance/storage benchmark before authorizing multi-date expanding-lineage backfill.
- When a second indicator family exists, add cross-family contract tests for reusable component status and ordered-lineage helpers.
- Consider an exact full-string v3 explanation golden only if explanation text becomes an external compatibility surface; field/semantic tests are currently preferable to brittle prose snapshots.

No missing test warrants a methodology or production fix before Phase 2.2.

## O. Golden-case review

**PASS.** Independently researched cases reproduce their intended semantics:

| Case | Evidence | Review conclusion |
|---|---|---|
| Historical low, 2021-10-18 | SOFR 0.05%; broad midrank 19.47; recent distance 0bp | Low broad sample position can coexist with a flat local context; no policy/easing state assigned. |
| High plateau, 2024-06-14 | SOFR 5.31%; broad midrank 91.87; recent distance 0bp | Demonstrates why broad and recent Level contexts must remain separate. |
| Step, 2022-06-16 | recent distance +115bp; Direction +66bp; signs 4/8/8 | Large displacement with weak/conflicting sign persistence; no continuing rising state. |
| Round trip, 2019-10-21 | Direction net 0bp; total path 184bp | Endpoint flat is not path stability. |

The explanation rules preserve these distinctions rather than collapsing them into labels.

## P. Over-engineering risks

| Item | Classification | Review guidance |
|---|---|---|
| Raw Level, bp movement, exact ranks/counts, sign/path evidence | Essential | These directly answer the component questions and support audit. |
| Strict/weak tie evidence | Essential for discrete SOFR | Do not assume all continuous indicators need equally verbose tie evidence. |
| Secondary anomaly standard Z | Useful secondary / possibly removable in a future version | Retain in frozen v1–v3; do not copy by default. |
| Direction slope20 | Useful secondary / possibly removable in a future version | Retain in frozen v2/v3; require research before reuse. |
| Calendar flags | Useful contextual secondary | SOFR-specific and holiday-imperfect; never a generic default. |
| Expanding lineage | Essential to this frozen Level method, operationally costly | Do not generalize; benchmark before backfill. |
| Repeated immutable parameters | Audit-useful but verbose | A future registry/view may reduce presentation duplication; persistence clarity currently outweighs compression. |
| Canonical explanations | Audit-useful but verbose | Keep persisted text factual; allow shorter UI views rather than weakening canonical evidence. |

No frozen field is clearly erroneous. Phase 2.2 should resist cloning secondary fields merely because SOFR has them.

## Q. Under-engineering risks

**NON-BLOCKING FOLLOW-UP.** SOFR exposes several capabilities worth considering after another signal family provides comparative evidence:

- a reusable empirical-rank primitive with explicit ties and decimal policy;
- reusable fixed-valid-observation window/suffix validators;
- a component calculation/validation protocol with explicit status semantics;
- helpers that verify ordered role positions are unique and contiguous, not only that input rows are unique;
- a standard research-artifact manifest with snapshot hash, selected IDs, parameters, validation status, and decision status;
- component-specific explanation fragments composed into an outer deterministic explanation;
- storage/latency instrumentation for lineage-heavy observations.

Do not yet build a universal nested evidence schema, component database table, methodology registry service, “confidence” framework, automatic state classifier, or generic expanding-history cache. One SOFR family is insufficient evidence for those abstractions.

## R. Generalizable architecture lessons

| SOFR Design Choice | Generalize to Phase 2.2? | Reason |
|---|---|---|
| Immutable signal definitions | GENERALIZE | Prevents silent reinterpretation and preserves queryable history. |
| Outer signal versioning | GENERALIZE | Composition/economic-contract changes require new identities. |
| Component methodology IDs | GENERALIZE | Separates component semantics from outer composition. |
| Evidence/state separation | GENERALIZE | Quantitative evidence remains useful without forced labels. |
| Nullable categorical states | GENERALIZE | Null can explicitly mean “not classified under this method.” |
| Exact input lineage | GENERALIZE | Required for reconstruction and revision-aware identity. |
| Prior-only windows | GENERALIZE AS A DISCIPLINE | Window type/length remains indicator-specific; future data exclusion does not. |
| Deterministic explanations | GENERALIZE | Persisted meaning must be reproducible and non-LLM-authored. |
| Component warm-up | GENERALIZE | Each component declares its own exact minimum information set. |
| Structural failure vs low quality | GENERALIZE | Corrupt evidence must never masquerade as uncertain evidence. |
| Evidence-quality metadata | GENERALIZE | Represents information completeness/availability, not forecast confidence. |
| Research → freeze → implementation workflow | GENERALIZE | Prevents code from inventing economic meaning. |
| 60/252 anomaly windows | DO NOT GENERALIZE | SOFR-specific empirical choice. |
| 20-change Direction horizon | DO NOT GENERALIZE | SOFR path behavior selected this horizon. |
| 60-level median context | DO NOT GENERALIZE | Specific recent reference for discrete policy-dependent SOFR levels. |
| Full-history percentile | DO NOT GENERALIZE | Regime dependence and history meaning differ across indicators. |
| Expanding lineage | DO NOT GENERALIZE | It follows this Level method and has substantial storage cost. |
| Standard Z diagnostic | DO NOT GENERALIZE | Scale stability and diagnostic value must be researched per indicator. |
| Calendar context | DO NOT GENERALIZE | SOFR calendar semantics are source/instrument specific. |

## S. SOFR-specific choices that must NOT be generalized

**PHASE 2.2 DESIGN LESSON.** Do not encode SOFR's 60/252 rarity windows, 20-change path, 60-level median, full-history Level rank, Gregorian boundary flags, standard-Z diagnostics, exact explanation order, or expanding lineage volume into a generic signal base class.

The reusable object is the discipline: state the economic question, preserve units, use prior-only information, expose ties/missingness, freeze parameters, link exact inputs, fail on corruption, keep classifications optional, and version semantic changes.

## T. Remaining limitations

| Limitation | Classification | Reason |
|---|---|---|
| No historical publication-time reconstruction | Acceptable now; blocks claims of full point-in-time backtest readiness | Economic-date discipline is sound, but historical “known when” is incomplete. |
| No SOFR–IORB or SOFR–EFFR spread | Acceptable current scope | Needed for richer funding/policy-relative interpretation, not for self-history description. |
| No repo volume/collateral context | Acceptable current scope | Prevents broader funding-stress claims, which v3 already refuses. |
| No categorical states | Acceptable and intentional | Research did not justify thresholds. |
| No policy-event context | Acceptable current scope | Causal/policy interpretation belongs to later authorized work. |
| Expanding lineage storage cost | Acceptable for latest reference observation; follow-up before backfill | Exact reproducibility is achieved, but multi-date volume can grow quadratically. |
| Full-history Level rank is regime-dependent | Acceptable with explicit caveat | It is sample position only, not a policy/stress state. |
| Recent Level/Direction correlation | Acceptable with semantic separation | They answer distinct questions and are not combined. |
| CLI default remains v1 | Safe but potentially surprising | Preserves backward compatibility; an explicit production alias may be evaluated later. |

None is a blocking defect for Phase 2.2 design work. They constrain downstream claims and future backtesting.

## U. Phase 2.2 readiness

**SOFR VERTICAL SLICE APPROVED WITH NON-BLOCKING FOLLOW-UPS.** It is a credible reference for future Phase 2 signal families and exposes adequate raw evidence for later cross-asset comparison without embedding Phase 3 conclusions.

### Required Phase 2.2 lessons

**L1 — Generic contract.** Inherit immutable outer definitions, component methodology IDs, exact parameters/inputs, point-in-time fields, optional orthogonal states, component warm-up, outer evidence quality, deterministic explanations, and explicit integrity failures.

**L2 — Indicator-specific decisions.** Economic question, transformations/units, horizons, reference distributions, tie handling, diagnostics, calendar rules, state thresholds, and lineage scope must remain research-driven per indicator.

**L3 — Standard research outputs.** Standardize a selected-input snapshot and hash, machine-readable method comparison, case studies, results/decision record, independent validation record, concise report, and named golden observations. Do not require the same metrics or plots.

**L4 — Worthwhile helpers.** Abstract canonical empirical-rank math, decimal-safe unit conversion, fixed-valid-observation window selection, ordered-lineage construction/validation, component status scaffolding, and deterministic explanation composition after confirming their shape with a second indicator family.

**L5 — Delay abstractions.** Delay universal evidence schemas, a database-level component registry, universal Level/Direction/Anomaly formulas, automatic “latest” semantics, generic state/confidence engines, and optimized aggregate lineage caches.

**L6 — Prevent arbitrary thresholds.** Require research evidence, an economic interpretation, documented error trade-offs, golden cases, a frozen decision record, and a new methodology/outer version before any state threshold enters production. Null state is valid.

**L7 — Point-in-time availability.** Every signal must distinguish observation date, actual availability timestamp/date/precision, retrieval time, and revision/vintage. Unknown availability must remain explicit and cap claims/quality; backtests must not infer publication timestamps or use future-selected vintages silently.

No Phase 2.2 implementation, Phase 3 logic, threshold, trade rule, or methodology change is authorized by this approval.
