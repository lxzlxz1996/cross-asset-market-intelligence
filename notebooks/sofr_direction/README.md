# SOFR direction research

Research only. This study reuses the frozen validated SOFR snapshot and existing
anomaly research evidence. It does not write the database, alter
`sofr_rate_state/v1`, populate `direction_state`, or define production thresholds.

## Reproduce

From the repository root:

```powershell
.\.venv\Scripts\python.exe notebooks/sofr_direction/analyze.py
.\.venv\Scripts\python.exe notebooks/sofr_direction/validate.py
.\.venv\Scripts\python.exe -m pytest notebooks/sofr_direction/test_analysis.py -q
```

Primary outputs are `outputs/direction_research.csv`, `method_comparison.csv`,
`case_studies.csv`, `results.json`, `report.md`, and `validation.json`.

The decision narrative and all 19 required sections are in
[`outputs/report.md`](outputs/report.md). Machine-readable decision facts are in
[`outputs/results.json`](outputs/results.json).

Definitions:

- `net_change_N = 100 × (SOFR_t - SOFR_(t-N))` over valid observations.
- `linear_slope_N` is OLS slope over the latest N levels, in bp per valid observation.
- Sign counts and median use the latest N consecutive valid changes including the
  current change.
- No method uses a future observation. Calendar gaps remain unfilled.
- Existing 60/252 anomaly percentiles are joined from the independently validated
  Phase 2.1B-2 artifact; they are not recomputed or modified.
