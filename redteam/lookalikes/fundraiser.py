"""honest look-alike persona, synthetic, planted by the red team; must NOT be flagged as a mule"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World


def plant_fundraiser(w: World, n: int = 3, instance: int = 0) -> None:
    """Plant honest fundraisers collecting for a relative: many distinct donors send small
    gifts over a few days, then the collected total is remitted to a clinic abroad (DE or AT)."""
    popular_pool = w.popular_pool(20)
    _ = popular_pool
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        contract_date = datetime(2026, 7, 1, tzinfo=UTC) - timedelta(days=int(w.rng.integers(365, 2191)))
        cid = w.new_client(bank, contract_date=contract_date)
        w.label(cid, "honest", "lookalike", persona="fundraiser", instance=instance)

        n_in = int(w.rng.integers(15, 41))
        span_days = int(w.rng.integers(3, 9))
        start_day = int(w.rng.integers(1, 23))
        last_day = start_day + span_days
        in_days = [start_day, last_day] + [int(w.rng.integers(start_day, last_day + 1)) for _ in range(n_in - 2)]
        inflows = sorted(
            (w.random_time(day_from=d, day_to=d), round(float(w.rng.uniform(200.0, 5000.0)), 2), w.new_ext_account())
            for d in in_days
        )
        total_in = 0.0
        for ts, amount, sender in inflows:
            w.add_tx(cid, ts, amount, "in", sender)
            total_in += amount

        last_in = inflows[-1][0]
        out_ts = last_in + timedelta(days=int(w.rng.integers(1, 5)), hours=int(w.rng.integers(0, 5)))
        clinic = w.new_ext_account(country=str(w.rng.choice(["DE", "AT"])))
        w.add_tx(cid, out_ts, round(total_in * float(w.rng.uniform(0.92, 1.0)), 2), "remit_out", clinic,
                 country=clinic[1:3])
