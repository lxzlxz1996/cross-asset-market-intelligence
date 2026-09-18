"""Research invariants; synthetic values here are tests, never report inputs."""

from datetime import date
import pytest

from analyze import evaluate_change, event_comparison_rows, quantile, successive_diagnostics, weekday_month_end


def test_current_event_is_excluded_and_constant_baseline_is_undefined():
    result = evaluate_change(10, [0] * 20)
    assert result["prior_mean_bp"] == 0
    assert result["prior_std_bp"] == 0
    assert result["prior_mad_bp"] == 0
    assert result["standard_z"] is None and result["robust_z"] is None
    assert result["percentile_midrank"] == 100


def test_ties_preserve_three_distinct_conventions():
    result = evaluate_change(1, [0, 0, 1, -1, 2])
    assert result["percentile_strict"] == 40
    assert result["percentile_midrank"] == 60
    assert result["percentile_weak"] == 80
    assert (result["prior_less_count"], result["prior_equal_count"], result["prior_greater_count"]) == (2, 2, 1)


def test_sample_standard_deviation_and_unscaled_mad():
    result = evaluate_change(3, [-1, 0, 1])
    assert result["prior_std_bp"] == 1
    assert result["standard_z"] == 3
    assert result["prior_mad_bp"] == 1
    assert result["robust_z"] == pytest.approx(.6745 * 3)


def test_decimal_quantiles_and_calendar_rule():
    assert quantile([0, 1, 2, 3], .5) == 1.5
    assert weekday_month_end(date(2026, 10, 1)) == date(2026, 10, 30)


def test_successive_diagnostics_are_absolute_and_interpretable():
    result = successive_diagnostics([{"x": 1}, {"x": 3}, {"x": 2}, {"x": 6}], "x")
    assert result["count"] == 3
    assert result["median_absolute_change"] == 2
    assert result["maximum_absolute_change"] == 4


def test_successive_diagnostics_does_not_bridge_undefined_scores():
    result = successive_diagnostics([{"x": 1}, {"x": None}, {"x": 5}, {"x": 8}], "x")
    assert result["count"] == 1
    assert result["median_absolute_change"] == 3


def test_event_comparison_requires_every_window_and_keeps_all_four_rows():
    scores = []
    for day, magnitude, windows in (("2026-01-02", 5, (20, 60, 120, 252)), ("2026-01-03", 9, (20, 60))):
        for window in windows:
            scores.append({
                "date": day, "absolute_change_bp": magnitude, "change_bp": magnitude,
                "sofr_percent": 4.0, "previous_sofr_percent": 3.95, "window": window,
                "standard_z": 1, "robust_z": 1, "percentile_strict": 90,
                "percentile_midrank": 95, "percentile_weak": 100,
                "prior_less_count": window-1, "prior_equal_count": 1, "prior_greater_count": 0,
                "baseline_first_change_date": "2025-01-01", "baseline_last_change_date": "2026-01-01",
            })
    rows = event_comparison_rows(scores)
    assert len(rows) == 4
    assert {row["window"] for row in rows} == {20, 60, 120, 252}
    assert {row["date"] for row in rows} == {"2026-01-02"}
