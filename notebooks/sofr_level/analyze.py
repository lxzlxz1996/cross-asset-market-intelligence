"""Research-only SOFR Level study over the frozen validated history."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics as st
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cross_asset_market_intelligence.config import load_settings
from cross_asset_market_intelligence.dashboard.sofr_read_model import sofr_history
from cross_asset_market_intelligence.database import connect

ANALYSIS_VERSION = "sofr_level_research_v1"
PERCENTILE_WINDOWS = (60, 120, 252, 504)
DISTANCE_WINDOWS = (20, 60, 120, 252)
Z_WINDOWS = (60, 120, 252, 504)
DIRECTION_RESEARCH = ROOT / "notebooks" / "sofr_direction" / "outputs" / "direction_research.csv"
CASE_DEFINITIONS = (
    ("near_zero_plateau", "2021-10-18", (0,), "long observational plateau near 0.05%"),
    ("upward_step", "2022-06-16", (-1, 0, 1, 5, 10, 20, 60), "discrete upward level shift"),
    ("sustained_rising_environment", "2023-07-27", (0,), "end portion of a sustained rising level transition"),
    ("high_plateau", "2024-06-14", (0,), "historically high level with flat recent direction"),
    ("historical_high_recent_flat", "2024-08-15", (0,), "high broad position but little 20-change displacement"),
    ("downward_step", "2024-09-19", (-1, 0, 1, 5, 10, 20, 60), "discrete downward level shift"),
    ("falling_environment", "2026-05-20", (0,), "sustained falling recent path"),
)
ENVIRONMENTS = (
    ("near_zero_level_environment", "2020-04-01", "2022-03-15"),
    ("rising_level_transition", "2022-03-16", "2023-07-27"),
    ("high_level_plateau", "2023-07-28", "2024-09-18"),
    ("falling_level_transition", "2024-09-19", "2026-09-16"),
)


def percentile_evidence(current: Decimal, prior: list[Decimal]) -> dict[str, float | int]:
    less = sum(value < current for value in prior)
    equal = sum(value == current for value in prior)
    greater = len(prior) - less - equal
    count = len(prior)
    return {
        "less": less,
        "equal": equal,
        "greater": greater,
        "strict": 100 * less / count,
        "midrank": 100 * (less + .5 * equal) / count,
        "weak": 100 * (less + equal) / count,
    }


def decimal_median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def level_z(current: Decimal, prior: list[Decimal]) -> tuple[float | None, str]:
    mean = sum(prior, Decimal("0")) / Decimal(len(prior))
    variance = sum(((value - mean) ** 2 for value in prior), Decimal("0")) / Decimal(len(prior) - 1)
    scale = variance.sqrt()
    if scale == 0:
        return None, "zero_scale"
    return float((current - mean) / scale), "available"


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    mean_x = st.mean(x for x, _ in pairs)
    mean_y = st.mean(y for _, y in pairs)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator = (
        sum((x - mean_x) ** 2 for x, _ in pairs)
        * sum((y - mean_y) ** 2 for _, y in pairs)
    ) ** .5
    return None if denominator == 0 else numerator / denominator


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _direction_by_date(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["date"]: row for row in csv.DictReader(handle)}


def build_level_rows(
    levels: list[dict[str, object]], direction_by_date: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    values = [Decimal(str(item["sofr_percent"])) for item in levels]
    rows: list[dict[str, object]] = []
    for index, item in enumerate(levels):
        current = values[index]
        prior_all = values[:index]
        joined = direction_by_date.get(str(item["date"]), {})
        row: dict[str, object] = {
            "date": item["date"],
            "processed_observation_id": item["processed_observation_id"],
            "current_sofr_level": float(current),
            "change_1obs_bp": None if index == 0 else float((current - values[index - 1]) * 100),
        }
        if prior_all:
            full = percentile_evidence(current, prior_all)
            row.update({
                "full_history_prior_count": len(prior_all),
                "full_history_percentile": full["midrank"],
                "full_history_strict": full["strict"],
                "full_history_midrank": full["midrank"],
                "full_history_weak": full["weak"],
                "full_history_less_count": full["less"],
                "full_history_equal_count": full["equal"],
                "full_history_greater_count": full["greater"],
            })
        else:
            row.update({field: None for field in (
                "full_history_prior_count", "full_history_percentile", "full_history_strict",
                "full_history_midrank", "full_history_weak", "full_history_less_count",
                "full_history_equal_count", "full_history_greater_count",
            )})
        for window in PERCENTILE_WINDOWS:
            if index < window:
                evidence = None
            else:
                evidence = percentile_evidence(current, values[index-window:index])
            row[f"level_percentile_{window}"] = None if evidence is None else evidence["midrank"]
            row[f"level_strict_{window}"] = None if evidence is None else evidence["strict"]
            row[f"level_midrank_{window}"] = None if evidence is None else evidence["midrank"]
            row[f"level_weak_{window}"] = None if evidence is None else evidence["weak"]
            row[f"level_less_count_{window}"] = None if evidence is None else evidence["less"]
            row[f"level_equal_count_{window}"] = None if evidence is None else evidence["equal"]
            row[f"level_greater_count_{window}"] = None if evidence is None else evidence["greater"]
        for window in DISTANCE_WINDOWS:
            if index < window:
                row[f"distance_mean_{window}_bp"] = None
                row[f"distance_median_{window}_bp"] = None
            else:
                prior = values[index-window:index]
                mean = sum(prior, Decimal("0")) / Decimal(window)
                median = decimal_median(prior)
                row[f"distance_mean_{window}_bp"] = float((current - mean) * 100)
                row[f"distance_median_{window}_bp"] = float((current - median) * 100)
        for window in Z_WINDOWS:
            if index < window:
                row[f"level_z_{window}"] = None
                row[f"level_z_status_{window}"] = "insufficient_history"
            else:
                value, status = level_z(current, values[index-window:index])
                row[f"level_z_{window}"] = value
                row[f"level_z_status_{window}"] = status
        for source, target in (
            ("net_change_20", "direction_net_change_20_bp"),
            ("positive_change_count_20", "direction_positive_count_20"),
            ("zero_change_count_20", "direction_zero_count_20"),
            ("negative_change_count_20", "direction_negative_count_20"),
            ("linear_slope_20", "direction_slope_20"),
            ("recent_anomaly_midrank", "recent_anomaly_midrank"),
            ("broad_anomaly_midrank", "broad_anomaly_midrank"),
        ):
            value = joined.get(source, "")
            row[target] = None if value == "" else float(value)
        rows.append(row)
    return rows


def _metric_stats(rows: list[dict[str, object]], field: str) -> dict[str, object]:
    eligible = [(index, float(row[field])) for index, row in enumerate(rows) if row[field] is not None]
    revisions = [abs(current[1] - previous[1]) for previous, current in zip(eligible, eligible[1:])]
    flat_revisions = [
        abs(float(rows[index][field]) - float(rows[index - 1][field]))
        for index, _ in eligible
        if index > 0 and rows[index - 1][field] is not None and rows[index]["change_1obs_bp"] == 0
    ]
    direction_pairs = [
        (float(row[field]), float(row["direction_net_change_20_bp"]))
        for row in rows if row[field] is not None and row["direction_net_change_20_bp"] is not None
    ]
    anomaly_pairs = [
        (float(row[field]), float(row["recent_anomaly_midrank"]))
        for row in rows if row[field] is not None and row["recent_anomaly_midrank"] is not None
    ]
    level_pairs = [
        (float(row[field]), float(row["current_sofr_level"]))
        for row in rows if row[field] is not None
    ]
    return {
        "eligible_n": len(eligible),
        "median_abs_daily_revision": st.median(revisions) if revisions else None,
        "p90_abs_daily_revision": quantile(revisions, .9),
        "flat_level_comparisons": len(flat_revisions),
        "flat_level_metric_changed_count": sum(value != 0 for value in flat_revisions),
        "flat_level_metric_changed_percent": (
            100 * sum(value != 0 for value in flat_revisions) / len(flat_revisions)
            if flat_revisions else None
        ),
        "flat_level_median_abs_revision": st.median(flat_revisions) if flat_revisions else None,
        "correlation_with_current_level": pearson(level_pairs),
        "correlation_with_direction_net20": pearson(direction_pairs),
        "correlation_with_recent_anomaly_rarity": pearson(anomaly_pairs),
    }


def _percentile_summary(rows: list[dict[str, object]], prefix: str) -> dict[str, object]:
    if prefix == "full_history":
        midrank_field, strict_field, weak_field = (
            "full_history_midrank", "full_history_strict", "full_history_weak"
        )
    else:
        window = prefix.removeprefix("level_")
        midrank_field, strict_field, weak_field = (
            f"level_midrank_{window}", f"level_strict_{window}", f"level_weak_{window}"
        )
    eligible = [row for row in rows if row[midrank_field] is not None]
    brackets = [float(row[weak_field]) - float(row[strict_field]) for row in eligible]
    midranks = [float(row[midrank_field]) for row in eligible]
    return {
        "eligible_n": len(eligible),
        "midrank_exact_0_count": sum(value == 0 for value in midranks),
        "midrank_exact_100_count": sum(value == 100 for value in midranks),
        "midrank_saturation_percent": 100 * sum(value in (0, 100) for value in midranks) / len(midranks),
        "mean_tie_bracket_points": st.mean(brackets),
        "median_tie_bracket_points": st.median(brackets),
        "p90_tie_bracket_points": quantile(brackets, .9),
        "max_tie_bracket_points": max(brackets),
    }


def _mad_zero_summary(values: list[Decimal], window: int) -> dict[str, object]:
    eligible = zero = 0
    for index in range(window, len(values)):
        prior = values[index-window:index]
        median = decimal_median(prior)
        mad = decimal_median([abs(value - median) for value in prior])
        eligible += 1
        zero += mad == 0
    return {"eligible_n": eligible, "mad_zero_count": zero, "mad_zero_percent": 100 * zero / eligible}


def _method_comparison(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    specs: list[tuple[str, str, str]] = [("Full-history percentile", "expanding", "full_history_midrank")]
    specs.extend(("Rolling percentile", str(window), f"level_midrank_{window}") for window in PERCENTILE_WINDOWS)
    specs.extend(("Distance from mean", str(window), f"distance_mean_{window}_bp") for window in DISTANCE_WINDOWS)
    specs.extend(("Distance from median", str(window), f"distance_median_{window}_bp") for window in DISTANCE_WINDOWS)
    specs.extend(("Level Z", str(window), f"level_z_{window}") for window in Z_WINDOWS)
    output: list[dict[str, object]] = []
    summaries: dict[str, object] = {}
    for method, window, field in specs:
        stats = _metric_stats(rows, field)
        key = f"{method.lower().replace(' ', '_').replace('-', '_')}_{window}"
        summaries[key] = stats
        if "percentile" in method.lower():
            prefix = "full_history" if window == "expanding" else f"level_{window}"
            tie = _percentile_summary(rows, prefix)
            tie_text = (
                f"midrank 0/100={tie['midrank_saturation_percent']:.3g}%; "
                f"mean strict-weak bracket={tie['mean_tie_bracket_points']:.3g} points"
            )
            plateau = f"changed on {stats['flat_level_metric_changed_percent']:.3g}% of unchanged-level comparisons"
            step = "jumps toward an edge after a new level, then adapts as the prior-only baseline rolls"
            interpretation = "0-100 empirical rank with explicit tie bracket"
            weakness = "reference-frame and policy-environment dependent; ties can create wide brackets"
        elif method.startswith("Distance"):
            tie_text = "not tie-ranked; exact zero is directly interpretable"
            plateau = f"median revision on unchanged levels={stats['flat_level_median_abs_revision']:.3g}bp"
            step = "reports the raw bp gap, then decays as the baseline catches up"
            interpretation = "current level minus prior-only center, in bp"
            weakness = "transition-sensitive and horizon-dependent; not a stress measure"
        else:
            zero_scale = sum(row[f"level_z_status_{window}"] == "zero_scale" for row in rows)
            tie_text = f"zero-scale nulls={zero_scale}"
            plateau = f"median revision on unchanged levels={stats['flat_level_median_abs_revision']:.3g} z"
            step = "can become extreme after a step and decays mechanically as scale/mean adapt"
            interpretation = "signed standard deviations from prior-only mean; not probability"
            weakness = "zero/low denominator and transition amplification obscure bp magnitude"
        output.append({
            "method": method,
            "window": window,
            "eligible_n": stats["eligible_n"],
            "responsiveness": (
                f"median/p90 absolute daily revision="
                f"{stats['median_abs_daily_revision']:.6g}/{stats['p90_abs_daily_revision']:.6g}"
            ),
            "plateau_behavior": plateau,
            "regime_contamination": f"correlation with current level={stats['correlation_with_current_level']:.4f}",
            "tie_saturation_issue": tie_text,
            "step_change_behavior": step,
            "independence_from_direction": f"correlation with net20={stats['correlation_with_direction_net20']:.4f}",
            "interpretability": interpretation,
            "main_weakness": weakness,
        })
    return output, summaries


def _case_studies(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    index = {str(row["date"]): position for position, row in enumerate(rows)}
    keep = (
        "date", "current_sofr_level", "change_1obs_bp", "full_history_midrank",
        "level_midrank_60", "level_midrank_120", "level_midrank_252", "level_midrank_504",
        "distance_mean_20_bp", "distance_mean_60_bp", "distance_mean_120_bp", "distance_mean_252_bp",
        "distance_median_20_bp", "distance_median_60_bp", "distance_median_120_bp", "distance_median_252_bp",
        "level_z_60", "level_z_120", "level_z_252", "level_z_504",
        "direction_net_change_20_bp", "direction_positive_count_20", "direction_zero_count_20",
        "direction_negative_count_20", "recent_anomaly_midrank", "broad_anomaly_midrank",
    )
    selected: list[dict[str, object]] = []
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


def _environment_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for name, start, end in ENVIRONMENTS:
        sample = [row for row in rows if start <= str(row["date"]) <= end]
        levels = [float(row["current_sofr_level"]) for row in sample]
        changes = [float(row["change_1obs_bp"]) for row in sample if row["change_1obs_bp"] is not None]
        output.append({
            "environment": name, "start_date": start, "end_date": end,
            "observation_count": len(sample), "first_level": levels[0], "last_level": levels[-1],
            "minimum_level": min(levels), "maximum_level": max(levels),
            "endpoint_change_bp": 100 * (levels[-1] - levels[0]),
            "zero_change_percent": 100 * sum(value == 0 for value in changes) / len(changes),
            "median_full_history_midrank": st.median(
                float(row["full_history_midrank"]) for row in sample
                if row["full_history_midrank"] is not None
            ),
            "median_level_midrank_252": st.median(
                float(row["level_midrank_252"]) for row in sample
                if row["level_midrank_252"] is not None
            ),
            "median_distance_median_60_bp": st.median(
                float(row["distance_median_60_bp"]) for row in sample
                if row["distance_median_60_bp"] is not None
            ),
            "median_level_z_252": st.median(
                float(row["level_z_252"]) for row in sample if row["level_z_252"] is not None
            ),
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=load_settings(ROOT).database_path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs")
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with connect(arguments.database.resolve(), read_only=True) as connection:
        history = sofr_history(connection)
        production = connection.execute(
            "SELECT signal_version, count(*), count(level_state) FROM signal_observations "
            "WHERE signal_id='sofr_rate_state' GROUP BY signal_version ORDER BY signal_version"
        ).fetchall()
    levels = [
        {
            "date": item.observation_date.isoformat(), "sofr_percent": item.value,
            "processed_observation_id": item.processed_observation_id,
            "processing_version": item.processing_version,
            "raw_source": item.lineage.raw_input.source, "raw_series_id": item.lineage.raw_input.series_id,
            "raw_vintage": item.lineage.raw_input.vintage,
        }
        for item in history
    ]
    encoded = json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
    rows = build_level_rows(levels, _direction_by_date(DIRECTION_RESEARCH))
    comparison, method_summaries = _method_comparison(rows)
    cases = _case_studies(rows)
    values = [Decimal(str(item["sofr_percent"])) for item in levels]
    percentile_summaries = {"full_history": _percentile_summary(rows, "full_history")}
    percentile_summaries.update({str(window): _percentile_summary(rows, f"level_{window}") for window in PERCENTILE_WINDOWS})
    z_summaries = {
        str(window): {
            "eligible_n": sum(row[f"level_z_status_{window}"] != "insufficient_history" for row in rows),
            "zero_scale_count": sum(row[f"level_z_status_{window}"] == "zero_scale" for row in rows),
            "available_count": sum(row[f"level_z_status_{window}"] == "available" for row in rows),
            "abs_z_at_least_2_count": sum(
                row[f"level_z_{window}"] is not None and abs(float(row[f"level_z_{window}"])) >= 2
                for row in rows
            ),
        }
        for window in Z_WINDOWS
    }
    for summary in z_summaries.values():
        summary["zero_scale_percent"] = 100 * summary["zero_scale_count"] / summary["eligible_n"]
        summary["abs_z_at_least_2_percent_of_available"] = 100 * summary["abs_z_at_least_2_count"] / summary["available_count"]
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_commit = None
    results = {
        "provenance": {
            "analysis_version": ANALYSIS_VERSION,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "database": str(arguments.database.resolve()), "git_commit": git_commit,
            "script_sha256": script_hash,
            "selected_snapshot_sha256": hashlib.sha256(encoded).hexdigest(),
            "direction_artifact": str(DIRECTION_RESEARCH.relative_to(ROOT)),
            "production_versions_unchanged": True,
        },
        "dataset": {
            "observation_count": len(levels), "first_date": levels[0]["date"],
            "last_date": levels[-1]["date"],
            "production_signal_level_state_counts": [
                {"signal_version": version, "observation_count": count, "level_state_populated": populated}
                for version, count, populated in production
            ],
        },
        "percentile_summaries": percentile_summaries,
        "method_summaries": method_summaries,
        "z_summaries": z_summaries,
        "mad_zero_frequency": {str(window): _mad_zero_summary(values, window) for window in Z_WINDOWS},
        "observed_level_environments": _environment_summaries(rows),
        "case_definitions": [
            {"case": name, "anchor_date": anchor, "offsets": list(offsets), "description": description}
            for name, anchor, offsets, description in CASE_DEFINITIONS
        ],
        "research_decision": {
            "status": "READY FOR LEVEL METHODOLOGY FREEZE",
            "preferred_design": "current level plus broad prior-only full-history percentile tie audit plus recent prior-60 median distance",
            "current_level_role": "mandatory raw evidence",
            "broad_context": {
                "method": "expanding prior-only empirical level percentile",
                "persist_if_frozen": ["less_count", "equal_count", "greater_count", "strict", "midrank", "weak"],
                "interpretation": "position within the available historical SOFR sample, not stress or policy state",
            },
            "recent_context": {
                "method": "current level minus median of exactly 60 prior valid levels",
                "unit": "basis_points",
                "interpretation": "distance from the recent observational level environment",
            },
            "rolling_percentiles_role": "research-only diagnostics; shorter windows adapt quickly and have wide tie brackets",
            "level_z_role": "exclude from proposed production evidence; transition-sensitive and scale-dependent",
            "robust_z_role": "exclude; MAD is structurally zero in material fractions of shorter windows",
            "level_state_policy": "null_evidence_only",
            "lineage_if_frozen": "current plus every exact prior selected processed level for broad rank; final 61 levels reconstruct recent median distance",
            "thresholds_frozen": False,
            "production_modified": False,
        },
    }
    _write_csv(output / "level_research.csv", rows)
    _write_csv(output / "method_comparison.csv", comparison)
    _write_csv(output / "case_studies.csv", cases)
    (output / "selected_observations.json").write_text(json.dumps(levels, indent=2), encoding="utf-8")
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "dataset": results["dataset"]}, indent=2))


if __name__ == "__main__":
    main()
