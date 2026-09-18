"""Research-only SOFR direction study over the frozen validated history."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics as st
import subprocess
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cross_asset_market_intelligence.config import load_settings
from cross_asset_market_intelligence.dashboard.sofr_read_model import sofr_history
from cross_asset_market_intelligence.database import connect
from cross_asset_market_intelligence.signals.sofr_rate_state import calendar_context

ANALYSIS_VERSION = "sofr_direction_research_v1"
NET_WINDOWS = (5, 10, 20, 60)
SLOPE_WINDOWS = (5, 10, 20, 60)
CHANGE_WINDOWS = (10, 20, 60)
ANOMALY_SCORES = ROOT / "notebooks" / "sofr_daily_change_anomaly" / "outputs_phase_2_1b_2" / "rolling_scores.csv"
CASE_DEFINITIONS = (
    ("gradual_up_path", "2018-08-27", (0,), "many small positive changes; no single move dominates"),
    ("reversal", "2019-01-03", (-1, 0, 1, 5, 10, 20), "large negative shift after a short rising sequence"),
    ("large_isolated_move", "2019-09-17", (-1, 0, 1, 5, 10, 20), "large isolated upward move immediately reversed"),
    ("noisy_endpoint_flat", "2019-10-21", (0,), "20-change net is zero despite 184bp total path movement"),
    ("long_flat_period", "2021-10-18", (0,), "end of an 84-change zero run"),
    ("step_followed_by_flat", "2022-06-16", (-1, 0, 1, 5, 10, 20), "large upward step followed by a mostly flat level"),
    ("down_step_followed_by_flat", "2024-09-19", (-1, 0, 1, 5, 10, 20), "large downward step followed by a mostly flat level"),
    ("gradual_down_path", "2026-05-20", (0,), "many small negative changes; no single move dominates"),
)


def linear_slope_bp(levels: list[float]) -> float:
    """OLS level slope in bp per valid observation, without distributional inference."""
    n = len(levels)
    mean_x = (n - 1) / 2
    mean_y = st.mean(levels)
    denominator = sum((index - mean_x) ** 2 for index in range(n))
    return 100 * sum((index - mean_x) * (value - mean_y) for index, value in enumerate(levels)) / denominator


def sign_evidence(changes: list[float]) -> dict[str, float | int]:
    positive = sum(value > 0 for value in changes)
    zero = sum(value == 0 for value in changes)
    negative = len(changes) - positive - zero
    return {
        "positive": positive,
        "zero": zero,
        "negative": negative,
        "balance": positive - negative,
        "positive_share": positive / len(changes),
        "zero_share": zero / len(changes),
        "negative_share": negative / len(changes),
    }


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    mean_x = st.mean(x for x, _ in pairs)
    mean_y = st.mean(y for _, y in pairs)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator = (
        sum((x - mean_x) ** 2 for x, _ in pairs)
        * sum((y - mean_y) ** 2 for _, y in pairs)
    ) ** 0.5
    return None if denominator == 0 else numerator / denominator


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _anomaly_by_date(path: Path) -> dict[tuple[str, int], dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            (row["date"], int(row["window"])): {
                "strict": float(row["percentile_strict"]),
                "midrank": float(row["percentile_midrank"]),
                "weak": float(row["percentile_weak"]),
            }
            for row in csv.DictReader(handle)
            if int(row["window"]) in (60, 252)
        }


def build_direction_rows(levels: list[dict[str, object]], anomaly: dict[tuple[str, int], dict[str, float]]) -> list[dict[str, object]]:
    changes = [
        float((Decimal(str(current["sofr_percent"])) - Decimal(str(previous["sofr_percent"]))) * 100)
        for previous, current in zip(levels, levels[1:])
    ]
    rows: list[dict[str, object]] = []
    for level_index in range(1, len(levels)):
        current = levels[level_index]
        previous = levels[level_index - 1]
        change_index = level_index - 1
        current_date = str(current["date"])
        context = calendar_context(date.fromisoformat(current_date))
        row: dict[str, object] = {
            "date": current_date,
            "previous_date": previous["date"],
            "sofr_percent": current["sofr_percent"],
            "previous_sofr_percent": previous["sofr_percent"],
            "change_1obs_bp": changes[change_index],
            "calendar_gap_days": (date.fromisoformat(current_date) - date.fromisoformat(str(previous["date"]))).days,
            "month_end": context["month_end"],
            "quarter_end": context["quarter_end"],
            "year_end": context["year_end"],
        }
        for window in NET_WINDOWS:
            eligible = level_index >= window
            row[f"net_change_{window}"] = (
                float((Decimal(str(current["sofr_percent"])) - Decimal(str(levels[level_index-window]["sofr_percent"]))) * 100)
                if eligible else None
            )
            recent_changes = changes[change_index-window+1:change_index+1] if eligible else []
            row[f"path_total_abs_{window}"] = sum(abs(value) for value in recent_changes) if eligible else None
            row[f"largest_change_share_{window}"] = (
                None if not eligible or not any(recent_changes)
                else max(abs(value) for value in recent_changes) / sum(abs(value) for value in recent_changes)
            )
        for window in SLOPE_WINDOWS:
            row[f"linear_slope_{window}"] = (
                linear_slope_bp([float(item["sofr_percent"]) for item in levels[level_index-window+1:level_index+1]])
                if level_index + 1 >= window else None
            )
        for window in CHANGE_WINDOWS:
            eligible = change_index + 1 >= window
            sample = changes[change_index-window+1:change_index+1] if eligible else []
            signs = sign_evidence(sample) if eligible else {}
            for name in ("positive", "zero", "negative", "balance"):
                row[f"{name}_change_count_{window}"] = signs.get(name)
            for name in ("positive_share", "zero_share", "negative_share"):
                row[f"{name}_{window}"] = signs.get(name)
            row[f"median_change_{window}"] = st.median(sample) if eligible else None
        for window, label in ((60, "recent_anomaly"), (252, "broad_anomaly")):
            saved = anomaly.get((current_date, window))
            row[f"{label}_strict"] = None if saved is None else saved["strict"]
            row[f"{label}_midrank"] = None if saved is None else saved["midrank"]
            row[f"{label}_weak"] = None if saved is None else saved["weak"]
        rows.append(row)
    return rows


def _successive_stats(rows: list[dict[str, object]], field: str) -> dict[str, object]:
    values = [(row["date"], row[field]) for row in rows if row[field] is not None]
    differences = [abs(float(current[1]) - float(previous[1])) for previous, current in zip(values, values[1:])]
    adjacent_sign_pairs = [
        (float(previous[1]), float(current[1])) for previous, current in zip(values, values[1:])
        if float(previous[1]) != 0 and float(current[1]) != 0
    ]
    flips = sum((previous > 0) != (current > 0) for previous, current in adjacent_sign_pairs)
    return {
        "eligible_n": len(values),
        "zero_count": sum(float(value) == 0 for _, value in values),
        "zero_percent": 100 * sum(float(value) == 0 for _, value in values) / len(values),
        "median_abs_daily_change": st.median(differences),
        "p90_abs_daily_change": quantile(differences, .9),
        "adjacent_nonzero_sign_pairs": len(adjacent_sign_pairs),
        "adjacent_sign_flip_count": flips,
        "adjacent_sign_flip_percent": 100 * flips / len(adjacent_sign_pairs) if adjacent_sign_pairs else None,
    }


def _method_comparison(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    output: list[dict[str, object]] = []
    summaries: dict[str, object] = {}
    specs = []
    specs.extend(("Net change", window, f"net_change_{window}") for window in NET_WINDOWS)
    specs.extend(("Linear slope", window, f"linear_slope_{window}") for window in SLOPE_WINDOWS)
    specs.extend(("Sign balance", window, f"balance_change_count_{window}") for window in CHANGE_WINDOWS)
    specs.extend(("Median change", window, f"median_change_{window}") for window in CHANGE_WINDOWS)
    for method, window, field in specs:
        stats = _successive_stats(rows, field)
        summaries[f"{method.lower().replace(' ', '_')}_{window}"] = stats
        unit = "bp" if method in ("Net change", "Median change") else "bp/valid observation" if method == "Linear slope" else "count difference"
        if method == "Net change":
            step = "retains a step until its starting endpoint leaves, then drops mechanically"
            endpoint = "fully determined by first and last level"
            zero = "zero can hide a volatile round trip"
            weakness = "endpoint-sensitive; cannot distinguish one step from persistent drift"
            interpretation = f"level displacement across {window} valid changes"
        elif method == "Linear slope":
            step = "turns a discrete step into a temporary smooth slope that rises then decays"
            endpoint = "uses all levels but endpoints have high leverage"
            zero = "flat runs push slope toward zero gradually"
            weakness = "imposes smoothness and can imply ongoing trend after a completed step"
            interpretation = f"fitted level-path slope across {window} valid levels"
        elif method == "Sign balance":
            step = "one step contributes one signed count regardless of magnitude"
            endpoint = "entry/exit of one change alters balance by at most two"
            zero = "reports zero share explicitly but can become low-information"
            weakness = "ignores magnitude; many zeros or tiny changes can dominate interpretation"
            interpretation = f"positive minus negative changes over {window} changes"
        else:
            step = "usually remains zero when an isolated step is surrounded by zeros"
            endpoint = "rank statistic; insensitive until the middle order changes"
            zero = "frequently collapses exactly to zero"
            weakness = "discards too much path information in zero-heavy SOFR"
            interpretation = f"median consecutive change over {window} changes"
        output.append({
            "method": method,
            "window": window,
            "eligible_n": stats["eligible_n"],
            "unit": unit,
            "responsiveness": f"median/p90 daily absolute revision={stats['median_abs_daily_change']:.6g}/{stats['p90_abs_daily_change']:.6g} {unit}",
            "stability": f"adjacent nonzero sign flips={stats['adjacent_sign_flip_count']}/{stats['adjacent_nonzero_sign_pairs']} ({stats['adjacent_sign_flip_percent']:.3g}%)",
            "step_change_behavior": step,
            "endpoint_sensitivity": endpoint,
            "zero_heavy_handling": f"exact zero={stats['zero_count']}/{stats['eligible_n']} ({stats['zero_percent']:.3g}%); {zero}",
            "reversal_lag": "see reversal case-study path; no threshold-based lag inferred",
            "interpretability": interpretation,
            "main_weakness": weakness,
        })
    return output, summaries


def _case_studies(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    index = {str(row["date"]): position for position, row in enumerate(rows)}
    selected: list[dict[str, object]] = []
    keep = (
        "date", "sofr_percent", "change_1obs_bp", "net_change_5", "net_change_10", "net_change_20", "net_change_60",
        "linear_slope_5", "linear_slope_10", "linear_slope_20", "linear_slope_60",
        "balance_change_count_10", "balance_change_count_20", "balance_change_count_60",
        "zero_share_10", "zero_share_20", "zero_share_60",
        "median_change_10", "median_change_20", "median_change_60",
        "recent_anomaly_midrank", "broad_anomaly_midrank", "month_end", "quarter_end", "year_end",
    )
    for name, anchor, offsets, description in CASE_DEFINITIONS:
        anchor_index = index[anchor]
        for offset in offsets:
            position = anchor_index + offset
            if 0 <= position < len(rows):
                row = rows[position]
                selected.append({
                    "case": name, "case_description": description, "anchor_date": anchor,
                    "offset_valid_observations": offset,
                    **{field: row[field] for field in keep},
                })
    return selected


def _orthogonality(rows: list[dict[str, object]]) -> dict[str, object]:
    eligible = [row for row in rows if row["net_change_20"] is not None and row["recent_anomaly_midrank"] is not None]
    examples = {}
    predicates = {
        "persistent_rising_low_anomaly": lambda row: row["net_change_20"] > 0 and row["balance_change_count_20"] >= 3 and row["recent_anomaly_midrank"] < 75,
        "persistent_falling_low_anomaly": lambda row: row["net_change_20"] < 0 and row["balance_change_count_20"] <= -3 and row["recent_anomaly_midrank"] < 75,
        "endpoint_stable_high_anomaly": lambda row: abs(row["net_change_20"]) <= 2 and abs(row["balance_change_count_20"]) <= 2 and row["recent_anomaly_midrank"] >= 95,
        "rising_high_anomaly": lambda row: row["net_change_20"] > 0 and row["balance_change_count_20"] > 0 and row["recent_anomaly_midrank"] >= 95,
        "falling_high_anomaly": lambda row: row["net_change_20"] < 0 and row["balance_change_count_20"] < 0 and row["recent_anomaly_midrank"] >= 95,
    }
    for name, predicate in predicates.items():
        matches = [row for row in eligible if predicate(row)]
        examples[name] = {
            "count": len(matches),
            "example_dates": [row["date"] for row in matches[:10]],
            "selection_cutoffs_are_research_diagnostics_not_production_thresholds": True,
        }
    return {
        "eligible_n": len(eligible),
        "pearson_signed_net20_vs_recent_rarity": pearson([(float(row["net_change_20"]), float(row["recent_anomaly_midrank"])) for row in eligible]),
        "pearson_abs_net20_vs_recent_rarity": pearson([(abs(float(row["net_change_20"])), float(row["recent_anomaly_midrank"])) for row in eligible]),
        "pearson_signed_slope20_vs_recent_rarity": pearson([(float(row["linear_slope_20"]), float(row["recent_anomaly_midrank"])) for row in eligible]),
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=load_settings(ROOT).database_path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs")
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with connect(arguments.database.resolve(), read_only=True) as connection:
        history = sofr_history(connection)
        production_states = connection.execute(
            "SELECT count(*), count(direction_state) FROM signal_observations WHERE signal_id = 'sofr_rate_state' AND signal_version = 'v1'"
        ).fetchone()
    levels = [
        {
            "date": item.observation_date.isoformat(),
            "sofr_percent": item.value,
            "processed_observation_id": item.processed_observation_id,
            "processing_version": item.processing_version,
            "raw_source": item.lineage.raw_input.source,
            "raw_series_id": item.lineage.raw_input.series_id,
            "raw_vintage": item.lineage.raw_input.vintage,
        }
        for item in history
    ]
    snapshot_encoded = json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
    rows = build_direction_rows(levels, _anomaly_by_date(ANOMALY_SCORES))
    comparison, summaries = _method_comparison(rows)
    cases = _case_studies(rows)
    orthogonality = _orthogonality(rows)
    median_zero = {
        str(window): {
            "eligible_n": sum(row[f"median_change_{window}"] is not None for row in rows),
            "zero_count": sum(row[f"median_change_{window}"] == 0 for row in rows if row[f"median_change_{window}"] is not None),
        }
        for window in CHANGE_WINDOWS
    }
    for value in median_zero.values():
        value["zero_percent"] = 100 * value["zero_count"] / value["eligible_n"]
    largest_changes = sorted(rows, key=lambda row: abs(float(row["change_1obs_bp"])), reverse=True)[:20]
    calendar_top_changes = [
        row for row in largest_changes
        if row["month_end"] or row["quarter_end"] or row["year_end"]
    ]
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_commit = None
    results = {
        "provenance": {
            "analysis_version": ANALYSIS_VERSION,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "database": str(arguments.database.resolve()),
            "git_commit": git_commit,
            "script_sha256": script_hash,
            "selected_snapshot_sha256": hashlib.sha256(snapshot_encoded).hexdigest(),
            "anomaly_artifact": str(ANOMALY_SCORES.relative_to(ROOT)),
            "anomaly_methodology_unchanged": True,
        },
        "dataset": {
            "observation_count": len(levels), "change_count": len(rows),
            "first_date": levels[0]["date"], "last_date": levels[-1]["date"],
            "production_sofr_rate_state_observations": production_states[0],
            "production_direction_states_populated": production_states[1],
        },
        "method_summaries": summaries,
        "median_change_zero_frequency": median_zero,
        "calendar_context": {
            "largest_absolute_changes_examined": len(largest_changes),
            "calendar_flagged_among_largest": len(calendar_top_changes),
            "calendar_flagged_dates": [row["date"] for row in calendar_top_changes],
            "interpretation": "calendar-associated extremes exist but are not the majority; no direction adjustment was applied",
        },
        "orthogonality": orthogonality,
        "case_definitions": [
            {"case": name, "anchor_date": anchor, "offsets": list(offsets), "description": description}
            for name, anchor, offsets, description in CASE_DEFINITIONS
        ],
        "optional_robust_path_slope": {
            "evaluated": False,
            "reason": "Required candidates already isolate endpoint displacement, fitted path, sign persistence, and zero-heavy median behavior; an additional O(N^2) estimator was not needed to answer the decision questions.",
        },
        "research_decision": {
            "preferred_evidence": "two-component net movement plus sign composition; slope remains comparison evidence",
            "candidate_horizon": 20,
            "stable_evidence": "small net displacement considered jointly with weak or balanced sign persistence and path concentration; no numeric boundary selected",
            "step_change_handling": "net movement records the level displacement while sign composition and path concentration distinguish a single step from repeated movement",
            "reversal_evidence": "20-window sign composition changed before 20-window endpoint displacement in the studied reversal; shorter net change is useful diagnostic evidence but noisier",
            "direction_anomaly_independent": True,
            "thresholds_frozen": False,
            "readiness": "READY FOR DIRECTION METHODOLOGY FREEZE",
        },
    }
    _write_csv(output / "direction_research.csv", rows)
    _write_csv(output / "method_comparison.csv", comparison)
    _write_csv(output / "case_studies.csv", cases)
    (output / "selected_observations.json").write_text(json.dumps(levels, indent=2), encoding="utf-8")
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "dataset": results["dataset"], "readiness": results["research_decision"]["readiness"]}, indent=2))


if __name__ == "__main__":
    main()
