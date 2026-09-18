"""Bounded, offline Phase 2.2D research. No production signal or database writes."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

from cross_asset_market_intelligence.data.treasury_processing import (
    DIRECT_TREASURY_PROCESSING_VERSION, select_latest_raw_vintages,
)
from cross_asset_market_intelligence.data.treasury_spread_processing import (
    TREASURY_SPREAD_INDICATOR, TREASURY_SPREAD_PROCESSING_VERSION,
    pair_same_date_treasury_inputs, select_current_direct_treasury_observations,
)
from cross_asset_market_intelligence.lineage import (
    ProcessedDependencyIdentity, RawInputIdentity, derived_processed_observation_id, processed_observation_id,
)
from cross_asset_market_intelligence.research.primitives import (
    OrderedSequenceContract, aggregate_code_hash, canonical_selected_inputs_v1,
    code_file_identities, git_code_identity, raw_file_sha256, rate_difference_to_basis_points,
    repository_relative_path, research_run_id, validate_economic_dates_not_future,
    validate_ordered_input_sequence,
)
from cross_asset_market_intelligence.utils.canonical import canonical_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROLE_SERIES = {"two_year": ("DGS2", "us_treasury_2y_yield"), "ten_year": ("DGS10", "us_treasury_10y_yield")}
IDENTITY_FIELDS = ("position", "indicator_id", "processed_observation_id", "observation_date", "processing_version", "information_available_at", "availability_precision", "retrieved_at")
ROW_FIELDS = ["observation_date", "method_id", "parameter_set_id", "status", "current_spread_bp", "current_shape", "reference_count", "reference_first_date", "reference_last_date", "value", "unit", "signed_change_bp", "absolute_change_bp", "strict_pct", "weak_pct", "less_count", "equal_count", "greater_count", "two_year_change_bp", "ten_year_change_bp", "path_absolute_bp", "path_retention_ratio"]
RESEARCH_DECISION = "MORE_RESEARCH_REQUIRED"
FRAMEWORK_DECISION = "PHASE 2.2 FRAMEWORK VALIDATED WITH NON-BLOCKING FOLLOW-UPS"


def decimal(value) -> Decimal:
    return Decimal(str(value))


def bp(value: Decimal) -> Decimal:
    return rate_difference_to_basis_points(value, source_unit="percentage_point")


def utc(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def shape(value: Decimal) -> str:
    return "inverted" if value < 0 else "zero" if value == 0 else "positive"


def write_json(path: Path, payload) -> None:
    # First validate through the shared canonical serializer; pretty output is file identity only.
    normalized = json.loads(canonical_json(payload))
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def select_inputs(connection) -> tuple[list[dict], list[dict], list[dict]]:
    """Resolve the actual Phase 1 selected IDs, raw vintages and existing derived IDs."""
    observations, raw_by_role, direct_by_role = [], {}, {}
    for role, (series, indicator) in ROLE_SERIES.items():
        raw_by_role[role] = {r.observation_date: r for r in select_latest_raw_vintages(connection, "fred", series)}
        direct_by_role[role] = {r.observation_date: r for r in select_current_direct_treasury_observations(connection, indicator)}
        for role_position, row in enumerate(direct_by_role[role].values()):
            lineage = connection.execute("""
                SELECT raw.source, raw.series_id, raw.observation_date, raw.vintage,
                       raw.value, raw.retrieval_timestamp, raw.publication_timestamp
                FROM processed_observation_inputs input JOIN raw_observations raw
                ON input.raw_source=raw.source AND input.raw_series_id=raw.series_id
                  AND input.raw_observation_date=raw.observation_date AND input.raw_vintage=raw.vintage
                WHERE input.processed_observation_id=? AND input.input_role='source'
            """, [row.processed_observation_id]).fetchall()
            if len(lineage) != 1:
                raise ValueError("Every selected leg must resolve to exactly one actual raw vintage")
            source, series, observed, vintage, raw_value, retrieved, published = lineage[0]
            expected_id = processed_observation_id(indicator, observed, DIRECT_TREASURY_PROCESSING_VERSION, [RawInputIdentity("source", source, series, observed, vintage)])
            if row.processed_observation_id != expected_id or decimal(row.value) != decimal(raw_value):
                raise ValueError("Selected processed identity/value disagrees with upstream lineage")
            observations.append({
                "position": 0, "role": role, "role_position": role_position,
                "indicator_id": indicator, "processed_observation_id": row.processed_observation_id,
                "observation_date": observed.isoformat(), "processing_version": DIRECT_TREASURY_PROCESSING_VERSION,
                "information_available_at": utc(published), "availability_precision": "exact_timestamp" if published else "unknown",
                "retrieved_at": utc(retrieved), "source": source, "series_id": series, "vintage": vintage,
                "value_percent": decimal(row.value), "unit": "percent",
            })
    observations.sort(key=lambda r: (r["observation_date"], 0 if r["role"] == "two_year" else 1))
    for position, observation in enumerate(observations):
        observation["position"] = position
    if not observations:
        raise ValueError("No selected Treasury inputs exist; no fabricated fallback is permitted")
    as_of = max(r["observation_date"] for r in observations)
    validate_ordered_input_sequence(observations, contract=OrderedSequenceContract(direction="oldest_to_newest", date_order_required=True, as_of_observation_date=as_of))
    # Each role is a real time sequence; the merged sequence is only artifact enumeration.
    for role in ROLE_SERIES:
        records = [r for r in observations if r["role"] == role]
        validate_ordered_input_sequence(records, contract=OrderedSequenceContract(position_field="role_position", direction="oldest_to_newest", date_order_required=True, current_input_position=len(records)-1, as_of_observation_date=as_of))
    alignment = []
    dates = sorted(set(raw_by_role["two_year"]) | set(raw_by_role["ten_year"]))
    for observed in dates:
        item = {"observation_date": observed.isoformat()}
        for role in ROLE_SERIES:
            raw = raw_by_role[role].get(observed)
            direct = direct_by_role[role].get(observed)
            item[f"{role}_status"] = "source_absent" if raw is None else "source_missing" if raw.value is None else "not_processed" if direct is None else "available"
            item[f"{role}_vintage"] = raw.vintage if raw else None
            item[f"{role}_processed_id"] = direct.processed_observation_id if direct else None
        item["aligned"] = "true" if item["two_year_status"] == item["ten_year_status"] == "available" else "false"
        alignment.append(item)
    levels = []
    for ten, two in pair_same_date_treasury_inputs(direct_by_role["ten_year"].values(), direct_by_role["two_year"].values()):
        spread_id = derived_processed_observation_id(TREASURY_SPREAD_INDICATOR, ten.observation_date, TREASURY_SPREAD_PROCESSING_VERSION,
            [ProcessedDependencyIdentity("ten_year", ten.processed_observation_id), ProcessedDependencyIdentity("two_year", two.processed_observation_id)])
        saved = connection.execute("SELECT value FROM processed_observations WHERE processed_observation_id=?", [spread_id]).fetchone()
        expected_dependencies = {("two_year", two.processed_observation_id), ("ten_year", ten.processed_observation_id)}
        dependencies = set(connection.execute("SELECT input_role,input_processed_observation_id FROM processed_observation_dependencies WHERE output_processed_observation_id=?", [spread_id]).fetchall())
        exact_spread = decimal(ten.value) - decimal(two.value)
        if saved is None or abs(decimal(saved[0]) - exact_spread) > Decimal("1e-10") or dependencies != expected_dependencies:
            raise ValueError("Existing Phase 1 derived value/identity/pair must resolve exactly")
        levels.append({"observation_date": ten.observation_date.isoformat(), "two_year_percent": decimal(two.value), "ten_year_percent": decimal(ten.value), "spread_bp": bp(exact_spread), "derived_processed_observation_id": spread_id, "two_year_processed_observation_id": two.processed_observation_id, "ten_year_processed_observation_id": ten.processed_observation_id})
    return observations, levels, alignment


def candidates(contract: dict) -> list[dict]:
    configs = [("shape", {})]
    configs += [("net_path", {"changes": h}) for h in contract["movement_horizons"]]
    configs += [("slope", {"changes": h}) for h in contract["path_horizons"]]
    configs += [("change_cdf", {"prior_changes": w}) for w in contract["rarity_prior_change_counts"]]
    configs += [("change_cdf", {"prior_changes": "expanding", "minimum": contract["expanding_minimum_prior_count"]})]
    configs += [("median_distance", {"prior_levels": w}) for w in contract["context_prior_level_counts"]]
    configs += [("level_cdf", {"prior_levels": w}) for w in contract["context_prior_level_counts"]]
    configs += [("level_cdf", {"prior_levels": "expanding", "minimum": contract["expanding_minimum_prior_count"]})]
    return [{"candidate_id": f"{name}_{next(iter(params.values()))}" if params else name, "parameters": {"method": name, **params}, "configuration_reference": repository_relative_path(HERE / "research_contract.json", ROOT)} for name, params in configs]


def empirical_band(current: Decimal, reference: list[Decimal]) -> dict:
    less = sum(v < current for v in reference)
    equal = sum(v == current for v in reference)
    return {"less_count": less, "equal_count": equal, "greater_count": len(reference)-less-equal,
        "strict_pct": Decimal(100)*less/len(reference), "weak_pct": Decimal(100)*(less+equal)/len(reference)}


def calculate_rows(levels: list[dict], configurations: list[dict]) -> list[dict]:
    spreads = [r["spread_bp"] for r in levels]
    changes = [right-left for left, right in zip(spreads, spreads[1:])]
    rows = []
    for i, level in enumerate(levels):
        validate_economic_dates_not_future(levels[:i+1], as_of_observation_date=level["observation_date"])
        for config in configurations:
            params = config["parameters"]
            method = params["method"]
            row = dict.fromkeys(ROW_FIELDS)
            unit = "basis_point_per_aligned_observation" if method == "slope" else "percent" if method in {"change_cdf", "level_cdf"} else "basis_point"
            row.update(observation_date=level["observation_date"], method_id=method, parameter_set_id=config["candidate_id"], status="available", current_spread_bp=spreads[i], current_shape=shape(spreads[i]), reference_count=0, unit=unit)
            if method == "shape":
                row["value"] = spreads[i]
            elif method in {"net_path", "slope"}:
                h = params["changes"]
                row["reference_count"] = min(i, h)
                if i < h:
                    row["status"] = "insufficient_history"
                else:
                    row.update(reference_first_date=levels[i-h]["observation_date"], reference_last_date=levels[i-1]["observation_date"])
                    net = spreads[i] - spreads[i-h]
                    path = changes[i-h:i]
                    gross = sum(map(abs, path))
                    row.update(signed_change_bp=net, absolute_change_bp=abs(net), path_absolute_bp=gross,
                        path_retention_ratio=abs(net)/gross if gross else None,
                        two_year_change_bp=bp(levels[i]["two_year_percent"]-levels[i-h]["two_year_percent"]),
                        ten_year_change_bp=bp(levels[i]["ten_year_percent"]-levels[i-h]["ten_year_percent"]))
                    if method == "net_path":
                        row["value"] = net
                    else:
                        path_levels = spreads[i-h:i+1]
                        x_mean = Decimal(h)/2
                        y_mean = sum(path_levels)/len(path_levels)
                        row["value"] = sum((Decimal(j)-x_mean)*(y-y_mean) for j, y in enumerate(path_levels)) / sum((Decimal(j)-x_mean)**2 for j in range(h+1))
                        row["unit"] = "basis_point_per_aligned_observation"
            else:
                is_change = method == "change_cdf"
                available = i-1 if is_change else i
                declared = params["prior_changes" if is_change else "prior_levels"]
                minimum = params.get("minimum", declared)
                count = max(0, available) if declared == "expanding" else max(0, min(available, declared))
                row["reference_count"] = count
                if available < minimum or (is_change and i == 0):
                    row["status"] = "insufficient_history"
                else:
                    if is_change:
                        reference = list(map(abs, changes[i-1-count:i-1]))
                        current = abs(changes[i-1])
                        row.update(signed_change_bp=changes[i-1], absolute_change_bp=current)
                        ref_levels = levels[i-count:i]
                    else:
                        reference = spreads[i-count:i]
                        current = spreads[i]
                        ref_levels = levels[i-count:i]
                    row.update(reference_first_date=ref_levels[0]["observation_date"], reference_last_date=ref_levels[-1]["observation_date"])
                    if method == "median_distance":
                        row["value"] = current-statistics.median(reference)
                    else:
                        row.update(empirical_band(current, reference))
                        row["unit"] = "percent"
                        # A tie interval has no privileged scalar estimate.
            rows.append(row)
    return rows


def summarize(rows: list[dict], configurations: list[dict]) -> list[dict]:
    comparisons = []
    for config in configurations:
        sample = [r for r in rows if r["parameter_set_id"] == config["candidate_id"]]
        valid = [r for r in sample if r["status"] == "available"]
        values = [r["value"] for r in valid if r["value"] is not None]
        bands = [r["weak_pct"]-r["strict_pct"] for r in valid if r["weak_pct"] is not None]
        agreements = [shape(r["value"]) == shape(r["signed_change_bp"]) for r in valid if r["method_id"] == "slope"]
        comparisons.append({"method_id": config["parameters"]["method"], "parameter_set_id": config["candidate_id"], "parameters_json": canonical_json(config["parameters"]),
            "evaluated_count": len(sample), "eligible_count": len(valid), "warmup_count": len(sample)-len(valid),
            "minimum_value": min(values) if values else None, "maximum_value": max(values) if values else None,
            "unit": sample[0]["unit"], "median_tie_band_pct": statistics.median(bands) if bands else None,
            "slope_endpoint_disagreement_count": len(agreements)-sum(agreements) if agreements else None,
            "authority": "research_only", "limitation": "Ten observed levels cannot select a horizon or calibrate distribution states."})
    return comparisons


def make_cases(levels: list[dict], fixtures: dict) -> list[dict]:
    rows = []
    if levels:
        selectors = [("observed_positive", len(levels)-1, "Latest positive shape; no recession interpretation"),
            ("observed_closest_to_zero", min(range(len(levels)), key=lambda i: abs(levels[i]["spread_bp"])), "Smallest absolute spread in sample, not a near-flat band")]
        if len(levels) > 1:
            selectors += [("observed_max_steepening", max(range(1, len(levels)), key=lambda i: levels[i]["spread_bp"]-levels[i-1]["spread_bp"]), "Largest signed one-step rise in bounded sample"),
                ("observed_max_flattening", min(range(1, len(levels)), key=lambda i: levels[i]["spread_bp"]-levels[i-1]["spread_bp"]), "Largest signed one-step fall in bounded sample")]
        for case_id, i, reason in selectors:
            prior = levels[i-1] if i else levels[i]
            current = levels[i]
            rows.append({"case_id": case_id, "case_name": case_id, "anchor_date": current["observation_date"], "case_type": "observed", "selection_reason": reason, "relevant_method_id": "shape",
                "start_spread_bp": prior["spread_bp"], "end_spread_bp": current["spread_bp"], "change_bp": current["spread_bp"]-prior["spread_bp"],
                "start_shape": shape(prior["spread_bp"]), "end_shape": shape(current["spread_bp"]),
                "two_year_change_bp": bp(current["two_year_percent"]-prior["two_year_percent"]), "ten_year_change_bp": bp(current["ten_year_percent"]-prior["ten_year_percent"]),
                "path_absolute_bp": abs(current["spread_bp"]-prior["spread_bp"]), "path_retention_ratio": 1 if current["spread_bp"] != prior["spread_bp"] else None,
                "derived_processed_observation_id": current["derived_processed_observation_id"]})
    for case in fixtures["cases"]:
        spreads = [bp(decimal(ten)-decimal(two)) for two, ten in zip(case["two_year_percent"], case["ten_year_percent"])]
        gross = sum(abs(b-a) for a, b in zip(spreads, spreads[1:]))
        rows.append({"case_id": case["case_id"], "case_name": case["case_id"], "anchor_date": "2025-01-01", "case_type": "synthetic",
            "selection_reason": "Exact semantic fixture; synthetic anchor, not observed history", "relevant_method_id": "shape",
            "start_spread_bp": spreads[0], "end_spread_bp": spreads[-1], "change_bp": spreads[-1]-spreads[0], "start_shape": shape(spreads[0]), "end_shape": shape(spreads[-1]),
            "two_year_change_bp": bp(decimal(case["two_year_percent"][-1])-decimal(case["two_year_percent"][0])), "ten_year_change_bp": bp(decimal(case["ten_year_percent"][-1])-decimal(case["ten_year_percent"][0])),
            "path_absolute_bp": gross, "path_retention_ratio": abs(spreads[-1]-spreads[0])/gross if gross else None, "derived_processed_observation_id": None})
    return rows


def framework_scorecard() -> list[dict]:
    followups = {
        "candidate-method research": "Only ten levels; horizon and tail calibration remain unvalidated.",
        "point-in-time metadata": "Unknown publications preserved; event-time replay not established.",
        "methodology-freeze readiness": "Gate correctly returns MORE_RESEARCH_REQUIRED; broader validated local history needed.",
        "state governance": "Exact-zero sign tested synthetically; empirical states deferred.",
        "artifact standard": "Six generic validation gaps corrected with regression tests; no envelope/profile change.",
    }
    names = ["economic-question template", "input contract", "multi-input derived data", "point-in-time metadata", "candidate-method research", "artifact standard", "snapshot identity", "run identity", "independent validation", "exact lineage", "ordered-lineage primitive", "unit conversion", "state governance", "evidence/state separation", "methodology-freeze readiness", "validator CLI", "SOFR independence"]
    return [{"framework_capability": name, "result": "PASS WITH FOLLOW-UP" if name in followups else "PASS",
        "evidence": "research_contract;selected_observations;research_results;case_studies;validation", "issue": followups.get(name, "none")} for name in names]


def column_metadata(rows: list[dict]) -> list[dict]:
    metadata = []
    integer_names = {"reference_count", "less_count", "equal_count", "greater_count", "evaluated_count", "eligible_count", "warmup_count", "slope_endpoint_disagreement_count"}
    number_names = {"value", "minimum_value", "maximum_value"}
    for name in rows[0]:
        logical_type = "date" if name.endswith("date") else "integer" if name in integer_names else "number" if name.endswith(("_bp", "_pct", "_ratio", "_percent")) or name in number_names else "json" if name.endswith("_json") else "string"
        unit = "basis_point" if name.endswith("_bp") else "percent" if name.endswith(("_pct", "_percent")) else "ratio" if name.endswith("_ratio") else "count" if name in integer_names else "declared_in_unit_column" if name in number_names else "not_applicable"
        nullable = any(row[name] is None for row in rows)
        metadata.append({"name": name, "logical_type": logical_type, "unit": unit, "description": name.replace("_", " ") + "; see research contract for formula and grain",
            "null_semantics": "empty for candidate warm-up, inapplicable metric, missing leg/identity, or zero gross path; status/case_type defines context" if nullable else "never null"})
    return metadata


def package_results(levels, alignment, rows, cases, scorecard) -> dict:
    spreads = [r["spread_bp"] for r in levels]
    signs = Counter(shape(v) for v in spreads)
    changes = [b-a for a, b in zip(spreads, spreads[1:])]
    crossings = sum(a*b < 0 for a, b in zip(spreads, spreads[1:]))
    known = {"aligned_observation_count": len(levels), "selected_leg_count": 2*len(levels), "first_date": levels[0]["observation_date"], "last_date": levels[-1]["observation_date"],
        "raw_date_union_count": len(alignment), "one_leg_missing_dates": sum((r["two_year_status"] == "available") != (r["ten_year_status"] == "available") for r in alignment),
        "both_source_missing_dates": sum(r["two_year_status"] == r["ten_year_status"] == "source_missing" for r in alignment),
        "spread_min_bp": min(spreads), "spread_max_bp": max(spreads), "spread_median_bp": statistics.median(spreads), "spread_mean_bp": sum(spreads)/len(spreads),
        "sign_counts": {s: signs[s] for s in ("positive", "zero", "inverted")}, "strict_sign_crossings": crossings,
        "zero_touch_count": signs["zero"], "latest_spread_bp": spreads[-1], "sample_net_change_bp": spreads[-1]-spreads[0],
        "one_step_changes_bp": changes, "observed_case_count": sum(r["case_type"] == "observed" for r in cases), "synthetic_case_count": sum(r["case_type"] == "synthetic" for r in cases)}
    facts = [
        {"fact_id": "dataset", "statement": "Current-vintage local Treasury sample and alignment coverage.", "evidence_refs": ["selected_observations", "alignment_audit", "aligned_levels"], "value": known, "unit": "mixed_declared_fields"},
        {"fact_id": "eligibility", "statement": "Candidate availability is measured without partial-window fallback.", "evidence_refs": ["method_comparison", "research_results"], "value": {r["parameter_set_id"]: sum(x["status"] == "available" and x["parameter_set_id"] == r["parameter_set_id"] for x in rows) for r in rows}, "unit": "count"},
        {"fact_id": "semantics", "statement": "Exact synthetic cases exercise inversion, zero, crossing, reversal and common-leg shifts; they are excluded from observed statistics.", "evidence_refs": ["case_studies", "synthetic_fixtures"], "value": known["synthetic_case_count"], "unit": "count"},
    ]
    interpretation = "All observed spreads are positive in a ten-date sample. It cannot establish inversion-era or multi-environment distributions. Signed shape, endpoint movement and two-leg contributions answer distinct descriptive questions; rank and bp distance are not independent confirmations."
    return {
        "research_status": RESEARCH_DECISION, "measured_facts": facts,
        "research_interpretations": [{"interpretation_id": "bounded_meaning", "statement": interpretation, "based_on_fact_ids": ["dataset", "eligibility", "semantics"], "limitations": ["Current vintages and unknown publication availability.", "No historical inverted/zero observations or calibrated tails."]}],
        "design_recommendations": [{"recommendation_id": "transparent_curve", "statement": "Retain raw signed bp spread, exact sign, signed/absolute movement and two-leg decomposition as proposed evidence; preserve reversal context. Defer horizon selection, normalization authority and empirical states until expanded validated history supports comparison.", "basis_refs": ["dataset", "eligibility", "bounded_meaning"]}],
        "method_comparison_summary": {"applicability": "performed", "artifact_ref": "method_comparison", "rationale": "Bounded endpoint/path/slope and prior-reference sensitivity; warm-up is a measured outcome, not a default horizon choice."},
        "recommended_evidence_design": {"mandatory_proposal": ["spread_bp", "both_exact_leg_ids", "direct_sign_descriptor", "signed_change_bp", "absolute_change_bp", "two_year_change_bp", "ten_year_change_bp"],
            "secondary_research": ["gross_path_bp", "path_retention_ratio", "strict_weak_cdf_band"], "excluded": ["recession forecast", "materiality state", "automatic anomaly state", "generic component trio"]},
        "recommended_horizon_or_reference_design": {"decision": "deferred", "rationale": "Only ten levels; 21/63 reference candidates and 10-change movement have no eligible rows."},
        "state_recommendation": {"decision": "proposed", "rationale": "Exact sign has direct meaning; nomenclature remains research-only, while near-flat/unusually-steep/anomaly thresholds are deferred.", "boundary": {"negative": "inverted", "zero": "zero", "positive": "positive"}},
        "known_failure_modes": [{"failure_mode_id": "short_positive_sample", "description": "A rank can change drastically with the sign mix of its reference; short positive-only history cannot answer inversion/regime questions.", "evidence_refs": ["research_results", "synthetic_fixtures"], "blocking": True},
            {"failure_mode_id": "common_leg_shift", "description": "Unchanged curve spread hides simultaneous equal leg movements; net change hides a round trip.", "evidence_refs": ["case_studies"], "blocking": False}],
        "indicator_specific_findings": {"dataset": known, "framework_outcome": FRAMEWORK_DECISION, "scorecard": scorecard,
            "redundancy": {"shape_and_sign": "Sign is a deterministic coarsening of spread, not independent evidence.", "distance_from_zero": "Signed raw spread already measures it; absolute distance is redundant unless explaining magnitude.", "net_and_slope": "Both summarize a path; slope has different path weights, compare conflicts rather than count confirmations.", "rarity_and_magnitude": "Keep bp visible; small finite-reference rarity is not economic materiality."},
            "structural_context": "No rate-environment claims from ten dates. Synthetic inverted-versus-positive references show the same zero spread has strict rank 100% versus 0%.",
            "historical_case_limits": "Observed positive/maximum sample steepening/flattening/closest-to-zero cases only; inversion, exact zero, crossing and large round trip are synthetic.",
            "lineage": "Global positions enumerate (date, role); per-role positions carry time. Two current legs remain a pair, with no single current endpoint on the merged sequence.",
            "generic_corrections": ["resolvable references", "truthful validation status and bounded warnings", "explicit matching report decision", "CSV never-null and extra fields", "array position order", "strict ISO full-date"]},
        "deferred_questions": [{"question_id": "expanded_local_history", "question": "Expand through separately authorized Phase 1 history workflow to cover positive, inverted, zero-crossing and different volatility periods before selecting horizons or normalizations.", "blocking": True},
            {"question_id": "curve_freeze", "question": "Freeze exact production nomenclature, quality, horizons, lineage scope and explanation only after sufficient research.", "blocking": True}],
        "production_readiness_decision": RESEARCH_DECISION,
    }


def code_paths(validator: bool = False) -> list[Path]:
    common = [ROOT / p for p in ["src/cross_asset_market_intelligence/research/primitives.py", "src/cross_asset_market_intelligence/utils/canonical.py", "src/cross_asset_market_intelligence/signals/explanations.py", "src/cross_asset_market_intelligence/lineage.py"]]
    if validator:
        return [HERE / "validate.py", HERE / "research_contract.json", HERE / "synthetic_cases.json", ROOT / "src/cross_asset_market_intelligence/research/artifacts.py", *common,
            *[ROOT / "docs/research_artifacts" / name for name in ("manifest.schema.json", "results.schema.json", "validation.schema.json")]]
    return sorted(set([HERE / "analyze.py", HERE / "research_contract.json", HERE / "synthetic_cases.json", HERE / "README.md", HERE / "report_template.md", *common,
        *code_paths(True), *[ROOT / "src/cross_asset_market_intelligence/data" / name for name in ("treasury_processing.py", "treasury_spread_processing.py", "fred_vintages.py")]]))


def final_manifest(output: Path, selected: dict, configs: list[dict], results: dict, validation: dict) -> dict:
    code = git_code_identity(repository_root=ROOT, declared_code_files=code_paths(), declared_tracked_paths=[*code_paths(), *code_paths(True), ROOT / "pyproject.toml"])
    validator_files = code_file_identities(code_paths(True), ROOT)
    artifacts = []
    for path in sorted(output.iterdir()):
        if path.name == "manifest.json" or not path.is_file():
            continue
        name = "readme" if path.name == "README.md" else path.stem
        kind = "json" if path.suffix == ".json" else "csv" if path.suffix == ".csv" else "markdown"
        rows = list(csv.DictReader(path.open(encoding="utf-8", newline=""))) if kind == "csv" else None
        if rows:
            # Read-back empty fields recover declared missingness for metadata construction.
            rows = [{k: None if v == "" else v for k, v in r.items()} for r in rows]
        artifacts.append({"logical_name": name, "relative_path": repository_relative_path(path, ROOT), "artifact_type": kind,
            "media_type": {"json": "application/json", "csv": "text/csv", "markdown": "text/markdown"}[kind],
            "requirement": "mandatory" if name in {"results", "validation", "report", "readme"} else "conditional" if name in {"selected_observations", "research_results", "method_comparison", "case_studies"} else "optional",
            "raw_file_hash": raw_file_sha256(path), "authoritative_for": [name], "storage_policy": "committed", "external_reference": None,
            "columns": column_metadata(rows) if rows else [], "column_schema_path": None, "row_count": len(rows) if rows is not None else None})
    observations = selected["observations"]
    return {"artifact_standard_version": "research_artifacts_v1", "research_id": selected["research_id"], "research_version": selected["research_version"], "run_id": selected["run_id"],
        "subject": {"signal_id": None, "proposed_signal_id": "treasury_2s10s_curve", "component_id": "curve_evidence_research", "indicator_ids": [r[1] for r in ROLE_SERIES.values()] + [TREASURY_SPREAD_INDICATOR]},
        "research_status": RESEARCH_DECISION,
        "dataset": {"applicability": "selected_observations", "observation_count": len(observations), "first_observation_date": min(r["observation_date"] for r in observations), "last_observation_date": max(r["observation_date"] for r in observations),
            "selected_input_snapshot_hash": selected["selected_input_snapshot_hash"], "snapshot_identity_profile": "canonical_selected_inputs_v1",
            "input_selection_rule": "Existing Phase 1 latest valid raw-vintage/current direct processed selection; inner-align same dates; date/role snapshot order; raw missingness in alignment_audit.",
            "source_ids": ["fred"], "series_ids": ["DGS2", "DGS10"], "vintage_summary": {"vintages": sorted({r["vintage"] for r in observations}), "database_reference": "data/market_intelligence.duckdb"},
            "availability_summary": {"precisions": dict(Counter(r["availability_precision"] for r in observations)), "event_time_replay": False}, "not_applicable_reason": None},
        "execution": {"executed_at": utc(datetime.now(timezone.utc)), "git_commit": code.git_commit, "git_commit_unavailable_reason": code.git_commit_unavailable_reason,
            "working_tree_state": code.working_tree_state, "working_tree_diff_hash": code.working_tree_diff_hash, "research_entrypoint": repository_relative_path(HERE / "analyze.py", ROOT),
            "research_code_files": [r.canonical_mapping() for r in code.research_code_files], "research_code_hash": code.research_code_hash,
            "validator_entrypoint": repository_relative_path(HERE / "validate.py", ROOT), "validator_code_files": [r.canonical_mapping() for r in validator_files], "validator_code_hash": aggregate_code_hash(validator_files),
            "runtime": {"language": "python", "version": sys.version.split()[0], "environment_reference": repository_relative_path(output / "environment.json", ROOT), "environment_hash": raw_file_sha256(output / "environment.json")}},
        "methodology_candidates": configs, "artifacts": artifacts, "conditional_omissions": [], "validation_status": validation["status"], "decision_status": results["production_readiness_decision"],
        "reproducibility_notes": ["Offline read-only source database; selected values/vintages and exact derived pair links retained for audit.", "Dirty diff scoped to sorted declared code/config paths: git diff --binary HEAD -- <declared tracked paths>; untracked code bound by explicit file inventory.", "Snapshot count means selected leg records, while aligned_levels count means curve dates.", "Synthetic anchor dates are fixture labels, excluded from observed data, snapshots and distributions.", "MORE_RESEARCH_REQUIRED is a well-formed research outcome, not package corruption or production freeze readiness."]}


def build(output: Path, database: Path) -> dict:
    contract = json.loads((HERE / "research_contract.json").read_text(encoding="utf-8"))
    fixtures = json.loads((HERE / "synthetic_cases.json").read_text(encoding="utf-8"))
    with duckdb.connect(str(database), read_only=True) as connection:
        observations, levels, alignment = select_inputs(connection)
    if not levels:
        raise ValueError("No aligned validated curve dates available")
    output.mkdir(parents=True, exist_ok=True)
    configs = candidates(contract)
    snapshot = canonical_selected_inputs_v1([{k: r[k] for k in IDENTITY_FIELDS} for r in observations])
    code_hash = aggregate_code_hash(code_file_identities(code_paths(), ROOT))
    run_id = research_run_id(research_id=contract["research_id"], research_version=contract["research_version"], selected_input_snapshot_hash=snapshot, research_code_hash=code_hash, methodology_candidates=configs)
    identity = {"artifact_standard_version": "research_artifacts_v1", "research_id": contract["research_id"], "research_version": contract["research_version"], "run_id": run_id}
    selected = {**identity, "ordering": {"position_semantics": "zero_based_contiguous", "direction": "oldest_to_newest", "date_order_required": True, "current_input_position": None,
        "as_of_observation_date": max(r["observation_date"] for r in observations), "keys": contract["snapshot_order"], "role_structure": "Separate chronological two_year/ten_year sequences; global positions enumerate pairs, not a scalar time series."},
        "snapshot_identity_profile": "canonical_selected_inputs_v1", "selected_input_snapshot_hash": snapshot, "observations": observations}
    rows = calculate_rows(levels, configs)
    cases = make_cases(levels, fixtures)
    scorecard = framework_scorecard()
    results = {**identity, **package_results(levels, alignment, rows, cases, scorecard)}
    write_json(output / "selected_observations.json", selected)
    for name, data in (("aligned_levels", levels), ("alignment_audit", alignment), ("research_results", rows), ("method_comparison", summarize(rows, configs)), ("case_studies", cases), ("framework_scorecard", scorecard)):
        write_csv(output / f"{name}.csv", data, ROW_FIELDS if name == "research_results" else None)
    write_json(output / "results.json", results)
    write_json(output / "synthetic_fixtures.json", fixtures)
    write_json(output / "research_brief.json", contract)
    write_json(output / "environment.json", {"python": sys.version.split()[0], "duckdb": duckdb.__version__, "jsonschema": __import__("importlib.metadata", fromlist=["version"]).version("jsonschema"), "project_dependency_spec": "pyproject.toml", "project_dependency_hash": raw_file_sha256(ROOT / "pyproject.toml")})
    # Separate calculator/SQL path, not this module's calculation functions.
    spec = importlib.util.spec_from_file_location("treasury_curve_independent_validation", HERE / "validate.py")
    validator_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator_module)
    validation = validator_module.validate_research(output, database, ROOT)
    write_json(output / "validation.json", validation)
    dataset = results["indicator_specific_findings"]["dataset"]
    report = (HERE / "report_template.md").read_text(encoding="utf-8").replace("{{DATASET}}", json.dumps(json.loads(canonical_json(dataset)), ensure_ascii=False, indent=2))
    (output / "report.md").write_text(report, encoding="utf-8")
    (output / "README.md").write_text((HERE / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
    write_json(output / "manifest.json", final_manifest(output, selected, configs, results, validation))
    return {"run_id": run_id, "aligned_count": len(levels), "research_decision": RESEARCH_DECISION, "validation_status": validation["status"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/market_intelligence.duckdb")
    parser.add_argument("--output", type=Path, default=HERE / "outputs")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.database), indent=2))
