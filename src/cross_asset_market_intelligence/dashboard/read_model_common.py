"""Small shared helpers for read-only selected-observation projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class DashboardChange:
    """A descriptive difference from a prior valid selected observation."""

    lag_observations: Literal[1, 5, 20]
    value: float | None
    unit: Literal["percentage_points"] = "percentage_points"


def changes_for_index(
    selected: list[tuple[str, str, date, float, str]], index: int
) -> tuple[DashboardChange, DashboardChange, DashboardChange]:
    """Calculate approved observation-count lags from selected history only."""
    current_value = selected[index][3]
    return tuple(
        DashboardChange(
            lag_observations=lag,
            value=current_value - selected[index - lag][3] if index >= lag else None,
        )
        for lag in (1, 5, 20)
    )  # type: ignore[return-value]
