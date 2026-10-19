"""Middleman co-host lookalike: honest rental co-host forwarding a fixed commission; must NOT be flagged as a mule."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World


def plant_middleman_cohost(w: World, n: int = 3, instance: int = 0) -> None:
    """Plant honest look-alike co-hosts: receive guest payments, forward amount minus a fixed cut to one host."""
    popular = w.popular_pool(20)
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        months = int(w.rng.integers(6, 31))
        contract_date = datetime(2026, 7, 1, tzinfo=UTC) - timedelta(days=months * 30)
        cid = w.new_client(bank, contract_date=contract_date, client_type="natural person")
        w.label(cid, "honest", "lookalike", persona="middleman_cohost", instance=instance)

        host = w.new_ext_account()
        k = float(w.rng.uniform(0.10, 0.14))
        total_in = 0.0
        for _ in range(int(w.rng.integers(4, 9))):
            guest = w.new_ext_account()
            amount = float(w.rng.uniform(8000.0, 30000.0))
            total_in += amount
            ts_in = w.random_time(1, 27)
            w.add_tx(cid, ts_in, amount, "in", guest)
            ts_out = ts_in + timedelta(hours=float(w.rng.uniform(1.0, 48.0)))
            fwd = amount * (1.0 - k + float(w.rng.uniform(-0.003, 0.003)))
            w.add_tx(cid, ts_out, fwd, "out", host)

        n_small = int(w.rng.integers(5, 11))
        weights = w.rng.uniform(0.5, 1.5, size=n_small)
        small = total_in * float(w.rng.uniform(0.005, 0.01)) * weights / weights.sum()
        for amount in small:
            w.add_tx(
                cid,
                w.random_time(1, 31),
                float(amount),
                "in",
                popular[int(w.rng.integers(0, len(popular)))],
            )
