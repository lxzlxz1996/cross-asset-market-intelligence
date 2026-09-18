"""Independent SQL cross-check of archived research inputs and every score.

Uses an in-memory DuckDB only. Does not import the analysis implementation,
read/write the production database, or fetch data.
"""

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
def close(actual, expected):
    if actual is None or expected is None:
        assert actual is expected, (actual, expected)
    else:
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "outputs")
    out = parser.parse_args().output.resolve()
    levels = json.loads((out / "selected_observations.json").read_text(encoding="utf-8"))
    scores = json.loads((out / "rolling_scores.json").read_text(encoding="utf-8"))
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    encoded = json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == results["provenance"]["selected_snapshot_sha256"]
    assert len({row["date"] for row in levels}) == len(levels)
    assert [row["date"] for row in levels] == sorted(row["date"] for row in levels)
    with duckdb.connect(":memory:") as connection:
        connection.execute("CREATE TABLE levels(day DATE, value DECIMAL(18,8), id VARCHAR)")
        connection.executemany("INSERT INTO levels VALUES (?, ?, ?)", [
            (row["date"], str(row["sofr_percent"]), row["processed_observation_id"]) for row in levels
        ])
        connection.execute("""
            CREATE TABLE changes AS
            WITH pairs AS (
                SELECT day, value, id, lag(day) OVER(ORDER BY day) previous_day,
                    lag(value) OVER(ORDER BY day) previous_value,
                    lag(id) OVER(ORDER BY day) previous_id FROM levels
            ) SELECT row_number() OVER(ORDER BY day) i, *,
                ((value-previous_value)*100)::DOUBLE delta
            FROM pairs WHERE previous_day IS NOT NULL
        """)
        with (out / "changes.csv").open(encoding="utf-8", newline="") as handle:
            archived_changes = list(csv.DictReader(handle))
        independent = connection.execute("SELECT day, previous_day, delta, id, previous_id FROM changes ORDER BY i").fetchall()
        assert len(independent) == len(archived_changes) == results["dataset"]["valid_changes"]
        for row, saved in zip(independent, archived_changes):
            assert row[0].isoformat() == saved["date"] and row[1].isoformat() == saved["previous_date"]
            close(row[2], float(saved["change_bp"]))
            assert row[3] == saved["current_processed_id"] and row[4] == saved["previous_processed_id"]
        signed = results["signed_distribution_bp"]
        close(connection.execute("SELECT stddev_samp(delta) FROM changes").fetchone()[0], signed["sample_std_ddof1"])
        for probability, expected in signed["quantiles"].items():
            close(connection.execute("SELECT quantile_cont(delta, ?) FROM changes", [float(probability)]).fetchone()[0], expected)
        checked = 0
        for window in (20, 60, 120, 252):
            # p.i < c.i explicitly excludes the current delta from every baseline.
            sql = """
                WITH pairs AS (
                    SELECT c.i, c.day, c.delta current_delta, p.day prior_day, p.delta prior_delta
                    FROM changes c JOIN changes p ON p.i >= c.i-? AND p.i < c.i
                    WHERE c.i > ?
                ), centers AS (
                    SELECT i, day, current_delta, count(*) n, min(prior_day) first_day,
                        max(prior_day) last_day, avg(prior_delta) mean,
                        stddev_samp(prior_delta) sd, median(prior_delta) center,
                        count(*) FILTER(WHERE abs(prior_delta)<abs(current_delta)) less,
                        count(*) FILTER(WHERE abs(prior_delta)=abs(current_delta)) equal
                    FROM pairs GROUP BY i, day, current_delta
                ), scales AS (
                    SELECT c.*, median(abs(p.prior_delta-c.center)) mad
                    FROM centers c JOIN pairs p USING(i)
                    GROUP BY ALL
                ) SELECT day, first_day, last_day, n, mean, sd, center, mad,
                    (current_delta-mean)/nullif(sd,0) z,
                    .6745*(current_delta-center)/nullif(mad,0) robust,
                    100.0*less/n strict_rank, 100.0*(less+.5*equal)/n midrank,
                    100.0*(less+equal)/n weak_rank, less, equal, n-less-equal greater
                FROM scales ORDER BY day
            """
            rows = connection.execute(sql, [window, window]).fetchall()
            expected_rows = [row for row in scores if row["window"] == window]
            assert len(rows) == len(expected_rows) == next(r["eligible_dates"] for r in results["windows"] if r["window"] == window)
            for actual, saved in zip(rows, expected_rows):
                assert actual[0].isoformat() == saved["date"]
                assert actual[1].isoformat() == saved["baseline_first_change_date"]
                assert actual[2].isoformat() == saved["baseline_last_change_date"]
                assert actual[2] < actual[0] and actual[3] == window
                for index, field in enumerate(("prior_mean_bp", "prior_std_bp", "prior_median_bp", "prior_mad_bp", "standard_z", "robust_z", "percentile_strict", "percentile_midrank", "percentile_weak", "prior_less_count", "prior_equal_count", "prior_greater_count"), 4):
                    close(actual[index], saved[field])
                checked += 1
    tables_checked = 0
    report_snapshot = out / "reviewed_report.json"
    if report_snapshot.exists():
        snapshot = json.loads(report_snapshot.read_text(encoding="utf-8"))
        assert len(snapshot["researchSections"]) == 11
        for section in snapshot["researchSections"]:
            width = None
            for line in section["body"].splitlines():
                if line.startswith("|"):
                    cells = re.split(r"(?<!\\)\|", line)[1:-1]
                    if width is None:
                        width = len(cells)
                        tables_checked += 1
                    assert len(cells) == width, (section["id"], line)
                else:
                    width = None
        assert tables_checked == 7
    required = {
        "expanded_validated_sofr_history.csv", "rolling_scores.csv",
        "window_comparison.csv", "event_comparison.csv", "results.json",
    }
    assert required <= {path.name for path in out.iterdir()}
    verification = {"status": "passed", "implementation": "independent in-memory DuckDB SQL",
                    "validated_levels": len(levels), "validated_changes": len(independent),
                    "validated_score_rows": checked, "validated_report_tables": tables_checked, "windows": [20, 60, 120, 252],
                    "selected_snapshot_sha256": results["provenance"]["selected_snapshot_sha256"],
                    "checks": ["input snapshot hash and chronological uniqueness", "Decimal level differences and lineage IDs", "ddof1 standard deviation and all signed quantiles", "strict prior-only windows, dates, mean/std/median/MAD and all five scores", "required Phase 2.1B-2 machine-readable artifacts"]}
    (out / "validation.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
