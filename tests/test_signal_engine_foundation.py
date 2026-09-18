from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import SignalDefinitionImmutableError, SignalValidationError
from cross_asset_market_intelligence.signals.contract import AvailabilityPrecision, EvidenceQuality, SignalDefinition, SignalDefinitionStatus, SignalObservation, SignalObservationInput
from cross_asset_market_intelligence.signals.explanations import render_explanation
from cross_asset_market_intelligence.signals.persistence import persist_signal_definition, persist_signal_observation


def _connection(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / "signals.duckdb")
    initialize_phase_0_schema(connection)
    return connection


def _definition(**changes: object) -> SignalDefinition:
    values: dict[str, object] = {
        "signal_id": "example_signal", "signal_version": "v1", "indicator_id": "synthetic_indicator",
        "name": "Example signal contract", "economic_question": "What does a synthetic input demonstrate?",
        "economic_hypothesis": "This is a non-production test fixture.",
        "what_it_measures": "Contract persistence only.",
        "what_it_does_not_mean": "A market, regime, or allocation conclusion.",
        "methodology_description": "No quantitative methodology is implemented.",
        "parameter_definition": {"window": "fixture"}, "limitations": "Synthetic fixture only.",
        "status": SignalDefinitionStatus.DRAFT,
    }
    values.update(changes)
    return SignalDefinition(**values)  # type: ignore[arg-type]


def _insert_processed(connection: duckdb.DuckDBPyConnection, identifier: str, observation_date: date) -> None:
    connection.execute(
        "INSERT INTO processed_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
        (identifier, "synthetic_indicator", observation_date, 1.0, "fixture_v1", "fixture_only", datetime(2026, 9, 16, tzinfo=timezone.utc)),
    )


def _observation(**changes: object) -> SignalObservation:
    values: dict[str, object] = {
        "signal_id": "example_signal", "signal_version": "v1", "indicator_id": "synthetic_indicator",
        "as_of_observation_date": date(2026, 9, 15), "information_available_at": None,
        "information_available_date": None, "availability_precision": AvailabilityPrecision.UNKNOWN,
        "calculated_at": datetime(2026, 9, 16, tzinfo=timezone.utc), "level_state": None,
        "direction_state": "rising", "anomaly_state": "unusual", "evidence_quality": EvidenceQuality.SUFFICIENT,
        "evidence": {"some_measure": 2.4}, "parameters_used": {"window": "fixture"},
        "explanation": "Synthetic evidence is rising and unusual.", "quality_reasons": ("complete_lineage",),
        "inputs": (SignalObservationInput("proc-1", "lookback_window", 0),),
    }
    values.update(changes)
    return SignalObservation(**values)  # type: ignore[arg-type]


def test_definition_is_idempotent_but_incompatible_version_is_immutable(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        definition = _definition()
        assert persist_signal_definition(connection, definition) is True
        assert persist_signal_definition(connection, definition) is False
        with pytest.raises(SignalDefinitionImmutableError):
            persist_signal_definition(connection, _definition(name="Changed semantics"))
    finally:
        connection.close()


def test_observation_persists_idempotently_with_orthogonal_states_and_exact_lineage(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 14))
        _insert_processed(connection, "proc-2", date(2026, 9, 15))
        observation = _observation(inputs=(SignalObservationInput("proc-1", "lookback_window", 0), SignalObservationInput("proc-2", "current_observation", 1)))
        assert persist_signal_observation(connection, observation) is True
        assert persist_signal_observation(connection, observation) is False
        states = connection.execute("SELECT direction_state, anomaly_state FROM signal_observations").fetchone()
        inputs = connection.execute("SELECT processed_observation_id, input_role, window_position FROM signal_observation_inputs ORDER BY window_position").fetchall()
    finally:
        connection.close()
    assert states == ("rising", "unusual")
    assert inputs == [("proc-1", "lookback_window", 0), ("proc-2", "current_observation", 1)]


def test_nullable_state_dimensions_and_unknown_availability_are_valid(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 15))
        persist_signal_observation(connection, _observation(level_state=None, direction_state=None, anomaly_state=None))
        row = connection.execute("SELECT information_available_at, information_available_date, availability_precision, level_state, direction_state, anomaly_state FROM signal_observations").fetchone()
    finally:
        connection.close()
    assert row == (None, None, "unknown", None, None, None)


def test_unordered_input_role_can_omit_window_position(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 15))
        observation = _observation(inputs=(SignalObservationInput("proc-1", "benchmark"),))
        persist_signal_observation(connection, observation)
        row = connection.execute("SELECT input_role, window_position FROM signal_observation_inputs").fetchone()
    finally:
        connection.close()
    assert row == ("benchmark", None)


def test_exact_and_date_only_availability_preserve_honest_precision(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 15))
        exact = _observation(information_available_at=datetime(2026, 9, 15, 16, tzinfo=timezone.utc), availability_precision=AvailabilityPrecision.EXACT_TIMESTAMP)
        assert persist_signal_observation(connection, exact) is True
        date_only = _observation(information_available_date=date(2026, 9, 15), availability_precision=AvailabilityPrecision.DATE_ONLY, evidence={"some_measure": 2.5})
        assert persist_signal_observation(connection, date_only) is True
    finally:
        connection.close()


def test_evidence_and_parameters_are_canonical_and_round_trip(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 15))
        persist_signal_observation(connection, _observation(evidence={"b": 2, "a": 1}, parameters_used={"z": [1, 2]}))
        row = connection.execute("SELECT evidence::VARCHAR, parameters_used::VARCHAR FROM signal_observations").fetchone()
    finally:
        connection.close()
    assert row == ('{"a":1,"b":2}', '{"z":[1,2]}')


def test_same_identity_with_different_evidence_is_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 15))
        persist_signal_observation(connection, _observation())
        with pytest.raises(SignalValidationError, match="different evidence"):
            persist_signal_observation(connection, _observation(evidence={"some_measure": 99.0}))
    finally:
        connection.close()


def test_future_processed_input_is_rejected_without_claiming_intraday_availability(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        persist_signal_definition(connection, _definition())
        _insert_processed(connection, "proc-1", date(2026, 9, 16))
        with pytest.raises(SignalValidationError, match="after its as-of date"):
            persist_signal_observation(connection, _observation())
    finally:
        connection.close()


def test_unknown_availability_cannot_claim_a_date_or_timestamp() -> None:
    with pytest.raises(SignalValidationError, match="cannot claim"):
        _observation(information_available_date=date(2026, 9, 15)).validate()


def test_deterministic_explanation_template_is_stable() -> None:
    template = "{signal_name}: direction={direction}; anomaly={anomaly}."
    values = {"signal_name": "Example", "direction": "rising", "anomaly": "unusual"}
    assert render_explanation(template, values) == render_explanation(template, values)
    assert render_explanation(template, values) == "Example: direction=rising; anomaly=unusual."
