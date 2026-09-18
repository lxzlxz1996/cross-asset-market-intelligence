from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from cross_asset_market_intelligence.data.sofr_processing import process_sofr
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import SignalDefinitionImmutableError, SignalGenerationError
from cross_asset_market_intelligence.signals.contract import EvidenceQuality
from cross_asset_market_intelligence.signals.persistence import persist_signal_definition
from cross_asset_market_intelligence.signals.sofr_rate_state import (
    SOFR_ANOMALY_METHODOLOGY_ID,
    SOFR_LEVEL_INPUT_ROLE,
    build_sofr_rate_state_observation,
    calendar_context,
    generate_sofr_rate_state,
    sofr_rate_state_definition,
)

CALCULATED_AT = datetime(2030, 1, 1, tzinfo=timezone.utc)


def _connection(tmp_path: Path, name: str = "sofr_signal.duckdb") -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / name)
    initialize_phase_0_schema(connection)
    return connection


def _insert_levels(
    connection: duckdb.DuckDBPyConnection,
    changes_bp: list[int | float],
    *,
    dates: list[date] | None = None,
    publication_known: bool = True,
) -> list[date]:
    if dates is None:
        first = date(2025, 1, 1)
        dates = [first + timedelta(days=index) for index in range(len(changes_bp) + 1)]
    assert len(dates) == len(changes_bp) + 1
    values = [Decimal("3.00")]
    for change in changes_bp:
        values.append(values[-1] + Decimal(str(change)) / Decimal("100"))
    publication = datetime(2029, 1, 1, tzinfo=timezone.utc) if publication_known else None
    connection.executemany(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "frbny",
                "SOFR",
                observation_date,
                float(value),
                datetime(2029, 1, 2, tzinfo=timezone.utc),
                publication,
                "frbny_sofr_revision:original",
                "{}",
            )
            for observation_date, value in zip(dates, values)
        ],
    )
    process_sofr(connection)
    return dates


def test_change_math_sign_zero_and_calendar_gaps_use_previous_valid_observation(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    dates = [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 8), date(2026, 1, 9)]
    _insert_levels(connection, [1, -2, 0], dates=dates)
    try:
        expected = ((dates[1], 1.0, 3), (dates[2], -2.0, 3), (dates[3], 0.0, 1))
        for as_of, change, gap in expected:
            observation = build_sofr_rate_state_observation(
                connection, as_of_observation_date=as_of, calculated_at=CALCULATED_AT
            )
            assert observation.evidence["change"] == {
                "previous_observation_date": dates[dates.index(as_of) - 1].isoformat(),
                "calendar_gap_days": gap,
                "change_1obs_bp": change,
                "absolute_change_1obs_bp": abs(change),
            }
            assert all(item.processed_observation_id for item in observation.inputs)
            assert max(item.window_position for item in observation.inputs) == len(observation.inputs) - 1
    finally:
        connection.close()


def test_tie_math_current_exclusion_recent_window_and_contract_absences(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    dates = _insert_levels(connection, [0] * 20 + [1] * 20 + [2] * 20 + [2])
    try:
        observation = build_sofr_rate_state_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    recent = observation.evidence["recent_rarity_60"]
    assert recent == {
        "status": "available",
        "window_count": 60,
        "available_prior_change_count": 60,
        "strict_percentile": pytest.approx(100 * 40 / 60),
        "midrank_percentile": pytest.approx(100 * 50 / 60),
        "weak_percentile": 100.0,
        "less_count": 40,
        "equal_count": 20,
        "greater_count": 0,
        "baseline_start_date": dates[1].isoformat(),
        "baseline_end_date": dates[-2].isoformat(),
    }
    assert observation.evidence_quality is EvidenceQuality.LIMITED
    assert observation.anomaly_state is None
    assert observation.level_state is None and observation.direction_state is None
    assert "robust" not in json.dumps(observation.evidence).lower()
    assert "materiality" not in observation.evidence
    assert observation.evidence["secondary_diagnostics"]["standard_z_60"]["status"] == "available"
    assert len(observation.inputs) == 62
    assert [item.window_position for item in observation.inputs] == list(range(62))
    assert {item.input_role for item in observation.inputs} == {SOFR_LEVEL_INPUT_ROLE}


@pytest.mark.parametrize(
    ("prior_count", "quality", "recent_status", "broad_status"),
    [
        (59, EvidenceQuality.INSUFFICIENT, "insufficient_history", "insufficient_history"),
        (60, EvidenceQuality.LIMITED, "available", "insufficient_history"),
        (251, EvidenceQuality.LIMITED, "available", "insufficient_history"),
        (252, EvidenceQuality.SUFFICIENT, "available", "available"),
    ],
)
def test_warmup_quality_and_no_window_shortening(
    tmp_path: Path,
    prior_count: int,
    quality: EvidenceQuality,
    recent_status: str,
    broad_status: str,
) -> None:
    connection = _connection(tmp_path, f"warmup_{prior_count}.duckdb")
    _insert_levels(connection, [0] * prior_count + [1], publication_known=True)
    try:
        observation = build_sofr_rate_state_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    recent = observation.evidence["recent_rarity_60"]
    broad = observation.evidence["broad_rarity_252"]
    assert observation.evidence_quality is quality
    assert recent["status"] == recent_status and broad["status"] == broad_status
    assert recent["window_count"] == 60 and broad["window_count"] == 252
    if recent_status != "available":
        assert recent["midrank_percentile"] is None
    if broad_status != "available":
        assert broad["midrank_percentile"] is None


def test_standard_z_zero_scale_is_null_without_changing_primary_evidence(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    _insert_levels(connection, [0] * 60 + [1])
    try:
        observation = build_sofr_rate_state_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    diagnostic = observation.evidence["secondary_diagnostics"]["standard_z_60"]
    assert diagnostic == {
        "status": "zero_scale",
        "value": None,
        "prior_mean_bp": 0.0,
        "prior_sample_std_bp": 0.0,
    }
    assert observation.evidence["recent_rarity_60"]["midrank_percentile"] == 100.0
    assert observation.anomaly_state is None


def test_calendar_rule_is_context_only() -> None:
    assert calendar_context(date(2026, 6, 30)) == {
        "rule_id": "gregorian_last_weekday_v1",
        "month_end": True,
        "quarter_end": True,
        "year_end": False,
    }
    assert calendar_context(date(2026, 12, 31))["year_end"] is True
    assert calendar_context(date(2026, 6, 29))["month_end"] is False


def test_calendar_context_does_not_change_scores_or_quality(tmp_path: Path) -> None:
    changes = [index % 5 - 2 for index in range(61)]
    results = []
    for name, last_date in (("ordinary", date(2026, 6, 29)), ("quarter_end", date(2026, 6, 30))):
        connection = _connection(tmp_path, f"calendar_{name}.duckdb")
        dates = [last_date - timedelta(days=len(changes) - index) for index in range(len(changes) + 1)]
        _insert_levels(connection, changes, dates=dates)
        try:
            observation = build_sofr_rate_state_observation(connection, calculated_at=CALCULATED_AT)
            results.append((observation.evidence["recent_rarity_60"], observation.evidence_quality, observation.evidence["calendar_context"]))
        finally:
            connection.close()
    score_fields = (
        "status", "window_count", "available_prior_change_count", "strict_percentile",
        "midrank_percentile", "weak_percentile", "less_count", "equal_count", "greater_count",
    )
    assert {field: results[0][0][field] for field in score_fields} == {
        field: results[1][0][field] for field in score_fields
    }
    assert results[0][1] is results[1][1] is EvidenceQuality.LIMITED
    assert results[0][2]["quarter_end"] is False
    assert results[1][2]["quarter_end"] is True


def test_exact_lineage_as_of_discipline_idempotency_and_explanation(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    dates = _insert_levels(connection, [index % 5 - 2 for index in range(260)])
    requested_as_of = dates[253]
    try:
        first = generate_sofr_rate_state(
            connection, as_of_observation_date=requested_as_of, calculated_at=CALCULATED_AT
        )
        second = generate_sofr_rate_state(
            connection,
            as_of_observation_date=requested_as_of,
            calculated_at=CALCULATED_AT + timedelta(hours=1),
        )
        rows = connection.execute(
            """SELECT input.processed_observation_id, input.input_role, input.window_position,
                      processed.date
               FROM signal_observation_inputs AS input
               JOIN processed_observations AS processed USING (processed_observation_id)
               WHERE signal_observation_id = ? ORDER BY input.window_position""",
            (first.observation.signal_observation_id,),
        ).fetchall()
        counts = connection.execute(
            "SELECT (SELECT count(*) FROM signal_definitions), (SELECT count(*) FROM signal_observations)"
        ).fetchone()
    finally:
        connection.close()
    assert first.definition_inserted is True and first.observation_inserted is True
    assert second.definition_inserted is False and second.observation_inserted is False
    assert first.observation.signal_observation_id == second.observation.signal_observation_id
    assert first.observation.explanation == second.observation.explanation
    assert len(rows) == 254 and counts == (1, 1)
    assert [row[2] for row in rows] == list(range(254))
    assert {row[1] for row in rows} == {SOFR_LEVEL_INPUT_ROLE}
    assert rows[-1][3] == requested_as_of and all(row[3] <= requested_as_of for row in rows)
    assert "No categorical anomaly classification is assigned under v1." in first.observation.explanation


def test_definition_is_active_idempotent_and_immutable(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    definition = sofr_rate_state_definition()
    try:
        assert definition.parameter_definition["anomaly_methodology_id"] == SOFR_ANOMALY_METHODOLOGY_ID
        assert persist_signal_definition(connection, definition) is True
        assert persist_signal_definition(connection, definition) is False
        with pytest.raises(SignalDefinitionImmutableError):
            persist_signal_definition(connection, replace(definition, name="Changed SOFR state"))
    finally:
        connection.close()


def test_missing_exact_as_of_and_missing_previous_fail_without_persistence(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    dates = _insert_levels(connection, [1])
    try:
        with pytest.raises(SignalGenerationError, match="requested as-of date"):
            generate_sofr_rate_state(
                connection,
                as_of_observation_date=dates[-1] + timedelta(days=1),
                calculated_at=CALCULATED_AT,
            )
        with pytest.raises(SignalGenerationError, match="current and previous"):
            generate_sofr_rate_state(
                connection, as_of_observation_date=dates[0], calculated_at=CALCULATED_AT
            )
        assert connection.execute("SELECT count(*) FROM signal_observations").fetchone()[0] == 0
    finally:
        connection.close()


def test_frozen_2026_09_16_golden_example_matches_independent_research(tmp_path: Path) -> None:
    artifact = (
        Path(__file__).resolve().parents[1]
        / "notebooks"
        / "sofr_daily_change_anomaly"
        / "outputs_phase_2_1b_2"
        / "selected_observations.json"
    )
    selected = json.loads(artifact.read_text(encoding="utf-8"))[-254:]
    connection = _connection(tmp_path)
    connection.executemany(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["raw_source"],
                row["raw_series_id"],
                date.fromisoformat(row["date"]),
                row["sofr_percent"],
                datetime.fromisoformat(row["retrieval_timestamp"]),
                None,
                row["raw_vintage"],
                "{}",
            )
            for row in selected
        ],
    )
    process_sofr(connection)
    try:
        result = generate_sofr_rate_state(connection, calculated_at=CALCULATED_AT)
        saved_inputs = connection.execute(
            "SELECT processed_observation_id FROM signal_observation_inputs WHERE signal_observation_id = ?",
            (result.observation.signal_observation_id,),
        ).fetchall()
    finally:
        connection.close()
    observation = result.observation
    recent = observation.evidence["recent_rarity_60"]
    broad = observation.evidence["broad_rarity_252"]
    diagnostics = observation.evidence["secondary_diagnostics"]
    assert observation.as_of_observation_date == date(2026, 9, 16)
    assert observation.evidence["change"]["change_1obs_bp"] == -2.0
    assert (recent["less_count"], recent["equal_count"], recent["greater_count"]) == (34, 15, 11)
    assert recent["strict_percentile"] == pytest.approx(56.666666666666664)
    assert recent["midrank_percentile"] == pytest.approx(69.16666666666667)
    assert recent["weak_percentile"] == pytest.approx(81.66666666666667)
    assert (broad["less_count"], broad["equal_count"], broad["greater_count"]) == (126, 46, 80)
    assert broad["strict_percentile"] == 50.0
    assert broad["midrank_percentile"] == pytest.approx(59.12698412698413)
    assert broad["weak_percentile"] == pytest.approx(68.25396825396825)
    assert diagnostics["standard_z_60"]["value"] == pytest.approx(-0.968731893106422)
    assert diagnostics["standard_z_252"]["value"] == pytest.approx(-0.3788316332971471)
    assert observation.evidence["calendar_context"] == {
        "rule_id": "gregorian_last_weekday_v1",
        "month_end": False,
        "quarter_end": False,
        "year_end": False,
    }
    assert observation.evidence_quality is EvidenceQuality.LIMITED
    assert observation.quality_reasons == ("information_availability_unknown",)
    assert observation.anomaly_state is None
    assert len(saved_inputs) == 254
    assert {row[0] for row in saved_inputs} == {row["processed_observation_id"] for row in selected}
