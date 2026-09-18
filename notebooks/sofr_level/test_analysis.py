from decimal import Decimal

import pytest

from analyze import decimal_median, level_z, percentile_evidence


def test_percentile_evidence_preserves_ties_and_excludes_current_by_input_contract():
    result = percentile_evidence(Decimal("2"), [Decimal("1"), Decimal("2"), Decimal("2"), Decimal("3")])
    assert result == {
        "less": 1, "equal": 2, "greater": 1,
        "strict": 25.0, "midrank": 50.0, "weak": 75.0,
    }


def test_decimal_median_and_level_z_zero_scale():
    assert decimal_median([Decimal("1"), Decimal("3")]) == Decimal("2")
    assert decimal_median([Decimal("1"), Decimal("2"), Decimal("3")]) == Decimal("2")
    assert level_z(Decimal("1"), [Decimal("1")] * 20) == (None, "zero_scale")


def test_level_z_uses_sample_standard_deviation():
    value, status = level_z(Decimal("4"), [Decimal("1"), Decimal("2"), Decimal("3")])
    assert status == "available"
    assert value == pytest.approx(2.0)
