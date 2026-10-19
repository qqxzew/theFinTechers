"""honest look-alike persona, synthetic, planted by the red team; must NOT be flagged as a mule"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World

JUL1 = datetime(2026, 7, 1, tzinfo=UTC)


def plant_group_collection(w: World, n: int = 4, instance: int = 0) -> None:
    """Plant honest organisers of a group collection: many distinct payers send small
    contributions, then exactly one near-total payment goes to a single venue/supplier,
    alongside small everyday transfers with popular accounts."""
    popular_pool = [w.new_ext_account() for _ in range(20)]
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        contract_date = JUL1 - timedelta(days=int(w.rng.integers(365, 2191)))
        cid = w.new_client(bank, contract_date=contract_date)
        w.label(cid, "honest", "lookalike", persona="group_collection", instance=instance)

        start_day = int(w.rng.integers(1, 23))
        last_day = start_day + int(w.rng.integers(2, 6))
        n_in = int(w.rng.integers(10, 26))
        in_days = [start_day, last_day] + [int(w.rng.integers(start_day, last_day + 1)) for _ in range(n_in - 2)]

        in_times: list[datetime] = []
        total_in = 0.0
        for _ in range(int(w.rng.integers(4, 9))):
            ts = w.random_time(1, last_day)
            amount = round(float(w.rng.uniform(30.0, 450.0)), 2)
            w.add_tx(cid, ts, amount, "in", popular_pool[int(w.rng.integers(0, len(popular_pool)))])
            in_times.append(ts)
            total_in += amount
        for day in in_days:
            ts = w.random_time(day, day)
            amount = round(float(w.rng.uniform(500.0, 2500.0)), 2)
            w.add_tx(cid, ts, amount, "in", w.new_ext_account())
            in_times.append(ts)
            total_in += amount

        out_ts = max(in_times) + timedelta(days=int(w.rng.integers(1, 4)))
        venue = w.new_ext_account()
        w.add_tx(cid, out_ts, round(total_in * float(w.rng.uniform(0.951, 0.999)), 2), "out", venue)
