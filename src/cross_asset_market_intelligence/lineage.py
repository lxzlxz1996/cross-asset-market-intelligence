"""Deterministic identity rules for immutable processed observations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .utils.canonical import canonical_json


@dataclass(frozen=True, order=True)
class RawInputIdentity:
    """The complete primary-key identity of one raw input and its semantic role."""

    input_role: str
    raw_source: str
    raw_series_id: str
    raw_observation_date: date
    raw_vintage: str

    def canonical_mapping(self) -> dict[str, str]:
        """Return the stable, JSON-ready representation used in output identity."""
        return {
            "input_role": self.input_role,
            "raw_source": self.raw_source,
            "raw_series_id": self.raw_series_id,
            "raw_observation_date": self.raw_observation_date.isoformat(),
            "raw_vintage": self.raw_vintage,
        }


@dataclass(frozen=True, order=True)
class ProcessedDependencyIdentity:
    """The identity of one upstream processed observation and its semantic role."""

    input_role: str
    input_processed_observation_id: str

    def canonical_mapping(self) -> dict[str, str]:
        """Return the stable, JSON-ready representation used in derived identity."""
        return {
            "input_role": self.input_role,
            "input_processed_observation_id": self.input_processed_observation_id,
        }


def processed_observation_id(
    indicator_id: str,
    observation_date: date,
    processing_version: str,
    inputs: Iterable[RawInputIdentity],
) -> str:
    """Create a stable SHA-256 identity from methodology and exact raw inputs."""
    canonical_inputs = [input_.canonical_mapping() for input_ in sorted(inputs)]
    if not canonical_inputs:
        raise ValueError("A processed observation requires at least one raw input")
    payload = {
        "identity_algorithm": "processed_observation_sha256_v1",
        "indicator_id": indicator_id,
        "observation_date": observation_date.isoformat(),
        "processing_version": processing_version,
        "inputs": canonical_inputs,
    }
    encoded = canonical_json(payload).encode("utf-8")
    return f"proc_sha256:{hashlib.sha256(encoded).hexdigest()}"


def derived_processed_observation_id(
    indicator_id: str,
    observation_date: date,
    processing_version: str,
    dependencies: Iterable[ProcessedDependencyIdentity],
) -> str:
    """Create a stable identity from methodology and exact processed dependencies."""
    canonical_dependencies = [dependency.canonical_mapping() for dependency in sorted(dependencies)]
    if not canonical_dependencies:
        raise ValueError("A derived processed observation requires at least one dependency")
    payload = {
        "identity_algorithm": "processed_observation_sha256_v1",
        "indicator_id": indicator_id,
        "observation_date": observation_date.isoformat(),
        "processing_version": processing_version,
        "dependencies": canonical_dependencies,
    }
    encoded = canonical_json(payload).encode("utf-8")
    return f"proc_sha256:{hashlib.sha256(encoded).hexdigest()}"
