from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from cross_asset_market_intelligence import __main__ as cli
from cross_asset_market_intelligence.dashboard.sofr_read_model import sofr_history
from cross_asset_market_intelligence.data.sofr_processing import process_sofr
from cross_asset_market_intelligence.database import connect, initialize_phase_0_schema
from cross_asset_market_intelligence.exceptions import SignalDefinitionImmutableError, SignalGenerationError
from cross_asset_market_intelligence.signals.contract import EvidenceQuality
from cross_asset_market_intelligence.signals.persistence import persist_signal_definition
from cross_asset_market_intelligence.signals.sofr_rate_state import generate_sofr_rate_state
from cross_asset_market_intelligence.signals.sofr_rate_state_v2 import generate_sofr_rate_state_v2
from cross_asset_market_intelligence.signals.sofr_rate_state_v3 import (
    SOFR_LEVEL_METHODOLOGY_ID,
    SOFR_RATE_STATE_V3_PARAMETERS,
    _level_evidence,
    _validate_level_evidence,
    build_sofr_rate_state_v3_observation,
    generate_sofr_rate_state_v3,
    sofr_rate_state_v3_definition,
)

CALCULATED_AT = datetime(2030, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
HISTORY_ARTIFACT = (
    ROOT / "notebooks" / "sofr_daily_change_anomaly" /
    "outputs_phase_2_1b_2" / "selected_observations.json"
)
LEVEL_ROWS = ROOT / "notebooks" / "sofr_level" / "outputs" / "level_research.csv"
FROZEN_V1_GOLDEN_ID = "signal_sha256:608e2c405d933340bce628620c2964b23611be053d3e45e0df2c0dfaec57b793"
FROZEN_V2_GOLDEN_ID = "signal_sha256:59898db5c5231b2d882d1a55e4c1b0280c3607a453130b7a61ff68d2dd1c4a43"
FROZEN_V3_GOLDEN_ID = "signal_sha256:e5f25533033535ad725c7a044af5417d97549f6e0b79b50e2a72a7b603151f1d"


def _connection(tmp_path: Path, name: str) -> duckdb.DuckDBPyConnection:
    connection = connect(tmp_path / name)
    initialize_phase_0_schema(connection)
    return connection


def _insert_values(
    connection: duckdb.DuckDBPyConnection,
    values: list[Decimal | float | int | str],
    *,
    publication_known: bool = True,
) -> list[date]:
    first = date(2025, 1, 1)
    dates = [first + timedelta(days=index) for index in range(len(values))]
    publication = datetime(2029, 1, 1, tzinfo=timezone.utc) if publication_known else None
    connection.executemany(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "frbny", "SOFR", observation_date, float(Decimal(str(value))),
                datetime(2029, 1, 2, tzinfo=timezone.utc), publication,
                "frbny_sofr_revision:original", "{}",
            )
            for observation_date, value in zip(dates, values)
        ],
    )
    process_sofr(connection)
    return dates


def _artifact_rows() -> list[dict[str, object]]:
    return json.loads(HISTORY_ARTIFACT.read_text(encoding="utf-8"))


def _insert_artifact_rows(
    connection: duckdb.DuckDBPyConnection, rows: list[dict[str, object]]
) -> None:
    connection.executemany(
        "INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["raw_source"], row["raw_series_id"], date.fromisoformat(str(row["date"])),
                row["sofr_percent"], datetime.fromisoformat(str(row["retrieval_timestamp"])),
                None, row["raw_vintage"], "{}",
            )
            for row in rows
        ],
    )
    process_sofr(connection)


def _insert_frozen_history_through(
    connection: duckdb.DuckDBPyConnection, anchor: str
) -> list[dict[str, object]]:
    rows = _artifact_rows()
    anchor_index = next(index for index, row in enumerate(rows) if row["date"] == anchor)
    selected = rows[:anchor_index + 1]
    _insert_artifact_rows(connection, selected)
    return selected


def _level_row(anchor: str) -> dict[str, str]:
    with LEVEL_ROWS.open(encoding="utf-8", newline="") as handle:
        return next(row for row in csv.DictReader(handle) if row["date"] == anchor)


def test_v1_v2_are_unchanged_and_v3_is_distinct_immutable_idempotent_and_full_lineage(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path, "versions_v3.duckdb")
    selected = _insert_frozen_history_through(connection, "2026-09-16")
    try:
        v1 = generate_sofr_rate_state(connection, calculated_at=CALCULATED_AT)
        v2 = generate_sofr_rate_state_v2(connection, calculated_at=CALCULATED_AT)
        v3 = generate_sofr_rate_state_v3(connection, calculated_at=CALCULATED_AT)
        replay = generate_sofr_rate_state_v3(
            connection, calculated_at=CALCULATED_AT + timedelta(minutes=1)
        )
        definitions = connection.execute(
            "SELECT signal_version FROM signal_definitions WHERE signal_id = 'sofr_rate_state' "
            "ORDER BY signal_version"
        ).fetchall()
        inputs = connection.execute(
            """SELECT input.window_position, processed.date, input.processed_observation_id
               FROM signal_observation_inputs AS input
               JOIN processed_observations AS processed USING (processed_observation_id)
               WHERE input.signal_observation_id = ? ORDER BY input.window_position""",
            (v3.observation.signal_observation_id,),
        ).fetchall()
        with pytest.raises(SignalDefinitionImmutableError):
            persist_signal_definition(
                connection, replace(sofr_rate_state_v3_definition(), name="Mutated v3")
            )
    finally:
        connection.close()

    assert v1.observation.signal_observation_id == FROZEN_V1_GOLDEN_ID
    assert v2.observation.signal_observation_id == FROZEN_V2_GOLDEN_ID
    assert "level_evidence" not in v1.observation.evidence
    assert "level_evidence" not in v2.observation.evidence
    assert v3.observation.signal_version == "v3"
    assert v3.observation.signal_observation_id == FROZEN_V3_GOLDEN_ID
    assert v3.observation.signal_observation_id not in {
        v1.observation.signal_observation_id, v2.observation.signal_observation_id,
    }
    assert replay.observation.signal_observation_id == v3.observation.signal_observation_id
    assert replay.observation.evidence == v3.observation.evidence
    assert v3.definition_inserted and v3.observation_inserted
    assert not replay.definition_inserted and not replay.observation_inserted
    assert definitions == [("v1",), ("v2",), ("v3",)]
    for key in v2.observation.evidence:
        assert v3.observation.evidence[key] == v2.observation.evidence[key]
    assert v3.observation.level_state is None
    assert v3.observation.direction_state is None
    assert v3.observation.anomaly_state is None
    assert len(inputs) == len(selected) == 2112
    assert [row[0] for row in inputs] == list(range(2112))
    assert len({row[2] for row in inputs}) == 2112
    assert inputs[0][1].isoformat() == "2018-04-03"
    assert inputs[-1][1].isoformat() == "2026-09-16"


def test_v3_definition_and_parameters_reference_all_frozen_components() -> None:
    definition = sofr_rate_state_v3_definition()
    assert definition.signal_id == "sofr_rate_state"
    assert definition.signal_version == "v3"
    assert definition.parameter_definition == SOFR_RATE_STATE_V3_PARAMETERS
    assert definition.parameter_definition["anomaly_methodology_id"] == "sofr_change_rarity_v1"
    assert definition.parameter_definition["direction_methodology_id"] == "sofr_direction_evidence_v1"
    assert definition.parameter_definition["level_methodology_id"] == SOFR_LEVEL_METHODOLOGY_ID
    assert definition.parameter_definition["level_recent_window_levels"] == 60
    assert definition.parameter_definition["level_percentile_method"] == "midrank"
    assert definition.parameter_definition["level_state_classification"] == "none"
    assert "v3-specific" in definition.limitations


@pytest.mark.parametrize(
    ("prior", "current", "expected"),
    [
        (["1", "2", "2", "3"], "2", (1, 2, 1, 25.0, 50.0, 75.0)),
        (["2", "3", "4"], "1", (0, 0, 3, 0.0, 0.0, 0.0)),
        (["1", "2", "3"], "4", (3, 0, 0, 100.0, 100.0, 100.0)),
    ],
)
def test_broad_level_rank_uses_exact_ties_and_excludes_current(
    tmp_path: Path,
    prior: list[str],
    current: str,
    expected: tuple[int, int, int, float, float, float],
) -> None:
    connection = _connection(tmp_path, f"rank_{current}_{len(prior)}.duckdb")
    _insert_values(connection, [*prior, current])
    try:
        observation = build_sofr_rate_state_v3_observation(
            connection, calculated_at=CALCULATED_AT
        )
    finally:
        connection.close()
    level = observation.evidence["level_evidence"]
    broad = level["broad_historical_context"]
    less, equal, greater, strict, midrank, weak = expected
    assert level["current_level_percent"] == float(current)
    assert broad["prior_observation_count"] == len(prior)
    assert (broad["less_count"], broad["equal_count"], broad["greater_count"]) == (
        less, equal, greater,
    )
    assert broad["strict_percentile"] == strict
    assert broad["midrank_percentile"] == midrank
    assert broad["weak_percentile"] == weak
    assert broad["less_count"] + broad["equal_count"] + broad["greater_count"] == len(prior)


def test_recent_60_median_uses_exact_prior_window_without_rounding_or_extra_methods(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path, "median_precision.duckdb")
    _insert_values(connection, [Decimal("1.000")] * 60 + [Decimal("1.005")])
    try:
        observation = build_sofr_rate_state_v3_observation(
            connection, calculated_at=CALCULATED_AT
        )
    finally:
        connection.close()
    level = observation.evidence["level_evidence"]
    recent = level["recent_context"]
    assert level["current_level_percent"] == 1.005
    assert recent["status"] == "available"
    assert recent["prior_60_median_level_percent"] == 1.0
    assert recent["distance_from_prior_60_median_bp"] == 0.5
    assert recent["available_prior_level_count"] == 60
    serialized = json.dumps(level, sort_keys=True)
    for excluded in ("level_percentile_60", "level_z_60", "robust_level_z", "mad"):
        assert excluded not in serialized.lower()


@pytest.mark.parametrize(
    ("total_levels", "broad", "recent_level", "direction", "recent_anomaly", "broad_anomaly", "quality"),
    [
        (1, "insufficient_history", "insufficient_history", None, None, None, None),
        (2, "available", "insufficient_history", "insufficient_history", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (20, "available", "insufficient_history", "insufficient_history", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (21, "available", "insufficient_history", "available", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (60, "available", "insufficient_history", "available", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (61, "available", "available", "available", "insufficient_history", "insufficient_history", EvidenceQuality.INSUFFICIENT),
        (62, "available", "available", "available", "available", "insufficient_history", EvidenceQuality.LIMITED),
        (254, "available", "available", "available", "available", "available", EvidenceQuality.SUFFICIENT),
    ],
)
def test_component_warmups_are_independent(
    tmp_path: Path,
    total_levels: int,
    broad: str,
    recent_level: str,
    direction: str | None,
    recent_anomaly: str | None,
    broad_anomaly: str | None,
    quality: EvidenceQuality | None,
) -> None:
    connection = _connection(tmp_path, f"warmup_v3_{total_levels}.duckdb")
    _insert_values(connection, [Decimal("3") + Decimal(index % 3) / 100 for index in range(total_levels)])
    try:
        levels = sofr_history(connection)
        level = _level_evidence(levels)
        _validate_level_evidence(level, levels)
        assert level["broad_historical_context"]["status"] == broad
        assert level["recent_context"]["status"] == recent_level
        if total_levels == 1:
            with pytest.raises(SignalGenerationError, match="current and previous"):
                build_sofr_rate_state_v3_observation(connection, calculated_at=CALCULATED_AT)
            return
        observation = build_sofr_rate_state_v3_observation(
            connection, calculated_at=CALCULATED_AT
        )
    finally:
        connection.close()
    assert observation.evidence["direction_evidence"]["status"] == direction
    assert observation.evidence["recent_rarity_60"]["status"] == recent_anomaly
    assert observation.evidence["broad_rarity_252"]["status"] == broad_anomaly
    assert observation.evidence_quality is quality


def test_unknown_publication_availability_caps_complete_v3_at_limited(tmp_path: Path) -> None:
    connection = _connection(tmp_path, "quality_v3.duckdb")
    _insert_values(connection, [3 + (index % 5) / 100 for index in range(254)], publication_known=False)
    try:
        observation = build_sofr_rate_state_v3_observation(
            connection, calculated_at=CALCULATED_AT
        )
    finally:
        connection.close()
    assert observation.evidence["level_evidence"]["recent_context"]["status"] == "available"
    assert observation.evidence["broad_rarity_252"]["status"] == "available"
    assert observation.evidence_quality is EvidenceQuality.LIMITED
    assert observation.quality_reasons == ("information_availability_unknown",)


def test_later_future_rows_do_not_change_historical_v3_evidence_or_identity(tmp_path: Path) -> None:
    rows = _artifact_rows()
    anchor = "2024-06-14"
    anchor_index = next(index for index, row in enumerate(rows) if row["date"] == anchor)
    connection = _connection(tmp_path, "future_proof_v3.duckdb")
    _insert_artifact_rows(connection, rows[:anchor_index + 1])
    try:
        first = generate_sofr_rate_state_v3(
            connection, as_of_observation_date=date.fromisoformat(anchor), calculated_at=CALCULATED_AT
        )
        _insert_artifact_rows(connection, rows[anchor_index + 1:])
        replay = generate_sofr_rate_state_v3(
            connection,
            as_of_observation_date=date.fromisoformat(anchor),
            calculated_at=CALCULATED_AT + timedelta(days=1),
        )
    finally:
        connection.close()
    assert replay.observation.signal_observation_id == first.observation.signal_observation_id
    assert replay.observation.evidence == first.observation.evidence
    assert len(first.observation.inputs) == anchor_index + 1
    assert len(replay.observation.inputs) == anchor_index + 1


@pytest.mark.parametrize(
    ("anchor", "expected_midrank", "expected_distance"),
    [
        ("2021-10-18", 19.469525959367946, 0.0),
        ("2024-06-14", 91.87096774193549, 0.0),
        ("2022-06-16", 54.46768060836502, 115.0),
        ("2019-10-21", 16.3659793814433, -26.0),
    ],
)
def test_golden_level_environments_and_frozen_v2_evidence(
    tmp_path: Path, anchor: str, expected_midrank: float, expected_distance: float
) -> None:
    connection = _connection(tmp_path, f"golden_level_{anchor.replace('-', '_')}.duckdb")
    _insert_frozen_history_through(connection, anchor)
    try:
        v2 = build_sofr_rate_state_v3_observation(
            connection, as_of_observation_date=date.fromisoformat(anchor), calculated_at=CALCULATED_AT
        )
    finally:
        connection.close()
    research = _level_row(anchor)
    level = v2.evidence["level_evidence"]
    broad = level["broad_historical_context"]
    recent = level["recent_context"]
    assert broad["midrank_percentile"] == pytest.approx(expected_midrank)
    assert broad["midrank_percentile"] == pytest.approx(float(research["full_history_midrank"]))
    assert recent["distance_from_prior_60_median_bp"] == pytest.approx(expected_distance)
    assert recent["distance_from_prior_60_median_bp"] == pytest.approx(
        float(research["distance_median_60_bp"])
    )
    direction = v2.evidence["direction_evidence"]
    assert direction["net_change_20_bp"] == pytest.approx(float(research["direction_net_change_20_bp"]))
    assert v2.evidence["recent_rarity_60"]["midrank_percentile"] == pytest.approx(
        float(research["recent_anomaly_midrank"])
    )
    if anchor == "2024-06-14":
        assert broad["midrank_percentile"] > 90
        assert recent["distance_from_prior_60_median_bp"] == 0
    if anchor == "2022-06-16":
        assert recent["distance_from_prior_60_median_bp"] == 115
        assert "stress" not in v2.explanation.lower().replace("does not imply funding stress", "")
    if anchor == "2019-10-21":
        assert direction["net_change_20_bp"] == 0
        assert direction["path_total_abs_20_bp"] == 184


def test_level_validation_rejects_count_and_distance_corruption(tmp_path: Path) -> None:
    connection = _connection(tmp_path, "level_corruption.duckdb")
    _insert_values(connection, [1 + index / 100 for index in range(61)])
    try:
        levels = sofr_history(connection)
        level = _level_evidence(levels)
        level["broad_historical_context"]["less_count"] -= 1
        with pytest.raises(SignalGenerationError, match="counts do not sum"):
            _validate_level_evidence(level, levels)
        level = _level_evidence(levels)
        level["recent_context"]["distance_from_prior_60_median_bp"] += 1
        with pytest.raises(SignalGenerationError, match="bp distance"):
            _validate_level_evidence(level, levels)
    finally:
        connection.close()


def test_cli_keeps_v1_default_and_routes_explicit_v3(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []

    class DummyConnection:
        def close(self) -> None:
            pass

    def result(version: str) -> SimpleNamespace:
        calls.append(version)
        return SimpleNamespace(
            observation_inserted=True,
            observation=SimpleNamespace(
                signal_id="sofr_rate_state",
                signal_version=version,
                as_of_observation_date=date(2026, 9, 16),
                evidence_quality=EvidenceQuality.LIMITED,
                signal_observation_id=f"signal-{version}",
            ),
        )

    monkeypatch.setattr(cli, "load_settings", lambda: SimpleNamespace(database_path=Path("unused")))
    monkeypatch.setattr(cli, "configure_logging", lambda settings: None)
    monkeypatch.setattr(cli, "connect", lambda path, read_only=False: DummyConnection())
    monkeypatch.setattr(cli, "generate_sofr_rate_state", lambda *args, **kwargs: result("v1"))
    monkeypatch.setattr(cli, "generate_sofr_rate_state_v2", lambda *args, **kwargs: result("v2"))
    monkeypatch.setattr(cli, "generate_sofr_rate_state_v3", lambda *args, **kwargs: result("v3"))

    monkeypatch.setattr(sys, "argv", ["prog", "generate-sofr-rate-state"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["prog", "generate-sofr-rate-state", "--version", "v3"])
    cli.main()
    assert calls == ["v1", "v3"]
    assert "sofr_rate_state/v1 inserted" in capsys.readouterr().out
