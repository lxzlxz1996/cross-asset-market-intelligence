"""Typed, methodology-neutral contracts for immutable signal evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Mapping

from ..exceptions import SignalValidationError
from ..utils.canonical import canonical_json


class SignalDefinitionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class AvailabilityPrecision(StrEnum):
    EXACT_TIMESTAMP = "exact_timestamp"
    DATE_ONLY = "date_only"
    SOURCE_SCHEDULE = "source_schedule"
    UNKNOWN = "unknown"


class EvidenceQuality(StrEnum):
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, order=True)
class SignalObservationInput:
    """One exact processed input; position zero is the oldest ordered-window item."""

    processed_observation_id: str
    input_role: str
    window_position: int | None = None

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "input_role": self.input_role,
            "processed_observation_id": self.processed_observation_id,
            "window_position": self.window_position,
        }


@dataclass(frozen=True)
class SignalDefinition:
    signal_id: str
    signal_version: str
    indicator_id: str
    name: str
    economic_question: str
    economic_hypothesis: str | None
    what_it_measures: str
    what_it_does_not_mean: str
    methodology_description: str
    parameter_definition: Mapping[str, Any]
    limitations: str
    status: SignalDefinitionStatus

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_version": self.signal_version,
            "indicator_id": self.indicator_id,
            "name": self.name,
            "economic_question": self.economic_question,
            "economic_hypothesis": self.economic_hypothesis,
            "what_it_measures": self.what_it_measures,
            "what_it_does_not_mean": self.what_it_does_not_mean,
            "methodology_description": self.methodology_description,
            "parameter_definition": self.parameter_definition,
            "limitations": self.limitations,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class SignalObservation:
    signal_id: str
    signal_version: str
    indicator_id: str
    as_of_observation_date: date
    information_available_at: datetime | None
    information_available_date: date | None
    availability_precision: AvailabilityPrecision
    calculated_at: datetime
    level_state: str | None
    direction_state: str | None
    anomaly_state: str | None
    evidence_quality: EvidenceQuality
    evidence: Mapping[str, Any]
    parameters_used: Mapping[str, Any]
    explanation: str
    quality_reasons: tuple[str, ...]
    inputs: tuple[SignalObservationInput, ...]

    def validate(self) -> None:
        if not self.inputs:
            raise SignalValidationError("A signal observation requires at least one processed input")
        if self.availability_precision is AvailabilityPrecision.EXACT_TIMESTAMP:
            if self.information_available_at is None or self.information_available_date is not None:
                raise SignalValidationError("exact_timestamp requires only information_available_at")
        elif self.availability_precision is AvailabilityPrecision.DATE_ONLY:
            if self.information_available_at is not None or self.information_available_date is None:
                raise SignalValidationError("date_only requires only information_available_date")
        elif self.information_available_at is not None or self.information_available_date is not None:
            raise SignalValidationError("source_schedule and unknown cannot claim an availability time or date")
        if self.calculated_at.tzinfo is None:
            raise SignalValidationError("calculated_at must be timezone-aware")
        if self.information_available_at is not None and self.information_available_at.tzinfo is None:
            raise SignalValidationError("information_available_at must be timezone-aware")
        if self.information_available_at is not None and self.information_available_at > self.calculated_at:
            raise SignalValidationError("information availability cannot be after calculation time")
        if self.information_available_date is not None and self.information_available_date > self.calculated_at.date():
            raise SignalValidationError("information availability date cannot be after calculation date")
        if len(set(self.inputs)) != len(self.inputs):
            raise SignalValidationError("Signal observation inputs must be unique")
        for input_ in self.inputs:
            if input_.window_position is not None and input_.window_position < 0:
                raise SignalValidationError("window_position must be non-negative")

    def canonical_mapping(self) -> dict[str, Any]:
        self.validate()
        return {
            "identity_algorithm": "signal_observation_sha256_v1",
            "signal_id": self.signal_id,
            "signal_version": self.signal_version,
            "indicator_id": self.indicator_id,
            "as_of_observation_date": self.as_of_observation_date.isoformat(),
            "information_available_at": (
                None if self.information_available_at is None else self.information_available_at.isoformat()
            ),
            "information_available_date": (
                None if self.information_available_date is None else self.information_available_date.isoformat()
            ),
            "availability_precision": self.availability_precision.value,
            "parameters_used": self.parameters_used,
            "inputs": [item.canonical_mapping() for item in sorted(self.inputs)],
        }

    @property
    def signal_observation_id(self) -> str:
        encoded = canonical_json(self.canonical_mapping()).encode("utf-8")
        return f"signal_sha256:{hashlib.sha256(encoded).hexdigest()}"
