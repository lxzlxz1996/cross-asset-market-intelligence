import pytest

from analyze import linear_slope_bp, sign_evidence


def test_linear_slope_has_interpretable_bp_per_observation_units():
    assert linear_slope_bp([1.00, 1.01, 1.02, 1.03, 1.04]) == pytest.approx(1.0)
    assert linear_slope_bp([2.0] * 5) == 0.0


def test_sign_evidence_preserves_zeros_and_balance():
    result = sign_evidence([1, 0, -2, 0, 3])
    assert result == {
        "positive": 2, "zero": 2, "negative": 1, "balance": 1,
        "positive_share": .4, "zero_share": .4, "negative_share": .2,
    }
