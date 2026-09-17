from cross_asset_market_intelligence.indicators.rates import ten_year_minus_two_year


def test_ten_year_minus_two_year_is_calculated_in_percentage_points() -> None:
    assert ten_year_minus_two_year(4.50, 4.25) == 0.25
