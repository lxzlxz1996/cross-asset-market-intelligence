"""Independent validation of frozen-input SOFR Level research outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics as st
from decimal import Decimal
from pathlib import Path


def close(actual: str, expected: float) -> None:
    assert math.isclose(float(actual), expected, rel_tol=1e-11, abs_tol=1e-11), (actual, expected)


def median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def percentile(current: Decimal, prior: list[Decimal]) -> tuple[int, int, int, float, float, float]:
    less = sum(value < current for value in prior)
    equal = sum(value == current for value in prior)
    greater = len(prior) - less - equal
    count = len(prior)
    return (
        less, equal, greater, 100 * less / count,
        100 * (less + .5 * equal) / count, 100 * (less + equal) / count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs")
    output = parser.parse_args().output.resolve()
    levels = json.loads((output / "selected_observations.json").read_text(encoding="utf-8"))
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    with (output / "level_research.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    encoded = json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == results["provenance"]["selected_snapshot_sha256"]
    assert len(levels) == len(rows) == 2112
    assert len({row["date"] for row in levels}) == len(levels)
    values = [Decimal(str(row["sofr_percent"])) for row in levels]
    checked = 0
    for index, (source, saved) in enumerate(zip(levels, rows)):
        assert source["date"] == saved["date"]
        assert source["processed_observation_id"] == saved["processed_observation_id"]
        close(saved["current_sofr_level"], float(values[index]))
        if index == 0:
            assert saved["full_history_midrank"] == "" and saved["change_1obs_bp"] == ""
        else:
            close(saved["change_1obs_bp"], float((values[index] - values[index - 1]) * 100))
            less, equal, greater, strict, midrank, weak = percentile(values[index], values[:index])
            assert int(saved["full_history_less_count"]) == less
            assert int(saved["full_history_equal_count"]) == equal
            assert int(saved["full_history_greater_count"]) == greater
            close(saved["full_history_strict"], strict)
            close(saved["full_history_midrank"], midrank)
            close(saved["full_history_weak"], weak)
            checked += 7
        for window in (60, 120, 252, 504):
            if index < window:
                assert saved[f"level_midrank_{window}"] == ""
                assert saved[f"level_z_status_{window}"] == "insufficient_history"
                assert saved[f"level_z_{window}"] == ""
                continue
            prior = values[index-window:index]
            less, equal, greater, strict, midrank, weak = percentile(values[index], prior)
            assert int(saved[f"level_less_count_{window}"]) == less
            assert int(saved[f"level_equal_count_{window}"]) == equal
            assert int(saved[f"level_greater_count_{window}"]) == greater
            close(saved[f"level_strict_{window}"], strict)
            close(saved[f"level_midrank_{window}"], midrank)
            close(saved[f"level_weak_{window}"], weak)
            mean = sum(prior, Decimal("0")) / Decimal(window)
            variance = sum(((value - mean) ** 2 for value in prior), Decimal("0")) / Decimal(window - 1)
            scale = variance.sqrt()
            if scale == 0:
                assert saved[f"level_z_status_{window}"] == "zero_scale"
                assert saved[f"level_z_{window}"] == ""
            else:
                assert saved[f"level_z_status_{window}"] == "available"
                close(saved[f"level_z_{window}"], float((values[index] - mean) / scale))
            checked += 7
        for window in (20, 60, 120, 252):
            if index < window:
                assert saved[f"distance_mean_{window}_bp"] == ""
                assert saved[f"distance_median_{window}_bp"] == ""
                continue
            prior = values[index-window:index]
            mean = sum(prior, Decimal("0")) / Decimal(window)
            close(saved[f"distance_mean_{window}_bp"], float((values[index] - mean) * 100))
            close(saved[f"distance_median_{window}_bp"], float((values[index] - median(prior)) * 100))
            checked += 2
    verification = {
        "status": "passed",
        "implementation": "independent Python recomputation without importing analyze.py",
        "validated_levels": len(levels),
        "validated_rows": len(rows),
        "validated_calculations": checked,
        "selected_snapshot_sha256": results["provenance"]["selected_snapshot_sha256"],
        "checks": [
            "snapshot hash, exact processed identities, chronology, and row count",
            "prior-only full-history and 60/120/252/504 percentiles with exact tie counts",
            "prior-only 20/60/120/252 mean and median bp distances",
            "prior-only sample-standard-deviation level Z and zero-scale nulls",
            "exact warm-up nulls, fixed window sizes, and no future observations",
        ],
    }
    (output / "validation.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
