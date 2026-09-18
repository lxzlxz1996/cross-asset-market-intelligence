"""Validation for the frozen ``research_artifacts_v1`` package contract."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft7Validator, FormatChecker

from .primitives import (
    OrderedSequenceContract,
    ResearchPrimitiveError,
    aggregate_code_hash,
    canonical_selected_inputs_v1,
    is_safe_repository_relative_path,
    raw_file_sha256,
    repository_relative_path,
    research_run_id,
    validate_ordered_input_sequence,
)


ARTIFACT_STANDARD_VERSION = "research_artifacts_v1"
_MANDATORY_LOGICAL_ARTIFACTS = {"results", "validation", "report", "readme"}
_CONVENTIONAL_FILENAMES = {
    "selected_observations.json": "selected_observations",
    "research_results.csv": "research_results",
    "method_comparison.csv": "method_comparison",
    "case_studies.csv": "case_studies",
    "results.json": "results",
    "validation.json": "validation",
    "report.md": "report",
    "README.md": "readme",
}
_SECRET_KEY_PARTS = ("api_key", "password", "secret", "access_token", "private_key")
_NONFINITE_VALUES = {"nan", "+nan", "-nan", "infinity", "+infinity", "-infinity", "inf", "+inf", "-inf"}


@dataclass(frozen=True)
class ArtifactCheck:
    check_id: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class ArtifactValidationResult:
    research_directory: Path
    checks: list[ArtifactCheck] = field(default_factory=list)

    def add(self, check_id: str, passed: bool, message: str, *, severity: str = "blocking") -> None:
        self.checks.append(ArtifactCheck(check_id, passed, severity, message))

    @property
    def errors(self) -> list[ArtifactCheck]:
        return [check for check in self.checks if not check.passed and check.severity == "blocking"]

    @property
    def warnings(self) -> list[ArtifactCheck]:
        return [check for check in self.checks if not check.passed and check.severity == "warning"]

    @property
    def status(self) -> str:
        if self.errors:
            return "failed"
        if self.warnings:
            return "passed_with_warnings"
        return "passed"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "errors": [check.as_dict() for check in self.errors],
            "warnings": [check.as_dict() for check in self.warnings],
            "checks": [check.as_dict() for check in self.checks],
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _schema_path(name: str) -> Path:
    return _project_root() / "docs" / "research_artifacts" / name


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant is forbidden: {value}")


def _no_duplicate_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def _load_json(path: Path, result: ArtifactValidationResult, logical_name: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_object,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        result.add(f"json.{logical_name}.parse", False, f"{path.name}: {error}")
        return None
    if not isinstance(payload, dict):
        result.add(f"json.{logical_name}.object", False, f"{path.name} must contain a JSON object")
        return None
    if not _all_finite(payload):
        result.add(f"json.{logical_name}.finite", False, f"{path.name} contains a non-finite number")
        return None
    result.add(f"json.{logical_name}.parse", True, f"{path.name} is valid finite JSON")
    return payload


def _all_finite(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_finite(item) for item in value)
    return True


def _validate_schema(
    payload: Mapping[str, Any], schema_filename: str, result: ArtifactValidationResult, logical_name: str
) -> None:
    try:
        schema = json.loads(_schema_path(schema_filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        result.add(f"schema.{logical_name}.load", False, f"Could not load {schema_filename}: {error}")
        return
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: tuple(str(part) for part in item.absolute_path))
    if errors:
        for index, error in enumerate(errors):
            location = ".".join(str(part) for part in error.absolute_path) or "root"
            result.add(f"schema.{logical_name}.{index}", False, f"{location}: {error.message}")
    else:
        result.add(f"schema.{logical_name}", True, f"{logical_name} matches {schema_filename}")


def _resolve_repository_path(value: object, repository_root: Path) -> Path | None:
    if not is_safe_repository_relative_path(value):
        return None
    candidate = (repository_root / PurePosixPath(str(value))).resolve()
    try:
        candidate.relative_to(repository_root.resolve())
    except ValueError:
        return None
    return candidate


def _parse_iso_date(value: object) -> date:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError("Invalid ISO date: expected YYYY-MM-DD")
    return date.fromisoformat(value)


def _parse_iso_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("must be an ISO timestamp string")
    if not FormatChecker().conforms(value, "date-time"):
        raise ValueError("Invalid ISO timestamp: full date/time and timezone required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _validate_no_secrets(payload: Mapping[str, Any], result: ArtifactValidationResult, logical_name: str) -> None:
    def visit(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                lowered = str(key).lower()
                if any(part in lowered for part in _SECRET_KEY_PARTS):
                    result.add(
                        f"secrets.{logical_name}.{path}{key}",
                        False,
                        f"{logical_name} contains forbidden secret-like field name {key!r}",
                    )
                visit(nested, f"{path}{key}.")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, f"{path}{index}.")

    visit(payload, "")
    if not any(check.check_id.startswith(f"secrets.{logical_name}.") and not check.passed for check in result.checks):
        result.add(f"secrets.{logical_name}", True, f"{logical_name} has no obvious secret-like field names")


def _validate_artifact_inventory(
    manifest: Mapping[str, Any], *, research_directory: Path, repository_root: Path, result: ArtifactValidationResult
) -> dict[str, Mapping[str, Any]]:
    inventory: dict[str, Mapping[str, Any]] = {}
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        return inventory
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            result.add(f"inventory.{index}", False, "Artifact inventory item must be an object")
            continue
        logical_name = artifact.get("logical_name")
        if not isinstance(logical_name, str):
            result.add(f"inventory.{index}.logical_name", False, "Artifact logical_name must be a string")
            continue
        if logical_name in inventory:
            result.add(f"inventory.{logical_name}.unique", False, "Artifact logical names must be unique")
            continue
        inventory[logical_name] = artifact
        storage_policy = artifact.get("storage_policy")
        relative_path = artifact.get("relative_path")
        external_reference = artifact.get("external_reference")
        if storage_policy == "external_reference":
            if relative_path is not None or not isinstance(external_reference, str) or not external_reference:
                result.add(
                    f"inventory.{logical_name}.external",
                    False,
                    "External artifact requires null relative_path and a non-empty external_reference",
                )
            else:
                result.add(
                    f"inventory.{logical_name}.external",
                    False,
                    "External artifact integrity cannot be verified by the local validator",
                    severity="warning",
                )
            continue
        resolved = _resolve_repository_path(relative_path, repository_root)
        if resolved is None:
            result.add(
                f"inventory.{logical_name}.path",
                False,
                "Artifact path must be a safe repository-relative POSIX path",
            )
            continue
        if not resolved.is_file():
            result.add(f"inventory.{logical_name}.exists", False, f"Manifest-listed artifact is missing: {relative_path}")
            continue
        if resolved.stat().st_size == 0:
            result.add(f"inventory.{logical_name}.empty", False, f"Artifact may not be an empty placeholder: {relative_path}")
        expected_hash = artifact.get("raw_file_hash")
        actual_hash = raw_file_sha256(resolved)
        if expected_hash != actual_hash:
            result.add(
                f"inventory.{logical_name}.hash",
                False,
                f"Raw file hash mismatch for {relative_path}",
            )
        else:
            result.add(f"inventory.{logical_name}.hash", True, f"Raw file hash matches for {relative_path}")
        if artifact.get("artifact_type") == "csv":
            _validate_csv_artifact(resolved, artifact, result, logical_name)

    for logical_name in _MANDATORY_LOGICAL_ARTIFACTS:
        if logical_name not in inventory:
            result.add(f"inventory.{logical_name}.mandatory", False, f"Mandatory artifact {logical_name} is absent")
    for filename, logical_name in _CONVENTIONAL_FILENAMES.items():
        candidate = research_directory / filename
        if candidate.exists() and logical_name not in inventory:
            result.add(
                f"inventory.{logical_name}.declared",
                False,
                f"Present conventional artifact {filename} is missing from the manifest inventory",
            )
    declared_local_paths = {
        str(item.get("relative_path"))
        for item in inventory.values()
        if item.get("storage_policy") != "external_reference" and isinstance(item.get("relative_path"), str)
    }
    for candidate in research_directory.rglob("*"):
        if not candidate.is_file() or candidate.name == "manifest.json":
            continue
        relative_path = repository_relative_path(candidate, repository_root)
        if relative_path not in declared_local_paths:
            result.add(
                f"inventory.unlisted.{relative_path}",
                False,
                f"Retained local artifact is missing from the manifest inventory: {relative_path}",
            )
    return inventory


def _validate_csv_artifact(path: Path, artifact: Mapping[str, Any], result: ArtifactValidationResult, logical_name: str) -> None:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("UTF-8 BOM is not permitted")
        text = raw.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        header = reader.fieldnames or []
        rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error, ValueError, StopIteration) as error:
        result.add(f"csv.{logical_name}.parse", False, f"Could not parse CSV: {error}")
        return
    if not header or any(not column or column.startswith("Unnamed:") for column in header):
        result.add(f"csv.{logical_name}.header", False, "CSV requires explicit non-hidden header columns")
        return
    if len(set(header)) != len(header):
        result.add(f"csv.{logical_name}.header", False, "CSV header columns must be unique")
    columns = artifact.get("columns")
    if not isinstance(columns, list) or not columns:
        result.add(f"csv.{logical_name}.metadata", False, "CSV artifact requires non-empty manifest column metadata")
        return
    declared_names = [column.get("name") for column in columns if isinstance(column, Mapping)]
    if declared_names != header:
        result.add(f"csv.{logical_name}.columns", False, "CSV header must exactly match manifest column metadata order")
    else:
        result.add(f"csv.{logical_name}.columns", True, "CSV header matches manifest column metadata")
    expected_count = artifact.get("row_count")
    if isinstance(expected_count, int) and expected_count != len(rows):
        result.add(f"csv.{logical_name}.row_count", False, "CSV row count differs from manifest metadata")
    elif isinstance(expected_count, int):
        result.add(f"csv.{logical_name}.row_count", True, "CSV row count matches manifest metadata")
    if not rows:
        result.add(f"csv.{logical_name}.empty", False, "CSV artifact may not be an empty placeholder")
    metadata_by_name = {column["name"]: column for column in columns if isinstance(column, Mapping)}
    for row_index, row in enumerate(rows):
        for column_name, raw_value in row.items():
            if not isinstance(raw_value, str) or column_name is None:
                result.add(f"csv.{logical_name}.row.{row_index}", False, "CSV row has an inconsistent field count")
                continue
            if raw_value.strip().lower() in _NONFINITE_VALUES:
                result.add(
                    f"csv.{logical_name}.nonfinite.{row_index}.{column_name}",
                    False,
                    "CSV contains forbidden non-finite numeric token",
                )
            if raw_value == "":
                if metadata_by_name.get(column_name, {}).get("null_semantics") == "never null":
                    result.add(f"csv.{logical_name}.null.{row_index}.{column_name}", False, "CSV field violates never null semantics")
                continue
            logical_type = metadata_by_name.get(column_name, {}).get("logical_type")
            try:
                if logical_type == "date":
                    _parse_iso_date(raw_value)
                elif logical_type == "timestamp":
                    _parse_iso_timestamp(raw_value)
                elif logical_type == "integer":
                    int(raw_value)
                elif logical_type == "number" and not math.isfinite(float(raw_value)):
                    raise ValueError("number is non-finite")
            except ValueError as error:
                result.add(
                    f"csv.{logical_name}.value.{row_index}.{column_name}",
                    False,
                    f"Invalid {logical_type} value: {error}",
                )


def _selected_input_projection(observations: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projection: list[dict[str, Any]] = []
    common = (
        "position",
        "indicator_id",
        "observation_date",
        "processing_version",
        "information_available_at",
        "availability_precision",
        "retrieved_at",
    )
    for index, observation in enumerate(observations):
        missing = [field for field in common if field not in observation]
        if missing:
            raise ResearchPrimitiveError(f"Selected observation {index} is missing {', '.join(missing)}")
        item = {field: observation[field] for field in common}
        processed_id = observation.get("processed_observation_id")
        if isinstance(processed_id, str) and processed_id:
            item["processed_observation_id"] = processed_id
        elif isinstance(observation.get("external_input_identity"), Mapping):
            item["external_input_identity"] = dict(observation["external_input_identity"])
        else:
            raise ResearchPrimitiveError(
                f"Selected observation {index} requires processed_observation_id or external_input_identity"
            )
        projection.append(item)
    return projection


def _validate_selected_observations(
    path: Path,
    *,
    manifest: Mapping[str, Any],
    repository_root: Path,
    result: ArtifactValidationResult,
) -> None:
    payload = _load_json(path, result, "selected_observations")
    if payload is None:
        return
    required = {
        "artifact_standard_version",
        "research_id",
        "research_version",
        "run_id",
        "ordering",
        "snapshot_identity_profile",
        "selected_input_snapshot_hash",
        "observations",
    }
    missing = sorted(required - set(payload))
    if missing:
        result.add("selected_observations.contract", False, f"Missing selected-input fields: {', '.join(missing)}")
        return
    for field in ("artifact_standard_version", "research_id", "research_version", "run_id"):
        if payload[field] != manifest.get(field):
            result.add(f"selected_observations.identity.{field}", False, f"Selected inputs mismatch manifest {field}")
    if payload["snapshot_identity_profile"] != "canonical_selected_inputs_v1":
        result.add("selected_observations.profile", False, "Unsupported selected-input identity profile")
        return
    observations = payload["observations"]
    ordering = payload["ordering"]
    if not isinstance(observations, list) or not observations or not all(isinstance(item, Mapping) for item in observations):
        result.add("selected_observations.observations", False, "Selected observations must be a non-empty array of objects")
        return
    if not isinstance(ordering, Mapping):
        result.add("selected_observations.ordering", False, "Selected input ordering must be an object")
        return
    try:
        semantics = ordering["position_semantics"]
        direction = ordering["direction"]
        date_order_required = ordering["date_order_required"]
        current_position = ordering["current_input_position"]
        as_of = ordering["as_of_observation_date"]
        if semantics not in {"zero_based_contiguous", "unique_positions"}:
            raise ResearchPrimitiveError("Unsupported selected-input position semantics")
        if not isinstance(date_order_required, bool):
            raise ResearchPrimitiveError("date_order_required must be boolean")
        if current_position is not None and (not isinstance(current_position, int) or isinstance(current_position, bool)):
            raise ResearchPrimitiveError("current_input_position must be an integer or null")
        if as_of is not None:
            _parse_iso_date(as_of)
        for index, observation in enumerate(observations):
            _parse_iso_date(observation["observation_date"])
            _parse_iso_timestamp(observation["retrieved_at"])
            precision = observation["availability_precision"]
            availability = observation["information_available_at"]
            if precision == "exact_timestamp":
                _parse_iso_timestamp(availability)
            elif precision == "date_only":
                _parse_iso_date(availability)
            elif precision in {"unknown", "source_schedule"}:
                if availability is not None:
                    raise ResearchPrimitiveError("Unknown/source-schedule availability must be null")
            else:
                raise ResearchPrimitiveError(f"Selected observation {index} has invalid availability_precision")
        validate_ordered_input_sequence(
            observations,
            contract=OrderedSequenceContract(
                contiguous_positions=semantics == "zero_based_contiguous",
                direction=direction,
                date_order_required=date_order_required,
                current_input_position=current_position,
                as_of_observation_date=as_of,
            ),
        )
        snapshot_hash = canonical_selected_inputs_v1(_selected_input_projection(observations))
    except (KeyError, ResearchPrimitiveError, ValueError) as error:
        result.add("selected_observations.contract", False, str(error))
        return
    if snapshot_hash != payload["selected_input_snapshot_hash"]:
        result.add("selected_observations.snapshot", False, "Selected-input snapshot hash does not recompute")
    elif snapshot_hash != manifest.get("dataset", {}).get("selected_input_snapshot_hash"):
        result.add("selected_observations.snapshot", False, "Selected-input snapshot hash differs from manifest")
    else:
        result.add("selected_observations.snapshot", True, "Selected-input snapshot hash recomputes and matches manifest")
    dataset = manifest.get("dataset", {})
    if dataset.get("observation_count") != len(observations):
        result.add("selected_observations.count", False, "Selected-input count differs from manifest")
    dates = [item["observation_date"] for item in observations]
    if dataset.get("first_observation_date") != min(dates) or dataset.get("last_observation_date") != max(dates):
        result.add("selected_observations.range", False, "Selected-input date range differs from manifest")


def _validate_code_identity(manifest: Mapping[str, Any], repository_root: Path, result: ArtifactValidationResult) -> None:
    execution = manifest.get("execution", {})
    if not isinstance(execution, Mapping):
        return
    for prefix in ("research", "validator"):
        entrypoint = execution.get(f"{prefix}_entrypoint")
        entries = execution.get(f"{prefix}_code_files")
        aggregate = execution.get(f"{prefix}_code_hash")
        entrypoint_path = _resolve_repository_path(entrypoint, repository_root)
        if entrypoint_path is None or not entrypoint_path.is_file():
            result.add(f"code.{prefix}.entrypoint", False, f"Missing or unsafe {prefix} entrypoint")
        if not isinstance(entries, list):
            result.add(f"code.{prefix}.files", False, f"{prefix} code-file list is invalid")
            continue
        normalized: list[dict[str, str]] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                result.add(f"code.{prefix}.{index}", False, "Code-file identity must be an object")
                continue
            relative_path = entry.get("relative_path")
            expected_hash = entry.get("raw_file_hash")
            code_path = _resolve_repository_path(relative_path, repository_root)
            if code_path is None or not code_path.is_file():
                result.add(f"code.{prefix}.{index}.path", False, "Code-file path is missing or unsafe")
                continue
            if raw_file_sha256(code_path) != expected_hash:
                result.add(f"code.{prefix}.{index}.hash", False, "Code-file raw hash mismatch")
            normalized.append({"relative_path": str(relative_path), "raw_file_hash": str(expected_hash)})
        try:
            actual_aggregate = aggregate_code_hash(normalized)
        except ResearchPrimitiveError as error:
            result.add(f"code.{prefix}.aggregate", False, str(error))
            continue
        if actual_aggregate != aggregate:
            result.add(f"code.{prefix}.aggregate", False, "Aggregate code hash does not recompute")
        else:
            result.add(f"code.{prefix}.aggregate", True, "Aggregate code hash recomputes")
        if isinstance(entrypoint, str) and entrypoint not in {item["relative_path"] for item in normalized}:
            result.add(f"code.{prefix}.entrypoint_inventory", False, "Entrypoint is absent from its code-file list")


def _validate_cross_file_identity(
    manifest: Mapping[str, Any], results: Mapping[str, Any], validation: Mapping[str, Any], result: ArtifactValidationResult
) -> None:
    for field in ("artifact_standard_version", "research_id", "research_version", "run_id"):
        if manifest.get(field) != results.get(field) or manifest.get(field) != validation.get(field):
            result.add(f"identity.{field}", False, f"Cross-file {field} mismatch")
    if manifest.get("decision_status") != results.get("production_readiness_decision"):
        result.add("identity.decision", False, "Manifest decision_status differs from results decision")
    if manifest.get("research_status") != results.get("research_status"):
        result.add("identity.research_status", False, "Manifest research_status differs from results research_status")
    if manifest.get("validation_status") != validation.get("status"):
        result.add("identity.validation_status", False, "Manifest validation_status differs from validation status")
    validation_checks = validation.get("checks", [])
    validation_summary = validation.get("summary", {})
    if isinstance(validation_checks, list) and isinstance(validation_summary, Mapping):
        actual_passed = sum(1 for item in validation_checks if isinstance(item, Mapping) and item.get("passed") is True)
        actual_failed = sum(1 for item in validation_checks if isinstance(item, Mapping) and item.get("passed") is False)
        actual_warnings = sum(
            1
            for item in validation_checks
            if isinstance(item, Mapping) and item.get("passed") is False and item.get("severity") == "warning"
        )
        if validation_summary.get("total_checks") != len(validation_checks):
            result.add("validation.summary.total", False, "Validation summary total_checks does not match checks")
        if validation_summary.get("passed") != actual_passed:
            result.add("validation.summary.passed", False, "Validation summary passed count does not match checks")
        if validation_summary.get("failed") != actual_failed:
            result.add("validation.summary.failed", False, "Validation summary failed count does not match checks")
        if validation_summary.get("warnings") != actual_warnings:
            result.add("validation.summary.warnings", False, "Validation summary warnings count does not match checks")
    if validation.get("status") == "failed":
        result.add("validation.finalizable", False, "A failed validation record cannot finalize a research package")
    if any(item.get("passed") is False and item.get("severity") == "blocking" for item in validation_checks):
        result.add("validation.blocking_checks", False, "Validation contains a failed blocking check")
    limitations = validation.get("unresolved_limitations", [])
    if any(item.get("blocking") is True for item in limitations):
        result.add("validation.blocking_limitations", False, "Validation contains a blocking unresolved limitation")
    warning_count = sum(item.get("passed") is False and item.get("severity") == "warning" for item in validation_checks)
    if validation.get("status") == "passed" and (warning_count or limitations):
        result.add("validation.status_truth", False, "Passed validation must not hide warning checks or limitations")
    if validation.get("status") == "passed_with_warnings":
        if not limitations:
            result.add("validation.warning_bounds", False, "Passed-with-warnings requires explicit non-blocking limitations")
        else:
            result.add("validation.inherited_warning", False, "Independent validation has explicit limitations", severity="warning")
    execution = manifest.get("execution", {})
    for suffix, field in (("entrypoint", "entrypoint"), ("code_hash", "code_hash")):
        if validation.get("validator", {}).get(field) != execution.get(f"validator_{suffix}"):
            result.add(f"identity.validator.{suffix}", False, "Validation validator identity differs from manifest")
    if validation.get("status") == "passed_with_warnings":
        limitations = validation.get("unresolved_limitations", [])
        if any(isinstance(item, Mapping) and item.get("blocking") is True for item in limitations):
            result.add("validation.warnings_blocking", False, "Passed-with-warnings package has a blocking limitation")
    try:
        execution = manifest["execution"]
        expected_run_id = research_run_id(
            research_id=manifest["research_id"],
            research_version=manifest["research_version"],
            selected_input_snapshot_hash=manifest["dataset"]["selected_input_snapshot_hash"],
            research_code_hash=execution["research_code_hash"],
            methodology_candidates=manifest["methodology_candidates"],
        )
    except (KeyError, ResearchPrimitiveError) as error:
        result.add("identity.run_id", False, f"Cannot recompute run identity: {error}")
        return
    if expected_run_id != manifest.get("run_id"):
        result.add("identity.run_id", False, "Manifest run_id does not recompute")
    else:
        result.add("identity.run_id", True, "Research run_id recomputes")


def _validate_references_and_report(
    manifest: Mapping[str, Any], results: Mapping[str, Any], validation: Mapping[str, Any],
    inventory: Mapping[str, Mapping[str, Any]], research_directory: Path, result: ArtifactValidationResult,
) -> None:
    """Enforce generic reference ownership and explicit narrative decision, not economics."""
    roots = {"manifest": manifest, "results": results, "validation": validation}
    artifact_ids = set(inventory) | set(roots)
    fact_ids = {item["fact_id"] for item in results["measured_facts"]}
    interpretation_ids = {item["interpretation_id"] for item in results["research_interpretations"]}
    known_ids = artifact_ids | fact_ids | interpretation_ids | {item["candidate_id"] for item in manifest["methodology_candidates"]}

    def resolved(reference: str, allowed: set[str]) -> bool:
        if reference in allowed:
            return True
        root, *fields = reference.split(".")
        if root not in roots or root not in allowed:
            return False
        payload: object = roots[root]
        for field_name in fields:
            if not isinstance(payload, Mapping) or field_name not in payload:
                return False
            payload = payload[field_name]
        return True

    reference_groups = [
        ("facts", [ref for item in results["measured_facts"] for ref in item["evidence_refs"]], artifact_ids),
        ("interpretations", [ref for item in results["research_interpretations"] for ref in item["based_on_fact_ids"]], fact_ids),
        ("recommendations", [ref for item in results["design_recommendations"] for ref in item["basis_refs"]], known_ids),
        ("failures", [ref for item in results["known_failure_modes"] for ref in item["evidence_refs"]], known_ids),
        ("validation", [ref for item in validation["checks"] for ref in item["targets"]], known_ids),
    ]
    for group, references, allowed in reference_groups:
        for reference in references:
            if not resolved(reference, allowed):
                result.add(f"references.{group}", False, f"Unresolvable reference: {reference}")
    omissions = {item["logical_name"] for item in manifest["conditional_omissions"]}
    for name in ("selected_observations", "research_results", "method_comparison", "case_studies"):
        if name not in inventory and name not in omissions:
            result.add(f"omission.{name}", False, "Conditional artifact requires presence or explicit not-applicable rationale")
        if name in inventory and name in omissions:
            result.add(f"omission.{name}", False, "Artifact cannot be present and declared not applicable")
    comparison = results["method_comparison_summary"]
    if comparison["applicability"] == "performed" and comparison["artifact_ref"] != "method_comparison":
        result.add("references.comparison", False, "Performed comparison must reference method_comparison")
    report_path = research_directory / "report.md"
    if report_path.is_file():
        decisions = {"READY_FOR_METHODOLOGY_FREEZE", "MORE_RESEARCH_REQUIRED", "BLOCKED_BY_DATA_OR_ARCHITECTURE"}
        try:
            declared = {line.strip().strip("*` ") for line in report_path.read_text(encoding="utf-8").splitlines()} & decisions
            result.add("identity.report_decision", declared == {manifest["decision_status"]}, "Report must have one explicit matching research decision")
        except (OSError, UnicodeDecodeError) as error:
            result.add("identity.report_decision", False, str(error))


def _find_repository_root(research_directory: Path) -> Path:
    for candidate in (research_directory, *research_directory.parents):
        if (candidate / "pyproject.toml").is_file() or (candidate / ".git").exists():
            return candidate
    return research_directory.parent


def validate_research_artifacts(
    research_directory: Path, *, repository_root: Path | None = None
) -> ArtifactValidationResult:
    """Validate one research package and return machine-readable pass/warning/failure checks."""

    research_directory = research_directory.resolve()
    repository_root = (repository_root or _find_repository_root(research_directory)).resolve()
    result = ArtifactValidationResult(research_directory)
    required_paths = {
        "manifest": research_directory / "manifest.json",
        "results": research_directory / "results.json",
        "validation": research_directory / "validation.json",
        "report": research_directory / "report.md",
        "readme": research_directory / "README.md",
    }
    for logical_name, path in required_paths.items():
        if not path.is_file():
            result.add(f"required.{logical_name}", False, f"Missing mandatory artifact: {path.name}")
    manifest = _load_json(required_paths["manifest"], result, "manifest") if required_paths["manifest"].is_file() else None
    results = _load_json(required_paths["results"], result, "results") if required_paths["results"].is_file() else None
    validation = _load_json(required_paths["validation"], result, "validation") if required_paths["validation"].is_file() else None
    if manifest is None or results is None or validation is None:
        return result
    _validate_schema(manifest, "manifest.schema.json", result, "manifest")
    _validate_schema(results, "results.schema.json", result, "results")
    _validate_schema(validation, "validation.schema.json", result, "validation")
    # Invalid nested schema shapes must return structured errors rather than crash downstream.
    if any(check.check_id.startswith("schema.") and not check.passed for check in result.checks):
        return result
    for logical_name, payload in (("manifest", manifest), ("results", results), ("validation", validation)):
        _validate_no_secrets(payload, result, logical_name)
    if manifest.get("artifact_standard_version") != ARTIFACT_STANDARD_VERSION:
        result.add("standard.version", False, "Unknown artifact standard version")
        return result
    inventory = _validate_artifact_inventory(
        manifest, research_directory=research_directory, repository_root=repository_root, result=result
    )
    _validate_cross_file_identity(manifest, results, validation, result)
    _validate_references_and_report(manifest, results, validation, inventory, research_directory, result)
    _validate_code_identity(manifest, repository_root, result)
    dataset = manifest.get("dataset", {})
    selected_item = inventory.get("selected_observations")
    if dataset.get("applicability") == "selected_observations":
        if selected_item is None:
            result.add("selected_observations.required", False, "Selected observations are applicable but absent")
        else:
            selected_path = _resolve_repository_path(selected_item.get("relative_path"), repository_root)
            if selected_path is not None and selected_path.is_file():
                _validate_selected_observations(
                    selected_path,
                    manifest=manifest,
                    repository_root=repository_root,
                    result=result,
                )
    elif dataset.get("applicability") == "not_applicable":
        omissions = {item.get("logical_name") for item in manifest.get("conditional_omissions", []) if isinstance(item, Mapping)}
        if "selected_observations" not in omissions:
            result.add("selected_observations.omission", False, "No-data package must declare selected_observations not applicable")
    comparison = results.get("method_comparison_summary", {})
    if isinstance(comparison, Mapping) and comparison.get("applicability") == "performed":
        if "method_comparison" not in inventory:
            result.add("method_comparison.required", False, "Performed comparison requires method_comparison artifact")
    return result
