from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from cross_asset_market_intelligence import __main__ as cli
from cross_asset_market_intelligence.research.artifacts import validate_research_artifacts
from cross_asset_market_intelligence.research.primitives import (
    OrderedSequenceContract,
    RateDifferenceUnit,
    ResearchPrimitiveError,
    aggregate_code_hash,
    canonical_json,
    canonical_selected_inputs_v1,
    code_file_identities,
    git_code_identity,
    rate_difference_to_basis_points,
    raw_file_sha256,
    render_named_fields,
    research_run_id,
    semantic_sha256,
    validate_economic_dates_not_future,
    validate_ordered_input_sequence,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def _artifact(
    logical_name: str,
    path: Path,
    root: Path,
    *,
    artifact_type: str,
    requirement: str,
    authoritative_for: list[str],
    columns: list[dict[str, str]] | None = None,
    row_count: int | None = None,
) -> dict[str, object]:
    return {
        "logical_name": logical_name,
        "relative_path": path.relative_to(root).as_posix(),
        "artifact_type": artifact_type,
        "media_type": {"json": "application/json", "csv": "text/csv", "markdown": "text/markdown"}[artifact_type],
        "requirement": requirement,
        "raw_file_hash": raw_file_sha256(path),
        "authoritative_for": authoritative_for,
        "storage_policy": "committed",
        "external_reference": None,
        "columns": columns or [],
        "column_schema_path": None,
        "row_count": row_count,
    }


def _make_generic_package(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "fixture_repo"
    research_dir = root / "research" / "generic_credit" / "outputs"
    research_dir.mkdir(parents=True)
    analysis = research_dir.parent / "analyze.py"
    validator = research_dir.parent / "validate.py"
    analysis.write_text("# generic non-SOFR research fixture\n", encoding="utf-8")
    validator.write_text("# independent fixture validator\n", encoding="utf-8")
    research_files = code_file_identities([analysis], root)
    validator_files = code_file_identities([validator], root)
    research_hash = aggregate_code_hash(research_files)
    validator_hash = aggregate_code_hash(validator_files)

    observations = [
        {
            "position": 0,
            "indicator_id": "generic_credit_spread",
            "processed_observation_id": "proc_sha256:one",
            "observation_date": "2025-01-02",
            "processing_version": "generic_credit_identity_v1",
            "information_available_at": "2025-01-02T18:00:00Z",
            "availability_precision": "exact_timestamp",
            "retrieved_at": "2025-01-02T18:05:00Z",
        },
        {
            "position": 1,
            "indicator_id": "generic_credit_spread",
            "processed_observation_id": "proc_sha256:two",
            "observation_date": "2025-01-03",
            "processing_version": "generic_credit_identity_v1",
            "information_available_at": "2025-01-03T18:00:00Z",
            "availability_precision": "exact_timestamp",
            "retrieved_at": "2025-01-03T18:05:00Z",
        },
    ]
    projection = [
        {
            key: item[key]
            for key in (
                "position",
                "indicator_id",
                "processed_observation_id",
                "observation_date",
                "processing_version",
                "information_available_at",
                "availability_precision",
                "retrieved_at",
            )
        }
        for item in observations
    ]
    snapshot_hash = canonical_selected_inputs_v1(projection)
    candidates = [{"candidate_id": "generic_spread_change", "parameters": {"lag": 1}, "configuration_reference": None}]
    run_id = research_run_id(
        research_id="generic_credit_research",
        research_version="v1",
        selected_input_snapshot_hash=snapshot_hash,
        research_code_hash=research_hash,
        methodology_candidates=candidates,
    )
    selected_path = research_dir / "selected_observations.json"
    _write_json(
        selected_path,
        {
            "artifact_standard_version": "research_artifacts_v1",
            "research_id": "generic_credit_research",
            "research_version": "v1",
            "run_id": run_id,
            "ordering": {
                "position_semantics": "zero_based_contiguous",
                "direction": "oldest_to_newest",
                "date_order_required": True,
                "current_input_position": 1,
                "as_of_observation_date": "2025-01-03",
            },
            "snapshot_identity_profile": "canonical_selected_inputs_v1",
            "selected_input_snapshot_hash": snapshot_hash,
            "observations": observations,
        },
    )
    results_path = research_dir / "results.json"
    _write_json(
        results_path,
        {
            "artifact_standard_version": "research_artifacts_v1",
            "research_id": "generic_credit_research",
            "research_version": "v1",
            "run_id": run_id,
            "research_status": "READY_FOR_METHODOLOGY_FREEZE",
            "measured_facts": [
                {
                    "fact_id": "fact_001",
                    "statement": "Two generic credit observations were selected.",
                    "evidence_refs": ["selected_observations", "research_results"],
                    "value": 2,
                    "unit": "count",
                }
            ],
            "research_interpretations": [],
            "design_recommendations": [],
            "method_comparison_summary": {
                "applicability": "not_applicable",
                "artifact_ref": None,
                "rationale": "The generic fixture has one declared method.",
            },
            "recommended_evidence_design": {"fixture": "generic"},
            "recommended_horizon_or_reference_design": None,
            "state_recommendation": {"decision": "none", "rationale": "No state methodology is part of this fixture."},
            "known_failure_modes": [],
            "indicator_specific_findings": {"asset_class": "credit"},
            "deferred_questions": [],
            "production_readiness_decision": "READY_FOR_METHODOLOGY_FREEZE",
        },
    )
    validation_path = research_dir / "validation.json"
    _write_json(
        validation_path,
        {
            "artifact_standard_version": "research_artifacts_v1",
            "research_id": "generic_credit_research",
            "research_version": "v1",
            "run_id": run_id,
            "validation_version": "v1",
            "status": "passed",
            "validated_at": "2025-01-03T20:00:00Z",
            "validator": {
                "entrypoint": validator.relative_to(root).as_posix(),
                "code_hash": validator_hash,
                "independence_notes": "Fixture uses a structural invariant path.",
            },
            "checks": [
                {
                    "check_id": "identity_consistent",
                    "description": "Fixture identities are consistent.",
                    "method": "structural_validation",
                    "targets": ["manifest", "results", "validation"],
                    "invariant": "all IDs match",
                    "passed": True,
                    "severity": "blocking",
                    "notes": None,
                }
            ],
            "summary": {"total_checks": 1, "passed": 1, "failed": 0, "warnings": 0},
            "unresolved_limitations": [],
        },
    )
    csv_path = research_dir / "research_results.csv"
    csv_path.write_text("observation_date,spread_change_bp\n2025-01-02,1.25\n2025-01-03,-0.50\n", encoding="utf-8")
    report_path = research_dir / "report.md"
    readme_path = research_dir / "README.md"
    report_path.write_text("# Generic credit research\n\nREADY_FOR_METHODOLOGY_FREEZE\n", encoding="utf-8")
    readme_path.write_text("# Reproduction\n\nGeneric non-SOFR fixture.\n", encoding="utf-8")
    columns = [
        {
            "name": "observation_date",
            "logical_type": "date",
            "unit": "not_applicable",
            "description": "Economic observation date.",
            "null_semantics": "never null",
        },
        {
            "name": "spread_change_bp",
            "logical_type": "number",
            "unit": "basis_point",
            "description": "Generic spread change.",
            "null_semantics": "never null",
        },
    ]
    artifacts = [
        _artifact("selected_observations", selected_path, root, artifact_type="json", requirement="conditional", authoritative_for=["selected_input_set"]),
        _artifact("research_results", csv_path, root, artifact_type="csv", requirement="conditional", authoritative_for=["row_level_evidence"], columns=columns, row_count=2),
        _artifact("results", results_path, root, artifact_type="json", requirement="mandatory", authoritative_for=["research_conclusions", "research_decision"]),
        _artifact("validation", validation_path, root, artifact_type="json", requirement="mandatory", authoritative_for=["independent_validation"]),
        _artifact("report", report_path, root, artifact_type="markdown", requirement="mandatory", authoritative_for=["human_review_narrative"]),
        _artifact("readme", readme_path, root, artifact_type="markdown", requirement="mandatory", authoritative_for=["reproduction_instructions"]),
    ]
    manifest_path = research_dir / "manifest.json"
    _write_json(
        manifest_path,
        {
            "artifact_standard_version": "research_artifacts_v1",
            "research_id": "generic_credit_research",
            "research_version": "v1",
            "run_id": run_id,
            "subject": {
                "signal_id": None,
                "proposed_signal_id": "generic_credit_signal",
                "component_id": "generic_credit_component",
                "indicator_ids": ["generic_credit_spread"],
            },
            "research_status": "READY_FOR_METHODOLOGY_FREEZE",
            "dataset": {
                "applicability": "selected_observations",
                "observation_count": 2,
                "first_observation_date": "2025-01-02",
                "last_observation_date": "2025-01-03",
                "selected_input_snapshot_hash": snapshot_hash,
                "snapshot_identity_profile": "canonical_selected_inputs_v1",
                "input_selection_rule": "Two selected generic credit observations.",
                "source_ids": ["generic_source"],
                "series_ids": ["GENERIC_CREDIT"],
                "vintage_summary": {},
                "availability_summary": {"precision": "exact_timestamp"},
                "not_applicable_reason": None,
            },
            "execution": {
                "executed_at": "2025-01-03T20:00:00Z",
                "git_commit": "0000000000000000000000000000000000000000",
                "git_commit_unavailable_reason": None,
                "working_tree_state": "clean",
                "working_tree_diff_hash": None,
                "research_entrypoint": analysis.relative_to(root).as_posix(),
                "research_code_files": [item.canonical_mapping() for item in research_files],
                "research_code_hash": research_hash,
                "validator_entrypoint": validator.relative_to(root).as_posix(),
                "validator_code_files": [item.canonical_mapping() for item in validator_files],
                "validator_code_hash": validator_hash,
                "runtime": {"language": "python", "version": "3.11", "environment_reference": None, "environment_hash": None},
            },
            "methodology_candidates": candidates,
            "artifacts": artifacts,
            "conditional_omissions": [
                {"logical_name": "method_comparison", "status": "not_applicable", "rationale": "One fixture method."},
                {"logical_name": "case_studies", "status": "not_applicable", "rationale": "No case study is needed for a fixture."},
            ],
            "validation_status": "passed",
            "decision_status": "READY_FOR_METHODOLOGY_FREEZE",
            "reproducibility_notes": ["Generic non-SOFR validator fixture."],
        },
    )
    return root, research_dir


def _rewrite_json(path: Path, mutate) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    _write_json(path, payload)


def test_canonical_hashes_snapshot_run_and_raw_file_are_distinct(tmp_path: Path) -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
    assert semantic_sha256({"b": 1, "a": 2}) == semantic_sha256({"a": 2, "b": 1})
    assert semantic_sha256({"a": 3, "b": 1}) != semantic_sha256({"a": 2, "b": 1})
    ordered = [{"position": 0, "processed_observation_id": "one"}, {"position": 1, "processed_observation_id": "two"}]
    assert canonical_selected_inputs_v1(ordered) != canonical_selected_inputs_v1(list(reversed(ordered)))
    source = tmp_path / "artifact.txt"
    source.write_bytes(b"line-one\n")
    first_hash = raw_file_sha256(source)
    source.write_bytes(b"line-one\r\n")
    assert raw_file_sha256(source) != first_hash
    assert canonical_json({"at": datetime(2025, 1, 1, tzinfo=timezone.utc), "amount": Decimal("1.20")}) == '{"amount":"1.2","at":"2025-01-01T00:00:00Z"}'
    with pytest.raises(Exception):
        canonical_json({"bad": float("nan")})


def test_run_identity_excludes_execution_time_and_sorts_candidates() -> None:
    first = research_run_id(
        research_id="generic", research_version="v1", selected_input_snapshot_hash="sha256:" + "a" * 64,
        research_code_hash="sha256:" + "b" * 64,
        methodology_candidates=[{"candidate_id": "b", "parameters": {}}, {"candidate_id": "a", "parameters": {}}],
    )
    second = research_run_id(
        research_id="generic", research_version="v1", selected_input_snapshot_hash="sha256:" + "a" * 64,
        research_code_hash="sha256:" + "b" * 64,
        methodology_candidates=[{"candidate_id": "a", "parameters": {}}, {"candidate_id": "b", "parameters": {}}],
    )
    changed = research_run_id(
        research_id="generic", research_version="v1", selected_input_snapshot_hash="sha256:" + "c" * 64,
        research_code_hash="sha256:" + "b" * 64,
        methodology_candidates=[{"candidate_id": "a", "parameters": {}}, {"candidate_id": "b", "parameters": {}}],
    )
    assert first == second
    assert first != changed


def test_git_code_identity_records_clean_and_dirty_states_deterministically(tmp_path: Path) -> None:
    repository = tmp_path / "git_fixture"
    repository.mkdir()
    code_path = repository / "analysis.py"
    code_path.write_text("VALUE = 1\n", encoding="utf-8")
    for command in (
        ["git", "init"],
        ["git", "config", "user.email", "fixture@example.invalid"],
        ["git", "config", "user.name", "Fixture"],
        ["git", "add", "analysis.py"],
        ["git", "commit", "-m", "fixture"],
    ):
        subprocess.run(command, cwd=repository, check=True, capture_output=True, text=True)
    clean = git_code_identity(repository_root=repository, declared_code_files=[code_path], declared_tracked_paths=[code_path])
    assert clean.working_tree_state == "clean"
    assert clean.working_tree_diff_hash is None
    code_path.write_text("VALUE = 2\n", encoding="utf-8")
    dirty = git_code_identity(repository_root=repository, declared_code_files=[code_path], declared_tracked_paths=[code_path])
    repeat = git_code_identity(repository_root=repository, declared_code_files=[code_path], declared_tracked_paths=[code_path])
    assert dirty.working_tree_state == "dirty"
    assert dirty.git_commit == clean.git_commit
    assert dirty.working_tree_diff_hash is not None
    assert dirty.working_tree_diff_hash == repeat.working_tree_diff_hash


def test_ordered_dates_prior_only_units_and_named_rendering_are_generic() -> None:
    records = [
        {"position": 0, "processed_observation_id": "proc-a", "observation_date": "2025-01-01"},
        {"position": 1, "processed_observation_id": "proc-b", "observation_date": "2025-01-02"},
    ]
    validate_ordered_input_sequence(
        records,
        contract=OrderedSequenceContract(
            direction="oldest_to_newest", date_order_required=True, current_input_position=1,
            as_of_observation_date=date(2025, 1, 2),
        ),
    )
    validate_ordered_input_sequence(
        [{**record, "position": index} for index, record in enumerate(reversed(records))],
        contract=OrderedSequenceContract(
            direction="newest_to_oldest", date_order_required=True, current_input_position=0,
            as_of_observation_date="2025-01-02",
        ),
    )
    with pytest.raises(ResearchPrimitiveError, match="duplicate processed"):
        validate_ordered_input_sequence(
            [records[0], {**records[1], "processed_observation_id": "proc-a"}],
            contract=OrderedSequenceContract(),
        )
    with pytest.raises(ResearchPrimitiveError, match="future"):
        validate_economic_dates_not_future(records, as_of_observation_date="2024-12-31")
    assert rate_difference_to_basis_points(Decimal("0.02"), source_unit=RateDifferenceUnit.PERCENTAGE_POINT) == Decimal("2.00")
    assert rate_difference_to_basis_points("-0.0001", source_unit="decimal_rate") == Decimal("-1.0000")
    assert rate_difference_to_basis_points(0, source_unit="percentage_point") == 0
    with pytest.raises(ResearchPrimitiveError):
        rate_difference_to_basis_points(0.02, source_unit="percentage_point")
    with pytest.raises(ResearchPrimitiveError):
        rate_difference_to_basis_points("2", source_unit="basis_point")
    assert render_named_fields("{instrument}: {value}", {"instrument": "generic", "value": "ready"}) == "generic: ready"
    with pytest.raises(KeyError):
        render_named_fields("{missing}", {})


def test_generic_non_sofr_research_package_passes_and_cli_is_automation_friendly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, research_dir = _make_generic_package(tmp_path)
    result = validate_research_artifacts(research_dir, repository_root=root)
    assert result.status == "passed", result.as_dict()
    monkeypatch.setattr(sys, "argv", ["prog", "validate-research-artifacts", str(research_dir), "--repo-root", str(root)])
    cli.main()
    assert '"status": "passed"' in capsys.readouterr().out


@pytest.mark.parametrize(
    ("name", "mutate", "needle"),
    [
        ("missing_mandatory", lambda root, directory: (directory / "report.md").unlink(), "Missing mandatory artifact"),
        ("wrong_hash", lambda root, directory: _rewrite_json(directory / "results.json", lambda p: p["measured_facts"][0].__setitem__("statement", "Changed bytes")), "Raw file hash mismatch"),
        (
            "absolute_path",
            lambda root, directory: _rewrite_json(
                directory / "manifest.json", lambda payload: payload["artifacts"][0].__setitem__("relative_path", "C:/absolute.json")
            ),
            "relative_path",
        ),
        (
            "run_id_mismatch",
            lambda root, directory: _rewrite_json(directory / "results.json", lambda payload: payload.__setitem__("run_id", "run_sha256:" + "f" * 64)),
            "Cross-file run_id mismatch",
        ),
        (
            "wrong_snapshot",
            lambda root, directory: _rewrite_json(
                directory / "manifest.json", lambda payload: payload["dataset"].__setitem__("selected_input_snapshot_hash", "sha256:" + "f" * 64)
            ),
            "snapshot hash",
        ),
        (
            "future_selected_input",
            lambda root, directory: _rewrite_json(
                directory / "selected_observations.json", lambda payload: payload["observations"][1].__setitem__("observation_date", "2025-02-01")
            ),
            "future",
        ),
        (
            "duplicate_position",
            lambda root, directory: _rewrite_json(
                directory / "selected_observations.json", lambda payload: payload["observations"][1].__setitem__("position", 0)
            ),
            "positions must be unique",
        ),
        (
            "undeclared_conditional",
            lambda root, directory: (directory / "method_comparison.csv").write_text("method_id\na\n", encoding="utf-8"),
            "missing from the manifest inventory",
        ),
        (
            "nonfinite_csv",
            lambda root, directory: (directory / "research_results.csv").write_text("observation_date,spread_change_bp\n2025-01-02,NaN\n", encoding="utf-8"),
            "non-finite",
        ),
        (
            "invalid_iso_date",
            lambda root, directory: _rewrite_json(
                directory / "selected_observations.json", lambda payload: payload["observations"][0].__setitem__("observation_date", "01/02/2025")
            ),
            "Invalid ISO",
        ),
        (
            "unknown_standard",
            lambda root, directory: _rewrite_json(
                directory / "manifest.json", lambda payload: payload.__setitem__("artifact_standard_version", "research_artifacts_v999")
            ),
            "research_artifacts_v1",
        ),
    ],
)
def test_invalid_research_packages_fail(tmp_path: Path, name: str, mutate, needle: str) -> None:
    root, research_dir = _make_generic_package(tmp_path)
    mutate(root, research_dir)
    result = validate_research_artifacts(research_dir, repository_root=root)
    assert result.status == "failed", (name, result.as_dict())
    assert needle.lower() in json.dumps(result.as_dict()).lower(), (name, result.as_dict())


@pytest.mark.parametrize("defect", ["dangling_reference", "false_pass", "report_conflict", "forbidden_null", "extra_csv_field"])
def test_framework_dogfood_rejects_semantically_inconsistent_package(tmp_path: Path, defect: str) -> None:
    root, directory = _make_generic_package(tmp_path)
    if defect == "dangling_reference":
        _rewrite_json(directory / "results.json", lambda p: p["measured_facts"][0].__setitem__("evidence_refs", ["nonexistent_artifact"]))
    elif defect == "false_pass":
        def mutate_validation(p):
            p["checks"][0]["passed"] = False
            p["summary"] = {"total_checks": 1, "passed": 0, "failed": 1, "warnings": 0}
        _rewrite_json(directory / "validation.json", mutate_validation)
    elif defect == "report_conflict":
        (directory / "report.md").write_text("MORE_RESEARCH_REQUIRED\n", encoding="utf-8")
    elif defect == "forbidden_null":
        (directory / "research_results.csv").write_text("observation_date,spread_change_bp\n2025-01-02,\n", encoding="utf-8")
        _rewrite_json(directory / "manifest.json", lambda p: p["artifacts"][1].__setitem__("row_count", 1))
    else:
        (directory / "research_results.csv").write_text("observation_date,spread_change_bp\n2025-01-02,1,unexpected\n", encoding="utf-8")
        _rewrite_json(directory / "manifest.json", lambda p: p["artifacts"][1].__setitem__("row_count", 1))
    # Repair hashes so this tests semantics, rather than the existing byte-integrity check.
    _rewrite_json(directory / "manifest.json", lambda p: [a.__setitem__("raw_file_hash", raw_file_sha256(root / a["relative_path"])) for a in p["artifacts"]])
    assert validate_research_artifacts(directory, repository_root=root).status == "failed"


def test_ordered_positions_follow_array_order_even_when_dates_tie() -> None:
    with pytest.raises(ResearchPrimitiveError, match="position order"):
        validate_ordered_input_sequence(
            [{"position": 1, "observation_date": "2025-01-01"}, {"position": 0, "observation_date": "2025-01-01"}],
            contract=OrderedSequenceContract(),
        )


@pytest.mark.parametrize("field,value", [("observation_date", "20250102"), ("retrieved_at", "20250102T180000Z"), ("retrieved_at", "2025-01-02T18:00:00")])
def test_non_normative_date_formats_fail_structurally(tmp_path, field, value):
    root, directory = _make_generic_package(tmp_path)
    _rewrite_json(directory / "selected_observations.json", lambda p: p["observations"][0].__setitem__(field, value))
    _rewrite_json(directory / "manifest.json", lambda p: p["artifacts"][0].__setitem__("raw_file_hash", raw_file_sha256(directory / "selected_observations.json")))
    assert validate_research_artifacts(directory, repository_root=root).status == "failed"


def test_nonblocking_validation_limitations_propagate_and_cannot_hide_blocker(tmp_path):
    root, directory = _make_generic_package(tmp_path)
    def warn(p):
        p["status"] = "passed_with_warnings"
        p["unresolved_limitations"] = [{"limitation_id": "availability", "description": "Unknown original publication time", "blocking": False}]
    _rewrite_json(directory / "validation.json", warn)
    def synchronize(p):
        p["validation_status"] = "passed_with_warnings"
        next(a for a in p["artifacts"] if a["logical_name"] == "validation")["raw_file_hash"] = raw_file_sha256(directory / "validation.json")
    _rewrite_json(directory / "manifest.json", synchronize)
    assert validate_research_artifacts(directory, repository_root=root).status == "passed_with_warnings"
    _rewrite_json(directory / "validation.json", lambda p: p["unresolved_limitations"][0].__setitem__("blocking", True))
    _rewrite_json(directory / "manifest.json", synchronize)
    assert validate_research_artifacts(directory, repository_root=root).status == "failed"
