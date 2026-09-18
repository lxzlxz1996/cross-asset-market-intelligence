"""Combined frozen anomaly, Direction, and Level evidence for SOFR Rate State v3."""

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
    SOFR_LEVEL_INPUT_ROLE,
    SOFR_RATE_STATE_INDICATOR_ID,
    SOFR_RATE_STATE_SIGNAL_ID,
    SofrSignalGenerationResult,
    _evidence_quality,
    _publication_availability,
    _validate_level_sequence,
)
from .sofr_rate_state_v2 import (
    SOFR_DIRECTION_METHODOLOGY_ID,
    SOFR_RATE_STATE_V2_PARAMETERS,
    _format_number,
    _format_percentile,
    _v2_explanation,
    build_sofr_rate_state_v2_observation,
)

SOFR_RATE_STATE_V3_SIGNAL_VERSION = "v3"
SOFR_LEVEL_METHODOLOGY_ID = "sofr_level_evidence_v1"
SOFR_LEVEL_RECENT_WINDOW = 60

SOFR_RATE_STATE_V3_PARAMETERS: dict[str, object] = {
    **{
        key: value
        for key, value in SOFR_RATE_STATE_V2_PARAMETERS.items()
        if key not in {"level_methodology", "level_state_policy"}
    },
    "level_methodology_id": SOFR_LEVEL_METHODOLOGY_ID,
    "level_current_unit": "percent_per_annum",
    "level_current_normalization": "none_canonical_processed_value",
    "level_broad_reference": "all_canonical_valid_prior_observations",
    "level_broad_current_excluded": True,
    "level_broad_future_excluded": True,
    "level_percentile_method": "midrank",
    "level_tie_audit": "strict_weak_counts",
    "level_tie_equality": "exact_decimal_percent_no_prerounding",
    "level_recent_reference": "prior_60_valid_level_median",
    "level_recent_window_levels": SOFR_LEVEL_RECENT_WINDOW,
    "level_recent_current_excluded": True,
    "level_recent_distance_unit": "basis_points",
    "level_missing_observation_policy": "valid_observations_no_fill_no_interpolation",
    "level_rolling_percentile_policy": "excluded",
    "level_z_policy": "excluded",
    "level_robust_z_policy": "excluded",
    "level_state_classification": "none",
    "direction_state_classification": "none",
    "anomaly_state_classification": "none",
    "level_lineage_policy": "exact_expanding_ordered_processed_inputs",
}


def sofr_rate_state_v3_definition() -> SignalDefinition:
    """Return the immutable production definition for SOFR Rate State v3."""
    return SignalDefinition(
        signal_id=SOFR_RATE_STATE_SIGNAL_ID,
        signal_version=SOFR_RATE_STATE_V3_SIGNAL_VERSION,
        indicator_id=SOFR_RATE_STATE_INDICATOR_ID,
        name="SOFR Rate State v3",
        economic_question=(
            "Where is the current SOFR level relative to broad prior history and its recent local "
            "environment, how unusual was its latest move, and what path occurred over the latest "
            "20 valid changes?"
        ),
        economic_hypothesis=(
            "Separate Level, anomaly, and Direction evidence provides an auditable description "
            "without collapsing policy-dependent measures into a state or score."
        ),
        what_it_measures=(
            "Unchanged sofr_change_rarity_v1 anomaly evidence, unchanged "
            "sofr_direction_evidence_v1 path evidence, and sofr_level_evidence_v1: the canonical "
            "current level, expanding prior-only tie-audited historical rank, and prior-60 median distance."
        ),
        what_it_does_not_mean=(
            "It does not establish funding or liquidity stress, tight or easy monetary policy, "
            "Federal Reserve intent, a market regime, expected returns, a trade, or a portfolio action."
        ),
        methodology_description=(
            "Evidence-only SOFR Rate State v3. Frozen v1 anomaly and v1 Direction components are "
            "preserved. Frozen Level v1 uses exact canonical decimal comparisons against every prior "
            "selected level and a separate exact prior-60 median reference. All categorical states are null."
        ),
        parameter_definition=SOFR_RATE_STATE_V3_PARAMETERS,
        limitations=(
            "No categorical Level, Direction, or anomaly state; no policy or funding-spread interpretation; "
            "historical publication-time replay remains unresolved. Exact expanding Level lineage grows "
            "with history and is a v3-specific reproducibility choice, not a system-wide requirement."
        ),
        status=SignalDefinitionStatus.ACTIVE,
    )


def generate_sofr_rate_state_v3(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of_observation_date: date | None = None,
    calculated_at: datetime | None = None,
) -> SofrSignalGenerationResult:
    """Build and persist one combined SOFR Rate State v3 observation idempotently."""
    timestamp = calculated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SignalGenerationError("calculated_at must be timezone-aware")
    observation = build_sofr_rate_state_v3_observation(
        connection,
        as_of_observation_date=as_of_observation_date,
        calculated_at=timestamp,
    )
    definition_inserted = persist_signal_definition(connection, sofr_rate_state_v3_definition())
    observation_inserted = persist_signal_observation(connection, observation)
    return SofrSignalGenerationResult(definition_inserted, observation_inserted, observation)


def build_sofr_rate_state_v3_observation(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of_observation_date: date | None = None,
    calculated_at: datetime,
) -> SignalObservation:
    """Construct a validated v3 observation while reusing the frozen v2 calculations."""
    v2 = build_sofr_rate_state_v2_observation(
        connection,
        as_of_observation_date=as_of_observation_date,
        calculated_at=calculated_at,
    )
    history = sofr_history(connection, end_date=as_of_observation_date)
    if not history or history[-1].observation_date != v2.as_of_observation_date:
        raise SignalGenerationError("V3 full history is inconsistent with the frozen v2 as-of observation")
    _validate_level_sequence(history)

    level = _level_evidence(history)
    _validate_level_evidence(level, history)
    evidence = dict(v2.evidence)
    evidence["level_evidence"] = level

    processed_ids = [item.processed_observation_id for item in history]
    availability_precision, information_available_at = _publication_availability(
        connection, processed_ids
    )
    quality, quality_reasons = _evidence_quality(len(history) - 2, availability_precision)
    inputs = tuple(
        SignalObservationInput(
            processed_observation_id=item.processed_observation_id,
            input_role=SOFR_LEVEL_INPUT_ROLE,
            window_position=position,
        )
        for position, item in enumerate(history)
    )
    return SignalObservation(
        signal_id=SOFR_RATE_STATE_SIGNAL_ID,
        signal_version=SOFR_RATE_STATE_V3_SIGNAL_VERSION,
        indicator_id=SOFR_RATE_STATE_INDICATOR_ID,
        as_of_observation_date=history[-1].observation_date,
        information_available_at=information_available_at,
        information_available_date=None,
        availability_precision=availability_precision,
        calculated_at=calculated_at,
        level_state=None,
        direction_state=None,
        anomaly_state=None,
        evidence_quality=quality,
        evidence=evidence,
        parameters_used=SOFR_RATE_STATE_V3_PARAMETERS,
        explanation=_v3_explanation(evidence),
        quality_reasons=quality_reasons,
        inputs=inputs,
    )


def _level_evidence(levels: Sequence[SofrDashboardObservation]) -> dict[str, Any]:
    """Calculate frozen Level evidence from an oldest-to-current canonical sequence."""
    if not levels:
        raise SignalGenerationError("Level evidence requires a current SOFR observation")
    current = _decimal_level(levels[-1])
    prior_levels = list(levels[:-1])
    prior_count = len(prior_levels)

    if prior_count == 0:
        broad: dict[str, Any] = {
            "status": "insufficient_history",
            "prior_observation_count": 0,
            "baseline_start_date": None,
            "baseline_end_date": None,
            "less_count": None,
            "equal_count": None,
            "greater_count": None,
            "strict_percentile": None,
            "midrank_percentile": None,
            "weak_percentile": None,
        }
    else:
        values = [_decimal_level(item) for item in prior_levels]
        less = sum(value < current for value in values)
        equal = sum(value == current for value in values)
        greater = prior_count - less - equal
        broad = {
            "status": "available",
            "prior_observation_count": prior_count,
            "baseline_start_date": prior_levels[0].observation_date.isoformat(),
            "baseline_end_date": prior_levels[-1].observation_date.isoformat(),
            "less_count": less,
            "equal_count": equal,
            "greater_count": greater,
            "strict_percentile": float(Decimal("100") * Decimal(less) / Decimal(prior_count)),
            "midrank_percentile": float(
                Decimal("100")
                * (Decimal(less) + Decimal("0.5") * Decimal(equal))
                / Decimal(prior_count)
            ),
            "weak_percentile": float(
                Decimal("100") * Decimal(less + equal) / Decimal(prior_count)
            ),
        }

    available_recent = min(prior_count, SOFR_LEVEL_RECENT_WINDOW)
    if prior_count < SOFR_LEVEL_RECENT_WINDOW:
        recent: dict[str, Any] = {
            "status": "insufficient_history",
            "required_prior_level_count": SOFR_LEVEL_RECENT_WINDOW,
            "available_prior_level_count": available_recent,
            "baseline_start_date": None,
            "baseline_end_date": None,
            "prior_60_median_level_percent": None,
            "distance_from_prior_60_median_bp": None,
        }
    else:
        window = prior_levels[-SOFR_LEVEL_RECENT_WINDOW:]
        ordered = sorted(_decimal_level(item) for item in window)
        median = (ordered[29] + ordered[30]) / Decimal("2")
        distance = Decimal("100") * (current - median)
        recent = {
            "status": "available",
            "required_prior_level_count": SOFR_LEVEL_RECENT_WINDOW,
            "available_prior_level_count": SOFR_LEVEL_RECENT_WINDOW,
            "baseline_start_date": window[0].observation_date.isoformat(),
            "baseline_end_date": window[-1].observation_date.isoformat(),
            "prior_60_median_level_percent": float(median),
            "distance_from_prior_60_median_bp": float(distance),
        }

    return {
        "methodology_id": SOFR_LEVEL_METHODOLOGY_ID,
        "current_level_percent": float(current),
        "broad_historical_context": broad,
        "recent_context": recent,
    }


def _decimal_level(level: SofrDashboardObservation) -> Decimal:
    value = Decimal(str(level.value))
    if not value.is_finite():
        raise SignalGenerationError("SOFR Level evidence contains a non-finite value")
    return value


def _validate_level_evidence(
    level: dict[str, Any], levels: Sequence[SofrDashboardObservation]
) -> None:
    if level.get("methodology_id") != SOFR_LEVEL_METHODOLOGY_ID:
        raise SignalGenerationError("Level methodology identity is invalid")
    if not levels:
        raise SignalGenerationError("Level validation requires a current observation")
    current = _decimal_level(levels[-1])
    if Decimal(str(level.get("current_level_percent"))) != current:
        raise SignalGenerationError("Current Level evidence does not match the canonical processed value")

    broad = level["broad_historical_context"]
    prior_count = len(levels) - 1
    if broad["prior_observation_count"] != prior_count:
        raise SignalGenerationError("Broad Level prior count does not match exact history")
    if prior_count == 0:
        if broad["status"] != "insufficient_history":
            raise SignalGenerationError("Broad Level must be unavailable without prior history")
        nullable = (
            "baseline_start_date", "baseline_end_date", "less_count", "equal_count",
            "greater_count", "strict_percentile", "midrank_percentile", "weak_percentile",
        )
        if any(broad[field] is not None for field in nullable):
            raise SignalGenerationError("Broad Level warm-up contains mathematically undefined fields")
    else:
        if broad["status"] != "available":
            raise SignalGenerationError("Broad Level availability is inconsistent with prior history")
        expected = _level_evidence(levels)["broad_historical_context"]
        counts = (broad["less_count"], broad["equal_count"], broad["greater_count"])
        if any(not isinstance(count, int) for count in counts) or sum(counts) != prior_count:
            raise SignalGenerationError("Broad Level counts do not sum to prior history")
        if broad["baseline_start_date"] != levels[0].observation_date.isoformat() or broad[
            "baseline_end_date"
        ] != levels[-2].observation_date.isoformat():
            raise SignalGenerationError("Broad Level dates do not match exact prior history")
        for field in ("less_count", "equal_count", "greater_count"):
            if broad[field] != expected[field]:
                raise SignalGenerationError("Broad Level tie counts do not match exact history")
        strict = float(broad["strict_percentile"])
        midrank = float(broad["midrank_percentile"])
        weak = float(broad["weak_percentile"])
        if not all(math.isfinite(value) for value in (strict, midrank, weak)):
            raise SignalGenerationError("Broad Level contains a non-finite percentile")
        if not 0 <= strict <= midrank <= weak <= 100:
            raise SignalGenerationError("Broad Level percentile ordering is invalid")
        if not math.isclose(midrank, (strict + weak) / 2, rel_tol=1e-12, abs_tol=1e-12):
            raise SignalGenerationError("Broad Level midrank is inconsistent with its tie bracket")
        if any(
            not math.isclose(float(broad[field]), float(expected[field]), rel_tol=1e-12, abs_tol=1e-12)
            for field in ("strict_percentile", "midrank_percentile", "weak_percentile")
        ):
            raise SignalGenerationError("Broad Level percentiles do not match exact history")

    recent = level["recent_context"]
    if recent["required_prior_level_count"] != SOFR_LEVEL_RECENT_WINDOW:
        raise SignalGenerationError("Recent Level required count is invalid")
    expected_available = min(prior_count, SOFR_LEVEL_RECENT_WINDOW)
    if recent["available_prior_level_count"] != expected_available:
        raise SignalGenerationError("Recent Level available count is inconsistent with history")
    if prior_count < SOFR_LEVEL_RECENT_WINDOW:
        if recent["status"] != "insufficient_history":
            raise SignalGenerationError("Recent Level must be unavailable before 60 prior levels")
        nullable = (
            "baseline_start_date", "baseline_end_date", "prior_60_median_level_percent",
            "distance_from_prior_60_median_bp",
        )
        if any(recent[field] is not None for field in nullable):
            raise SignalGenerationError("Recent Level warm-up must not contain partial values")
        return

    if recent["status"] != "available":
        raise SignalGenerationError("Recent Level availability is inconsistent with history")
    window = levels[-(SOFR_LEVEL_RECENT_WINDOW + 1):-1]
    ordered = sorted(_decimal_level(item) for item in window)
    median = (ordered[29] + ordered[30]) / Decimal("2")
    distance = Decimal("100") * (current - median)
    if (
        recent["baseline_start_date"] != window[0].observation_date.isoformat()
        or recent["baseline_end_date"] != window[-1].observation_date.isoformat()
    ):
        raise SignalGenerationError("Recent Level dates do not match the exact 60-level window")
    if Decimal(str(recent["prior_60_median_level_percent"])) != median:
        raise SignalGenerationError("Recent Level median does not match the exact prior window")
    if Decimal(str(recent["distance_from_prior_60_median_bp"])) != distance:
        raise SignalGenerationError("Recent Level bp distance does not match current minus median")


def _v3_explanation(evidence: dict[str, Any]) -> str:
    level = evidence["level_evidence"]
    sentences = [
        render_explanation(
            "SOFR is currently {level}%.",
            {"level": f"{float(level['current_level_percent']):.2f}"},
        )
    ]
    broad = level["broad_historical_context"]
    if broad["status"] == "available":
        sentences.append(
            render_explanation(
                "Relative to all eligible prior SOFR observations, the current level has midrank "
                "{midrank} on a 0-100 scale, with a strict-to-weak range of {strict} to {weak} "
                "across {count} prior observations because identical historical levels affect the "
                "empirical rank.",
                {
                    "midrank": _format_percentile(broad["midrank_percentile"]),
                    "strict": _format_percentile(broad["strict_percentile"]),
                    "weak": _format_percentile(broad["weak_percentile"]),
                    "count": broad["prior_observation_count"],
                },
            )
        )
    else:
        sentences.append("Broad historical Level context is unavailable because no prior valid level exists.")

    recent = level["recent_context"]
    if recent["status"] == "available":
        distance = float(recent["distance_from_prior_60_median_bp"])
        if distance > 0:
            relation = f"{_format_number(distance)}bp above"
        elif distance < 0:
            relation = f"{_format_number(abs(distance))}bp below"
        else:
            relation = "equal to"
        sentences.append(
            render_explanation(
                "The current level is {relation} the median of the prior 60 valid SOFR observations.",
                {"relation": relation},
            )
        )
    else:
        sentences.append(
            render_explanation(
                "Recent Level context is unavailable because {available} of 60 required prior valid "
                "levels are available.",
                {"available": recent["available_prior_level_count"]},
            )
        )
    sentences.append(
        "The broad historical rank describes sample position only and does not imply funding stress "
        "or monetary-policy state."
    )
    v2_state_sentence = "No categorical direction or anomaly state is assigned under v2."
    v2_text = _v2_explanation(evidence)
    if not v2_text.endswith(v2_state_sentence):
        raise SignalGenerationError("Frozen v2 explanation ending is inconsistent")
    sentences.append(v2_text.removesuffix(v2_state_sentence).strip())
    sentences.append("No categorical level, direction, or anomaly state is assigned under v3.")
    return " ".join(sentence for sentence in sentences if sentence)
