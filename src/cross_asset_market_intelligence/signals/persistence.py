"""Immutable, idempotent persistence for Phase 2 signal contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb

from ..database import initialize_phase_0_schema
from ..exceptions import SignalDefinitionImmutableError, SignalPersistenceError, SignalValidationError
from .contract import SignalDefinition, SignalObservation, canonical_json


def persist_signal_definition(connection: duckdb.DuckDBPyConnection, definition: SignalDefinition) -> bool:
    """Insert an immutable definition, returning false only for an exact replay."""
    initialize_phase_0_schema(connection)
    existing = connection.execute(
        "SELECT indicator_id, name, economic_question, economic_hypothesis, what_it_measures, "
        "what_it_does_not_mean, methodology_description, parameter_definition, limitations, status "
        "FROM signal_definitions WHERE signal_id = ? AND signal_version = ?",
        (definition.signal_id, definition.signal_version),
    ).fetchone()
    expected = definition.canonical_mapping()
    if existing is not None:
        actual = {
            "signal_id": definition.signal_id,
            "signal_version": definition.signal_version,
            "indicator_id": existing[0], "name": existing[1], "economic_question": existing[2],
            "economic_hypothesis": existing[3], "what_it_measures": existing[4],
            "what_it_does_not_mean": existing[5], "methodology_description": existing[6],
            "parameter_definition": _json_value(existing[7]), "limitations": existing[8], "status": existing[9],
        }
        if canonical_json(actual) != canonical_json(expected):
            raise SignalDefinitionImmutableError(
                f"Signal definition {definition.signal_id}/{definition.signal_version} is immutable"
            )
        return False
    connection.execute(
        """INSERT INTO signal_definitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            definition.signal_id, definition.signal_version, definition.indicator_id, definition.name,
            definition.economic_question, definition.economic_hypothesis, definition.what_it_measures,
            definition.what_it_does_not_mean, definition.methodology_description,
            canonical_json(definition.parameter_definition), definition.limitations, definition.status.value,
            datetime.now(timezone.utc),
        ),
    )
    return True


def persist_signal_observation(connection: duckdb.DuckDBPyConnection, observation: SignalObservation) -> bool:
    """Persist an observation with exact inputs; same deterministic observation is a no-op."""
    initialize_phase_0_schema(connection)
    observation.validate()
    _validate_definition_indicator(connection, observation)
    _validate_input_dates(connection, observation)
    identifier = observation.signal_observation_id
    transaction_started = False
    try:
        connection.execute("BEGIN TRANSACTION")
        transaction_started = True
        existing = connection.execute(
            """SELECT indicator_id, as_of_observation_date, information_available_at,
            information_available_date, availability_precision, level_state, direction_state,
            anomaly_state, evidence_quality, evidence, parameters_used, explanation, quality_reasons
            FROM signal_observations WHERE signal_observation_id = ?""",
            (identifier,),
        ).fetchone()
        if existing is not None:
            if canonical_json(_existing_observation_content(existing)) != canonical_json(
                _observation_content(observation)
            ):
                raise SignalValidationError(
                    "A deterministic signal identity already exists with different evidence or states"
                )
            connection.execute("COMMIT")
            return False
        connection.execute(
            """INSERT INTO signal_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                identifier, observation.signal_id, observation.signal_version, observation.indicator_id,
                observation.as_of_observation_date, observation.information_available_at,
                observation.information_available_date, observation.availability_precision.value,
                observation.calculated_at, observation.level_state, observation.direction_state,
                observation.anomaly_state, observation.evidence_quality.value,
                canonical_json(observation.evidence), canonical_json(observation.parameters_used),
                observation.explanation, canonical_json(observation.quality_reasons),
            ),
        )
        for input_ in observation.inputs:
            connection.execute(
                """INSERT INTO signal_observation_inputs VALUES (?, ?, ?, ?)
                ON CONFLICT DO NOTHING""",
                (identifier, input_.processed_observation_id, input_.input_role, input_.window_position),
            )
        connection.execute("COMMIT")
        return True
    except SignalValidationError:
        if transaction_started:
            connection.execute("ROLLBACK")
        raise
    except duckdb.Error as error:
        if transaction_started:
            connection.execute("ROLLBACK")
        raise SignalPersistenceError("Could not persist complete signal observation lineage") from error


def _validate_definition_indicator(connection: duckdb.DuckDBPyConnection, observation: SignalObservation) -> None:
    row = connection.execute(
        "SELECT indicator_id FROM signal_definitions WHERE signal_id = ? AND signal_version = ?",
        (observation.signal_id, observation.signal_version),
    ).fetchone()
    if row is None:
        raise SignalValidationError("Signal observation requires a persisted signal definition")
    if row[0] != observation.indicator_id:
        raise SignalValidationError("Signal observation indicator must match its definition")


def _validate_input_dates(connection: duckdb.DuckDBPyConnection, observation: SignalObservation) -> None:
    identifiers = [input_.processed_observation_id for input_ in observation.inputs]
    placeholders = ", ".join("?" for _ in identifiers)
    rows = connection.execute(
        f"SELECT processed_observation_id, date FROM processed_observations WHERE processed_observation_id IN ({placeholders})",
        identifiers,
    ).fetchall()
    dates = {row[0]: row[1] for row in rows}
    if len(dates) != len(set(identifiers)):
        raise SignalValidationError("Signal observation input lineage references a missing processed observation")
    future = [identifier for identifier, input_date in dates.items() if input_date > observation.as_of_observation_date]
    if future:
        raise SignalValidationError("Signal observation cannot use processed inputs after its as-of date")


def _json_value(value: object) -> object:
    import json

    return json.loads(value) if isinstance(value, str) else value


def _observation_content(observation: SignalObservation) -> dict[str, object]:
    return {
        "indicator_id": observation.indicator_id,
        "as_of_observation_date": observation.as_of_observation_date.isoformat(),
        "information_available_at": (
            None if observation.information_available_at is None else observation.information_available_at.isoformat()
        ),
        "information_available_date": (
            None if observation.information_available_date is None else observation.information_available_date.isoformat()
        ),
        "availability_precision": observation.availability_precision.value,
        "level_state": observation.level_state,
        "direction_state": observation.direction_state,
        "anomaly_state": observation.anomaly_state,
        "evidence_quality": observation.evidence_quality.value,
        "evidence": observation.evidence,
        "parameters_used": observation.parameters_used,
        "explanation": observation.explanation,
        "quality_reasons": list(observation.quality_reasons),
    }


def _existing_observation_content(row: tuple[object, ...]) -> dict[str, object]:
    return {
        "indicator_id": row[0],
        "as_of_observation_date": row[1].isoformat(),
        "information_available_at": None if row[2] is None else row[2].isoformat(),
        "information_available_date": None if row[3] is None else row[3].isoformat(),
        "availability_precision": row[4],
        "level_state": row[5], "direction_state": row[6], "anomaly_state": row[7],
        "evidence_quality": row[8], "evidence": _json_value(row[9]),
        "parameters_used": _json_value(row[10]), "explanation": row[11],
        "quality_reasons": _json_value(row[12]),
    }
