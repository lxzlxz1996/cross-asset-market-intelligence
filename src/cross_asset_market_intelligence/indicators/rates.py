"""Pure, documented rate calculations with no data-source dependency."""


def ten_year_minus_two_year(ten_year_yield: float, two_year_yield: float) -> float:
    """Return the 10Y–2Y slope in percentage points.

    Inputs must use the same observation date and yield unit. Date alignment and
    missing-value handling belong to the future processing layer.
    """
    return ten_year_yield - two_year_yield
