"""Independent Treasury research checks; never imports analyze.py calculators."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

from cross_asset_market_intelligence.research.primitives import (
    OrderedSequenceContract, aggregate_code_hash, code_file_identities,
    repository_relative_path, validate_ordered_input_sequence,
)
from cross_asset_market_intelligence.research.artifacts import validate_research_artifacts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IDENTITY_FIELDS = ("position", "indicator_id", "processed_observation_id", "observation_date", "processing_version", "information_available_at", "availability_precision", "retrieved_at")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def validator_paths(root: Path) -> list[Path]:
    return [HERE / "validate.py", HERE / "research_contract.json", HERE / "synthetic_cases.json", *[root / name for name in (
        "src/cross_asset_market_intelligence/research/artifacts.py", "src/cross_asset_market_intelligence/research/primitives.py",
        "src/cross_asset_market_intelligence/utils/canonical.py", "src/cross_asset_market_intelligence/signals/explanations.py", "src/cross_asset_market_intelligence/lineage.py",
        "docs/research_artifacts/manifest.schema.json", "docs/research_artifacts/results.schema.json", "docs/research_artifacts/validation.schema.json")]]


def D(value) -> Decimal:
    return Decimal(str(value))


def independent_median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    m = len(ordered)//2
    return ordered[m] if len(ordered) % 2 else (ordered[m-1]+ordered[m])/2


def independent_shape(value: Decimal) -> str:
    return {True: "inverted", False: "positive"}[value < 0] if value != 0 else "zero"


def same(saved: str, expected: Decimal | int | None) -> bool:
    if expected is None:
        return saved == ""
    return saved != "" and abs(D(saved)-D(expected)) <= Decimal("1e-20")


def validate_research(output: Path, database: Path | None, root: Path = ROOT) -> dict:
    selected = json.loads((output / "selected_observations.json").read_text(encoding="utf-8"))
    contract = json.loads((HERE / "research_contract.json").read_text(encoding="utf-8"))
    observations = selected["observations"]
    levels = read_csv(output / "aligned_levels.csv")
    rows = read_csv(output / "research_results.csv")
    checks = []

    def check(name: str, passed: bool, invariant: str, targets: list[str], method="separate_implementation", **extra):
        checks.append({"check_id": name, "description": name.replace("_", " "), "method": method, "targets": targets,
            "invariant": invariant, "passed": bool(passed), "severity": "blocking", "notes": None, **extra})

    identity = [{k: row[k] for k in IDENTITY_FIELDS} for row in observations]
    digest = "sha256:" + hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    check("snapshot_hash", digest == selected["selected_input_snapshot_hash"], "Independent standard-library projection hash matches selected snapshot", ["selected_observations"], method="structural_validation")
    lookup = {r["processed_observation_id"]: r for r in observations}
    exact_pairs = True
    for level in levels:
        two = lookup[level["two_year_processed_observation_id"]]
        ten = lookup[level["ten_year_processed_observation_id"]]
        exact_pairs &= two["role"] == "two_year" and ten["role"] == "ten_year" and two["observation_date"] == ten["observation_date"] == level["observation_date"]
        exact_pairs &= D(level["spread_bp"]) == (D(ten["value_percent"])-D(two["value_percent"]))*100
    check("snapshot_pair_math", exact_pairs, "Exact selected two-leg IDs share a date; Decimal spread is 100*(10Y-2Y)", ["selected_observations", "aligned_levels"])
    try:
        for role in ("two_year", "ten_year"):
            sequence = [r for r in observations if r["role"] == role]
            validate_ordered_input_sequence(sequence, contract=OrderedSequenceContract(position_field="role_position", direction="oldest_to_newest", date_order_required=True, current_input_position=len(sequence)-1, as_of_observation_date=selected["ordering"]["as_of_observation_date"]))
        lineage_pass = all(observations[i]["observation_date"] <= observations[i+1]["observation_date"] for i in range(len(observations)-1))
    except ValueError:
        lineage_pass = False
    check("two_role_ordering", lineage_pass, "Global enumeration and two separate role sequences reconstruct exact pairs without a single-series assumption", ["selected_observations"], method="structural_validation")

    if database is not None:
        with duckdb.connect(str(database), read_only=True) as c:
            sql_selected = c.execute("""
                WITH ranked AS (
                    SELECT *, row_number() OVER(PARTITION BY series_id,observation_date
                      ORDER BY split_part(vintage,':',2) DESC,split_part(vintage,':',3) DESC,vintage DESC) AS choice
                    FROM raw_observations WHERE source='fred' AND series_id IN ('DGS2','DGS10')
                )
                SELECT p.processed_observation_id,p.indicator_id,p.date,p.value,r.series_id,r.vintage,
                       r.retrieval_timestamp,r.publication_timestamp
                FROM ranked r JOIN processed_observation_inputs i ON i.raw_source=r.source AND i.raw_series_id=r.series_id
                  AND i.raw_observation_date=r.observation_date AND i.raw_vintage=r.vintage AND i.input_role='source'
                JOIN processed_observations p ON p.processed_observation_id=i.processed_observation_id AND p.date=r.observation_date
                WHERE r.choice=1 AND r.value IS NOT NULL
                  AND p.processing_version='fred_treasury_direct_percent_identity_v1'
                  AND p.indicator_id=CASE r.series_id WHEN 'DGS2' THEN 'us_treasury_2y_yield' ELSE 'us_treasury_10y_yield' END
                ORDER BY p.date,CASE r.series_id WHEN 'DGS2' THEN 0 ELSE 1 END
            """).fetchall()
            selected_ok = len(sql_selected) == len(observations)
            for expected, saved in zip(sql_selected, observations):
                identifier, indicator, observed, value, series, vintage, retrieved, published = expected
                normalize = lambda t: t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if t else None
                selected_ok &= identifier == saved["processed_observation_id"] and indicator == saved["indicator_id"] and observed.isoformat() == saved["observation_date"] and D(value) == D(saved["value_percent"])
                selected_ok &= vintage == saved["vintage"] and series == saved["series_id"] and normalize(retrieved) == saved["retrieved_at"] and normalize(published) == saved["information_available_at"]
            check("independent_sql_selection", selected_ok, "SQL latest-vintage selection equals full exported selected leg identity/value/time set", ["selected_observations"], method="independent_sql")
            sql_pairs = {}
            for saved in levels:
                two_id, ten_id = saved["two_year_processed_observation_id"], saved["ten_year_processed_observation_id"]
                result = c.execute("""SELECT (CAST(t.value AS DECIMAL(18,8))-CAST(s.value AS DECIMAL(18,8)))*100
                    FROM processed_observations t JOIN processed_observations s ON t.date=s.date
                    WHERE t.processed_observation_id=? AND s.processed_observation_id=?""", [ten_id, two_id]).fetchone()
                dependencies = set(c.execute("SELECT input_role,input_processed_observation_id FROM processed_observation_dependencies WHERE output_processed_observation_id=?", [saved["derived_processed_observation_id"]]).fetchall())
                sql_pairs[saved["observation_date"]] = result is not None and D(result[0]) == D(saved["spread_bp"]) and dependencies == {("two_year", two_id), ("ten_year", ten_id)}
            check("independent_sql_spreads_and_lineage", all(sql_pairs.values()), "All actual same-date spreads recompute in decimal SQL and resolve both saved Phase 1 dependency roles", ["aligned_levels"], method="independent_sql", observed=len(sql_pairs))
            alignment = read_csv(output / "alignment_audit.csv")
            raw_dates = c.execute("SELECT DISTINCT observation_date FROM raw_observations WHERE source='fred' AND series_id IN ('DGS2','DGS10') ORDER BY 1").fetchall()
            check("alignment_date_coverage", [d[0].isoformat() for d in raw_dates] == [r["observation_date"] for r in alignment], "Audit includes every raw date without inserting non-publication dates", ["alignment_audit"], method="independent_sql")
    else:
        # Portable offline export validation cannot claim original-DB resolution.
        checks.append({"check_id": "original_database_unverified", "description": "Original database omitted", "method": "structural_validation", "targets": ["selected_observations"], "invariant": None, "passed": False, "severity": "warning", "notes": "Snapshot-only validation does not establish that IDs resolve in the original database."})

    spreads = [D(r["spread_bp"]) for r in levels]
    changes = [spreads[j]-spreads[j-1] for j in range(1, len(spreads))]
    date_index = {r["observation_date"]: i for i, r in enumerate(levels)}
    configs = {}
    comparisons = read_csv(output / "method_comparison.csv")
    for row in comparisons:
        configs[row["parameter_set_id"]] = json.loads(row["parameters_json"])
    metric_ok, prior_ok, status_ok = True, True, True
    for row in rows:
        i = date_index[row["observation_date"]]
        params = configs[row["parameter_set_id"]]
        method = params["method"]
        expected_unit = "basis_point_per_aligned_observation" if method == "slope" else "percent" if method in {"change_cdf", "level_cdf"} else "basis_point"
        metric_ok &= row["unit"] == expected_unit
        metric_ok &= D(row["current_spread_bp"]) == spreads[i] and row["current_shape"] == independent_shape(spreads[i])
        if method == "shape":
            metric_ok &= same(row["value"], spreads[i])
            continue
        if method in {"net_path", "slope"}:
            h = params["changes"]
            eligible = i >= h
            status_ok &= row["status"] == ("available" if eligible else "insufficient_history")
            status_ok &= int(row["reference_count"]) == min(i, h)
            if not eligible:
                metric_ok &= all(row[key] == "" for key in ("value", "signed_change_bp", "path_absolute_bp"))
                continue
            delta = spreads[i]-spreads[i-h]
            gross = sum(abs(spreads[j]-spreads[j-1]) for j in range(i-h+1, i+1))
            metric_ok &= same(row["signed_change_bp"], delta) and same(row["absolute_change_bp"], abs(delta))
            metric_ok &= same(row["path_absolute_bp"], gross) and same(row["path_retention_ratio"], abs(delta)/gross if gross else None)
            two_delta = (D(levels[i]["two_year_percent"])-D(levels[i-h]["two_year_percent"]))*100
            ten_delta = (D(levels[i]["ten_year_percent"])-D(levels[i-h]["ten_year_percent"]))*100
            metric_ok &= same(row["two_year_change_bp"], two_delta) and same(row["ten_year_change_bp"], ten_delta) and delta == ten_delta-two_delta
            if method == "slope":
                # Independent closed-form regression using sums, not centered implementation.
                ys = spreads[i-h:i+1]
                n = D(len(ys)); sx = D(h*(h+1))/2; sxx = D(h*(h+1)*(2*h+1))/6
                expected = (n*sum(D(j)*y for j, y in enumerate(ys))-sx*sum(ys))/(n*sxx-sx*sx)
            else:
                expected = delta
            metric_ok &= same(row["value"], expected)
            prior_ok &= row["reference_first_date"] == levels[i-h]["observation_date"] and row["reference_last_date"] == levels[i-1]["observation_date"]
        else:
            is_change = method == "change_cdf"
            available = i-1 if is_change else i
            w = params["prior_changes" if is_change else "prior_levels"]
            required = params.get("minimum", w)
            eligible = available >= required
            status_ok &= row["status"] == ("available" if eligible else "insufficient_history")
            count = max(0, available) if w == "expanding" else max(0, min(available, w))
            status_ok &= int(row["reference_count"]) == count
            if not eligible:
                metric_ok &= all(row[key] == "" for key in ("value", "strict_pct", "weak_pct"))
                continue
            reference = [abs(changes[j]) for j in range(i-1-count, i-1)] if is_change else [spreads[j] for j in range(i-count, i)]
            current = abs(changes[i-1]) if is_change else spreads[i]
            prior_ok &= len(reference) == count and row["reference_first_date"] == levels[i-count]["observation_date"] and row["reference_last_date"] == levels[i-1]["observation_date"] < levels[i]["observation_date"]
            if method == "median_distance":
                metric_ok &= same(row["value"], current-independent_median(reference))
            else:
                ordered = sorted(reference)
                less = len([x for x in ordered if x < current]); weak = len([x for x in ordered if x <= current])
                metric_ok &= same(row["strict_pct"], D(100)*less/count) and same(row["weak_pct"], D(100)*weak/count)
                metric_ok &= (int(row["less_count"]), int(row["equal_count"]), int(row["greater_count"])) == (less, weak-less, count-weak)
                if is_change:
                    metric_ok &= same(row["signed_change_bp"], changes[i-1]) and same(row["absolute_change_bp"], current)
    check("independent_candidate_metrics", metric_ok, "Every observed candidate row recomputes through separate formulas; decimal tolerance 1e-20 only for division", ["research_results"], observed=len(rows))
    check("prior_only_reference_indices", prior_ok, "Reference end excludes current level/current change; no future indices", ["research_results"])
    check("warmup_and_no_fallback", status_ok, "Each declared complete window and exact warm-up boundary is preserved", ["research_results"])
    compared_ok = all(int(r["evaluated_count"]) == len(levels) and int(r["eligible_count"]) == sum(x["parameter_set_id"] == r["parameter_set_id"] and x["status"] == "available" for x in rows) for r in comparisons)
    check("comparison_eligibility", compared_ok, "Method comparison counts reconcile with all rows", ["method_comparison"])

    fixtures = json.loads((HERE / "synthetic_cases.json").read_text(encoding="utf-8"))
    cases = read_csv(output / "case_studies.csv")
    fixture_ok = True
    for fixture in fixtures["cases"]:
        calculated = [(D(t)-D(s))*100 for s, t in zip(fixture["two_year_percent"], fixture["ten_year_percent"])]
        fixture_ok &= calculated == [D(v) for v in fixture["expected_spread_bp"]]
        saved = next(c for c in cases if c["case_id"] == fixture["case_id"])
        gross = sum(abs(b-a) for a, b in zip(calculated, calculated[1:]))
        fixture_ok &= saved["case_type"] == "synthetic" and saved["derived_processed_observation_id"] == ""
        fixture_ok &= same(saved["start_spread_bp"], calculated[0]) and same(saved["end_spread_bp"], calculated[-1]) and same(saved["change_bp"], calculated[-1]-calculated[0])
        fixture_ok &= saved["start_shape"] == independent_shape(calculated[0]) and saved["end_shape"] == independent_shape(calculated[-1])
        fixture_ok &= same(saved["path_absolute_bp"], gross) and same(saved["path_retention_ratio"], abs(calculated[-1]-calculated[0])/gross if gross else None)
    for saved in cases:
        if saved["case_type"] == "observed":
            i = date_index[saved["anchor_date"]]
            prior = max(i-1, 0)
            fixture_ok &= saved["derived_processed_observation_id"] == levels[i]["derived_processed_observation_id"]
            fixture_ok &= same(saved["start_spread_bp"], spreads[prior]) and same(saved["end_spread_bp"], spreads[i]) and same(saved["change_bp"], spreads[i]-spreads[prior])
    check("observed_and_synthetic_cases", fixture_ok, "Observed cases resolve actual IDs; synthetic curves satisfy exact manually declared spreads and never enter market distributions", ["case_studies", "synthetic_fixtures"], method="exact_fixture", observed=len(cases))
    sensitivity = fixtures["reference_sensitivity"]
    calculated_ranks = [D(100)*sum(D(v) < D(sensitivity["current_spread_bp"]) for v in sensitivity[key])/len(sensitivity[key]) for key in ("prior_inverted_spreads_bp", "prior_positive_spreads_bp")]
    check("synthetic_reference_sensitivity", calculated_ranks == list(map(D, sensitivity["expected_strict_pct"])), "Same zero curve has 100% versus 0% strict CDF under opposite-sign synthetic references", ["synthetic_fixtures"], method="exact_fixture")
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    dataset = results["indicator_specific_findings"]["dataset"]
    check("summary_facts", int(dataset["aligned_observation_count"]) == len(levels) and D(dataset["spread_min_bp"]) == min(spreads) and D(dataset["spread_max_bp"]) == max(spreads)
        and dataset["sign_counts"] == {s: sum(independent_shape(v) == s for v in spreads) for s in ("positive", "zero", "inverted")}
        and D(dataset["sample_net_change_bp"]) == spreads[-1]-spreads[0], "Counts/extrema/signs/net reconcile to observed data only", ["results", "aligned_levels"])
    check("honest_research_gate", results["production_readiness_decision"] == "MORE_RESEARCH_REQUIRED", "Bounded ten-level study does not assert methodology-freeze readiness", ["results"])
    limitations = [{"limitation_id": "unknown_availability", "description": "No full historical publication-time replay is established; retrieval is not availability.", "blocking": False},
        {"limitation_id": "short_history_scope", "description": "Checks validate bounded research calculations; longer-history horizon/state/regime validity remains a blocking research question, not a validator error.", "blocking": False}]
    if database is None:
        limitations.append({"limitation_id": "original_db_unverified", "description": "Snapshot-only mode cannot resolve original database IDs.", "blocking": False})
    failures = sum(not c["passed"] for c in checks)
    blocking = any(not c["passed"] and c["severity"] == "blocking" for c in checks)
    return {**{k: selected[k] for k in ("artifact_standard_version", "research_id", "research_version", "run_id")},
        "validation_version": "v1", "status": "failed" if blocking else "passed_with_warnings", "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "validator": {"entrypoint": repository_relative_path(HERE / "validate.py", root), "code_hash": aggregate_code_hash(code_file_identities(validator_paths(root), root)), "independence_notes": "Independent SQL raw-vintage selection/Decimal pair math plus separate closed-form regression, median, CDF, warm-up, case and snapshot hash implementation; analyze.py is never imported."},
        "checks": checks, "summary": {"total_checks": len(checks), "passed": len(checks)-failures, "failed": failures, "warnings": sum(not c["passed"] and c["severity"] == "warning" for c in checks)}, "unresolved_limitations": limitations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/market_intelligence.duckdb")
    parser.add_argument("--output", type=Path, default=HERE / "outputs")
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()
    research = validate_research(args.output, None if args.snapshot_only else args.database)
    package = validate_research_artifacts(args.output, repository_root=ROOT)
    print(json.dumps({"independent_validation": research, "artifact_validation": package.as_dict()}, indent=2))
    raise SystemExit(1 if research["status"] == "failed" or package.status == "failed" else 0)
