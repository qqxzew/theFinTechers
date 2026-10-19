"""honest look-alike persona, synthetic, planted by the red team; must NOT be flagged as a mule"""
from __future__ import annotations

import math
from datetime import UTC, datetime

from redteam.world import World


def plant_freelancer(w: World, n: int = 4, instance: int = 0) -> None:
    """Plant `n` honest freelancer clients (labelled honest/lookalike, persona 'freelancer').

    Each freelancer holds a personal account funded by 2..4 recurring payer
    external accounts (1..2 incoming payments of 20000..80000 CZK each, on
    varying days in July) and spends the income over the following days via
    6..14 outgoing payments of 800..15000 CZK into a shared pool of 20 popular
    external accounts, never exceeding 60% of total income in any 24h window.
    """
    popular = [w.new_ext_account() for _ in range(20)]
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(len(w.banks)))]
        contract_date = datetime(2026 - int(w.rng.integers(1, 6)), 7, int(w.rng.integers(1, 29)), tzinfo=UTC)
        cid = w.new_client(bank, contract_date=contract_date, client_type="natural person")
        w.label(cid, "honest", "lookalike", persona="freelancer", instance=instance)

        income_days: list[int] = []
        income_total = 0.0
        for _ in range(int(w.rng.integers(2, 5))):
            payer = w.new_ext_account()
            n_payments = int(w.rng.integers(1, 3))
            for d in w.rng.choice(18, size=n_payments, replace=False) + 1:
                day = int(d)
                amount = float(w.rng.integers(200, 801)) * 100.0
                w.add_tx(cid, w.random_time(day, day), amount, "in", payer)
                income_days.append(day)
                income_total += amount

        cap = 0.6 * income_total
        n_out = min(int(w.rng.integers(6, 15)), int(cap // 800))
        spend_days = sorted(int(w.rng.integers(max(income_days), 32)) for _ in range(n_out))
        spent = 0.0
        for i, day in enumerate(spend_days):
            upper = min(15000.0, cap - spent - 800.0 * (n_out - i - 1))
            amount = float(w.rng.integers(800, math.floor(upper) + 1))
            spent += amount
            w.add_tx(cid, w.random_time(day, day), amount, "out", popular[int(w.rng.integers(len(popular)))])
