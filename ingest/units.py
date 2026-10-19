"""Unit normalization helpers for cost values."""

Q2_DAYS = 91


def projected_monthly(value: float, unit: str) -> float:
    """Project value to a monthly figure; ValueError for unknown units."""
    if unit == "monthly":
        return value
    if unit == "quarterly":
        return value / 3
    if unit == "yearly":
        return value / 12
    raise ValueError(f"unknown unit: {unit}")


def q2_daily_average(value: float, unit: str) -> float:
    """Average per Q2 2026 day; ValueError for unknown units."""
    if unit == "quarterly":
        return value / Q2_DAYS
    if unit == "monthly":
        return value * 3 / Q2_DAYS
    if unit == "yearly":
        return value / 365
    raise ValueError(f"unknown unit: {unit}")
