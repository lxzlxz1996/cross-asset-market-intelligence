"""Production SOFR anomaly evidence under the frozen v1 methodology."""

from __future__ import annotations

import calendar
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

import duckdb

from ..dashboard.sofr_read_model import SofrDashboardObservation, sofr_history
from ..exceptions import SignalGenerationError
from .contract import (
    AvailabilityPrecision,
    EvidenceQuality,
    SignalDefinition,
    SignalDefinitionStatus,
    SignalObservation,
    SignalObservationInput,
)
from .explanations import render_explanation
from .persistence import persist_signal_definition, persist_signal_observation

SOFR_RATE_STATE_SIGNAL_ID = "sofr_rate_state"
SOFR_RATE_STATE_SIGNAL_VERSION = "v1"
SOFR_RATE_STATE_INDICATOR_ID = "sofr"
SOFR_ANOMALY_METHODOLOGY_ID = "sofr_change_rarity_v1"
SOFR_RECENT_WINDOW = 60
SOFR_BROAD_WINDOW = 252
SOFR_LEVEL_INPUT_ROLE = "sofr_level_history"
SOFR_CALENDAR_RULE_ID = "gregorian_last_weekday_v1"

SOFR_RATE_STATE_PARAMETERS: dict[str, object] = {
    "anomaly_methodology_id": SOFR_ANOMALY_METHODOLOGY_ID,
    "recent_window_count": SOFR_RECENT_WINDOW,
    "broad_window_count": SOFR_BROAD_WINDOW,
    "window_unit": "prior_valid_changes",
    "current_change_excluded": True,
    "percentile_basis": "absolute_change_1obs_bp",
    "primary_percentile_convention": "midrank",
    "audit_percentile_conventions": ["strict", "weak"],
    "tie_equality": "exact_decimal_bp_no_prerounding",
    "standard_z_role": "secondary_only",
    "standard_z_scale": "sample_std_ddof1",
    "missing_observation_policy": "previous_valid_no_fill_no_interpolation",
    "calendar_rule_id": SOFR_CALENDAR_RULE_ID,
    "anomaly_state_policy": "null_evidence_only",
    "materiality_policy": "quantitative_bp_only_no_threshold",
}


@dataclass(frozen=True)
class SofrSignalGenerationResult:
    """Persistence outcome and the deterministic observation that was evaluated."""

    definition_inserted: bool
    observation_inserted: bool
    observation: SignalObservation


def sofr_rate_state_definition() -> SignalDefinition:
    """Return the immutable production definition for SOFR Rate State v1."""
    return SignalDefinition(
        signal_id=SOFR_RATE_STATE_SIGNAL_ID,
        signal_version=SOFR_RATE_STATE_SIGNAL_VERSION,
        indicator_id=SOFR_RATE_STATE_INDICATOR_ID,
        name="SOFR Rate State",
        economic_question=(
            "How large was the latest SOFR move, and how unusual was it relative "
            "to recent and broader prior SOFR behavior?"
        ),
        economic_hypothesis=(
            "Recent and broad self-history ranks provide distinct, auditable context "
            "for the latest SOFR movement."
        ),
        what_it_measures=(
            "Signed and absolute consecutive-valid-observation SOFR change, empirical "
            "absolute-change rarity over prior 60 and 252 changes, and secondary standard-Z context."
        ),
        what_it_does_not_mean=(
            "It does not establish funding or liquidity stress, financial crisis, financial-conditions "
            "direction, asset-return direction, or a portfolio action."
        ),
        methodology_description=(
            "Evidence-only anomaly methodology sofr_change_rarity_v1: current-excluded empirical "
            "absolute-change midrank with strict/weak tie audit at 60 and 252 prior valid changes; "
            "signed bp magnitude remains separate; anomaly_state is null."
        ),
        parameter_definition=SOFR_RATE_STATE_PARAMETERS,
        limitations=(
            "No materiality threshold or categorical anomaly state; standard Z is secondary only; "
            "robust Z is excluded; calendar context lacks holiday adjustment; historical publication "
            "times may be unknown and economic-date history is not point-in-time replay."
        ),
        status=SignalDefinitionStatus.ACTIVE,
    )


def generate_sofr_rate_state(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of_observation_date: date | None = None,
    calculated_at: datetime | None = None,
) -> SofrSignalGenerationResult:
    """Build and persist one SOFR anomaly-evidence observation idempotently."""
    timestamp = calculated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SignalGenerationError("calculated_at must be timezone-aware")
    observation = build_sofr_rate_state_observation(
        connection,
        as_of_observation_date=as_of_observation_date,
        calculated_at=timestamp,
    )
    definition_inserted = persist_signal_definition(connection, sofr_rate_state_definition())
    observation_inserted = persist_signal_observation(connection, observation)
    return SofrSignalGenerationResult(definition_inserted, observation_inserted, observation)


def build_sofr_rate_state_observation(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of_observation_date: date | None = None,
    calculated_at: datetime,
) -> SignalObservation:
    """Construct a validated observation without persisting it."""
    if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
        raise SignalGenerationError("calculated_at must be timezone-aware")
    history = sofr_history(connection, end_date=as_of_observation_date)
    if not history:
        raise SignalGenerationError("No selected SOFR observation is available")
    if as_of_observation_date is not None and history[-1].observation_date != as_of_observation_date:
        raise SignalGenerationError("The requested as-of date is not a selected SOFR observation date")
    if len(history) < 2:
        raise SignalGenerationError("SOFR anomaly evidence requires current and previous valid observations")

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
    availability_precision, information_available_at = _publication_availability(
        connection, [item.processed_observation_id for item in lineage_levels]
    )
    quality, quality_reasons = _evidence_quality(
        len(prior_changes), availability_precision
    )

    change_value = float(current_change)
    evidence: dict[str, Any] = {
        "methodology_id": SOFR_ANOMALY_METHODOLOGY_ID,
        "change": {
            "previous_observation_date": lineage_levels[-2].observation_date.isoformat(),
            "calendar_gap_days": (
                lineage_levels[-1].observation_date - lineage_levels[-2].observation_date
            ).days,
            "change_1obs_bp": change_value,
            "absolute_change_1obs_bp": float(abs(current_change)),
        },
        "recent_rarity_60": recent,
        "broad_rarity_252": broad,
        "calendar_context": context,
        "secondary_diagnostics": diagnostics,
    }
    _validate_evidence(evidence, prior_changes)
    explanation = _explanation(evidence)
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
        signal_version=SOFR_RATE_STATE_SIGNAL_VERSION,
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
        parameters_used=SOFR_RATE_STATE_PARAMETERS,
        explanation=explanation,
        quality_reasons=quality_reasons,
        inputs=inputs,
    )


def calendar_context(observation_date: date) -> dict[str, object]:
    """Return frozen, holiday-unadjusted Gregorian boundary context."""
    boundary = date(
        observation_date.year,
        observation_date.month,
        calendar.monthrange(observation_date.year, observation_date.month)[1],
    )
    while boundary.weekday() >= 5:
        boundary -= timedelta(days=1)
    month_end = observation_date == boundary
    return {
        "rule_id": SOFR_CALENDAR_RULE_ID,
        "month_end": month_end,
        "quarter_end": month_end and observation_date.month in (3, 6, 9, 12),
        "year_end": month_end and observation_date.month == 12,
    }


def _change_bp(previous: SofrDashboardObservation, current: SofrDashboardObservation) -> Decimal:
    return (Decimal(str(current.value)) - Decimal(str(previous.value))) * Decimal("100")


def _rarity_evidence(
    current: Decimal,
    prior_changes: Sequence[Decimal],
    prior_dates: Sequence[date],
    window_count: int,
) -> dict[str, object]:
    available = min(len(prior_changes), window_count)
    if len(prior_changes) < window_count:
        return {
            "status": "insufficient_history",
            "window_count": window_count,
            "available_prior_change_count": available,
            "strict_percentile": None,
            "midrank_percentile": None,
            "weak_percentile": None,
            "less_count": None,
            "equal_count": None,
            "greater_count": None,
            "baseline_start_date": None,
            "baseline_end_date": None,
        }
    prior = prior_changes[-window_count:]
    dates = prior_dates[-window_count:]
    current_abs = abs(current)
    less = sum(abs(item) < current_abs for item in prior)
    equal = sum(abs(item) == current_abs for item in prior)
    greater = window_count - less - equal
    return {
        "status": "available",
        "window_count": window_count,
        "available_prior_change_count": window_count,
        "strict_percentile": 100.0 * less / window_count,
        "midrank_percentile": 100.0 * (less + 0.5 * equal) / window_count,
        "weak_percentile": 100.0 * (less + equal) / window_count,
        "less_count": less,
        "equal_count": equal,
        "greater_count": greater,
        "baseline_start_date": dates[0].isoformat(),
        "baseline_end_date": dates[-1].isoformat(),
    }


def _standard_z_evidence(
    current: Decimal, prior_changes: Sequence[Decimal], window_count: int
) -> dict[str, object]:
    if len(prior_changes) < window_count:
        return {
            "status": "insufficient_history",
            "value": None,
            "prior_mean_bp": None,
            "prior_sample_std_bp": None,
        }
    prior = [float(item) for item in prior_changes[-window_count:]]
    mean = statistics.mean(prior)
    standard_deviation = statistics.stdev(prior)
    if standard_deviation == 0:
        return {
            "status": "zero_scale",
            "value": None,
            "prior_mean_bp": mean,
            "prior_sample_std_bp": standard_deviation,
        }
    return {
        "status": "available",
        "value": (float(current) - mean) / standard_deviation,
        "prior_mean_bp": mean,
        "prior_sample_std_bp": standard_deviation,
    }


def _validate_level_sequence(levels: Sequence[SofrDashboardObservation]) -> None:
    if len(levels) < 2:
        raise SignalGenerationError("SOFR level history must contain at least two observations")
    dates = [item.observation_date for item in levels]
    identifiers = [item.processed_observation_id for item in levels]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise SignalGenerationError("SOFR level history must have unique increasing dates")
    if len(set(identifiers)) != len(identifiers):
        raise SignalGenerationError("SOFR level history contains duplicate processed identities")
    if any(item.indicator_id != SOFR_RATE_STATE_INDICATOR_ID for item in levels):
        raise SignalGenerationError("SOFR signal inputs contain an inconsistent indicator identity")


def _validate_evidence(evidence: dict[str, Any], prior_changes: Sequence[Decimal]) -> None:
    for field, window in (("recent_rarity_60", 60), ("broad_rarity_252", 252)):
        rarity = evidence[field]
        expected_available = len(prior_changes) >= window
        if (rarity["status"] == "available") != expected_available:
            raise SignalGenerationError(f"{field} availability is inconsistent with prior history")
        if not expected_available:
            continue
        counts = (rarity["less_count"], rarity["equal_count"], rarity["greater_count"])
        if any(not isinstance(count, int) for count in counts) or sum(counts) != window:
            raise SignalGenerationError(f"{field} percentile counts do not sum to its window")
        strict = rarity["strict_percentile"]
        midrank = rarity["midrank_percentile"]
        weak = rarity["weak_percentile"]
        if not (0 <= strict <= midrank <= weak <= 100):
            raise SignalGenerationError(f"{field} percentile ordering is invalid")
        if abs(midrank - (strict + weak) / 2) > 1e-12:
            raise SignalGenerationError(f"{field} midrank is inconsistent with its tie bracket")


def _publication_availability(
    connection: duckdb.DuckDBPyConnection, processed_ids: Sequence[str]
) -> tuple[AvailabilityPrecision, datetime | None]:
    placeholders = ", ".join("?" for _ in processed_ids)
    try:
        rows = connection.execute(
            f"""
            SELECT input.processed_observation_id, raw.publication_timestamp
            FROM processed_observation_inputs AS input
            JOIN raw_observations AS raw
              ON raw.source = input.raw_source
             AND raw.series_id = input.raw_series_id
             AND raw.observation_date = input.raw_observation_date
             AND raw.vintage = input.raw_vintage
            WHERE input.input_role = 'source'
              AND input.processed_observation_id IN ({placeholders})
            """,
            list(processed_ids),
        ).fetchall()
    except duckdb.Error as error:
        raise SignalGenerationError("Could not resolve SOFR publication-time lineage") from error
    by_identifier = {identifier: publication for identifier, publication in rows}
    if len(by_identifier) != len(processed_ids):
        raise SignalGenerationError("SOFR signal inputs do not have exact raw publication lineage")
    publications = [by_identifier[identifier] for identifier in processed_ids]
    if any(publication is None for publication in publications):
        return AvailabilityPrecision.UNKNOWN, None
    return AvailabilityPrecision.EXACT_TIMESTAMP, max(publications)


def _evidence_quality(
    prior_change_count: int, availability_precision: AvailabilityPrecision
) -> tuple[EvidenceQuality, tuple[str, ...]]:
    reasons: list[str] = []
    if prior_change_count < SOFR_RECENT_WINDOW:
        quality = EvidenceQuality.INSUFFICIENT
        reasons.append("recent_history_warmup")
    elif prior_change_count < SOFR_BROAD_WINDOW:
        quality = EvidenceQuality.LIMITED
        reasons.append("broad_history_warmup")
    else:
        quality = EvidenceQuality.SUFFICIENT
    if availability_precision is AvailabilityPrecision.UNKNOWN:
        reasons.append("information_availability_unknown")
        if quality is EvidenceQuality.SUFFICIENT:
            quality = EvidenceQuality.LIMITED
    return quality, tuple(reasons)


def _explanation(evidence: dict[str, Any]) -> str:
    change = evidence["change"]["change_1obs_bp"]
    if change > 0:
        movement = f"rose {_format_number(change)}bp"
    elif change < 0:
        movement = f"declined {_format_number(abs(change))}bp"
    else:
        movement = "was unchanged"
    sentences = [
        render_explanation(
            "SOFR {movement} from the previous valid observation.",
            {"movement": movement},
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
                    "The absolute move has {label} midrank {midrank} on a 0-100 scale "
                    "relative to the prior {window} valid SOFR changes "
                    "(strict {strict}; weak {weak}).",
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
    context = evidence["calendar_context"]
    boundary = "year-end" if context["year_end"] else "quarter-end" if context["quarter_end"] else "month-end" if context["month_end"] else None
    if boundary is not None:
        sentences.append(
            render_explanation(
                "The observation matches the {boundary} context under the {rule} calendar rule; "
                "calendar context does not alter either rarity measure.",
                {"boundary": boundary, "rule": context["rule_id"]},
            )
        )
    sentences.append("No categorical anomaly classification is assigned under v1.")
    return " ".join(sentences)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.6g}"


def _format_percentile(value: float) -> str:
    return f"{value:.1f}"
