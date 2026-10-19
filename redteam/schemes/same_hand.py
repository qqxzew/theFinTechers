"""'Same hand' scheme: one operator runs many accounts with a single lag, commission and exit pool.

Planted red-team scheme, synthetic, designed from public descriptions of Czech/CEE money-mule schemes.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import END, START, World


def plant_same_hand(w: World, n: int = 12, instance: int = 0) -> None:
    """Plant n mule accounts controlled by one operator sharing timing, skim rate and exit accounts."""
    lag_h = float(w.rng.uniform(1.5, 4.0))
    k = float(w.rng.uniform(0.05, 0.12))
    h0 = int(w.rng.integers(17, 22))
    exits = [w.new_ext_account() for _ in range(3)]

    for i in range(n):
        bank = w.banks[i % len(w.banks)]
        contract_date = START - timedelta(days=int(w.rng.integers(10, 121)))
        form = "distant form" if w.rng.random() < 0.5 else "in person"
        expected_volume = float(w.rng.uniform(20000, 80000))
        cid = w.new_client(
            bank,
            contract_date=contract_date,
            contract_form=form,
            expected_volume=expected_volume,
            q2_volume=expected_volume * 0.2,
            q2_count=30.0 * 0.2,
            q2_max=expected_volume / 20,
        )
        w.label(cid, "mule", "same_hand", instance=instance)

        k_acc = k + float(w.rng.uniform(-0.003, 0.003))
        n_cycles = int(w.rng.integers(4, 9))
        days = (w.rng.choice(31, size=n_cycles, replace=False) + 1).tolist()
        for day in days:
            inflow_ts = datetime(2026, 7, day, tzinfo=UTC) + timedelta(hours=h0 + float(w.rng.uniform(0, 1)))
            amount = float(w.rng.uniform(20000, 80000))
            payer = w.new_ext_account()
            w.add_tx(cid, inflow_ts, amount, "in", payer)
            out_ts = inflow_ts + timedelta(hours=lag_h, minutes=float(w.rng.uniform(-10, 10)))
            out_ts = min(out_ts, END)
            w.add_tx(cid, out_ts, amount * (1 - k_acc), "out", exits[int(w.rng.integers(0, 3))])
