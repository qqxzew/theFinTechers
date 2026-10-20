"""Collector worlds: python -m redteam.generate_collector --seed 1 --hub shared --jitter none --out data/collector/s1_shared_none

Same background, legacy schemes and honest look-alikes as redteam.generate, plus decoys, 30 days of history and (unless --crime-free) two
low-and-slow rings. The crime-free world has no legacy schemes and no rings. Writes tx/clients/labels (labels HIDDEN, eval only),
ring_flows.parquet (ground truth for the time evaluation), public_registry.json (allowlist of institutional accounts: popular pool only) and meta.json.
ISOLATED package (red team).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from ingest.fx import load_fx
from redteam.background import add_background
from redteam.decoys import plant_decoys
from redteam.generate import LOOKALIKES, SCHEMES
from redteam.history import clone_history
from redteam.lookalikes.freelancer import plant_freelancer
from redteam.lookalikes.fundraiser import plant_fundraiser
from redteam.lookalikes.group_collection import plant_group_collection
from redteam.lookalikes.middleman_cohost import plant_middleman_cohost
from redteam.lookalikes.migrant_remit import plant_migrant_remit
from redteam.lookalikes.second_hand_seller import plant_second_hand_seller
from redteam.lookalikes.students_rent import plant_students_rent
from redteam.schemes.day_zero import plant_day_zero
from redteam.schemes.fixed_skim import plant_fixed_skim
from redteam.schemes.ghost_ring import plant_ghost_ring
from redteam.schemes.invoice_mule import plant_invoice_mule
from redteam.schemes.low_slow_ring import plant_low_slow_ring
from redteam.schemes.same_hand import plant_same_hand
from redteam.schemes.same_hand_stealth import plant_same_hand_stealth
from redteam.schemes.victim import plant_victim
from redteam.world import World

N_RINGS = 2


def generate_collector(seed: int, out: str, hub_mode: str = "shared", script_jitter: str = "none", crime_free: bool = False,
                       n_banks: int = 3, n_per_bank: int = 1000, cnb_dir: str = "data/raw/cnb") -> World:
    w = World(rng=np.random.default_rng(seed), banks=[f"B{i + 1}" for i in range(n_banks)])
    add_background(w, f"{cnb_dir}/transactions.csv", f"{cnb_dir}/clients.csv", n_per_bank, load_fx("config/fx.yaml"))
    decoy_info = plant_decoys(w, np.random.default_rng(seed * 104729 + 5))
    if not crime_free:
        plant_day_zero(w, n=SCHEMES["day_zero"])
        for inst in range(SCHEMES["same_hand"]):
            plant_same_hand(w, n=int(w.rng.integers(9, 16)), instance=inst + 1)
        plant_same_hand_stealth(w, n=int(w.rng.integers(12, 19)), instance=10)
        plant_fixed_skim(w, n=SCHEMES["fixed_skim"], k=float(w.rng.uniform(0.06, 0.12)))
        plant_invoice_mule(w, n=SCHEMES["invoice_mule"])
        plant_victim(w, n=SCHEMES["victim"])
    for fn, name in ((plant_migrant_remit, "migrant_remit"), (plant_students_rent, "students_rent"), (plant_second_hand_seller, "second_hand_seller"),
                     (plant_group_collection, "group_collection"), (plant_middleman_cohost, "middleman_cohost"),
                     (plant_freelancer, "freelancer"), (plant_fundraiser, "fundraiser")):
        fn(w, n=LOOKALIKES[name])
    for lab_row in list(w.labels):
        if lab_row["persona"] in ("fundraiser", "group_collection", "middleman_cohost", "students_rent", "freelancer"):
            w.add_everyday(lab_row["client_id"])
    if not crime_free:
        saved = w.rng
        w.rng = np.random.default_rng(seed * 7919 + 1)
        plant_ghost_ring(w, n=9)
        w.rng = saved
    clone_history(w)
    rings: list[list[str]] = []
    if not crime_free:
        r_rng, j_rng = np.random.default_rng(seed * 7919 + 2), np.random.default_rng(seed * 7919 + 3)   # schedule and noise on separate streams
        for k in range(N_RINGS):
            rings.append(plant_low_slow_ring(w, r_rng, j_rng, hub_mode=hub_mode, script_jitter=script_jitter, instance=31 + k))
    p = Path(out)
    p.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(w.tx, infer_schema_length=None).sort("ts").write_parquet(p / "tx.parquet")
    pl.DataFrame(w.clients, infer_schema_length=None).write_parquet(p / "clients.parquet")
    pl.DataFrame(w.labels, infer_schema_length=None).write_parquet(p / "labels.parquet")
    if w.ring_flows:
        pl.DataFrame(w.ring_flows).write_parquet(p / "ring_flows.parquet")
    (p / "public_registry.json").write_text(json.dumps(sorted(w.popular_tokens)), encoding="utf-8")
    (p / "meta.json").write_text(json.dumps({"seed": seed, "hub_mode": hub_mode, "script_jitter": script_jitter, "crime_free": crime_free,
                                             "rings": rings, "decoys": decoy_info}), encoding="utf-8")
    return w


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--hub", default="shared", choices=["shared", "rotating"])
    ap.add_argument("--jitter", default="none", choices=["none", "medium", "high"])
    ap.add_argument("--crime-free", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    w = generate_collector(a.seed, a.out, a.hub, a.jitter, a.crime_free)
    print(f"tx={len(w.tx)} clients={len(w.clients)} labels={len(w.labels)} ring_events={len(w.ring_flows)}")
