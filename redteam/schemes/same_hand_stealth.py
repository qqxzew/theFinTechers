"""Planted red-team scheme (synthetic): STEALTH same hand.

One operator spreads the same payout routine over many accounts at several banks, keeping every account below the volume the single-account
detectors react to (2-3 cycles of 15-45k CZK each). Only the cross-bank view (shared rare exits + identical lag, retention and active hours)
reveals the common hand. Designed from public descriptions of Czech/CEE money-mule herding; parameters are our own.
"""
from __future__ import annotations

from datetime import timedelta

from redteam.world import World


def plant_same_hand_stealth(w: World, n: int = 15, instance: int = 0) -> None:
    lag_h = float(w.rng.uniform(1.5, 4.0))
    k = float(w.rng.uniform(0.06, 0.12))
    h0 = int(w.rng.integers(17, 22))
    exits = [w.new_ext_account(country=str(w.rng.choice(["CZ", "SK", "DE"]))) for _ in range(3)]
    for i in range(n):
        bank = w.banks[i % len(w.banks)]
        cid = w.new_client(bank, contract_date=w.START - timedelta(days=int(w.rng.integers(10, 120))),
                           contract_form="distant form" if w.rng.random() < 0.5 else "in person",
                           expected_volume=float(w.rng.uniform(20000, 80000)), q2_volume=0.0, q2_count=0.0, q2_max=0.0)
        k_acc = k + float(w.rng.uniform(-0.003, 0.003))
        days = sorted(w.rng.choice(range(3, 28), size=int(w.rng.integers(2, 4)), replace=False).tolist())
        for d in days:
            amount = float(w.rng.uniform(15000, 45000))
            t_in = w.START.replace(day=int(d), hour=h0) + timedelta(minutes=float(w.rng.uniform(0, 60)))
            w.add_tx(cid, t_in, amount, "in", w.new_ext_account())
            t_out = t_in + timedelta(hours=lag_h, minutes=float(w.rng.uniform(-10, 10)))
            w.add_tx(cid, t_out, amount * (1 - k_acc), "out", exits[int(w.rng.integers(0, 3))])
        w.label(cid, "mule", "same_hand_stealth", instance=instance)
