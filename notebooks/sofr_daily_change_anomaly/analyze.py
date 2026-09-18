"""Phase 2.1B-1 research only: read validated SOFR, write auditable artifacts.

Run from the repository root with its existing virtual environment. No network,
schema initialization, production signal definitions, or signal writes are used.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import statistics as st
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cross_asset_market_intelligence.config import load_settings
from cross_asset_market_intelligence.dashboard.sofr_read_model import sofr_history
from cross_asset_market_intelligence.database import connect
from cross_asset_market_intelligence.lineage import RawInputIdentity, processed_observation_id

WINDOWS = (20, 60, 120, 252)
QUANTILES = (0, .025, .25, .5, .75, .9, .95, .975, .99, .995, 1)
ANALYSIS_VERSION = "sofr_change_anomaly_research_v2_expanded"


def quantile(values, probability):
    """Linear interpolation at (n-1)*p, descriptive rather than fitted tails."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    return ordered[lower] + (position - lower) * (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower])


def summarize(values):
    if not values:
        return {"n": 0}
    median = st.median(values)
    mean = st.mean(values)
    variance = st.pvariance(values)
    return {
        "n": len(values), "min": min(values), "max": max(values),
        "mean": mean, "median": median,
        "sample_std_ddof1": st.stdev(values) if len(values) > 1 else None,
        "mad": st.median(abs(v - median) for v in values),
        "moment_skewness": None if variance == 0 else st.mean((v - mean) ** 3 for v in values) / variance ** 1.5,
        "moment_excess_kurtosis": None if variance == 0 else st.mean((v - mean) ** 4 for v in values) / variance ** 2 - 3,
        "quantiles": {str(p): quantile(values, p) for p in QUANTILES},
    }


def evaluate_change(current, prior):
    """Current is never included in prior. Zero scale remains undefined."""
    mean = st.mean(prior)
    median = st.median(prior)
    std = st.stdev(prior)
    mad = st.median(abs(v - median) for v in prior)
    less = sum(abs(v) < abs(current) for v in prior)
    equal = sum(abs(v) == abs(current) for v in prior)
    greater = len(prior) - less - equal
    largest_index = max(range(len(prior)), key=lambda i: (abs(prior[i]), -i))
    without_largest = prior[:largest_index] + prior[largest_index + 1:]
    clean_std = st.stdev(without_largest)
    return {
        "prior_mean_bp": mean, "prior_median_bp": median,
        "prior_std_bp": std, "prior_mad_bp": mad,
        "standard_z": None if std == 0 else (current - mean) / std,
        "robust_z": None if mad == 0 else .6745 * (current - median) / mad,
        "percentile_strict": 100 * less / len(prior),
        "percentile_midrank": 100 * (less + .5 * equal) / len(prior),
        "percentile_weak": 100 * (less + equal) / len(prior),
        "prior_less_count": less, "prior_equal_count": equal, "prior_greater_count": greater,
        "prior_max_abs_bp": max(abs(v) for v in prior),
        "std_without_largest_bp": clean_std,
        "std_inflation_ratio": None if clean_std == 0 else std / clean_std,
        "z_without_largest": None if clean_std == 0 else (current - st.mean(without_largest)) / clean_std,
    }


def weekday_month_end(observation_date):
    boundary = date(observation_date.year, observation_date.month, calendar.monthrange(observation_date.year, observation_date.month)[1])
    while boundary.weekday() >= 5:
        boundary -= timedelta(days=1)
    return boundary


def contextualize(changes, levels):
    """Weekday boundary ignores holidays; +/-1 uses actual saved observations.

    Around-boundary flags are retrospective descriptive context, never score
    inputs. Boundary dates must themselves exist in the saved selection.
    """
    indices = {row["date"]: i for i, row in enumerate(levels)}
    boundaries = {weekday_month_end(date.fromisoformat(row["date"])) for row in levels}
    present = [boundary for boundary in sorted(boundaries) if boundary.isoformat() in indices]
    for row in changes:
        current = date.fromisoformat(row["date"])
        boundary = weekday_month_end(current)
        row["month_end"] = current == boundary
        row["quarter_end"] = row["month_end"] and current.month in (3, 6, 9, 12)
        row["year_end"] = row["month_end"] and current.month == 12
        for label, months in (("month", range(1, 13)), ("quarter", (3, 6, 9, 12)), ("year", (12,))):
            row[f"around_{label}_end"] = any(
                b.month in months and abs(indices[row["date"]] - indices[b.isoformat()]) <= 1
                for b in present
            )
    return [b.isoformat() for b in present]


def method_summary(rows, window):
    available = [r for r in rows if r["window"] == window]
    result = {"window": window, "eligible_dates": len(available)}
    if not available:
        return result
    result.update({
        "mad_zero_count": sum(r["prior_mad_bp"] == 0 for r in available),
        "mad_below_1bp_count": sum(0 < r["prior_mad_bp"] < 1 for r in available),
        "mad_at_most_1bp_count": sum(r["prior_mad_bp"] <= 1 for r in available),
        "std_zero_count": sum(r["prior_std_bp"] == 0 for r in available),
        "std_below_1bp_count": sum(0 < r["prior_std_bp"] < 1 for r in available),
        "std_range_bp": [min(r["prior_std_bp"] for r in available), max(r["prior_std_bp"] for r in available)],
        "mad_range_bp": [min(r["prior_mad_bp"] for r in available), max(r["prior_mad_bp"] for r in available)],
        "max_std_inflation_ratio": max(r["std_inflation_ratio"] for r in available if r["std_inflation_ratio"] is not None),
        "tie_count_range": [min(r["prior_equal_count"] for r in available), max(r["prior_equal_count"] for r in available)],
        "mean_percentile_tie_gap_pp": st.mean(r["percentile_weak"] - r["percentile_strict"] for r in available),
        "median_percentile_tie_gap_pp": st.median(r["percentile_weak"] - r["percentile_strict"] for r in available),
        "max_percentile_tie_gap_pp": max(r["percentile_weak"] - r["percentile_strict"] for r in available),
        "percentile_saturation_100_count": sum(r["percentile_midrank"] == 100 for r in available),
        "percentile_weak_saturation_100_count": sum(r["percentile_weak"] == 100 for r in available),
    })
    for method in ("standard_z", "robust_z", "percentile_strict", "percentile_midrank", "percentile_weak"):
        scores = [r[method] for r in available if r[method] is not None]
        result[method] = summarize(scores)
        result[method]["undefined_count"] = len(available) - len(scores)
        result[method]["absolute_quantiles"] = {str(p): quantile([abs(s) for s in scores], p) for p in (.5, .9, .95, .99, 1)}
        thresholds = (2, 3) if method.endswith("_z") else (90, 95, 99)
        result[method]["diagnostic_counts"] = {
            str(threshold): {
                "all": sum(abs(r[method]) >= threshold for r in available if r[method] is not None),
                "at_most_1bp": sum(abs(r["change_bp"]) <= 1 and abs(r[method]) >= threshold for r in available if r[method] is not None),
                "exact_1bp": sum(abs(r["change_bp"]) == 1 and abs(r[method]) >= threshold for r in available if r[method] is not None),
                "at_most_2bp": sum(abs(r["change_bp"]) <= 2 and abs(r[method]) >= threshold for r in available if r[method] is not None),
            } for threshold in thresholds
        }
    return result


def successive_diagnostics(rows, field):
    differences = [
        abs(current[field] - previous[field])
        for previous, current in zip(rows, rows[1:])
        if previous[field] is not None and current[field] is not None
    ]
    return {
        "count": len(differences),
        "median_absolute_change": st.median(differences) if differences else None,
        "p90_absolute_change": quantile(differences, .9),
        "maximum_absolute_change": max(differences) if differences else None,
    }


def window_diagnostics(scores, changes, window):
    rows = [row for row in scores if row["window"] == window]
    if not rows:
        return {"window": window, "eligible_dates": 0}
    largest_index = max(range(len(changes)), key=lambda i: (changes[i]["absolute_change_bp"], -i))
    largest = changes[largest_index]
    exit_index = largest_index + window + 1
    exit_date = changes[exit_index]["date"] if exit_index < len(changes) else None
    by_date = {row["date"]: row for row in rows}
    exit_row = by_date.get(exit_date)
    previous_row = rows[rows.index(exit_row) - 1] if exit_row in rows and rows.index(exit_row) else None
    return {
        "window": window,
        "eligible_dates": len(rows),
        "score_stability": {
            field: successive_diagnostics(rows, field)
            for field in ("standard_z", "robust_z", "percentile_midrank")
        },
        "scale_stability": {
            field: successive_diagnostics(rows, field)
            for field in ("prior_std_bp", "prior_mad_bp")
        },
        "level_range_percent": summarize([row["baseline_level_range_percent"] for row in rows]),
        "largest_full_history_change": {
            "date": largest["date"], "change_bp": largest["change_bp"],
            "baseline_residence_changes": window,
            "first_possible_exit_score_date": exit_date,
            "std_change_when_exiting": None if not previous_row or not exit_row else exit_row["prior_std_bp"] - previous_row["prior_std_bp"],
            "mad_change_when_exiting": None if not previous_row or not exit_row else exit_row["prior_mad_bp"] - previous_row["prior_mad_bp"],
        },
    }


def comparison_rows(scores, summaries, diagnostics):
    rows = []
    by_summary = {row["window"]: row for row in summaries}
    by_diagnostic = {row["window"]: row for row in diagnostics}
    for window in WINDOWS:
        sample = [row for row in scores if row["window"] == window]
        summary = by_summary[window]
        diagnostic = by_diagnostic[window]
        eligible = len(sample)
        methods = (
            ("standard_z", "Standard Z", summary["standard_z"]["undefined_count"],
             f"std={summary['std_range_bp'][0]:.4g}..{summary['std_range_bp'][1]:.4g}bp",
             sum(abs(row["change_bp"]) <= 2 and row["standard_z"] is not None and abs(row["standard_z"]) >= 2 for row in sample),
             f"max std inflation={summary['max_std_inflation_ratio']:.4g}x",
             "signed deviation from prior mean in sample-std units", "outlier-widened or zero scale"),
            ("robust_z", "Robust Z / MAD", summary["robust_z"]["undefined_count"],
             f"MAD={summary['mad_range_bp'][0]:.4g}..{summary['mad_range_bp'][1]:.4g}bp; zero={summary['mad_zero_count']}",
             sum(abs(row["change_bp"]) <= 2 and row["robust_z"] is not None and abs(row["robust_z"]) >= 2 for row in sample),
             "median/MAD reduces squared-tail leverage",
             "signed deviation from prior median in MAD units", "zero/small MAD and discrete jumps"),
            ("percentile_midrank", "Absolute-change midrank percentile", 0,
             f"tie bracket mean/median/max={summary['mean_percentile_tie_gap_pp']:.3g}/{summary['median_percentile_tie_gap_pp']:.3g}/{summary['max_percentile_tie_gap_pp']:.3g}pp",
             sum(abs(row["change_bp"]) <= 2 and row["percentile_midrank"] >= 90 for row in sample),
             f"rank weight={100/window:.3g}pp; no scale denominator",
             "relative rank of absolute movement; direction and magnitude separate", "ties, saturation, and horizon dependence"),
        )
        for field, method, undefined, issue, small, contamination, interpretation, failure in methods:
            stability = diagnostic["score_stability"][field]
            scale_field = "prior_mad_bp" if field == "robust_z" else "prior_std_bp"
            responsiveness = None if field == "percentile_midrank" else diagnostic["scale_stability"].get(scale_field)
            rows.append({
                "method": method, "window": window, "eligible_n": eligible,
                "undefined_count": undefined, "undefined_rate_percent": 100 * undefined / eligible,
                "scale_or_tie_issue": issue, "small_move_escalation_count": small,
                "outlier_contamination": contamination,
                "responsiveness": f"median daily scale move={responsiveness['median_absolute_change']:.4g}" if responsiveness else f"rank resolution={100/window:.4g}pp",
                "stability": f"median/p90 |daily score change|={stability['median_absolute_change']:.4g}/{stability['p90_absolute_change']:.4g}",
                "interpretability": interpretation, "key_failure_mode": failure,
            })
    return rows


def event_comparison_rows(scores, limit=20):
    all_windows = {}
    for row in scores:
        all_windows.setdefault(row["date"], {})[row["window"]] = row
    comparable = [by_window for by_window in all_windows.values() if all(window in by_window for window in WINDOWS)]
    selected = sorted(comparable, key=lambda group: (-group[252]["absolute_change_bp"], group[252]["date"]))[:limit]
    rows = []
    for group in selected:
        for window in WINDOWS:
            row = group[window]
            rows.append({
                "selection_reason": "top absolute movement with all windows available",
                "date": row["date"], "sofr_percent": row["sofr_percent"],
                "previous_sofr_percent": row["previous_sofr_percent"], "change_bp": row["change_bp"],
                "window": window, "standard_z": row["standard_z"], "robust_z": row["robust_z"],
                "percentile_strict": row["percentile_strict"], "percentile_midrank": row["percentile_midrank"],
                "percentile_weak": row["percentile_weak"], "prior_less_count": row["prior_less_count"],
                "prior_equal_count": row["prior_equal_count"], "prior_greater_count": row["prior_greater_count"],
                "baseline_first_change_date": row["baseline_first_change_date"],
                "baseline_last_change_date": row["baseline_last_change_date"],
            })
    return rows


def disagreement_summary(scores):
    by_date = {}
    for row in scores:
        by_date.setdefault(row["date"], {})[row["window"]] = row
    common = [group for group in by_date.values() if all(window in group for window in WINDOWS)]
    predicates = {
        "small_move_robust_extreme_percentile_below_90": lambda group: abs(group[20]["change_bp"]) <= 2 and group[20]["robust_z"] is not None and abs(group[20]["robust_z"]) >= 3 and group[20]["percentile_midrank"] < 90,
        "percentile_at_least_95_standard_z_below_2": lambda group: group[20]["percentile_midrank"] >= 95 and group[20]["standard_z"] is not None and abs(group[20]["standard_z"]) < 2,
        "long_high_short_below_75": lambda group: group[252]["percentile_midrank"] >= 95 and group[20]["percentile_midrank"] < 75,
        "short_high_long_below_75": lambda group: group[20]["percentile_midrank"] >= 95 and group[252]["percentile_midrank"] < 75,
        "cross_window_midrank_spread_at_least_25pp": lambda group: max(group[w]["percentile_midrank"] for w in WINDOWS) - min(group[w]["percentile_midrank"] for w in WINDOWS) >= 25,
    }
    result = {"common_eligible_dates": len(common), "diagnostic_cutoffs_are_not_production_thresholds": True}
    for name, predicate in predicates.items():
        matches = [group for group in common if predicate(group)]
        result[name] = {
            "count": len(matches), "percent": 100 * len(matches) / len(common),
            "example_dates": [group[20]["date"] for group in matches[:10]],
        }
    paired = [(group[20]["percentile_midrank"], group[252]["percentile_midrank"]) for group in common]
    if paired:
        mean_x, mean_y = st.mean(x for x, _ in paired), st.mean(y for _, y in paired)
        covariance = sum((x-mean_x)*(y-mean_y) for x, y in paired)
        denominator = (sum((x-mean_x)**2 for x, _ in paired) * sum((y-mean_y)**2 for _, y in paired)) ** .5
        result["midrank_20_252"] = {
            "pearson_correlation_descriptive": None if denominator == 0 else covariance / denominator,
            "mean_absolute_difference_pp": st.mean(abs(x-y) for x, y in paired),
            "median_absolute_difference_pp": st.median(abs(x-y) for x, y in paired),
        }
    return result


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=load_settings(ROOT).database_path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs")
    arguments = parser.parse_args()
    database = arguments.database.resolve()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    executed_at = datetime.now(timezone.utc).isoformat()
    with connect(database, read_only=True) as connection:
        history = sofr_history(connection)
        raw = connection.execute(
            """SELECT source, series_id, observation_date, value, retrieval_timestamp,
            publication_timestamp, vintage, metadata::VARCHAR FROM raw_observations
            WHERE source = ? AND series_id = ? ORDER BY observation_date, vintage""", ("frbny", "SOFR")
        ).fetchall()
        processed_count = connection.execute("SELECT count(*) FROM processed_observations WHERE indicator_id = ?", ("sofr",)).fetchone()[0]
        raw_duplicate_identity_count = connection.execute(
            """SELECT coalesce(sum(n - 1), 0) FROM (
            SELECT count(*) n FROM raw_observations WHERE source = ? AND series_id = ?
            GROUP BY source, series_id, observation_date, vintage HAVING count(*) > 1)""", ("frbny", "SOFR")
        ).fetchone()[0]
        table_counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("raw_observations", "processed_observations", "signals")}
        raw_by_identity = {(r[0], r[1], r[2], r[6]): r for r in raw}
        levels = []
        for item in history:
            lineage = item.lineage.raw_input
            source_row = raw_by_identity[(lineage.source, lineage.series_id, lineage.observation_date, lineage.vintage)]
            expected_id = processed_observation_id(item.indicator_id, item.observation_date, item.processing_version, [RawInputIdentity("source", lineage.source, lineage.series_id, lineage.observation_date, lineage.vintage)])
            if expected_id != item.processed_observation_id or Decimal(str(source_row[3])) != Decimal(str(item.value)):
                raise ValueError("Selected processed identity/value does not agree with raw lineage")
            levels.append({
                "date": item.observation_date.isoformat(), "sofr_percent": item.value,
                "processed_observation_id": item.processed_observation_id,
                "processing_version": item.processing_version, "raw_source": lineage.source,
                "raw_series_id": lineage.series_id, "raw_vintage": lineage.vintage,
                "retrieval_timestamp": source_row[4].astimezone(timezone.utc).isoformat(),
                "publication_timestamp": None if source_row[5] is None else source_row[5].astimezone(timezone.utc).isoformat(),
            })
    changes = []
    for previous, current in zip(levels, levels[1:]):
        change = (Decimal(str(current["sofr_percent"])) - Decimal(str(previous["sofr_percent"]))) * 100
        changes.append({
            "date": current["date"], "previous_date": previous["date"],
            "sofr_percent": current["sofr_percent"], "previous_sofr_percent": previous["sofr_percent"],
            "change_bp": float(change), "absolute_change_bp": float(abs(change)),
            "calendar_gap_days": (date.fromisoformat(current["date"]) - date.fromisoformat(previous["date"])).days,
            "current_processed_id": current["processed_observation_id"], "previous_processed_id": previous["processed_observation_id"],
        })
    boundaries = contextualize(changes, levels)
    scores = []
    for i, row in enumerate(changes):
        for window in WINDOWS:
            if i < window:
                continue
            prior = changes[i-window:i]
            assert len(prior) == window and prior[-1]["date"] < row["date"]
            score = evaluate_change(row["change_bp"], [r["change_bp"] for r in prior])
            baseline_levels = [r["sofr_percent"] for r in prior]
            scores.append({
                **row, "window": window,
                "baseline_first_change_date": prior[0]["date"], "baseline_last_change_date": prior[-1]["date"],
                "baseline_level_min_percent": min(baseline_levels), "baseline_level_max_percent": max(baseline_levels),
                "baseline_level_range_percent": max(baseline_levels) - min(baseline_levels),
                "baseline_processed_ids_sha256": hashlib.sha256("|".join(r["current_processed_id"] for r in prior).encode()).hexdigest(),
                **score,
            })
    values = [r["change_bp"] for r in changes]
    frequency = Counter(values)
    monthly = []
    for month in sorted({row["date"][:7] for row in changes}):
        sample = [row["change_bp"] for row in changes if row["date"].startswith(month)]
        monthly.append({"month": month, "n_changes": len(sample), "zero_count": sample.count(0), "mean_absolute_bp": st.mean(abs(v) for v in sample), "max_absolute_bp": max(abs(v) for v in sample), "sample_std_bp": st.stdev(sample) if len(sample) > 1 else None})
    yearly = []
    for year in sorted({row["date"][:4] for row in changes}):
        sample = [row["change_bp"] for row in changes if row["date"].startswith(year)]
        yearly.append({
            "year": year, "n_changes": len(sample), "zero_percent": 100 * sample.count(0) / len(sample),
            "mean_absolute_bp": st.mean(abs(v) for v in sample), "median_absolute_bp": st.median(abs(v) for v in sample),
            "sample_std_bp": st.stdev(sample) if len(sample) > 1 else None,
            "mad_bp": st.median(abs(v-st.median(sample)) for v in sample),
            "absolute_p95_bp": quantile([abs(v) for v in sample], .95),
        })
    level_bands = []
    bands = (("below_1_percent", -float("inf"), 1), ("1_to_3_percent", 1, 3), ("3_to_5_percent", 3, 5), ("at_least_5_percent", 5, float("inf")))
    for label, lower, upper in bands:
        sample = [row["change_bp"] for row in changes if lower <= row["previous_sofr_percent"] < upper]
        if sample:
            level_bands.append({
                "level_band": label, "n_changes": len(sample), "mean_absolute_bp": st.mean(abs(v) for v in sample),
                "median_absolute_bp": st.median(abs(v) for v in sample), "sample_std_bp": st.stdev(sample) if len(sample) > 1 else None,
                "zero_percent": 100 * sample.count(0) / len(sample), "absolute_p95_bp": quantile([abs(v) for v in sample], .95),
            })
    calendar_groups = []
    for flag in ("month_end", "quarter_end", "year_end", "around_month_end", "around_quarter_end", "around_year_end"):
        for flag_value in (True, False):
            group = [r for r in changes if r[flag] == flag_value]
            if group:
                calendar_groups.append({"flag": flag, "value": flag_value, "n": len(group), "mean_abs_bp": st.mean(r["absolute_change_bp"] for r in group), "abs_at_least_3bp": sum(r["absolute_change_bp"] >= 3 for r in group), "abs_at_least_5bp": sum(r["absolute_change_bp"] >= 5 for r in group)})
    calendar_score_groups = []
    for window in WINDOWS:
        window_scores = [row for row in scores if row["window"] == window]
        for flag in ("month_end", "quarter_end", "year_end", "around_month_end", "around_quarter_end", "around_year_end"):
            group = [row for row in window_scores if row[flag]]
            if group:
                calendar_score_groups.append({
                    "window": window, "flag": flag, "n": len(group),
                    "mean_abs_bp": st.mean(row["absolute_change_bp"] for row in group),
                    "median_abs_bp": st.median(row["absolute_change_bp"] for row in group),
                    "median_midrank_percentile": st.median(row["percentile_midrank"] for row in group),
                    "median_abs_standard_z": st.median(abs(row["standard_z"]) for row in group if row["standard_z"] is not None),
                    "median_abs_robust_z": st.median(abs(row["robust_z"]) for row in group if row["robust_z"] is not None) if any(row["robust_z"] is not None for row in group) else None,
                })
    tops = {}
    for method in ("standard_z", "robust_z", "percentile_strict", "percentile_midrank", "percentile_weak"):
        rows = [r for r in scores if r[method] is not None]
        rows.sort(key=lambda r: (-abs(r[method]), -r["absolute_change_bp"], r["date"]))
        tops[method] = rows[:20]
        write_csv(output / f"top20_{method}.csv", rows[:20])
    snapshot_encoded = json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
    summaries = [method_summary(scores, w) for w in WINDOWS]
    window_details = [window_diagnostics(scores, changes, w) for w in WINDOWS]
    window_comparison = comparison_rows(scores, summaries, window_details)
    event_comparison = event_comparison_rows(scores)
    summary = {
        "provenance": {
            "analysis_version": ANALYSIS_VERSION, "database": str(database), "executed_at": executed_at,
            "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_code_sha256": {
                str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (ROOT / "src/cross_asset_market_intelligence/dashboard/sofr_read_model.py",
                             ROOT / "src/cross_asset_market_intelligence/data/sofr_processing.py",
                             ROOT / "src/cross_asset_market_intelligence/lineage.py")
            },
            "selected_snapshot_sha256": hashlib.sha256(snapshot_encoded).hexdigest(),
            "selection": "Existing sofr_history: r if stored, otherwise original; approved processed version with exact raw match.",
            "temporal_scope": "Retrospective saved-vintage snapshot; chronological prior-only baselines, not historical availability-time replay.",
        },
        "dataset": {
            "selected_observations": len(levels), "valid_changes": len(changes),
            "first_date": levels[0]["date"], "last_date": levels[-1]["date"],
            "raw_count": len(raw), "processed_count": processed_count,
            "raw_vintages": dict(Counter(r[6] for r in raw)),
            "raw_duplicate_identity_count": raw_duplicate_identity_count,
            "raw_duplicate_date_count": len(raw) - len({r[2] for r in raw}),
            "selected_duplicate_date_count": len(levels) - len({r["date"] for r in levels}),
            "null_raw_values": sum(r[3] is None for r in raw),
            "publication_timestamps_known": sum(r[5] is not None for r in raw),
            "retrieval_first": min(r["retrieval_timestamp"] for r in levels),
            "retrieval_last": max(r["retrieval_timestamp"] for r in levels),
            "integer_bp_changes": all(v == int(v) for v in values),
            "calendar_gap_frequencies": dict(Counter(r["calendar_gap_days"] for r in changes)),
            "database_table_counts": table_counts,
            "lineage_mismatch_count": 0, "processed_identity_mismatch_count": 0,
        },
        "signed_distribution_bp": summarize(values),
        "absolute_distribution_bp": summarize([abs(v) for v in values]),
        "frequency_bp": [{"change_bp": v, "count": count, "percent": 100*count/len(values)} for v, count in sorted(frequency.items())],
        "absolute_at_least_10bp_count": sum(abs(v) >= 10 for v in values),
        "monthly": monthly, "yearly": yearly, "sofr_level_bands": level_bands,
        "windows": summaries, "window_diagnostics": window_details,
        "window_comparison": window_comparison, "event_comparison": event_comparison,
        "disagreements": disagreement_summary(scores),
        "calendar_boundary_dates": boundaries, "calendar_groups": calendar_groups,
        "calendar_score_groups": calendar_score_groups,
        "latest": [r for r in scores if r["date"] == levels[-1]["date"]],
        "top20": tops,
    }
    (output / "results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (output / "selected_observations.json").write_text(json.dumps(levels, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "rolling_scores.json").write_text(json.dumps(scores, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    write_csv(output / "selected_observations.csv", levels)
    write_csv(output / "expanded_validated_sofr_history.csv", levels)
    write_csv(output / "changes.csv", changes)
    write_csv(output / "rolling_scores.csv", scores)
    write_csv(output / "window_comparison.csv", window_comparison)
    write_csv(output / "event_comparison.csv", event_comparison)
    write_csv(output / "calendar_comparison.csv", calendar_score_groups)
    print(json.dumps({"output": str(output), "dataset": summary["dataset"], "distribution": summary["signed_distribution_bp"], "windows": summary["windows"], "latest": summary["latest"]}, indent=2))


if __name__ == "__main__":
    main()
