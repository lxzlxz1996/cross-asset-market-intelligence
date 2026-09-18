# SOFR Level Research

Research version: `sofr_level_research_v1`  
Scope: research evidence only; no production Level fields, state, or thresholds

## 1. Executive conclusion

**MEASURED FACT.** The 2,112-observation SOFR history contains observationally distinct level environments: a near-zero plateau, a +526bp rising transition, a high plateau with only +3bp endpoint change, and a later -120bp falling transition. Full-history percentile correlates 0.812 with the current level but only 0.299 with Direction net20. Recent median-distance measures correlate much more strongly with Direction (0.749–0.823). Level Z becomes extreme around discrete transitions; the 60-level Z reached -31.49 on 2024-09-19.

**RESEARCH INTERPRETATION.** Level adds useful descriptive context, but no single normalized statistic is a policy-neutral state. Full-history rank describes historical sample position and therefore largely separates level environments. Recent distance describes displacement from a local baseline and partly duplicates Direction. The two concepts are nevertheless distinguishable on established plateaus.

**DESIGN RECOMMENDATION.** Advance an evidence-only two-context design to methodology freeze: mandatory current SOFR level, prior-only full-history percentile with complete tie audit as broad context, and current-minus-prior-60-median distance in bp as recent context. Exclude Level Z and rolling percentiles from proposed primary production evidence. Keep `level_state=null`; do not freeze low/normal/high thresholds.

## 2. Dataset / reproducibility

**MEASURED FACT.** The study uses 2,112 canonical processed SOFR observations from 2018-04-03 through 2026-09-16 through the approved FRBNY → raw → processed lineage. Snapshot SHA-256 is `bef72683a3fe8fe0da76518ca325a19867fbb9249a7a69a76c510f65d167792d`. Exact processed IDs and source/vintage metadata are archived in `selected_observations.json`; timestamp, Git commit, database path, and script hash are in `results.json`.

All baselines are prior-only. Windows use valid observations, are never shortened, and do not fill calendar gaps. Percentile ties use exact decimal level equality. Z uses prior-only sample standard deviation (`ddof=1`). Existing Direction and anomaly evidence is joined without modification.

## 3. SOFR level structure

**MEASURED FACT.** The selected descriptive environments have the following observed properties:

| Observed environment | Dates | Level path | Zero-change share |
| --- | --- | ---: | ---: |
| Near-zero level | 2020-04-01–2022-03-15 | 0.01% → 0.05%; range 0.01–0.13% | 69.94% |
| Rising transition | 2022-03-16–2023-07-27 | 0.05% → 5.31%; +526bp | 56.89% |
| High plateau | 2023-07-28–2024-09-18 | 5.30% → 5.33%; range 5.30–5.40% | 59.93% |
| Falling transition | 2024-09-19–2026-09-16 | 4.82% → 3.62%; -120bp | 21.17% |

These labels describe the observed SOFR series only; they are not official policy regimes or causal claims.

## 4. Full-history percentile findings

**MEASURED FACT.** Across 2,111 eligible dates, full-history midrank was exactly 0 or 100 on 1.99% of dates. The mean/median/p90 strict–weak tie bracket was 2.51/0.92/6.84 percentile points, with a 60-point maximum. It changed on 99.67% of unchanged-level comparisons because the expanding baseline and equal-count set continue changing. Its median daily revision was only 0.184 points.

Median full-history midranks were 13.38 in the near-zero environment, 98.77 in the rising transition, 98.17 on the high plateau, and 65.12 in the falling transition.

**RESEARCH INTERPRETATION.** Full-history rank is highly interpretable as “position within all prior observations,” and is more independent from Direction than recent-relative candidates. It also strongly encodes which historical level environment is present. It must not be called normality, stress, or an invariant economic level.

**DESIGN RECOMMENDATION.** Retain it only as explicitly labeled broad historical-sample context, with strict/midrank/weak and counts. Midrank alone would hide potentially material ties.

## 5. Rolling percentile findings

| Prior window | Exact midrank 0/100 | Mean tie bracket | Median/p90 daily revision | Corr. with Direction net20 |
| ---: | ---: | ---: | ---: | ---: |
| 60 | 5.99% | 18.85 points | 1.67 / 28.33 points | 0.543 |
| 120 | 5.27% | 13.81 | 0.83 / 19.58 | 0.530 |
| 252 | 4.41% | 8.24 | 0.40 / 11.11 | 0.510 |
| 504 | 3.23% | 4.90 | 0.10 / 5.56 | 0.500 |

**MEASURED FACT.** Rolling percentiles frequently move while SOFR is unchanged: 81.45% of flat-level comparisons for 60 and 100% for 504. The 60-window maximum tie bracket is 100 points. Short windows normalize a new plateau quickly; long windows retain older transitional observations and lag.

**RESEARCH INTERPRETATION.** A rolling percentile mixes recent transition and level context, has material tie ambiguity, and substantially overlaps Direction. No tested window has a uniquely defensible economic meaning.

**DESIGN RECOMMENDATION.** Keep rolling percentiles as research diagnostics rather than primary proposed production evidence.

## 6. Distance-from-central-tendency findings

**MEASURED FACT.** Median-distance measures have zero median revision on unchanged-level dates and change on only 16.6–17.3% of those comparisons, versus 63.9–97.2% for mean distance. Median/p90 absolute daily revision is 1/5bp at all tested 20/60/120/252 windows.

Distance from the prior-60 median correlates 0.823 with Direction net20; prior-60 mean distance correlates 0.847. Correlation falls with longer windows but their baseline adapts more slowly.

**RESEARCH INTERPRETATION.** Raw bp distance is clearer than percentile or Z and preserves economic magnitude without a scale denominator. Median is more stable on plateaus than mean. The high Direction correlation shows it is not an independent trend signal; its distinct role is only “distance from a local level baseline.”

**DESIGN RECOMMENDATION.** Carry prior-60 median distance into methodology freeze as recent-relative Level context, explicitly subordinate to current level and not a second Direction classifier.

## 7. Level Z-score findings

**MEASURED FACT.** Standard Level Z is undefined because of zero scale on 35 of 2,052 eligible 60-window dates (1.71%). Absolute Z was at least 2 on 13.49%, 15.71%, 22.04%, and 24.69% of available 60/120/252/504 observations. The 2024-09-19 downward step produced Z60=-31.49, which decayed to -0.94 after 60 valid observations.

**RESEARCH INTERPRETATION.** Z is primarily a transition-versus-flat-baseline detector. Its magnitude depends on denominator history and can be enormous without representing stress or probability. Longer windows reduce daily revision but increase persistence of transition effects.

**DESIGN RECOMMENDATION.** Exclude Level Z from proposed production Level evidence.

## 8. Optional robust-level findings

**MEASURED FACT.** Prior-level MAD was exactly zero in 19.54%, 16.67%, 9.46%, and 0% of eligible 60/120/252/504 windows.

**RESEARCH INTERPRETATION.** Robust scaling would be structurally unavailable in a material fraction of shorter windows. Adding epsilon or silent fallback would change the meaning and repeat the failure pattern identified in anomaly research.

**DESIGN RECOMMENDATION.** Retain raw median distance, but do not produce median/MAD Level Z.

## 9. Policy-regime contamination

**MEASURED FACT.** Median full-history midrank changed from 13.38 in the near-zero environment to 98.77 during the rising transition and 98.17 on the high plateau. Median prior-252 percentile was 33.33, 97.62, 88.89, and 7.14 across the four selected environments. Median prior-60 distance was 0bp, +45bp, +1bp, and -3bp.

**RESEARCH INTERPRETATION.** Full-history and long rolling ranks largely identify observational level eras. Recent median distance instead normalizes an established plateau. Neither provides a policy-neutral high/normal/low truth.

## 10. Step-change behavior

**MEASURED FACT.** On 2022-06-16, a new upward level produced percentile60/252/504=100, prior-60 median distance +115bp, and Z60=3.76. After 60 observations, percentile60 was 65.83, median distance60 +1bp, and Z60=0.92, while percentile252 remained 91.87 and median distance252 +223bp.

On 2024-09-19, a downward step produced percentile60/252=0, median distance60=-52bp, and Z60=-31.49. After 60 observations these became 31.67, -20bp, and -0.94; percentile252 remained 7.54 and median distance252=-69bp.

**RESEARCH INTERPRETATION.** Short recent context adapts to a new level; broad context deliberately retains the earlier environment. Z exaggerates the transition when its prior scale is small. None of these facts imply funding conditions.

## 11. Plateau behavior

**MEASURED FACT.** On 2024-06-14 SOFR was 5.31%, full-history midrank 91.87, but prior-60/252 percentile was 30/50, median distance60/252 was 0bp, Z60=-0.66, and Direction net20 was 0bp. On 2021-10-18 the 0.05% near-zero plateau had full-history midrank 19.47, percentile60 50, and median distance60=0bp.

**RESEARCH INTERPRETATION.** A level can remain historically high or low while being centered in its recent environment. This is the clearest empirical support for separating broad and recent context.

## 12. Broad vs recent context

**MEASURED FACT.** Full-history percentile correlation with current level is 0.812 and with Direction net20 is 0.299. Prior-60 median distance correlations are 0.088 and 0.823 respectively.

**RESEARCH INTERPRETATION.** Broad rank primarily describes absolute historical sample position; recent distance primarily describes transition away from a local baseline. They are not interchangeable. Together they can state “historically high, recently centered” without assigning a level state.

**DESIGN RECOMMENDATION.** A two-context evidence design is supported, but the fields must remain separately named and explained. They must not be aggregated.

## 13. Level vs Direction

**MEASURED FACT.** Recent-relative candidates correlate strongly with Direction net20: mean distances 0.591–0.847, median distances 0.596–0.823, rolling percentiles about 0.500–0.543, and Z 0.411–0.645. Full-history percentile is lower at 0.299.

Examples include high level + flat direction (2024-06-14: 5.31%, full-history 91.87, net20=0), high level + falling direction (2024-09-19: 4.82%, net20=-49), and low historical position + flat direction (2021-10-18: full-history 19.47, net20=0).

**DESIGN RECOMMENDATION.** Do not use recent Level evidence to recreate Direction state. Its only distinct claim is reference-level distance.

## 14. Level vs Anomaly

**MEASURED FACT.** Correlations with recent anomaly rarity are low: 0.076 for full-history percentile, 0.057–0.134 for rolling percentiles, 0.024–0.083 for distances, and 0.061–0.087 for Z. The 2024-06-14 high plateau had a zero latest change and ordinary change rarity despite a 91.87 full-history Level rank; step dates combined Level displacement with high change rarity.

**RESEARCH INTERPRETATION.** Level position and one-change rarity are distinct. Anomaly must not classify Level, and Level must not be interpreted as stress.

## 15. Tie / saturation behavior

**MEASURED FACT.** Full-history ties are usually narrower than rolling ties but can still be large. Rolling60 has an 18.85-point mean bracket, 63.17-point p90, and 100-point maximum. Exact midrank saturation declines from 5.99% at 60 to 3.23% at 504, versus 1.99% for expanding history.

**DESIGN RECOMMENDATION.** Any percentile carried forward must persist less/equal/greater counts plus strict/midrank/weak. A single library percentile is insufficient.

## 16. Historical case studies

| Case | Broad context | Recent context | Direction/anomaly distinction |
| --- | --- | --- | --- |
| Near-zero plateau, 2021-10-18 | Full-history 19.47 | percentile60 50; median-distance60 0bp | net20 0; Level location differs from Direction |
| Upward step, 2022-06-16 | Full-history 54.47 | percentile60 100; distance60 +115bp; Z60 3.76 | current change rarity high; no stress inference |
| Rising transition, 2023-07-27 | Full-history 100 | percentile60/252 100; distance60 +26bp | net20 +25bp; recent metrics overlap Direction |
| High plateau, 2024-06-14 | Full-history 91.87 | percentile60 30; distance60 0bp | net20 0 despite historical-high context |
| Historical-high/recent-flat, 2024-08-15 | Full-history 99.09 | distance60 +2bp | net20 +1bp |
| Downward step, 2024-09-19 | Full-history 78.25 | percentile60/252 0; distance60 -52bp; Z60 -31.49 | net20 -49; rarity 100 |
| Falling environment, 2026-05-20 | Full-history 56.50 | percentile60/252 0; distance60 -14bp | net20 -14; Level and Direction partly overlap |

Complete before/on/+1/+5/+10/+20/+60 step paths are in `case_studies.csv`.

## 17. Method comparison

| Method | Windows | Plateau behavior | Regime contamination | Direction independence | Main weakness |
| --- | --- | --- | --- | --- | --- |
| Full-history percentile | expanding | slow numerical drift even when level is unchanged | high; corr. current level 0.812 | strongest tested normalized candidate; corr. net20 0.299 | expanding sample and policy-era dependence |
| Rolling percentile | 60/120/252/504 | baseline rolls even on flat dates | shorter adapts quickly; longer retains old environments | moderate; corr. net20 0.500–0.543 | ties, saturation, arbitrary horizon |
| Mean distance | 20/60/120/252 | baseline drifts on flat dates | transition-sensitive | weak; corr. net20 up to 0.847 | overlap with Direction and outlier sensitivity |
| Median distance | 20/60/120/252 | zero median revision on flat dates | recent horizon normalizes plateau | weak-to-moderate; corr. net20 up to 0.823 | transition overlap and horizon dependence |
| Level Z | 60/120/252/504 | denominator evolves mechanically | amplifies steps between flat environments | moderate at best | scale collapse, huge transition values, no probability meaning |
| Median/MAD Z | diagnostic only | unavailable when MAD=0 | same transition problem | not promoted | structural zero scale |

The complete per-method factual table is in `method_comparison.csv`; no arbitrary aggregate score was assigned.

## 18. Recommended Level evidence design

**DESIGN RECOMMENDATION.** Carry the following evidence family to methodology freeze:

```text
current_level_percent

broad_historical_context:
  prior_level_count
  less_count
  equal_count
  greater_count
  strict_percentile
  midrank_percentile
  weak_percentile
  baseline_start_date
  baseline_end_date

recent_context_60:
  prior_level_count: 60
  prior_median_level_percent
  distance_from_prior_median_bp
  baseline_start_date
  baseline_end_date
```

Full-history broad context requires the current level plus every exact prior selected processed level. Recent context requires the current plus exactly 60 prior levels; it is a suffix of the broad lineage. Methodology freeze must specify warm-up, expanding-lineage cost, and deterministic explanation, but no additional research formula is required.

Fields not recommended: rolling percentile production windows, mean distance, Level Z, robust Z, combined score, calendar adjustment, and Level classification threshold.

## 19. level_state assessment

**MEASURED FACT.** Candidate values change materially by reference frame. On 2024-06-14, the same 5.31% level was at full-history 91.87, percentile60 30, percentile252 50, and distance60 0bp. No tested cutoff has an externally grounded economic meaning.

**DESIGN RECOMMENDATION.** Keep `level_state=null`. The evidence does not justify `low/normal/high`; such labels would mostly encode a chosen reference window or observational policy era.

## 20. Production readiness

**READY FOR LEVEL METHODOLOGY FREEZE**

Q1: Level adds useful broad-versus-recent descriptive context beyond current level and Direction, but only with explicit semantics.  
Q2: Best evidence is current level + full-history tie-audited rank + prior-60 median distance.  
Q3: Use expanding prior history for broad context and 60 prior valid levels for recent context.  
Q4: The two-context design is supported by high-plateau cases.  
Q5: Level Z is mainly a transition/scale detector and is not recommended.  
Q6: Percentiles are interpretable only with complete tie brackets/counts.  
Q7: `level_state` should remain null.  
Q8: Advance only the evidence contract in Section 18.  
Q9: Ready for methodology freeze; no production changes were made.
