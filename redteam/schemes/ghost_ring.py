"""Planted red-team scheme (synthetic): GHOST RING - a ring of accounts with NO usable local signal.

One operator routes small pass-through payments through established, ordinary-looking accounts at several banks (3 accounts per bank, two
cycles each, 4-9 k CZK, fixed commission and lag, shared exit accounts, same active hours) and imitates an ordinary spending life. Pre-registered
in docs/PREREGISTRATION.md (Amendment 1); parameters are fixed there. Designed from public descriptions of Czech/CEE mule herding.
"""
from __future__ import annotations

from datetime import timedelta

from redteam.world import World


def plant_ghost_ring(w: World, n: int = 9, instance: int = 20) -> None:
    lag_h = float(w.rng.uniform(2.0, 4.0))
    k = float(w.rng.uniform(0.08, 0.12))
    h0 = int(w.rng.integers(18, 21))
    exits = [w.new_ext_account(country=str(w.rng.choice(["CZ", "SK"]))) for _ in range(2)]
    for i in range(n):
        bank = w.banks[i % len(w.banks)]
        expected = float(w.rng.uniform(200000, 400000))
        cid = w.new_client(bank, contract_date=w.START - timedelta(days=int(w.rng.integers(365, 365 * 5))), contract_form="in person",
                           expected_volume=expected, expected_count=40.0, q2_volume=3 * expected, q2_count=120.0, q2_max=20000.0)
        days = sorted(w.rng.choice(range(4, 27), size=2, replace=False).tolist())
        for d in days:
            amount = float(w.rng.uniform(4000, 9000))
            t_in = w.START.replace(day=int(d), hour=h0) + timedelta(minutes=float(w.rng.uniform(0, 50)))
            w.add_tx(cid, t_in, amount, "in", w.new_ext_account())
            t_out = t_in + timedelta(hours=lag_h, minutes=float(w.rng.uniform(-8, 8)))
            w.add_tx(cid, t_out, amount * (1 - k) * float(w.rng.uniform(0.99, 1.01)), "out", exits[int(w.rng.integers(0, 2))])
        w.add_everyday(cid)
        w.label(cid, "mule", "ghost_ring", instance=instance)
