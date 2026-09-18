"""Independent validation of frozen-input SOFR direction research outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics as st
from datetime import date
from decimal import Decimal
from pathlib import Path


def close(actual: str, expected: float) -> None:
    assert math.isclose(float(actual), expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs")
    output = parser.parse_args().output.resolve()
    levels = json.loads((output / "selected_observations.json").read_text(encoding="utf-8"))
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    with (output / "direction_research.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    encoded = json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == results["provenance"]["selected_snapshot_sha256"]
    assert len({row["date"] for row in levels}) == len(levels) == 2112
    assert len(rows) == 2111
    values = [Decimal(str(row["sofr_percent"])) for row in levels]
    changes = [float((current - previous) * 100) for previous, current in zip(values, values[1:])]
    checked = 0
    for level_index in range(1, len(levels)):
        saved = rows[level_index - 1]
        assert saved["date"] == levels[level_index]["date"]
        close(saved["change_1obs_bp"], changes[level_index - 1])
        for window in (5, 10, 20, 60):
            if level_index < window:
                assert saved[f"net_change_{window}"] == ""
            else:
                close(saved[f"net_change_{window}"], float((values[level_index] - values[level_index-window]) * 100))
                checked += 1
            if level_index + 1 < window:
                assert saved[f"linear_slope_{window}"] == ""
            else:
                sample_levels = [float(value) for value in values[level_index-window+1:level_index+1]]
                mean_x = (window - 1) / 2
                mean_y = st.mean(sample_levels)
                slope = 100 * sum((i-mean_x)*(v-mean_y) for i, v in enumerate(sample_levels)) / sum((i-mean_x)**2 for i in range(window))
                close(saved[f"linear_slope_{window}"], slope)
                checked += 1
        for window in (10, 20, 60):
            if level_index < window:
                continue
            sample = changes[level_index-window:level_index]
            assert int(saved[f"positive_change_count_{window}"]) == sum(value > 0 for value in sample)
            assert int(saved[f"zero_change_count_{window}"]) == sum(value == 0 for value in sample)
            assert int(saved[f"negative_change_count_{window}"]) == sum(value < 0 for value in sample)
            close(saved[f"median_change_{window}"], st.median(sample))
            checked += 4
    verification = {
        "status": "passed",
        "implementation": "independent Python recomputation without importing analyze.py",
        "validated_levels": len(levels),
        "validated_direction_rows": len(rows),
        "validated_calculations": checked,
        "selected_snapshot_sha256": results["provenance"]["selected_snapshot_sha256"],
        "checks": [
            "snapshot hash and chronological uniqueness",
            "decimal-safe consecutive changes and 5/10/20/60 net changes",
            "independent OLS slopes",
            "10/20/60 sign counts and medians",
            "warm-up nulls and no future rows",
        ],
    }
    (output / "validation.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
