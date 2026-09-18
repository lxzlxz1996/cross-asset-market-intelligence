# Phase 2.1B-2 — Historical Expansion + Multi-Window Research

This is a delta report. It updates, and should be read with, the [Phase 2.1B-1 report](../outputs/report.md). Unchanged definitions and derivations are not repeated. All diagnostic cutoffs below are research summaries, not production thresholds.

## 1. Executive research conclusion

- **MEASURED FACT:** The approved history now contains 2,112 canonical levels and 2,111 changes from 2018-04-03 through 2026-09-16. All four windows have 1,859 or more comparable evaluations.
- **RESEARCH INTERPRETATION:** Midrank absolute-change percentile remains the clearest rarity evidence. Robust Z remains structurally unreliable because MAD is zero in 34.15%-48.36% of windows. Standard Z is useful context but is contaminated by historical extremes.
- **DESIGN RECOMMENDATION:** Carry 60-change recent rarity and 252-change broad-history rarity into methodology freeze as distinct evidence fields, with signed bp magnitude retained separately. Do not combine them into one score or freeze a materiality cutoff here.

## 2. Historical data expansion

- **MEASURED FACT:** Existing approved FRBNY SOFR ingestion, immutable raw storage, Phase 1 processing, and exact lineage expanded the sample from 61 levels (2026-06-22–2026-09-16) to 2,112 levels (2018-04-03–2026-09-16). Raw, processed, and selected counts are each 2,112; duplicate identities/dates, null values, lineage mismatches, and processed-identity mismatches are all zero. All stored vintages are `frbny_sofr_revision:original`. A repeated backfill inserted zero rows.
- **MEASURED FACT:** Snapshot SHA-256 is `e4bc8c609b413e26ce8dfd0fc750b9c62af743e88f6c6e8239de02a52713cf9d`; exact processed IDs and source lineage are in the expanded history artifact. Script/source hashes, database path, commit, and execution time are in `results.json`.
- **RESEARCH INTERPRETATION:** Coverage is sufficient for a defensible window decision across multiple rate environments and calendar boundaries.

## 3. Expanded SOFR change distribution

- **MEASURED FACT:** 2,111 changes have min/max -270/+282bp, mean 0.085bp, median 0bp, sample standard deviation 10.521bp, and MAD 1bp. Zero moves are 43.72%; -1/+1bp are 15.68%/13.69%; -2/+2bp are 6.16%/4.12%. The 95th and 99th signed quantiles are 4.5bp and 19bp. Excess kurtosis is 457.0.
- **RESEARCH INTERPRETATION:** The expanded sample confirms discreteness, large tie masses, heavy tails, and strong regime dependence. Yearly zero frequency ranges from 18.4% (2019) to 84.8% (2021).

## 4. Standard Z multi-window findings

| Window | Undefined | Max scale inflation after one prior extreme | Small moves <=2bp with abs(Z)>=2 |
| ---: | ---: | ---: | ---: |
| 20 | 142 / 2,091 | 29.57x | 41 |
| 60 | 33 / 2,051 | 11.42x | 30 |
| 120 | 0 / 1,991 | 5.63x | 23 |
| 252 | 0 / 1,859 | 4.27x | 2 |

- **RESEARCH INTERPRETATION:** Longer windows remove zero-scale failures and reduce single-observation leverage, but old extremes suppress later Z scores for longer. Z is a standardized deviation, not a normal-tail probability.
- **DESIGN RECOMMENDATION:** Retain standard Z only as a secondary scale-sensitive diagnostic in v1.

## 5. Robust Z / MAD multi-window findings

| Window | MAD=0 | 0<MAD<1bp | MAD<=1bp | Small moves <=2bp with abs(robust Z)>=3 |
| ---: | ---: | ---: | ---: | ---: |
| 20 | 714 (34.15%) | 133 | 1,635 | 12 |
| 60 | 781 (38.08%) | 44 | 1,659 | 9 |
| 120 | 811 (40.73%) | 21 | 1,634 | 6 |
| 252 | 899 (48.36%) | 7 | 1,585 | 0 |

- **RESEARCH INTERPRETATION:** The earlier small-MAD amplification finding persists. Longer history reduces sub-1bp nonzero MAD cases, but increases zero-MAD frequency because the median absolute deviation remains pinned by repeated zero/one-bp moves. This is not fixed by a longer lookback.
- **DESIGN RECOMMENDATION:** Robust Z is unsuitable as the v1 primary classifier. If retained at all, expose it as a nullable secondary diagnostic with the raw MAD and no epsilon/fallback.

## 6. Empirical percentile multi-window findings

| Window | Resolution | Mean / median tie bracket | Midrank=100 | Weak=100 |
| ---: | ---: | ---: | ---: | ---: |
| 20 | 5.000pp | 37.53 / 35.00pp | 75 | 309 |
| 60 | 1.667pp | 36.91 / 31.67pp | 27 | 94 |
| 120 | 0.833pp | 36.52 / 30.83pp | 15 | 29 |
| 252 | 0.397pp | 36.02 / 31.35pp | 6 | 8 |

- **RESEARCH INTERPRETATION:** Longer windows materially improve rank resolution and saturation, but do not remove tie ambiguity: the mean strict-to-weak bracket remains about 36 percentage points. Midrank communicates the center of that bracket; strict and weak remain necessary audit fields.
- **DESIGN RECOMMENDATION:** Use midrank as primary rarity evidence and preserve strict, weak, and less/equal/greater counts.

## 7. Rarity vs materiality

- **MEASURED FACT:** Midrank >=90 occurs on <=2bp moves 63, 53, 70, and 67 times for 20/60/120/252 windows respectively.
- **RESEARCH INTERPRETATION:** High historical rarity does not imply a large economic movement. This is a property of quiet/discrete baselines, not a percentile defect.
- **DESIGN RECOMMENDATION:** Keep signed bp change and absolute bp magnitude beside rarity. The data supports a separate materiality concept, but not a defensible production cutoff yet.

## 8. Window responsiveness

- **MEASURED FACT:** The +282bp 2019-09-17 move remains in the 20/60/120/252 baselines for 20/60/120/252 subsequent changes and can first exit on 2019-10-17, 2019-12-16, 2020-03-13, and 2020-09-21. Its exit changes prior standard deviation by -28.52, -15.48, -10.65, and -7.00bp respectively.
- **RESEARCH INTERPRETATION:** 20 adapts rapidly but is mechanically sensitive to individual entries/exits. 252 is slower and answers a broader-history question.

## 9. Window stability

- **MEASURED FACT:** Median day-to-day absolute standard-Z change declines from 0.447 (20) to 0.239, 0.188, and 0.142 (252). Median midrank change declines from 20.0pp to 17.5pp, 17.5pp, and 14.09pp. These diagnostics compare adjacent defined observations only.
- **RESEARCH INTERPRETATION:** Longer windows are statistically smoother. Smoothness alone is not evidence of greater economic relevance.

## 10. Regime contamination

- **MEASURED FACT:** Median baseline SOFR-level range grows from 0.09 percentage points (20) to 0.26, 0.60, and 1.13 (252); the 252-window maximum is 5.24 points.
- **RESEARCH INTERPRETATION:** A 252-change baseline often spans materially different rate environments. That is acceptable for broad historical rarity but weakens its meaning as “recent behavior.”

## 11. Calendar context

- **MEASURED FACT:** Mean absolute change is 5.17bp on 99 month ends versus 2.09bp otherwise; 8.19bp on 32 quarter ends versus 2.14bp; and 10.88bp on eight year ends versus 2.20bp. The calendar rule is final weekday, without authoritative holiday adjustment.
- **RESEARCH INTERPRETATION:** Boundary clustering is economically relevant context, but small samples and calendar precision do not justify an adjustment.
- **DESIGN RECOMMENDATION:** Retain calendar flags as metadata only. Context explains; it does not erase an anomaly.

## 12. Historical extreme events

- **MEASURED FACT:** The largest signed moves are +282bp and -270bp. Full top-event rankings by method are saved separately and retain lineage.
- **RESEARCH INTERPRETATION:** Extreme moves dominate second-moment scales and demonstrate why standard Z and empirical rarity answer different questions.

## 13. Cross-window event comparison

- **MEASURED FACT:** `event_comparison.csv` contains the 20 largest absolute moves with all four windows available (80 rows), including SOFR levels, signed change, all five scores, tie counts, and baseline dates.
- **RESEARCH INTERPRETATION:** Cross-window differences are substantive, not formatting noise; the same move can be rare versus recent history and ordinary versus a broader stress-containing history.

## 14. Method disagreement analysis

- **MEASURED FACT:** Across 1,859 common dates, 20-window robust Z is extreme while percentile is below 90 on four small-move dates; 20-window midrank is at least 95 while abs(standard Z) is below 2 on 20 dates. A cross-window midrank spread of at least 25pp occurs on 118 dates (6.35%).
- **RESEARCH INTERPRETATION:** Robust-Z disagreement comes from a small denominator; percentile-versus-Z disagreement comes from rank versus second-moment scale; cross-window disagreement comes from different reference horizons.

## 15. Evidence quality implications

- **MEASURED FACT:** Known limitations are insufficient warm-up count, undefined scale, tie concentration, weekday-only calendar boundaries, and zero historical publication timestamps. Retrieval timestamps describe the backfill, not original availability.
- **DESIGN RECOMMENDATION:** Methodology freeze should define explicit evidence-quality reasons for warm-up, undefined scale, incomplete lineage, unknown availability time, and extreme ties. Do not yet map them to frozen `sufficient/limited/insufficient` states.

## 16. Method/window comparison table

- **MEASURED FACT:** The full 12-row factual table is [window_comparison.csv](window_comparison.csv). It includes eligible count, undefined rate, tie/scale issue, small-move escalation, outlier contamination, responsiveness, stability, interpretability, and failure mode, without a composite score.

## 17. Recommended anomaly evidence design

- **DESIGN RECOMMENDATION:** Primary rarity evidence: empirical absolute-change midrank percentile, accompanied by strict/weak bounds and counts. Secondary diagnostics: signed/absolute bp change and nullable standard Z. Robust Z should not drive v1 classification. No production threshold is proposed.

## 18. Recommended window design

- **MEASURED FACT:** 20-versus-252 midrank correlation is 0.877; mean/median absolute differences are 10.37/8.69pp, and 6.35% of common dates differ by at least 25pp.
- **RESEARCH INTERPRETATION:** The horizons overlap strongly but are not duplicates. A 60-change horizon offers recent-environment evidence with materially better resolution and less saturation than 20; 252 answers broad historical rarity but carries regime contamination.
- **DESIGN RECOMMENDATION:** Take a two-horizon candidate (60 recent + 252 broad) into Phase 2.1B-3. Keep semantics separate; do not average, maximize, or otherwise combine them without further specification.

## 19. Unresolved questions

- Historical publication timestamps are unavailable, so this is not availability-time replay.
- No approved policy-event dataset was found in the scoped architecture; FOMC/policy context remains deferred.
- Holiday-adjusted boundary dates and a production materiality cutoff remain unfrozen.
- Overlapping windows make score rows dependent; no pseudo-significance or causal claims are made.

## 20. Production readiness decision

**READY FOR METHODOLOGY FREEZE**

- **RESEARCH INTERPRETATION:** History is long enough to choose candidate evidence semantics and windows. The remaining issues are methodology choices for Phase 2.1B-3, not a missing SOFR source or inadequate sample.
- **DESIGN RECOMMENDATION:** Freeze definitions and evidence-quality behavior next; do not implement the production signal until that separate phase is approved.

