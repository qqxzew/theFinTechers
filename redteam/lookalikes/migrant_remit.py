"""honest look-alike persona, synthetic, planted by the red team; must NOT be flagged as a mule"""
from __future__ import annotations

from datetime import timedelta

from redteam.world import START, World


def plant_migrant_remit(w: World, n: int = 5, instance: int = 0) -> None:
    """Plant n honest migrant clients: monthly salary in, regular remittances home, small daily spends."""
    pool = [w.new_ext_account() for _ in range(20)]
    employer = pool[int(w.rng.integers(0, len(pool)))]

    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        contract_date = START - timedelta(days=int(w.rng.integers(365, 1462)))
        cid = w.new_client(bank, contract_date=contract_date, contract_form="in person")
        w.label(cid, "honest", "lookalike", persona="migrant_remit", instance=instance)

        salary = float(w.rng.uniform(28000, 45000))
        w.add_tx(cid, w.random_time(1, 3), salary, "in", employer)
        w.add_tx(cid, w.random_time(29, 31), salary * float(w.rng.uniform(0.98, 1.02)), "in", employer)

        base = float(w.rng.uniform(6000, 14000))
        recipient = w.new_ext_account()
        day = int(w.rng.integers(1, 5))
        for _ in range(int(w.rng.integers(3, 5))):
            amount = base * float(w.rng.uniform(0.98, 1.02))
            w.add_tx(cid, w.random_time(day, day), amount, "remit_out", recipient)
            day += int(w.rng.integers(5, 10))

        for _ in range(int(w.rng.integers(8, 16))):
            amount = float(w.rng.uniform(200, 3000))
            token = pool[int(w.rng.integers(0, len(pool)))]
            w.add_tx(cid, w.random_time(1, 31), amount, "out", token)
