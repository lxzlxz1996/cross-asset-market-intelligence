from __future__ import annotations

import csv
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
    generate_sofr_rate_state,
    sofr_rate_state_definition,
)
from cross_asset_market_intelligence.signals.sofr_rate_state_v2 import (
    SOFR_DIRECTION_METHODOLOGY_ID,
    SOFR_RATE_STATE_V2_PARAMETERS,
    _validate_direction_evidence,
    build_sofr_rate_state_v2_observation,
    generate_sofr_rate_state_v2,
    sofr_rate_state_v2_definition,
)

CALCULATED_AT = datetime(2030, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
HISTORY_ARTIFACT = (
    ROOT / "notebooks" / "sofr_daily_change_anomaly" /
    "outputs_phase_2_1b_2" / "selected_observations.json"
)
DIRECTION_ROWS = ROOT / "notebooks" / "sofr_direction" / "outputs" / "direction_research.csv"
FROZEN_V1_GOLDEN_ID = "signal_sha256:608e2c405d933340bce628620c2964b23611be053d3e45e0df2c0dfaec57b793"


def _connection(tmp_path: Path, name: str) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / name)
    initialize_phase_0_schema(connection)
    return connection


def _insert_levels(
    connection: duckdb.DuckDBPyConnection,
    changes_bp: list[int | float],
    *,
    publication_known: bool = True,
) -> list[date]:
    first = date(2025, 1, 1)
    dates = [first + timedelta(days=index) for index in range(len(changes_bp) + 1)]
    values = [Decimal("3.00")]
    for change in changes_bp:
        values.append(values[-1] + Decimal(str(change)) / Decimal("100"))
    publication = datetime(2029, 1, 1, tzinfo=timezone.utc) if publication_known else None
    connection.executemany(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "frbny", "SOFR", observation_date, float(value),
                datetime(2029, 1, 2, tzinfo=timezone.utc), publication,
                "frbny_sofr_revision:original", "{}",
            )
            for observation_date, value in zip(dates, values)
        ],
    )
    process_sofr(connection)
    return dates


def _insert_frozen_history_through(
    connection: duckdb.DuckDBPyConnection, anchor: str
) -> list[dict[str, object]]:
    history = json.loads(HISTORY_ARTIFACT.read_text(encoding="utf-8"))
    anchor_index = next(index for index, row in enumerate(history) if row["date"] == anchor)
    selected = history[max(0, anchor_index - 253):anchor_index + 1]
    connection.executemany(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["raw_source"], row["raw_series_id"], date.fromisoformat(row["date"]),
                row["sofr_percent"], datetime.fromisoformat(row["retrieval_timestamp"]),
                None, row["raw_vintage"], "{}",
            )
            for row in selected
        ],
    )
    process_sofr(connection)
    return selected


def _direction_row(anchor: str) -> dict[str, str]:
    with DIRECTION_ROWS.open(encoding="utf-8", newline="") as handle:
        return next(row for row in csv.DictReader(handle) if row["date"] == anchor)


def test_v1_is_unchanged_and_v2_is_distinct_immutable_and_idempotent(tmp_path: Path) -> None:
    connection = _connection(tmp_path, "versions.duckdb")
    _insert_frozen_history_through(connection, "2026-09-16")
    try:
        v1_first = generate_sofr_rate_state(connection, calculated_at=CALCULATED_AT)
        v1_replay = generate_sofr_rate_state(
            connection, calculated_at=CALCULATED_AT + timedelta(minutes=1)
        )
        v2_first = generate_sofr_rate_state_v2(connection, calculated_at=CALCULATED_AT)
        v2_replay = generate_sofr_rate_state_v2(
            connection, calculated_at=CALCULATED_AT + timedelta(minutes=1)
        )
        definitions = connection.execute(
            "SELECT signal_version FROM signal_definitions WHERE signal_id = 'sofr_rate_state' "
            "ORDER BY signal_version"
        ).fetchall()
        with pytest.raises(SignalDefinitionImmutableError):
            persist_signal_definition(
                connection, replace(sofr_rate_state_v2_definition(), name="Changed v2")
            )
    finally:
        connection.close()

    assert v1_first.observation.signal_observation_id == FROZEN_V1_GOLDEN_ID
    assert v1_replay.observation.signal_observation_id == FROZEN_V1_GOLDEN_ID
    assert "direction_evidence" not in v1_first.observation.evidence
    assert v1_first.observation.evidence == v1_replay.observation.evidence
    assert sofr_rate_state_definition().parameter_definition["anomaly_methodology_id"] == SOFR_ANOMALY_METHODOLOGY_ID
    assert "direction_methodology_id" not in sofr_rate_state_definition().parameter_definition
    assert v2_first.observation.signal_version == "v2"
    assert v2_first.observation.signal_observation_id != v1_first.observation.signal_observation_id
    assert v2_first.observation.signal_observation_id == v2_replay.observation.signal_observation_id
    assert v2_first.definition_inserted is True and v2_first.observation_inserted is True
    assert v2_replay.definition_inserted is False and v2_replay.observation_inserted is False
    assert definitions == [("v1",), ("v2",)]
    anomaly_keys = (
        "methodology_id", "change", "recent_rarity_60", "broad_rarity_252",
        "calendar_context", "secondary_diagnostics",
    )
    assert all(
        v1_first.observation.evidence[key] == v2_first.observation.evidence[key]
        for key in anomaly_keys
    )
    assert v2_first.observation.level_state is None
    assert v2_first.observation.direction_state is None
    assert v2_first.observation.anomaly_state is None


def test_v2_definition_references_both_frozen_components() -> None:
    definition = sofr_rate_state_v2_definition()
    assert definition.signal_id == "sofr_rate_state"
    assert definition.signal_version == "v2"
    assert definition.parameter_definition["anomaly_methodology_id"] == SOFR_ANOMALY_METHODOLOGY_ID
    assert definition.parameter_definition["direction_methodology_id"] == SOFR_DIRECTION_METHODOLOGY_ID
    assert definition.parameter_definition["direction_horizon_change_count"] == 20
    assert definition.parameter_definition["direction_slope_role"] == "secondary_only"
    assert definition.parameter_definition["direction_state_policy"] == "null_evidence_only"
    assert definition.parameter_definition["level_methodology"] == "none"
    assert SOFR_RATE_STATE_V2_PARAMETERS == definition.parameter_definition


@pytest.mark.parametrize(
    ("changes", "net", "counts", "path_total", "largest", "share", "slope"),
    [
        ([1] * 20, 20.0, (20, 0, 0), 20.0, 1.0, 0.05, 1.0),
        ([-1] * 20, -20.0, (0, 0, 20), 20.0, 1.0, 0.05, -1.0),
        ([0] * 20, 0.0, (0, 20, 0), 0.0, 0.0, None, 0.0),
        ([10, -10] + [0] * 18, 0.0, (1, 18, 1), 20.0, 10.0, 0.5, -0.14285714285714285),
        ([50] + [0] * 19, 50.0, (1, 19, 0), 50.0, 50.0, 1.0, 0.0),
    ],
)
def test_direction_calculation_paths(
    tmp_path: Path,
    changes: list[int],
    net: float,
    counts: tuple[int, int, int],
    path_total: float,
    largest: float,
    share: float | None,
    slope: float,
) -> None:
    connection = _connection(tmp_path, f"path_{abs(hash(tuple(changes)))}.duckdb")
    _insert_levels(connection, changes)
    try:
        observation = build_sofr_rate_state_v2_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    direction = observation.evidence["direction_evidence"]
    diagnostic = direction["secondary_diagnostics"]["linear_slope_20"]
    assert direction["status"] == "available"
    assert direction["net_change_20_bp"] == net
    assert (
        direction["positive_change_count_20"], direction["zero_change_count_20"],
        direction["negative_change_count_20"],
    ) == counts
    assert direction["path_total_abs_20_bp"] == path_total
    assert direction["largest_change_abs_20_bp"] == largest
    assert direction["largest_change_share_20"] == pytest.approx(share) if share is not None else direction["largest_change_share_20"] is None
    assert diagnostic["value_bp_per_valid_observation"] == pytest.approx(slope)
    assert diagnostic["level_count"] == 20
    assert observation.direction_state is None


def test_slope_uses_last_20_levels_while_net_uses_20_changes(tmp_path: Path) -> None:
    connection = _connection(tmp_path, "slope_index.duckdb")
    dates = _insert_levels(connection, [100] + [1] * 19)
    try:
        observation = build_sofr_rate_state_v2_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    direction = observation.evidence["direction_evidence"]
    slope = direction["secondary_diagnostics"]["linear_slope_20"]
    assert direction["net_change_20_bp"] == 119.0
    assert direction["baseline_start_date"] == dates[0].isoformat()
    assert slope["baseline_start_date"] == dates[1].isoformat()
    assert slope["baseline_end_date"] == dates[-1].isoformat()
    assert slope["value_bp_per_valid_observation"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("total_changes", "direction_status", "recent_status", "broad_status", "quality"),
    [
        (19, "insufficient_history", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (20, "available", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (60, "available", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (61, "available", "available", "insufficient_history", EvidenceQuality.LIMITED),
        (252, "available", "available", "insufficient_history", EvidenceQuality.LIMITED),
        (253, "available", "available", "available", EvidenceQuality.SUFFICIENT),
    ],
)
def test_independent_warmup_boundaries_and_outer_quality(
    tmp_path: Path,
    total_changes: int,
    direction_status: str,
    recent_status: str,
    broad_status: str,
    quality: EvidenceQuality,
) -> None:
    connection = _connection(tmp_path, f"warmup_v2_{total_changes}.duckdb")
    _insert_levels(connection, [0] * (total_changes - 1) + [1], publication_known=True)
    try:
        observation = build_sofr_rate_state_v2_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    direction = observation.evidence["direction_evidence"]
    assert direction["status"] == direction_status
    assert observation.evidence["recent_rarity_60"]["status"] == recent_status
    assert observation.evidence["broad_rarity_252"]["status"] == broad_status
    assert observation.evidence_quality is quality
    assert direction["available_change_count"] == min(total_changes, 20)
    if direction_status == "insufficient_history":
        assert direction["net_change_20_bp"] is None
        assert direction["secondary_diagnostics"]["linear_slope_20"]["value_bp_per_valid_observation"] is None
    else:
        assert direction["net_change_20_bp"] is not None


def test_unknown_availability_caps_full_v2_quality_at_limited(tmp_path: Path) -> None:
    connection = _connection(tmp_path, "unknown_availability.duckdb")
    _insert_levels(connection, [0] * 252 + [1], publication_known=False)
    try:
        observation = build_sofr_rate_state_v2_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    assert observation.evidence["direction_evidence"]["status"] == "available"
    assert observation.evidence["broad_rarity_252"]["status"] == "available"
    assert observation.evidence_quality is EvidenceQuality.LIMITED
    assert observation.quality_reasons == ("information_availability_unknown",)


@pytest.mark.parametrize("total_changes", [19, 20, 60, 61, 252, 253, 260])
def test_lineage_uses_one_minimum_ordered_sequence(tmp_path: Path, total_changes: int) -> None:
    connection = _connection(tmp_path, f"lineage_{total_changes}.duckdb")
    dates = _insert_levels(connection, [index % 5 - 2 for index in range(total_changes)])
    try:
        result = generate_sofr_rate_state_v2(connection, calculated_at=CALCULATED_AT)
        rows = connection.execute(
            """SELECT input.input_role, input.window_position, processed.date
               FROM signal_observation_inputs AS input
               JOIN processed_observations AS processed USING (processed_observation_id)
               WHERE input.signal_observation_id = ? ORDER BY input.window_position""",
            (result.observation.signal_observation_id,),
        ).fetchall()
    finally:
        connection.close()
    expected_levels = min(total_changes + 1, 254)
    assert len(rows) == expected_levels
    assert len({(role, position, saved_date) for role, position, saved_date in rows}) == expected_levels
    assert {row[0] for row in rows} == {SOFR_LEVEL_INPUT_ROLE}
    assert [row[1] for row in rows] == list(range(expected_levels))
    assert rows[-1][2] == dates[-1]
    if total_changes >= 20:
        assert [row[2] for row in rows[-21:]] == dates[-21:]
        slope = result.observation.evidence["direction_evidence"]["secondary_diagnostics"]["linear_slope_20"]
        assert slope["baseline_start_date"] == dates[-20].isoformat()


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        ("2018-08-27", (7.0, 11, 5, 4, 47.0, 0.19148936170212766, 0.3045112781954884)),
        ("2022-06-16", (66.0, 4, 8, 8, 90.0, 0.8333333333333334, 0.621804511278195)),
        ("2019-10-21", (0.0, 7, 3, 10, 184.0, 0.28804347826086957, -0.16240601503759408)),
    ],
)
def test_golden_historical_direction_cases(
    tmp_path: Path,
    anchor: str,
    expected: tuple[float, int, int, int, float, float, float],
) -> None:
    connection = _connection(tmp_path, f"golden_{anchor.replace('-', '_')}.duckdb")
    _insert_frozen_history_through(connection, anchor)
    try:
        observation = build_sofr_rate_state_v2_observation(connection, calculated_at=CALCULATED_AT)
    finally:
        connection.close()
    direction = observation.evidence["direction_evidence"]
    research = _direction_row(anchor)
    net, positive, zero, negative, path_total, share, slope = expected
    assert direction["net_change_20_bp"] == net == float(research["net_change_20"])
    assert (
        direction["positive_change_count_20"], direction["zero_change_count_20"],
        direction["negative_change_count_20"],
    ) == (positive, zero, negative)
    assert direction["path_total_abs_20_bp"] == path_total == float(research["path_total_abs_20"])
    assert direction["largest_change_share_20"] == pytest.approx(share)
    assert direction["largest_change_share_20"] == pytest.approx(float(research["largest_change_share_20"]))
    assert direction["secondary_diagnostics"]["linear_slope_20"]["value_bp_per_valid_observation"] == pytest.approx(slope)
    assert observation.direction_state is None
    if anchor == "2022-06-16":
        assert "positive changes do not outnumber negative changes" in observation.explanation
    if anchor == "2019-10-21":
        assert "endpoint is unchanged despite 184bp" in observation.explanation
        assert "stable" not in observation.explanation.lower()


def test_direction_validation_rejects_corrupt_counts_and_share(tmp_path: Path) -> None:
    connection = _connection(tmp_path, "corruption.duckdb")
    _insert_levels(connection, [1] * 20)
    try:
        observation = build_sofr_rate_state_v2_observation(connection, calculated_at=CALCULATED_AT)
        history = json.loads(json.dumps(observation.evidence["direction_evidence"]))
        from cross_asset_market_intelligence.dashboard.sofr_read_model import sofr_history
        levels = sofr_history(connection)
        changes = [
            (Decimal(str(current.value)) - Decimal(str(previous.value))) * Decimal("100")
            for previous, current in zip(levels, levels[1:])
        ]
        history["positive_change_count_20"] = 19
        with pytest.raises(SignalGenerationError, match="sign counts"):
            _validate_direction_evidence(history, levels, changes)
        history = json.loads(json.dumps(observation.evidence["direction_evidence"]))
        history["largest_change_share_20"] = 0.9
        with pytest.raises(SignalGenerationError, match="does not match"):
            _validate_direction_evidence(history, levels, changes)
    finally:
        connection.close()
