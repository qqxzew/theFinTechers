"""Students splitting rent: honest look-alike persona, synthetic, planted by the red team; must NOT be flagged as a mule."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World


def plant_students_rent(w: World, n: int = 4, instance: int = 0) -> None:
    """Plant n honest rent collectors: flatmates send their shares in, one rent payment goes out to the landlord."""
    popular_pool = w.popular_pool(20)
    for _ in range(n):
        bank_id = str(w.rng.choice(w.banks))
        months = int(w.rng.integers(6, 41))
        contract_date = datetime(2026, 7, 1, tzinfo=UTC) - timedelta(days=int(months * 30.4375))
        cid = w.new_client(bank_id, contract_date=contract_date)
        w.label(cid, "honest", "lookalike", persona="students_rent", instance=instance)

        base = datetime(2026, 7, 1, tzinfo=UTC)
        n_flat = int(w.rng.integers(3, 6))
        inflow_ts: list[datetime] = []
        total_in = 0.0
        for _ in range(n_flat):
            flatmate = w.new_ext_account()
            amount = round(float(w.rng.uniform(4000.0, 9000.0)), 2)
            ts = base + timedelta(hours=float(w.rng.uniform(0.0, 47.5)))
            w.add_tx(cid, ts, amount, "in", flatmate)
            inflow_ts.append(ts)
            total_in += amount

        n_small = int(w.rng.integers(6, 13))
        small_amounts = [round(float(w.rng.uniform(100.0, 2000.0)), 2) for _ in range(n_small)]
        total_small = sum(small_amounts)
        if total_small > 0.5 * total_in:
            scale = 0.5 * total_in / total_small
            small_amounts = [round(a * scale, 2) for a in small_amounts]
            total_small = sum(small_amounts)
        for amount in small_amounts:
            w.add_tx(cid, w.random_time(1, 31), amount, "out", str(w.rng.choice(popular_pool)))

        landlord = w.new_ext_account()
        frac = float(w.rng.uniform(0.92, 1.0))
        rent = round(frac * (total_in - total_small), 2)
        rent_ts = max(inflow_ts) + timedelta(hours=float(w.rng.uniform(1.0, 24.0)))
        w.add_tx(cid, rent_ts, rent, "out", landlord)
