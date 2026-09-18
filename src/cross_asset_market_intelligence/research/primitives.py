"""Deterministic primitives shared by research artifacts, never signal methodology."""

from __future__ import annotations

import hashlib
import math
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..signals.explanations import render_explanation
from ..utils.canonical import canonical_json, canonical_json_bytes, raw_file_sha256, semantic_sha256


class ResearchPrimitiveError(ValueError):
    """Raised when a generic identity, ordering, date, or unit contract is invalid."""


def canonical_selected_inputs_v1(identity_projection: Sequence[Mapping[str, Any]]) -> str:
    """Hash an already-normalized, order-bearing selected-input identity projection."""

    if not isinstance(identity_projection, Sequence) or isinstance(identity_projection, (str, bytes)):
        raise ResearchPrimitiveError("Selected-input identity projection must be an ordered sequence")
    return semantic_sha256(list(identity_projection))


def research_run_id(
    *,
    research_id: str,
    research_version: str,
    selected_input_snapshot_hash: str | None,
    research_code_hash: str,
    methodology_candidates: Sequence[Mapping[str, Any]],
) -> str:
    """Return the content identity for one research code/input/configuration combination."""

    normalized_candidates: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    for candidate in methodology_candidates:
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ResearchPrimitiveError("Every run-identity candidate requires a non-empty candidate_id")
        if candidate_id in candidate_ids:
            raise ResearchPrimitiveError("Run-identity candidate IDs must be unique")
        candidate_ids.add(candidate_id)
        normalized_candidates.append(dict(candidate))
    payload = {
        "run_identity_profile": "research_run_v1",
        "artifact_standard_version": "research_artifacts_v1",
        "research_id": research_id,
        "research_version": research_version,
        "selected_input_snapshot_hash": selected_input_snapshot_hash,
        "research_code_hash": research_code_hash,
        "methodology_candidates": sorted(normalized_candidates, key=lambda item: item["candidate_id"]),
    }
    return f"run_sha256:{semantic_sha256(payload).removeprefix('sha256:')}"


def repository_relative_path(path: Path, repository_root: Path) -> str:
    """Return a portable slash-separated path or reject a path outside the repository."""

    try:
        relative = path.resolve().relative_to(repository_root.resolve())
    except ValueError as error:
        raise ResearchPrimitiveError("Path must be inside the repository root") from error
    return relative.as_posix()


def is_safe_repository_relative_path(value: object) -> bool:
    """Return whether a manifest path is a portable repository-relative POSIX path."""

    if not isinstance(value, str) or not value or "\\" in value:
        return False
    candidate = Path(value)
    if candidate.is_absolute() or (len(value) >= 2 and value[1] == ":"):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


@dataclass(frozen=True)
class CodeFileIdentity:
    """One repository-relative executable code file and its raw-byte hash."""

    relative_path: str
    raw_file_hash: str

    def canonical_mapping(self) -> dict[str, str]:
        return {"relative_path": self.relative_path, "raw_file_hash": self.raw_file_hash}


def code_file_identities(paths: Iterable[Path], repository_root: Path) -> tuple[CodeFileIdentity, ...]:
    """Build a deterministic, path-sorted identity list for declared executable files."""

    identities = tuple(
        sorted(
            (
                CodeFileIdentity(repository_relative_path(path, repository_root), raw_file_sha256(path))
                for path in paths
            ),
            key=lambda item: item.relative_path,
        )
    )
    if not identities:
        raise ResearchPrimitiveError("At least one code file identity is required")
    if len({item.relative_path for item in identities}) != len(identities):
        raise ResearchPrimitiveError("Code file identity paths must be unique")
    return identities


def aggregate_code_hash(code_files: Sequence[CodeFileIdentity | Mapping[str, str]]) -> str:
    """Hash the declared code-file inventory, independent of caller ordering."""

    normalized: list[dict[str, str]] = []
    for item in code_files:
        mapping = item.canonical_mapping() if isinstance(item, CodeFileIdentity) else dict(item)
        path = mapping.get("relative_path")
        file_hash = mapping.get("raw_file_hash")
        if not is_safe_repository_relative_path(path) or not isinstance(file_hash, str):
            raise ResearchPrimitiveError("Invalid code file identity")
        normalized.append({"relative_path": path, "raw_file_hash": file_hash})
    normalized.sort(key=lambda item: item["relative_path"])
    if not normalized or len({item["relative_path"] for item in normalized}) != len(normalized):
        raise ResearchPrimitiveError("Code file identities must be non-empty and path-unique")
    return semantic_sha256(normalized)


@dataclass(frozen=True)
class GitCodeIdentity:
    """Mechanical Git and code identity suitable for a research manifest."""

    git_commit: str | None
    git_commit_unavailable_reason: str | None
    working_tree_state: str
    working_tree_diff_hash: str | None
    research_code_files: tuple[CodeFileIdentity, ...]
    research_code_hash: str


def git_code_identity(
    *, repository_root: Path, declared_code_files: Iterable[Path], declared_tracked_paths: Iterable[Path] | None = None
) -> GitCodeIdentity:
    """Capture Git state without storing a patch body; unavailable Git is represented honestly."""

    code_files = code_file_identities(declared_code_files, repository_root)
    code_hash = aggregate_code_hash(code_files)
    tracked_paths = tuple(declared_tracked_paths or ())
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, check=True, capture_output=True, text=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        dirty = bool(status.strip())
        if not dirty:
            return GitCodeIdentity(commit, None, "clean", None, code_files, code_hash)
        relative_paths = sorted(repository_relative_path(path, repository_root) for path in tracked_paths)
        diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD", "--", *relative_paths],
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
        return GitCodeIdentity(
            commit,
            None,
            "dirty",
            f"sha256:{hashlib.sha256(diff).hexdigest()}",
            code_files,
            code_hash,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        return GitCodeIdentity(
            None,
            f"Git metadata unavailable: {type(error).__name__}",
            "unavailable",
            None,
            code_files,
            code_hash,
        )


def _coerce_date(value: date | str) -> date:
    if isinstance(value, datetime):
        raise ResearchPrimitiveError("Economic-date validation requires dates, not timestamps")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            if len(value) != 10 or value[4] != "-" or value[7] != "-":
                raise ValueError("Full ISO date required")
            return date.fromisoformat(value)
        except ValueError as error:
            raise ResearchPrimitiveError(f"Invalid ISO observation date: {value}") from error
    raise ResearchPrimitiveError("Observation date must be a date or ISO date string")


def validate_economic_dates_not_future(
    records: Iterable[Mapping[str, Any]], *, as_of_observation_date: date | str, date_field: str = "observation_date"
) -> None:
    """Reject economically future observations; this does not prove availability-time validity."""

    as_of = _coerce_date(as_of_observation_date)
    for index, record in enumerate(records):
        if date_field not in record:
            raise ResearchPrimitiveError(f"Record {index} is missing {date_field}")
        observed = _coerce_date(record[date_field])
        if observed > as_of:
            raise ResearchPrimitiveError(
                f"Record {index} has economically future {date_field} {observed.isoformat()} after {as_of.isoformat()}"
            )


@dataclass(frozen=True)
class OrderedSequenceContract:
    """Methodology-declared mechanics for one ordered input sequence."""

    position_field: str = "position"
    processed_id_field: str = "processed_observation_id"
    date_field: str = "observation_date"
    contiguous_positions: bool = True
    direction: str = "declared"
    date_order_required: bool = False
    current_input_position: int | None = None
    as_of_observation_date: date | str | None = None
    allow_duplicate_processed_ids: bool = False


def validate_ordered_input_sequence(
    records: Sequence[Mapping[str, Any]], *, contract: OrderedSequenceContract
) -> None:
    """Validate generic position, date, duplicate, and current-location invariants."""

    if not records:
        raise ResearchPrimitiveError("Ordered input sequence cannot be empty")
    if contract.direction not in {"oldest_to_newest", "newest_to_oldest", "declared"}:
        raise ResearchPrimitiveError("Ordered sequence direction must be oldest_to_newest, newest_to_oldest, or declared")
    positions: list[int] = []
    processed_ids: list[str] = []
    dates: list[date] = []
    for index, record in enumerate(records):
        position = record.get(contract.position_field)
        if not isinstance(position, int) or isinstance(position, bool) or position < 0:
            raise ResearchPrimitiveError(f"Record {index} has invalid non-negative integer position")
        positions.append(position)
        processed_id = record.get(contract.processed_id_field)
        if processed_id is not None:
            if not isinstance(processed_id, str) or not processed_id:
                raise ResearchPrimitiveError(f"Record {index} has invalid processed observation ID")
            processed_ids.append(processed_id)
        if contract.date_field in record:
            dates.append(_coerce_date(record[contract.date_field]))
        elif contract.date_order_required or contract.as_of_observation_date is not None:
            raise ResearchPrimitiveError(f"Record {index} is missing {contract.date_field}")
    if len(set(positions)) != len(positions):
        raise ResearchPrimitiveError("Ordered input positions must be unique")
    if contract.contiguous_positions and sorted(positions) != list(range(len(positions))):
        raise ResearchPrimitiveError("Ordered input positions must be contiguous from zero")
    if positions != sorted(positions):
        raise ResearchPrimitiveError("Ordered input position order must agree with array order")
    if not contract.allow_duplicate_processed_ids and len(set(processed_ids)) != len(processed_ids):
        raise ResearchPrimitiveError("Ordered input sequence has duplicate processed observation IDs")
    if contract.current_input_position is not None and contract.current_input_position not in positions:
        raise ResearchPrimitiveError("Declared current input position is absent from ordered sequence")
    if contract.as_of_observation_date is not None:
        validate_economic_dates_not_future(
            records,
            as_of_observation_date=contract.as_of_observation_date,
            date_field=contract.date_field,
        )
    if contract.date_order_required:
        if len(dates) != len(records):
            raise ResearchPrimitiveError("Date-ordered sequence requires one date per record")
        if contract.direction == "declared":
            raise ResearchPrimitiveError("Date-ordered sequence requires explicit chronological direction")
        pairs = zip(dates, dates[1:])
        if contract.direction == "oldest_to_newest" and any(left > right for left, right in pairs):
            raise ResearchPrimitiveError("Ordered dates violate oldest_to_newest direction")
        if contract.direction == "newest_to_oldest" and any(left < right for left, right in pairs):
            raise ResearchPrimitiveError("Ordered dates violate newest_to_oldest direction")


class RateDifferenceUnit(StrEnum):
    """Explicit source semantics accepted by the opt-in basis-point converter."""

    PERCENTAGE_POINT = "percentage_point"
    DECIMAL_RATE = "decimal_rate"


def rate_difference_to_basis_points(value: Decimal | str | int, *, source_unit: RateDifferenceUnit | str) -> Decimal:
    """Convert an explicit rate difference to bp without guessing its source unit."""

    if isinstance(value, float):
        raise ResearchPrimitiveError("Float input is not accepted for Decimal-safe basis-point conversion")
    try:
        decimal_value = Decimal(str(value))
        unit = RateDifferenceUnit(source_unit)
    except (ArithmeticError, ValueError) as error:
        raise ResearchPrimitiveError("Unsupported rate difference value or source unit") from error
    if not decimal_value.is_finite():
        raise ResearchPrimitiveError("Basis-point conversion requires a finite value")
    multiplier = Decimal("100") if unit is RateDifferenceUnit.PERCENTAGE_POINT else Decimal("10000")
    return decimal_value * multiplier


def render_named_fields(template: str, values: Mapping[str, object]) -> str:
    """Expose the existing strict named-field renderer without adding economic wording."""

    return render_explanation(template, values)
