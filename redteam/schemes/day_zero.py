"""Day-zero mule: dormant fresh account, one large third-party inflow, rapid near-total cash-out.

Planted red-team scheme, synthetic, designed from public descriptions of Czech/CEE money-mule schemes.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World

EXIT_COUNTRIES = ["CZ", "SK", "DE", "LT", "BG"]


def _split_total(rng, total: float, k: int) -> list[float]:
    """Split `total` into `k` positive parts; the first part is >= 100000."""
    if k == 1:
        return [total]
    first = float(rng.uniform(100000.0, total * 0.7))
    rest = total - first
    weights = rng.uniform(0.2, 1.0, size=k - 1)
    parts = [first] + [float(rest * x / weights.sum()) for x in weights]
    return parts


def plant_day_zero(w: World, n: int = 5, instance: int = 0) -> None:
    """Plant `n` day-zero mule accounts into the world."""
    rng = w.rng
    for _ in range(n):
        bank = w.banks[int(rng.integers(len(w.banks)))]
        contract_date = datetime(2026, 7, 1, tzinfo=UTC) - timedelta(days=int(rng.integers(1, 41)))
        contract_form = "in person" if float(rng.random()) < 0.6 else "distant form"
        cid = w.new_client(
            bank,
            contract_date=contract_date,
            contract_form=contract_form,
            expected_volume=float(rng.uniform(20000.0, 60000.0)),
            q2_volume=0,
            q2_count=0,
            q2_max=0,
        )

        event_ts = w.random_time(3, 25)
        for _ in range(int(rng.integers(0, 3))):
            w.add_tx(
                cid,
                w.random_time(1, event_ts.day - 1),
                float(rng.uniform(500.0, 3000.0)),
                "out",
                w.new_ext_account(),
            )

        inflow_total = float(rng.uniform(150000.0, 600000.0))
        parts = _split_total(rng, inflow_total, int(rng.integers(1, 4)))
        big_ts = event_ts
        for i, part in enumerate(parts):
            ts = event_ts if i == 0 else event_ts + timedelta(minutes=int(rng.integers(0, 5)))
            w.add_tx(cid, ts, part, "in", w.new_ext_account())

        out_total = inflow_total * float(rng.uniform(0.92, 0.99))
        n_out = int(rng.integers(1, 5))
        weights = rng.uniform(0.2, 1.0, size=n_out)
        offsets = sorted(int(x) for x in rng.integers(1, 24 * 60, size=n_out))
        for j in range(n_out):
            amount = float(out_total * weights[j] / weights.sum())
            direction = "remit_out" if float(rng.random()) < 0.4 else "out"
            country = EXIT_COUNTRIES[int(rng.integers(len(EXIT_COUNTRIES)))]
            w.add_tx(
                cid,
                big_ts + timedelta(minutes=offsets[j]),
                amount,
                direction,
                w.new_ext_account(country),
                country=country,
            )

        w.label(cid, "mule", "day_zero", instance=instance)
