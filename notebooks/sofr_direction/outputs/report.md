# SOFR Direction Research

Research version: `sofr_direction_research_v1`  
Scope: research evidence only; no production classification or threshold

## 1. Executive conclusion

**MEASURED FACT.** Net change, linear slope, sign balance, and median change were evaluated over the frozen 2018-04-03 to 2026-09-16 SOFR history. At the 20-window, adjacent nonzero sign-flip rates were 10.10% for net change, 7.75% for linear slope, and 3.45% for sign balance. Median change was exactly zero in 77.92% of eligible 20-change windows.

**RESEARCH INTERPRETATION.** No single scalar faithfully separates persistent drift, a completed level step, and a volatile round trip. Net change preserves economically interpretable magnitude but is endpoint-sensitive. Sign composition describes persistence without allowing one large move to dominate, but ignores magnitude. Slope is useful corroboration, but imposes smoothness on a stepwise series. Median change loses too much information.

**DESIGN RECOMMENDATION.** Advance a two-component design to methodology freeze: 20-change net movement plus 20-change sign composition, with path concentration retained as supporting evidence and linear slope retained for comparison/diagnostics. Do not freeze category thresholds in this task.

## 2. Dataset / reproducibility

**MEASURED FACT.** The study selected 2,112 processed observations and 2,111 consecutive changes from the approved FRBNY → raw → processed lineage. The first and last dates are 2018-04-03 and 2026-09-16. Exact processed observation IDs, processing versions, source, series, and vintage are frozen in `selected_observations.json`. Snapshot SHA-256 is `bef72683a3fe8fe0da76518ca325a19867fbb9249a7a69a76c510f65d167792d`. The execution timestamp, Git commit, script hash, database path, and anomaly artifact are recorded in `results.json`.

**MEASURED FACT.** Calculations are backward-looking over valid observations; missing calendar days are not filled. Net change uses N consecutive changes; slope uses N levels. Existing 60/252 anomaly evidence is joined from the frozen research artifact and is not recomputed.

**DESIGN RECOMMENDATION.** Preserve these definitions and the exact snapshot identity during methodology freeze so any proposed thresholds can be reproduced against the same evidence.

## 3. SOFR directional behavior

**MEASURED FACT.** SOFR combines long zero-heavy stretches, small gradual changes, discrete steps, reversals, and isolated extreme round trips. The longest selected flat example ends 2021-10-18 after 84 consecutive zero changes. The 2019-09-17 +282 bp move was followed by -270 bp on the next valid observation. A gradual rising example on 2018-08-27 accumulated +7 bp over 20 changes, while a gradual falling example on 2026-05-20 accumulated -14 bp.

**RESEARCH INTERPRETATION.** Direction is a recent-path question, not a level percentile or a synonym for anomaly. A useful design must retain both movement magnitude and evidence about whether movement was repeated.

## 4. Net-change findings

**MEASURED FACT.** Exact-zero frequencies were 28.19%, 23.83%, 21.70%, and 10.58% for 5-, 10-, 20-, and 60-change net measures. Adjacent nonzero sign-flip rates declined from 16.24% at 5 changes to 4.29% at 60. Typical daily revision was 1 bp at every tested window; the 90th percentile was 6–7 bp.

**RESEARCH INTERPRETATION.** Net change is the clearest measure of recent level displacement and has directly interpretable bp units. Its weaknesses are structural: endpoints determine the result, a single step can dominate, and a zero endpoint difference can hide a volatile path. On 2019-10-21, net change over 20 changes was 0 bp despite 184 bp of total absolute movement.

**DESIGN RECOMMENDATION.** Use net change as magnitude evidence, not as a standalone direction classifier.

## 5. Linear-slope findings

**MEASURED FACT.** Adjacent nonzero sign-flip rates were 18.85%, 14.51%, 7.75%, and 1.49% for 5-, 10-, 20-, and 60-level slopes. At 20 levels, the median/p90 absolute daily revision was 0.039/0.319 bp per valid observation. After the +75 bp step on 2022-06-16, the 20-level slope rose from 0.62 on the step date to 5.48 ten observations later, although the new level was already mostly flat; it fell to 0.54 after 20 observations.

**RESEARCH INTERPRETATION.** Slope uses the full level path and can help detect a changing fitted path, but a completed step becomes a temporary smooth trend. That artificial ramp is undesirable as the sole economic definition of continuing direction.

**DESIGN RECOMMENDATION.** Retain slope as corroborating research evidence, not the primary production scalar. Do not use regression p-values or distributional assumptions.

## 6. Sign/balance findings

**MEASURED FACT.** At 10, 20, and 60 changes, exact-zero balance occurred in 30.11%, 27.49%, and 16.57% of eligible windows. Adjacent nonzero sign-flip rates were 4.77%, 3.45%, and 2.43%. Each observation affects magnitude-free counts; zero share is explicitly available.

**RESEARCH INTERPRETATION.** Sign composition is stable and resists domination by a single large move. It distinguishes repeated small movements from a one-off step, but can understate economically meaningful steps and can be distorted by many tiny changes unless paired with magnitude.

**DESIGN RECOMMENDATION.** Pair positive/zero/negative composition with net movement. Preserve the counts/shares rather than prematurely compressing them into a categorical threshold.

## 7. Median-change findings

**MEASURED FACT.** Rolling median change was exactly zero in 65.41%, 77.92%, and 95.18% of eligible 10-, 20-, and 60-change windows. For 60 changes, both the median and 90th percentile of daily absolute revision were zero.

**RESEARCH INTERPRETATION.** Robustness to isolated jumps is achieved by discarding too much information in this zero-heavy series. A zero median does not distinguish a genuinely flat path from a meaningful step surrounded by zeros.

**DESIGN RECOMMENDATION.** Do not use rolling median change as primary direction evidence. It may remain a descriptive stability statistic.

## 8. Optional robust-path findings

**MEASURED FACT.** Theil–Sen or another robust path slope was not evaluated.

**RESEARCH INTERPRETATION.** Required candidates already isolate endpoint displacement, fitted path, sign persistence, and zero-heavy median behavior. An additional O(N²) estimator was not needed to answer the current decision questions and would still need careful interpretation around steps.

**DESIGN RECOMMENDATION.** Add a robust slope only if methodology freeze reveals a specific failure not addressed by the two-component evidence.

## 9. Window comparison

| Window | Measured behavior | Interpretation |
| ---: | --- | --- |
| 5 | Net sign flips 16.24%; slope sign flips 18.85% | Responsive, but too noisy for the main state horizon |
| 10 | Net sign flips 13.53%; sign balance 4.77% | Useful short confirmation; still endpoint-sensitive |
| 20 | Net sign flips 10.10%; slope 7.75%; sign balance 3.45% | Best observed compromise between response and persistence |
| 60 | Net sign flips 4.29%; slope 1.49%; median zero 95.18% | Stable but slow; better context than primary recent direction |

**RESEARCH INTERPRETATION.** Smoothness alone is not sufficient. A 60-window can preserve stale direction, whereas 5/10 windows react strongly to short-lived changes.

**DESIGN RECOMMENDATION.** Take 20 as the candidate primary horizon. Keep 5/10 as responsiveness diagnostics and 60 as broad context; do not combine them into a vote without further justification.

## 10. Stable-definition research

**MEASURED FACT.** Endpoint equality is insufficient: the 2019-10-21 case had 0 bp net movement but 184 bp total path movement. Conversely, isolated steps followed by flat levels retain nonzero net movement after repeated changes cease. Sign balance can be near zero around a large step because magnitude is ignored.

**RESEARCH INTERPRETATION.** “Stable” needs joint evidence: small endpoint displacement, weak/balanced directional persistence, and awareness of whether one observation dominates total path movement. Near-zero slope may corroborate but should not define stability alone.

**DESIGN RECOMMENDATION.** The next phase should select defensible boundaries for net magnitude and sign persistence, and decide how path concentration vetoes a stable label. No bp, slope, or count boundary is selected here.

## 11. Step-change behavior

**MEASURED FACT.** On 2022-06-16, a +75 bp change produced net20 +66 bp while sign balance20 was -4 and median20 remained 0. Ten observations later, net20 was +73 bp, slope20 had risen to 5.48, sign balance20 was -3, and median20 remained 0. By +20 observations, net20 was +9 bp and slope20 0.54. On 2024-09-19, a -51 bp step produced net20 -49 bp with sign balance20 0; by +20 observations net20 was +2 bp and slope20 -0.12.

**RESEARCH INTERPRETATION.** Net movement correctly records the new-level displacement but cannot say whether movement continued. Slope temporarily turns the step into a trend. Sign composition identifies the absence of repeated same-direction changes but cannot represent the level shift. Median change misses the step.

**DESIGN RECOMMENDATION.** Use net movement plus sign composition and path concentration to describe a completed step without calling it a continuing trend.

## 12. Reversal behavior

**MEASURED FACT.** In the selected 2019-01-03 reversal, net20 remained +47 bp on the -45 bp anchor and +9 bp ten observations later. Slope20 remained positive through +5 and crossed slightly negative by +10. Sign balance20 moved from +6 before the anchor to -1 by +10 and -6 by +20. Net5 was already -27 bp by +5.

**RESEARCH INTERPRETATION.** Short net change reacts fastest but is noisy. Twenty-change sign composition detected a change in persistence before endpoint net20 turned negative, while slope supplied a similar but step-smoothed transition. Exact lag depends on a classification boundary that is intentionally not defined here.

**DESIGN RECOMMENDATION.** Use 20-window composition to confirm reversal and shorter net movement as diagnostic evidence, not as an independently voting production state.

## 13. Direction vs anomaly

**MEASURED FACT.** Across 2,051 jointly eligible dates, correlations with 60-change anomaly midrank were 0.046 for signed net20, 0.059 for absolute net20, and 0.060 for signed slope20. Research-only diagnostic selections found 94 rising/low-anomaly cases, 237 falling/low-anomaly cases, 35 endpoint-stable/high-anomaly cases, 40 rising/high-anomaly cases, and 30 falling/high-anomaly cases.

**RESEARCH INTERPRETATION.** Direction evidence and one-change rarity capture materially different information. The very low correlations and coexistence examples reject treating anomaly as a direction proxy.

**DESIGN RECOMMENDATION.** Keep direction and anomaly as separate components of `sofr_rate_state`. The diagnostic cutoffs used to select examples are not proposed production thresholds.

## 14. Historical case studies

| Case | Key measured result | What it exposes |
| --- | --- | --- |
| Long flat, 2021-10-18 | End of 84 zero changes; net5/10/20 = 0 | Genuine stability |
| Gradual up, 2018-08-27 | net20 +7 bp; no single move dominates | Persistent small movement |
| Gradual down, 2026-05-20 | net20 -14 bp; 13 negative vs 3 positive changes | Magnitude and persistence agree |
| Isolated round trip, 2019-09-17 | +282 bp then -270 bp | Anomaly without durable direction |
| Endpoint-flat noise, 2019-10-21 | net20 0; total absolute path 184 bp | Endpoint equality is not stability |
| Up step, 2022-06-16 | net20 +66; balance20 -4; median20 0 | Step magnitude vs continuing path |
| Down step, 2024-09-19 | net20 -49; balance20 0; median20 0 | Same asymmetry in falling direction |
| Reversal, 2019-01-03 | composition turns before net20 | Reversal evidence has multiple speeds |

The complete before/on/+1/+5/+10/+20 observations are in `case_studies.csv`; no case is declared ground truth beyond its stated research criterion.

## 15. Method comparison table

| Method / window | Responsiveness / stability | Step and endpoint behavior | Zero-heavy handling | Interpretability | Main weakness |
| --- | --- | --- | --- | --- | --- |
| Net 5 | 16.24% sign flips | Fast; endpoint-only | 28.19% exact zero | 5-change displacement, bp | Noisy; one move dominates |
| Net 10 | 13.53% | Moderate; endpoint-only | 23.83% | 10-change displacement, bp | Endpoint-sensitive |
| Net 20 | 10.10% | Balanced; retains step until start exits | 21.70% | 20-change displacement, bp | Cannot separate step from drift |
| Net 60 | 4.29% | Slow; step retained long | 10.58% | Broad displacement, bp | Stale direction risk |
| Slope 5 | 18.85% | Very fast; fits step as ramp | 21.20% | bp/valid observation | Noisiest slope |
| Slope 10 | 14.51% | Moderate; step-smoothed | 11.89% | bp/valid observation | Artificial smoothness |
| Slope 20 | 7.75% | Stable; step signal peaks after event | 7.12% | bp/valid observation | Implies trend after completed step |
| Slope 60 | 1.49% | Very slow | 1.70% | broad fitted path | High lag |
| Balance 10 | 4.77% | Fast; one move = one count | 30.11% exact zero | positive minus negative count | Ignores magnitude |
| Balance 20 | 3.45% | Stable; robust to one large move | 27.49% | persistence composition | Tiny changes count equally |
| Balance 60 | 2.43% | Slow | 16.57% | broad persistence | Stale and magnitude-free |
| Median 10 | 4.36% | Usually ignores isolated step | 65.41% exact zero | typical change, bp | Loses information |
| Median 20 | 0.75% | Usually ignores isolated step | 77.92% | typical change, bp | Usually zero |
| Median 60 | 0.00% | Nearly inert | 95.18% | typical change, bp | Uninformative |

All response revision statistics, eligible counts, reversal notes, and full qualitative fields are in `method_comparison.csv`.

## 16. Recommended evidence design

**DESIGN RECOMMENDATION.** Retain two primary pieces of evidence rather than force a single number:

1. `net_change_20` for economically interpretable recent level displacement;
2. 20-change positive/zero/negative composition (and derived balance) for persistence.

Retain 20-change total absolute path and largest-change share to identify round trips and one-step domination. Use slope20 only as corroboration. Do not infer policy causes, asset bullish/bearish meaning, stress, or liquidity state.

## 17. Recommended horizon design

**DESIGN RECOMMENDATION.** Carry 20 valid changes into methodology freeze as the primary net/composition horizon. It has materially fewer net sign flips than 5/10 while remaining more responsive than 60, and it covers approximately one observation month without assuming calendar-day continuity. Keep 5/10 and 60 only as documented diagnostics unless freeze-phase evidence justifies a formal multi-horizon design.

## 18. Remaining unresolved questions

- What net-movement band represents economically effective stability?
- What sign composition is sufficiently persistent, particularly with many zeros?
- Should a high largest-change share explicitly identify a completed step/isolated move, or remain explanatory metadata?
- How should conflicts between magnitude and persistence map to the three requested labels without adding a fourth state?
- What deterministic precedence and boundary behavior should apply exactly at thresholds?
- Calendar flags occur in 3 of the 20 largest absolute changes (2018-12-31, 2019-04-30, 2019-09-30), so calendar-associated extremes exist but are not the majority. No adjustment is justified or applied here.

These are methodology-freeze questions. No FOMC cause is inferred and no long-term level percentile is used.

## 19. Production readiness decision

**READY FOR DIRECTION METHODOLOGY FREEZE**

The research identifies a defensible evidence family and candidate horizon, quantifies the main failure modes, demonstrates anomaly independence, and supplies reproducible row-level evidence. It does not freeze categorical boundaries.

Production status after this research remains unchanged: `direction_state` has 0 populated observations, anomaly v1 is unchanged, no production threshold or Phase 3 logic was added, and Phase 1 semantics are unchanged.
