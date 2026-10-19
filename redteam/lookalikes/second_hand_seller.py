"""Second-hand seller: honest look-alike persona, synthetic, planted by the red team; must NOT be flagged as a mule."""
from __future__ import annotations

from datetime import timedelta

from redteam.world import World


def plant_second_hand_seller(w: World, n: int = 5, instance: int = 0) -> None:
    """Plant n honest second-hand sellers: many small distinct-sender sales in, few shipping/platform payments out."""
    popular_pool = [w.new_ext_account() for _ in range(20)]
    for _ in range(n):
        bank_id = str(w.rng.choice(w.banks))
        contract_date = w.random_time() - timedelta(days=365 * int(w.rng.integers(1, 7)))
        cid = w.new_client(bank_id, contract_date=contract_date)
        w.label(cid, "honest", "lookalike", persona="second_hand_seller", instance=instance)

        n_in = int(w.rng.integers(12, 31))
        n_distinct = max(10, n_in - 3)
        senders = [w.new_ext_account() for _ in range(n_distinct)]
        for i in range(n_in):
            sender = senders[i] if i < n_distinct else str(w.rng.choice(senders))
            amount = round(float(w.rng.uniform(150.0, 3000.0)), 2)
            w.add_tx(cid, w.random_time(1, 31), min(amount, 3500.0), "in", sender)

        n_out = int(w.rng.integers(5, 13))
        for _ in range(n_out):
            payee = str(w.rng.choice(popular_pool))
            amount = round(float(w.rng.uniform(300.0, 2500.0)), 2)
            w.add_tx(cid, w.random_time(1, 31), amount, "out", payee)
