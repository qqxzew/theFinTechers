"""Planted red-team scheme (synthetic): LOW-AND-SLOW RING for the collector evaluation.

Six recruited accounts, two per bank, forward small incoming payments (800-4,000 CZK) within minutes to hours, keeping a skim.
Few transfers per account, in waves of 2-4 active days: no single account gives a local signal. hub_mode 'shared' = one cash-out
account for the whole ring; 'rotating' = every mule has its own cash-out account. script_jitter adds noise to the skim and the delay.
Parameters are fixed in eval/prereg_collector.md section 4. ISOLATED package (red team).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from redteam.world import World

JITTER = {"none": (0.0, 0.0), "medium": (2.0, 0.3), "high": (5.0, 0.8)}   # (skim +- pp, delay lognormal sigma)


def plant_low_slow_ring(w: World, rng: np.random.Generator, jit_rng: np.random.Generator, *, hub_mode: str, script_jitter: str,
                        instance: int, size: int = 6) -> list[str]:
    assert hub_mode in ("shared", "rotating") and script_jitter in JITTER
    skim_w, delay_sigma = JITTER[script_jitter]
    base_skim = float(rng.uniform(8, 15))
    base_delay_min = float(rng.uniform(20, 90))
    h0 = int(rng.integers(9, 19))
    hub = w.new_ext_account(country="CZ")
    n_waves = int(rng.integers(1, 4))
    waves, cursor = [], int(rng.integers(3, 8))
    for _ in range(n_waves):
        length = int(rng.integers(2, 5))
        if cursor + length > 29:
            break
        waves.append((cursor, length))
        cursor += length + int(rng.integers(3, 7))
    if not waves:
        waves = [(5, 3)]
    per_bank = size // len(w.banks)
    mules: list[str] = []
    for i in range(size):
        bank = w.banks[i // per_bank]
        dormant = bool(rng.random() < 0.5)
        age = int(rng.integers(3, 25)) if dormant else int(rng.integers(365, 365 * 5))
        exp = float(rng.uniform(50000, 150000))
        cid = w.new_client(bank, contract_date=w.START - timedelta(days=age), contract_form="distant form" if dormant else "in person",
                           expected_volume=exp, q2_volume=3 * exp if not dormant else 0.0, q2_count=60.0 if not dormant else 0.0,
                           q2_max=exp / 4 if not dormant else 0.0)
        out_tok = hub if hub_mode == "shared" else w.new_ext_account()
        for start, length in waves:
            for _ in range(int(rng.integers(2, 5))):
                day = start + int(rng.integers(0, length))
                amount = float(rng.uniform(800, 4000))
                t_in = w.START.replace(day=day + 1, hour=h0 + int(rng.integers(0, 4))) + timedelta(minutes=float(rng.uniform(0, 59)))
                skim = float(np.clip(base_skim + skim_w * jit_rng.uniform(-1, 1), 1.0, 30.0))
                delay = float(np.clip(base_delay_min * np.exp(delay_sigma * jit_rng.standard_normal()), 3.0, 70 * 60.0))
                t_out = t_in + timedelta(minutes=delay)
                amt_out = amount * (1 - skim / 100.0)
                w.add_tx(cid, t_in, amount, "in", w.new_ext_account())
                w.add_tx(cid, t_out, amt_out, "out", out_tok)
                w.ring_flows.append({"client_id": cid, "ring": instance, "ts_out": t_out, "amount_in": amount, "amount_out": amt_out})
        if not dormant:
            w.add_everyday(cid)
        w.label(cid, "mule", "low_slow_ring", persona="dormant" if dormant else "established", instance=instance)
        mules.append(cid)
    return mules
