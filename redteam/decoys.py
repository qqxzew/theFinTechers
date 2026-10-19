"""Collector-world decoys (honest, synthetic): innocent structures that look like pass-through through a shared account.

- crypto-exchange top-up account: ~90 honest payers across all banks, 20 % of them pass-through-like (incoming credit, then top-up of 70-98 %)
- wholesale supplier paid by ~45 small businesses, 15 % pass-through-like
- own-account transfers (skim 0): out to own account A, later in from A, then out to own account B (same amount)
Payers are existing background clients (label stays 'background'); the activity is planted in both months (fresh sources per month).
ISOLATED package (red team). Decoy tx are remembered in w.decoy_tx so that the history cloning does not copy them.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from redteam.world import HIST_START, World


def _emit(w: World, rng: np.random.Generator, payers: list[str], pt_share: float, token: str, base, lo: float, hi: float,
          ratio: tuple[float, float], delay_h: tuple[float, float]) -> None:
    for k, cid in enumerate(payers):
        day = int(rng.integers(1, 27))
        t = base + timedelta(days=day, hours=int(rng.integers(8, 20)), minutes=int(rng.integers(0, 60)))
        amount = float(rng.uniform(lo, hi))
        if k < int(round(pt_share * len(payers))):
            ids = [w.add_tx(cid, t, amount, "in", w.new_ext_account(), clamp=False)]
            ids.append(w.add_tx(cid, t + timedelta(hours=float(rng.uniform(*delay_h))), amount * float(rng.uniform(*ratio)), "out", token, clamp=False))
        else:
            ids = [w.add_tx(cid, t, amount, "out", token, clamp=False)]
        w.decoy_tx.update(ids)


def plant_decoys(w: World, rng: np.random.Generator) -> dict:
    bg = [r["client_id"] for r in w.labels if r["label"] == "background"]
    idx = rng.permutation(len(bg))
    crypto, wholesale, own = ([bg[int(i)] for i in idx[a:b]] for a, b in ((0, 90), (90, 135), (135, 175)))
    t_crypto, t_whole = w.new_ext_account(country="CZ"), w.new_ext_account(country="CZ")
    for base in (HIST_START, w.START):
        _emit(w, rng, crypto, 0.20, t_crypto, base, 500, 20000, (0.70, 0.98), (1.0, 48.0))
        _emit(w, rng, wholesale, 0.15, t_whole, base, 3000, 40000, (0.75, 0.97), (2.0, 36.0))
        for cid in own:
            a, b = f"OWN-{cid}-A", f"OWN-{cid}-B"
            amount = float(rng.uniform(2000, 30000))
            d = int(rng.integers(1, 12))
            t = base + timedelta(days=d, hours=10)
            ids = [w.add_tx(cid, t, amount, "out", a, clamp=False),
                   w.add_tx(cid, t + timedelta(days=5), amount, "in", a, clamp=False)]
            ids.append(w.add_tx(cid, t + timedelta(days=5, hours=3), amount, "out", b, clamp=False))
            w.decoy_tx.update(ids)
    return {"crypto_exchange_token": t_crypto, "wholesale_token": t_whole, "n_crypto": len(crypto), "n_wholesale": len(wholesale), "n_own": len(own)}
