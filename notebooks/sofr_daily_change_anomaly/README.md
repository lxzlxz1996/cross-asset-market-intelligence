# Phase 2.1B-1 — SOFR daily-change anomaly research

## Phase 2.1B-2 expanded-history update

The preserved Phase 2.1B-1 output remains in `outputs/`. The expanded 2018-04-03
through 2026-09-16 research snapshot and delta report are in
`outputs_phase_2_1b_2/`. Reproduce and independently validate that snapshot with:

```powershell
.\.venv\Scripts\python.exe notebooks/sofr_daily_change_anomaly/analyze.py --output notebooks/sofr_daily_change_anomaly/outputs_phase_2_1b_2
.\.venv\Scripts\python.exe notebooks/sofr_daily_change_anomaly/validate.py --output notebooks/sofr_daily_change_anomaly/outputs_phase_2_1b_2
.\.venv\Scripts\python.exe -m pytest notebooks/sofr_daily_change_anomaly/test_analysis.py -q
```

Read the [Phase 2.1B-2 delta report](outputs_phase_2_1b_2/delta_report.md),
`results.json`, `rolling_scores.csv`, `window_comparison.csv`, and
`event_comparison.csv`. The expanded run is research-only and does not supersede
the frozen prior report or create a production signal.

Research only. This directory does not change frozen Phase 1 / Phase 2.1A code,
schemas, CLI behavior, production definitions, classification thresholds, or
signal observations. No live downloads, new dependencies, or invented events.

## Read the result

[11-section research report](outputs/report.md), with all 20-row event tables and
the conditional methodology recommendation. `outputs/results.json` contains the
full quantitative summary; CSVs retain selected levels, lineage identities,
all changes, rolling scores, and five top-20 rankings. `validation.json` records
an independent SQL cross-check. An optional local visual report is a rendering
of `reviewed_report.json`, not another signal engine or production dashboard.

The reviewed sample has 61 validated levels / 60 changes (2026-06-22 through
2026-09-16). Only the 20-change window has eligible scores. Longer-window
results are unavailable, not failed and not extrapolated. The snapshot was
backfilled on 2026-09-17 with unknown publication timestamps, so chronological
prior-only calculations are **not** historical availability-time replay.

## Reproduce from the existing validated database

From the repository root, using the existing environment:

```powershell
.\.venv\Scripts\python.exe notebooks/sofr_daily_change_anomaly/analyze.py
.\.venv\Scripts\python.exe notebooks/sofr_daily_change_anomaly/make_report.py
.\.venv\Scripts\python.exe notebooks/sofr_daily_change_anomaly/validate.py
.\.venv\Scripts\python.exe -m pytest notebooks/sofr_daily_change_anomaly/test_analysis.py -q
```

`analyze.py` opens the configured database read-only, without initialization.
`--database PATH` and `--output PATH` allow a separate source or research output
directory. `make_report.py` and `validate.py` consume the default `outputs/`.
`make_report.py` deliberately rejects a changed input hash: its interpretations
were reviewed against the archived sample, and must be reviewed again rather
than silently applied to new data. Re-running the scripts updates research
artifacts only. Archive outputs before rerunning if retaining the prior run is
important. Analysis version, source-code hashes, selected-input hash, execution
time and repository commit are recorded in `results.json`; the commit alone
does not identify uncommitted source changes.

## Conventions

- `delta_t = 100 × (SOFR_t − SOFR_previous_valid)` bp using decimal source levels.
  This is an observation-to-observation change, not a calendar-day difference.
- At change index `i`, the baseline is exactly `[i-N:i]`, excluding the current
  change. No filling, interpolation, annualization or calendar normalization.
- Standard Z uses sample standard deviation (ddof=1). Robust Z uses
  `0.6745 × (delta − median) / MAD`; zero scale is undefined, with no epsilon.
- Percentile compares absolute changes: strict `<`, weak `≤`, and midrank
  `< + 0.5×ties`. These are empirical ranks, not calibrated event probabilities.
- Calendar boundary flags use the final weekday and explicitly lack holiday
  adjustment. Adjacent-observation flags are retrospective report context only.
- Leave-one-largest-prior diagnostics are sensitivity tests, not proposed rules.
- Synthetic values occur only in unit tests, never in report inputs.

Policy-event/FOMC context is deferred; source-pending SPX/VIX/MOVE remain outside
scope. More validated history and economic materiality research are required
before production implementation or window/threshold selection.
