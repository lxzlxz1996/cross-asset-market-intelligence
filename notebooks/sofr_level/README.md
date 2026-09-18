# SOFR Level research

Research only. This study reuses the frozen selected SOFR history and existing
Direction/anomaly research evidence. It does not write the database, modify
`sofr_rate_state/v1` or `v2`, populate `level_state`, or define production thresholds.

## Reproduce

```powershell
.\.venv\Scripts\python.exe notebooks/sofr_level/analyze.py
.\.venv\Scripts\python.exe notebooks/sofr_level/validate.py
.\.venv\Scripts\python.exe -m pytest notebooks/sofr_level/test_analysis.py -q
```

Primary outputs are `outputs/level_research.csv`, `method_comparison.csv`,
`case_studies.csv`, `results.json`, `validation.json`, and `report.md`.

The 20-section decision narrative is in [`outputs/report.md`](outputs/report.md).
Machine-readable findings and the research recommendation are in
[`outputs/results.json`](outputs/results.json).

All percentiles compare the current level only with prior selected levels. Rolling
windows are never shortened. Mean/median distances use prior-only levels and bp units.
Level Z uses prior-only sample standard deviation (`ddof=1`) and is null at zero scale.
