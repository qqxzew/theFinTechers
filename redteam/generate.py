"""Red-team world generator: python -m redteam.generate --seed 7 --out data/redteam/seed7

Writes tx.parquet, clients.parquet (what banks get) and labels.parquet (HIDDEN: read only by eval/). ISOLATED package.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from ingest.fx import load_fx
from redteam.background import add_background
from redteam.lookalikes.freelancer import plant_freelancer
from redteam.lookalikes.fundraiser import plant_fundraiser
from redteam.lookalikes.group_collection import plant_group_collection
from redteam.lookalikes.middleman_cohost import plant_middleman_cohost
from redteam.lookalikes.migrant_remit import plant_migrant_remit
from redteam.lookalikes.second_hand_seller import plant_second_hand_seller
from redteam.lookalikes.students_rent import plant_students_rent
from redteam.schemes.day_zero import plant_day_zero
from redteam.schemes.fixed_skim import plant_fixed_skim
from redteam.schemes.invoice_mule import plant_invoice_mule
from redteam.schemes.same_hand import plant_same_hand
from redteam.schemes.same_hand_stealth import plant_same_hand_stealth
from redteam.schemes.victim import plant_victim
from redteam.world import World

SCHEMES = {"day_zero": 8, "same_hand": 2, "fixed_skim": 6, "invoice_mule": 6, "victim": 8}   # accounts per kind (same_hand: instances)
LOOKALIKES = {"migrant_remit": 10, "students_rent": 6, "second_hand_seller": 10, "group_collection": 6,
              "middleman_cohost": 6, "freelancer": 10, "fundraiser": 6}


def generate(seed: int, out: str, n_banks: int = 3, n_per_bank: int = 1000, cnb_dir: str = "data/raw/cnb") -> World:
    w = World(rng=np.random.default_rng(seed), banks=[f"B{i + 1}" for i in range(n_banks)])
    fx = load_fx("config/fx.yaml")
    add_background(w, f"{cnb_dir}/transactions.csv", f"{cnb_dir}/clients.csv", n_per_bank, fx)
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
    p = Path(out)
    p.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(w.tx, infer_schema_length=None).sort("ts").write_parquet(p / "tx.parquet")
    pl.DataFrame(w.clients, infer_schema_length=None).write_parquet(p / "clients.parquet")
    pl.DataFrame(w.labels, infer_schema_length=None).write_parquet(p / "labels.parquet")
    return w


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/redteam/seed7")
    ap.add_argument("--n-per-bank", type=int, default=1000)
    a = ap.parse_args()
    w = generate(a.seed, a.out, n_per_bank=a.n_per_bank)
    print(f"tx={len(w.tx)} clients={len(w.clients)} labels={len(w.labels)}")
