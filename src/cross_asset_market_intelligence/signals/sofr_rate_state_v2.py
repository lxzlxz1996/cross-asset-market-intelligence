"""Combined frozen anomaly and Direction evidence for SOFR Rate State v2."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Sequence

import duckdb

from ..dashboard.sofr_read_model import SofrDashboardObservation, sofr_history
from ..exceptions import SignalGenerationError
from .contract import SignalDefinition, SignalDefinitionStatus, SignalObservation, SignalObservationInput
from .explanations import render_explanation
from .persistence import persist_signal_definition, persist_signal_observation
from .sofr_rate_state import (
    SOFR_ANOMALY_METHODOLOGY_ID,
    SOFR_BROAD_WINDOW,
    SOFR_CALENDAR_RULE_ID,
    SOFR_LEVEL_INPUT_ROLE,
    SOFR_RATE_STATE_INDICATOR_ID,
    SOFR_RATE_STATE_PARAMETERS,
    SOFR_RATE_STATE_SIGNAL_ID,
    SOFR_RECENT_WINDOW,
    SofrSignalGenerationResult,
    _change_bp,
    _evidence_quality,
    _publication_availability,
    _rarity_evidence,
    _standard_z_evidence,
    _validate_evidence,
    _validate_level_sequence,
    calendar_context,
)

SOFR_RATE_STATE_V2_SIGNAL_VERSION = "v2"
SOFR_DIRECTION_METHODOLOGY_ID = "sofr_direction_evidence_v1"
SOFR_DIRECTION_HORIZON_CHANGES = 20
SOFR_DIRECTION_REQUIRED_LEVELS = SOFR_DIRECTION_HORIZON_CHANGES + 1
SOFR_DIRECTION_SLOPE_LEVELS = 20

SOFR_RATE_STATE_V2_PARAMETERS: dict[str, object] = {
    **SOFR_RATE_STATE_PARAMETERS,
    "direction_methodology_id": SOFR_DIRECTION_METHODOLOGY_ID,
    "direction_horizon_change_count": SOFR_DIRECTION_HORIZON_CHANGES,
    "direction_window_unit": "consecutive_valid_changes",
    "direction_required_level_count": SOFR_DIRECTION_REQUIRED_LEVELS,
    "direction_net_change_unit": "basis_points",
    "direction_sign_equality": "exact_decimal_bp_no_prerounding",
    "direction_persisted_sign_fields": ["positive_count", "zero_count", "negative_count"],
    "direction_derived_not_persisted": [
        "positive_share", "zero_share", "negative_share", "direction_balance"
    ],
    "direction_path_concentration_enabled": True,
    "direction_path_total": "sum_absolute_changes",
    "direction_largest_change": "max_absolute_change",
    "direction_zero_path_share_policy": "null",
    "direction_slope_role": "secondary_only",
    "direction_slope_level_count": SOFR_DIRECTION_SLOPE_LEVELS,
    "direction_state_policy": "null_evidence_only",
    "direction_calendar_policy": "no_adjustment_no_direction_fields",
    "direction_missing_observation_policy": "previous_valid_no_fill_no_interpolation",
    "level_methodology": "none",
    "level_state_policy": "null_not_implemented",
}


def sofr_rate_state_v2_definition() -> SignalDefinition:
    """Return the immutable production definition for SOFR Rate State v2."""
    return SignalDefinition(
        signal_id=SOFR_RATE_STATE_SIGNAL_ID,
        signal_version=SOFR_RATE_STATE_V2_SIGNAL_VERSION,
        indicator_id=SOFR_RATE_STATE_INDICATOR_ID,
        name="SOFR Rate State v2",
        economic_question=(
            "How large and unusual was the latest SOFR move, and what endpoint displacement, "
            "sign composition, and path concentration occurred over the latest 20 valid changes?"
        ),
        economic_hypothesis=(
            "Frozen anomaly rarity and transparent recent-path evidence provide distinct, auditable "
            "descriptions without requiring categorical market states."
        ),
        what_it_measures=(
            "The frozen sofr_change_rarity_v1 anomaly evidence plus sofr_direction_evidence_v1: "
            "20-change net displacement, exact sign counts, path concentration, and a secondary "
            "20-level linear-slope diagnostic."
        ),
        what_it_does_not_mean=(
            "It does not establish a SOFR level state, funding or liquidity stress, policy cause, "
            "financial crisis, asset-return direction, market regime, trade, or portfolio action."
        ),
        methodology_description=(
            "Combined evidence-only SOFR Rate State. Anomaly methodology sofr_change_rarity_v1 is "
            "unchanged. Direction methodology sofr_direction_evidence_v1 uses exactly 20 consecutive "
            "valid changes and assigns no categorical direction state."
        ),
        parameter_definition=SOFR_RATE_STATE_V2_PARAMETERS,
        limitations=(
            "No level methodology; no direction, anomaly, materiality, step, or reversal classifier; "
            "slope is secondary only; calendar context is not an adjustment; historical publication "
            "times may be unknown and economic-date history is not point-in-time replay."
        ),
        status=SignalDefinitionStatus.ACTIVE,
    )


def generate_sofr_rate_state_v2(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of_observation_date: date | None = None,
    calculated_at: datetime | None = None,
) -> SofrSignalGenerationResult:
    """Build and persist one combined SOFR Rate State v2 observation idempotently."""
    timestamp = calculated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SignalGenerationError("calculated_at must be timezone-aware")
    observation = build_sofr_rate_state_v2_observation(
        connection,
        as_of_observation_date=as_of_observation_date,
        calculated_at=timestamp,
    )
    definition_inserted = persist_signal_definition(connection, sofr_rate_state_v2_definition())
    observation_inserted = persist_signal_observation(connection, observation)
    return SofrSignalGenerationResult(definition_inserted, observation_inserted, observation)


def build_sofr_rate_state_v2_observation(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of_observation_date: date | None = None,
    calculated_at: datetime,
) -> SignalObservation:
    """Construct a validated v2 observation without persisting it."""
    if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
        raise SignalGenerationError("calculated_at must be timezone-aware")
    history = sofr_history(connection, end_date=as_of_observation_date)
    if not history:
        raise SignalGenerationError("No selected SOFR observation is available")
    if as_of_observation_date is not None and history[-1].observation_date != as_of_observation_date:
        raise SignalGenerationError("The requested as-of date is not a selected SOFR observation date")
    if len(history) < 2:
        raise SignalGenerationError("SOFR Rate State v2 requires current and previous valid observations")

    lineage_levels = history[-(SOFR_BROAD_WINDOW + 2):]
    _validate_level_sequence(lineage_levels)
    changes = [_change_bp(previous, current) for previous, current in zip(lineage_levels, lineage_levels[1:])]
    current_change = changes[-1]
    prior_changes = changes[:-1]
    prior_dates = [item.observation_date for item in lineage_levels[1:-1]]

    recent = _rarity_evidence(current_change, prior_changes, prior_dates, SOFR_RECENT_WINDOW)
    broad = _rarity_evidence(current_change, prior_changes, prior_dates, SOFR_BROAD_WINDOW)
    diagnostics = {
        "standard_z_60": _standard_z_evidence(current_change, prior_changes, SOFR_RECENT_WINDOW),
        "standard_z_252": _standard_z_evidence(current_change, prior_changes, SOFR_BROAD_WINDOW),
    }
    context = calendar_context(lineage_levels[-1].observation_date)
    direction = _direction_evidence(lineage_levels, changes)
    availability_precision, information_available_at = _publication_availability(
        connection, [item.processed_observation_id for item in lineage_levels]
    )
    quality, quality_reasons = _evidence_quality(len(prior_changes), availability_precision)

    evidence: dict[str, Any] = {
        "methodology_id": SOFR_ANOMALY_METHODOLOGY_ID,
        "change": {
            "previous_observation_date": lineage_levels[-2].observation_date.isoformat(),
            "calendar_gap_days": (
                lineage_levels[-1].observation_date - lineage_levels[-2].observation_date
            ).days,
            "change_1obs_bp": float(current_change),
            "absolute_change_1obs_bp": float(abs(current_change)),
        },
        "recent_rarity_60": recent,
        "broad_rarity_252": broad,
        "calendar_context": context,
        "secondary_diagnostics": diagnostics,
        "direction_evidence": direction,
    }
    _validate_evidence(evidence, prior_changes)
    _validate_direction_evidence(direction, lineage_levels, changes)
    inputs = tuple(
        SignalObservationInput(
            processed_observation_id=item.processed_observation_id,
            input_role=SOFR_LEVEL_INPUT_ROLE,
            window_position=position,
        )
        for position, item in enumerate(lineage_levels)
    )
    return SignalObservation(
        signal_id=SOFR_RATE_STATE_SIGNAL_ID,
        signal_version=SOFR_RATE_STATE_V2_SIGNAL_VERSION,
        indicator_id=SOFR_RATE_STATE_INDICATOR_ID,
        as_of_observation_date=lineage_levels[-1].observation_date,
        information_available_at=information_available_at,
        information_available_date=None,
        availability_precision=availability_precision,
        calculated_at=calculated_at,
        level_state=None,
        direction_state=None,
        anomaly_state=None,
        evidence_quality=quality,
        evidence=evidence,
        parameters_used=SOFR_RATE_STATE_V2_PARAMETERS,
        explanation=_v2_explanation(evidence),
        quality_reasons=quality_reasons,
        inputs=inputs,
    )


def _direction_evidence(
    lineage_levels: Sequence[SofrDashboardObservation], changes: Sequence[Decimal]
) -> dict[str, Any]:
    available = min(len(changes), SOFR_DIRECTION_HORIZON_CHANGES)
    empty_slope = {
        "role": "secondary_only",
        "level_count": SOFR_DIRECTION_SLOPE_LEVELS,
        "baseline_start_date": None,
        "baseline_end_date": None,
        "value_bp_per_valid_observation": None,
    }
    if len(changes) < SOFR_DIRECTION_HORIZON_CHANGES:
        return {
            "methodology_id": SOFR_DIRECTION_METHODOLOGY_ID,
            "status": "insufficient_history",
            "horizon_change_count": SOFR_DIRECTION_HORIZON_CHANGES,
            "available_change_count": available,
            "baseline_start_date": None,
            "baseline_end_date": None,
            "net_change_20_bp": None,
            "positive_change_count_20": None,
            "zero_change_count_20": None,
            "negative_change_count_20": None,
            "path_total_abs_20_bp": None,
            "largest_change_abs_20_bp": None,
            "largest_change_share_20": None,
            "secondary_diagnostics": {"linear_slope_20": empty_slope},
        }

    levels = lineage_levels[-SOFR_DIRECTION_REQUIRED_LEVELS:]
    window_changes = list(changes[-SOFR_DIRECTION_HORIZON_CHANGES:])
    direct_net = _change_bp(levels[0], levels[-1])
    summed_net = sum(window_changes, Decimal("0"))
    if direct_net != summed_net:
        raise SignalGenerationError("Direction net change does not equal the sum of its 20 changes")
    positive = sum(change > 0 for change in window_changes)
    zero = sum(change == 0 for change in window_changes)
    negative = sum(change < 0 for change in window_changes)
    path_total = sum((abs(change) for change in window_changes), Decimal("0"))
    largest = max(abs(change) for change in window_changes)
    share = None if path_total == 0 else float(largest / path_total)
    slope_levels = levels[-SOFR_DIRECTION_SLOPE_LEVELS:]
    slope = _linear_slope_bp_per_valid_observation(slope_levels)
    return {
        "methodology_id": SOFR_DIRECTION_METHODOLOGY_ID,
        "status": "available",
        "horizon_change_count": SOFR_DIRECTION_HORIZON_CHANGES,
        "available_change_count": SOFR_DIRECTION_HORIZON_CHANGES,
        "baseline_start_date": levels[0].observation_date.isoformat(),
        "baseline_end_date": levels[-1].observation_date.isoformat(),
        "net_change_20_bp": float(direct_net),
        "positive_change_count_20": positive,
        "zero_change_count_20": zero,
        "negative_change_count_20": negative,
        "path_total_abs_20_bp": float(path_total),
        "largest_change_abs_20_bp": float(largest),
        "largest_change_share_20": share,
        "secondary_diagnostics": {
            "linear_slope_20": {
                "role": "secondary_only",
                "level_count": SOFR_DIRECTION_SLOPE_LEVELS,
                "baseline_start_date": slope_levels[0].observation_date.isoformat(),
                "baseline_end_date": slope_levels[-1].observation_date.isoformat(),
                "value_bp_per_valid_observation": slope,
            }
        },
    }


def _linear_slope_bp_per_valid_observation(
    levels: Sequence[SofrDashboardObservation],
) -> float:
    if len(levels) != SOFR_DIRECTION_SLOPE_LEVELS:
        raise SignalGenerationError("Direction slope requires exactly 20 SOFR levels")
    values = [Decimal(str(item.value)) for item in levels]
    count = Decimal(len(values))
    mean_x = Decimal(len(values) - 1) / Decimal("2")
    mean_y = sum(values, Decimal("0")) / count
    numerator = sum(
        ((Decimal(index) - mean_x) * (value - mean_y) for index, value in enumerate(values)),
        Decimal("0"),
    )
    denominator = sum(
        ((Decimal(index) - mean_x) ** 2 for index in range(len(values))), Decimal("0")
    )
    value = float(Decimal("100") * numerator / denominator)
    if not math.isfinite(value):
        raise SignalGenerationError("Direction slope is not finite")
    return value


def _validate_direction_evidence(
    direction: dict[str, Any],
    lineage_levels: Sequence[SofrDashboardObservation],
    changes: Sequence[Decimal],
) -> None:
    if direction["methodology_id"] != SOFR_DIRECTION_METHODOLOGY_ID:
        raise SignalGenerationError("Direction methodology identity is invalid")
    if direction["horizon_change_count"] != SOFR_DIRECTION_HORIZON_CHANGES:
        raise SignalGenerationError("Direction horizon is invalid")
    expected_available = len(changes) >= SOFR_DIRECTION_HORIZON_CHANGES
    if (direction["status"] == "available") != expected_available:
        raise SignalGenerationError("Direction evidence availability is inconsistent with history")
    expected_count = min(len(changes), SOFR_DIRECTION_HORIZON_CHANGES)
    if direction["available_change_count"] != expected_count:
        raise SignalGenerationError("Direction available-change count is inconsistent with history")
    if not expected_available:
        quantitative = (
            "net_change_20_bp", "positive_change_count_20", "zero_change_count_20",
            "negative_change_count_20", "path_total_abs_20_bp",
            "largest_change_abs_20_bp", "largest_change_share_20",
        )
        if any(direction[field] is not None for field in quantitative):
            raise SignalGenerationError("Direction warm-up evidence must not contain partial values")
        if direction["baseline_start_date"] is not None or direction["baseline_end_date"] is not None:
            raise SignalGenerationError("Direction warm-up evidence must not contain baseline dates")
        slope = direction["secondary_diagnostics"]["linear_slope_20"]
        if any(slope[field] is not None for field in (
            "baseline_start_date", "baseline_end_date", "value_bp_per_valid_observation"
        )):
            raise SignalGenerationError("Direction slope must not be exposed before Direction is available")
        return

    counts = (
        direction["positive_change_count_20"],
        direction["zero_change_count_20"],
        direction["negative_change_count_20"],
    )
    if any(not isinstance(count, int) for count in counts) or sum(counts) != SOFR_DIRECTION_HORIZON_CHANGES:
        raise SignalGenerationError("Direction sign counts do not sum to 20")
    window_levels = lineage_levels[-SOFR_DIRECTION_REQUIRED_LEVELS:]
    window_changes = list(changes[-SOFR_DIRECTION_HORIZON_CHANGES:])
    expected_counts = (
        sum(change > 0 for change in window_changes),
        sum(change == 0 for change in window_changes),
        sum(change < 0 for change in window_changes),
    )
    if counts != expected_counts:
        raise SignalGenerationError("Direction sign counts do not match exact changes")
    if (
        direction["baseline_start_date"] != window_levels[0].observation_date.isoformat()
        or direction["baseline_end_date"] != window_levels[-1].observation_date.isoformat()
    ):
        raise SignalGenerationError("Direction baseline dates do not match exact levels")
    numeric_fields = (
        "net_change_20_bp", "path_total_abs_20_bp", "largest_change_abs_20_bp"
    )
    if any(not math.isfinite(float(direction[field])) for field in numeric_fields):
        raise SignalGenerationError("Direction evidence contains a non-finite value")
    net = Decimal(str(direction["net_change_20_bp"]))
    path_total = Decimal(str(direction["path_total_abs_20_bp"]))
    largest = Decimal(str(direction["largest_change_abs_20_bp"]))
    expected_path_total = sum((abs(change) for change in window_changes), Decimal("0"))
    expected_largest = max(abs(change) for change in window_changes)
    if not math.isclose(float(path_total), float(expected_path_total), rel_tol=1e-12, abs_tol=1e-12):
        raise SignalGenerationError("Direction total absolute path does not match exact changes")
    if not math.isclose(float(largest), float(expected_largest), rel_tol=1e-12, abs_tol=1e-12):
        raise SignalGenerationError("Direction largest move does not match exact changes")
    if path_total < abs(net) or largest < 0 or largest > path_total:
        raise SignalGenerationError("Direction path concentration invariants are invalid")
    share = direction["largest_change_share_20"]
    if path_total == 0:
        if largest != 0 or share is not None:
            raise SignalGenerationError("A zero Direction path requires zero largest move and null share")
    else:
        if share is None or not math.isfinite(float(share)) or not 0 < float(share) <= 1:
            raise SignalGenerationError("Direction largest-change share is invalid")
        if not math.isclose(float(share), float(largest / path_total), rel_tol=1e-12, abs_tol=1e-12):
            raise SignalGenerationError("Direction largest-change share does not match path evidence")
    exact_net = sum(window_changes, Decimal("0"))
    direct_net = _change_bp(
        lineage_levels[-SOFR_DIRECTION_REQUIRED_LEVELS], lineage_levels[-1]
    )
    if exact_net != direct_net or not math.isclose(
        float(direction["net_change_20_bp"]), float(direct_net), rel_tol=1e-12, abs_tol=1e-12
    ):
        raise SignalGenerationError("Direction net-change invariant failed")
    slope = direction["secondary_diagnostics"]["linear_slope_20"]
    slope_levels = window_levels[-SOFR_DIRECTION_SLOPE_LEVELS:]
    if slope["role"] != "secondary_only" or slope["level_count"] != SOFR_DIRECTION_SLOPE_LEVELS:
        raise SignalGenerationError("Direction slope level count is invalid")
    if (
        slope["baseline_start_date"] != slope_levels[0].observation_date.isoformat()
        or slope["baseline_end_date"] != slope_levels[-1].observation_date.isoformat()
    ):
        raise SignalGenerationError("Direction slope dates do not match exact levels")
    if not math.isfinite(float(slope["value_bp_per_valid_observation"])):
        raise SignalGenerationError("Direction slope is not finite")
    expected_slope = _linear_slope_bp_per_valid_observation(slope_levels)
    if not math.isclose(
        float(slope["value_bp_per_valid_observation"]), expected_slope,
        rel_tol=1e-12, abs_tol=1e-12,
    ):
        raise SignalGenerationError("Direction slope does not match exact levels")


def _v2_explanation(evidence: dict[str, Any]) -> str:
    change = float(evidence["change"]["change_1obs_bp"])
    if change > 0:
        movement = f"rose {_format_number(change)}bp"
    elif change < 0:
        movement = f"declined {_format_number(abs(change))}bp"
    else:
        movement = "was unchanged"
    sentences = [
        render_explanation(
            "SOFR {movement} from the previous valid observation.", {"movement": movement}
        )
    ]
    for field, label, window in (
        ("recent_rarity_60", "recent", 60),
        ("broad_rarity_252", "broad", 252),
    ):
        rarity = evidence[field]
        if rarity["status"] == "available":
            sentences.append(
                render_explanation(
                    "The absolute move has {label} midrank {midrank} on a 0-100 scale relative to "
                    "the prior {window} valid SOFR changes (strict {strict}; weak {weak}).",
                    {
                        "label": label,
                        "midrank": _format_percentile(rarity["midrank_percentile"]),
                        "window": window,
                        "strict": _format_percentile(rarity["strict_percentile"]),
                        "weak": _format_percentile(rarity["weak_percentile"]),
                    },
                )
            )
        else:
            sentences.append(
                render_explanation(
                    "The {label} {window}-change rarity measure is unavailable because only "
                    "{available} prior valid changes are available.",
                    {
                        "label": label,
                        "window": window,
                        "available": rarity["available_prior_change_count"],
                    },
                )
            )
    direction = evidence["direction_evidence"]
    if direction["status"] != "available":
        sentences.append(
            render_explanation(
                "Direction evidence is unavailable because {available} of 20 required valid changes "
                "are available.",
                {"available": direction["available_change_count"]},
            )
        )
    else:
        net = float(direction["net_change_20_bp"])
        if net > 0:
            displacement = f"{_format_number(net)}bp higher"
        elif net < 0:
            displacement = f"{_format_number(abs(net))}bp lower"
        else:
            displacement = "unchanged"
        sentences.append(
            render_explanation(
                "Over the most recent 20 valid changes, SOFR is {displacement}.",
                {"displacement": displacement},
            )
        )
        sentences.append(
            render_explanation(
                "Within those 20 changes, {positive} were positive, {zero} were unchanged, "
                "and {negative} were negative.",
                {
                    "positive": direction["positive_change_count_20"],
                    "zero": direction["zero_change_count_20"],
                    "negative": direction["negative_change_count_20"],
                },
            )
        )
        path_total = float(direction["path_total_abs_20_bp"])
        largest = float(direction["largest_change_abs_20_bp"])
        share = direction["largest_change_share_20"]
        if share is None:
            sentences.append(
                "All 20 changes were unchanged; total absolute path movement was 0bp and the "
                "largest-change share is undefined."
            )
        else:
            sentences.append(
                render_explanation(
                    "Total absolute path movement was {total}bp; the largest single change was "
                    "{largest}bp and accounted for {share}% of that path.",
                    {
                        "total": _format_number(path_total),
                        "largest": _format_number(largest),
                        "share": f"{100 * float(share):.1f}",
                    },
                )
            )
        positive = int(direction["positive_change_count_20"])
        negative = int(direction["negative_change_count_20"])
        if net > 0 and positive <= negative:
            sentences.append(
                "The endpoint is higher, while positive changes do not outnumber negative changes "
                "in the window."
            )
        elif net < 0 and negative <= positive:
            sentences.append(
                "The endpoint is lower, while negative changes do not outnumber positive changes "
                "in the window."
            )
        elif net == 0 and path_total > 0:
            sentences.append(
                render_explanation(
                    "The endpoint is unchanged despite {total}bp of total absolute path movement.",
                    {"total": _format_number(path_total)},
                )
            )
    context = evidence["calendar_context"]
    boundary = (
        "year-end" if context["year_end"] else
        "quarter-end" if context["quarter_end"] else
        "month-end" if context["month_end"] else None
    )
    if boundary is not None:
        sentences.append(
            render_explanation(
                "The observation matches the {boundary} context under the {rule} calendar rule; "
                "calendar context does not alter anomaly or Direction evidence.",
                {"boundary": boundary, "rule": context["rule_id"]},
            )
        )
    sentences.append("No categorical direction or anomaly state is assigned under v2.")
    return " ".join(sentences)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.6g}"


def _format_percentile(value: float) -> str:
    return f"{value:.1f}"
