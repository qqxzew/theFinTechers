import pytest

from ingest.units import projected_monthly, q2_daily_average


def test_projected_monthly():
    assert projected_monthly(1200.0, "monthly") == 1200.0
    assert projected_monthly(3000.0, "quarterly") == pytest.approx(1000.0)
    assert projected_monthly(12000.0, "yearly") == pytest.approx(1000.0)
    with pytest.raises(ValueError):
        projected_monthly(1.0, "weekly")


def test_q2_daily_average():
    # Q2 2026 has 91 days: April 30 + May 31 + June 30
    assert q2_daily_average(9100.0, "quarterly") == pytest.approx(100.0)
    assert q2_daily_average(9100.0, "monthly") == pytest.approx(9100.0 * 3 / 91)
    assert q2_daily_average(9100.0, "yearly") == pytest.approx(9100.0 / 365)
