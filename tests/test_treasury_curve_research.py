from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data.treasury_processing import process_approved_fred_treasuries
from cross_asset_market_intelligence.data.treasury_spread_processing import process_treasury_spread
from cross_asset_market_intelligence.database import initialize_phase_0_schema
from cross_asset_market_intelligence.research.artifacts import validate_research_artifacts

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "notebooks/treasury_curve"


def load(name):
    spec = importlib.util.spec_from_file_location(f"curve_research_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analysis = load("analyze")
validation = load("validate")
CONTRACT = json.loads((HERE / "research_contract.json").read_text(encoding="utf-8"))


def raw(c, series, observed, value, vintage="fred_realtime:2025-01-20:9999-12-31"):
    c.execute("INSERT INTO raw_observations VALUES (?,?,?,?,?,?,?,?)", ["fred", series, observed, value, datetime(2025, 1, 21, tzinfo=timezone.utc), None, vintage, "{}"])


@pytest.mark.parametrize("two,ten,expected,label", [("4.20", "4.50", "30", "positive"), ("4.20", "4.20", "0", "zero"), ("4.50", "4.20", "-30", "inverted")])
def test_decimal_spread_sign_resolves_existing_phase1_pair(two, ten, expected, label):
    with duckdb.connect(":memory:") as c:
        initialize_phase_0_schema(c)
        for series, value in (("DGS2", two), ("DGS10", ten)):
            raw(c, series, date(2025, 1, 2), float(value))
        process_approved_fred_treasuries(c)
        process_treasury_spread(c)
        selected, levels, audit = analysis.select_inputs(c)
    assert levels[0]["spread_bp"] == Decimal(expected)
    assert analysis.shape(levels[0]["spread_bp"]) == label
    assert len(selected) == 2 and selected[0]["observation_date"] == selected[1]["observation_date"]
    assert selected[0]["role"] == "two_year" and selected[1]["role"] == "ten_year"
    assert all(r["information_available_at"] is None and r["availability_precision"] == "unknown" for r in selected)
    assert audit[0]["aligned"] == "true"


def test_missing_leg_mismatch_and_latest_null_never_create_filled_pair():
    with duckdb.connect(":memory:") as c:
        initialize_phase_0_schema(c)
        raw(c, "DGS2", date(2025, 1, 2), 4.2)
        raw(c, "DGS10", date(2025, 1, 3), 4.5)
        raw(c, "DGS2", date(2025, 1, 6), 4.2)
        raw(c, "DGS10", date(2025, 1, 6), 4.5)
        process_approved_fred_treasuries(c)
        process_treasury_spread(c)
        raw(c, "DGS10", date(2025, 1, 6), None, "fred_realtime:2025-01-22:9999-12-31")
        selected, levels, audit = analysis.select_inputs(c)
    assert levels == []
    assert not any(r["role"] == "ten_year" and r["observation_date"] == "2025-01-06" for r in selected)
    assert [r["ten_year_status"] for r in audit] == ["source_absent", "available", "source_missing"]
    assert all(r["aligned"] == "false" for r in audit)


def synthetic_levels(spreads):
    return [{"observation_date": (date(2025, 1, 1)+timedelta(days=i)).isoformat(), "two_year_percent": Decimal(4), "ten_year_percent": Decimal(4)+Decimal(s)/100, "spread_bp": Decimal(s)} for i, s in enumerate(spreads)]


def test_prior_only_prefix_invariance_and_reference_excludes_current_change():
    configs = analysis.candidates(CONTRACT)
    levels = synthetic_levels([20, 22, 21, 24, 25, 23, 90, -50])
    prefix = analysis.calculate_rows(levels[:7], configs)
    whole = analysis.calculate_rows(levels, configs)
    assert prefix == whole[:len(prefix)]
    row = next(r for r in prefix if r["observation_date"] == levels[6]["observation_date"] and r["parameter_set_id"] == "change_cdf_5")
    assert row["reference_count"] == 5 and row["strict_pct"] == row["weak_pct"] == 100
    assert row["reference_last_date"] < row["observation_date"]
    assert row["absolute_change_bp"] == 67


def test_round_trip_endpoint_and_slope_conflict_is_not_hidden():
    rows = analysis.calculate_rows(synthetic_levels([0, 0, 50, 0]), analysis.candidates(CONTRACT))
    net = next(r for r in rows if r["parameter_set_id"] == "net_path_3" and r["status"] == "available")
    slope = next(r for r in rows if r["parameter_set_id"] == "slope_3" and r["status"] == "available")
    assert net["value"] == 0 and net["path_absolute_bp"] == 100 and net["path_retention_ratio"] == 0
    assert slope["value"] == 5
    assert analysis.empirical_band(Decimal(0), [Decimal(-60), Decimal(-40), Decimal(-20)])["strict_pct"] == 100
    assert analysis.empirical_band(Decimal(0), [Decimal(20), Decimal(40), Decimal(60)])["strict_pct"] == 0


def test_complete_window_boundaries_do_not_shorten_references():
    rows = analysis.calculate_rows(synthetic_levels(range(8)), analysis.candidates(CONTRACT))
    rarity = [r for r in rows if r["parameter_set_id"] == "change_cdf_5"]
    assert all(r["status"] == "insufficient_history" for r in rarity[:6])
    assert rarity[6]["status"] == "available" and rarity[6]["equal_count"] == 5
    assert rarity[6]["strict_pct"] == 0 and rarity[6]["weak_pct"] == 100
    assert all(r["status"] == "insufficient_history" for r in rows if r["parameter_set_id"] in {"net_path_10", "change_cdf_21", "change_cdf_63"})


def test_saved_package_passes_and_independent_checker_rejects_metric_corruption(tmp_path):
    # Integrity of checked-in real package; no live retrieval and no mutations of source DB.
    package = validate_research_artifacts(HERE / "outputs", repository_root=ROOT)
    assert package.status == "passed_with_warnings", package.as_dict()
    independent = validation.validate_research(HERE / "outputs", None)
    assert not any(not c["passed"] and c["severity"] == "blocking" for c in independent["checks"])
    import shutil
    copied = tmp_path / "copied"
    shutil.copytree(HERE / "outputs", copied)
    # Modify an actual saved, eligible scalar while preserving all other rows/identities.
    saved = validation.read_csv(copied / "research_results.csv")
    saved[0]["value"] = "999"
    analysis.write_csv(copied / "research_results.csv", saved)
    corrupted = validation.validate_research(copied, None)
    assert corrupted["status"] == "failed"
    assert next(c for c in corrupted["checks"] if c["check_id"] == "independent_candidate_metrics")["passed"] is False
