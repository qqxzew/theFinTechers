"""Normal-life background for the red-team world, resampled from the ČNB synthetic dataset (clients keep their real counterparties).

ČNB clients are split disjointly over the banks, so every bank sees only its own customers, while popular external accounts
(utilities, employers, merchants) are shared across banks exactly as in the source data.
"""
from __future__ import annotations

from datetime import UTC

import polars as pl

from ingest.cnb_clients import load_clients
from ingest.cnb_tx import load_transactions
from redteam.world import World


def add_background(w: World, cnb_tx: str, cnb_clients: str, n_per_bank: int, fx: dict) -> int:
    clients = load_clients(cnb_clients)
    tx = load_transactions(cnb_tx, fx)
    ids = clients["client_id"].to_list()
    pick = w.rng.permutation(len(ids))[: n_per_bank * len(w.banks)]
    remap: dict[str, str] = {}
    bank_of: dict[str, str] = {}
    cl_rows = {r["client_id"]: r for r in clients.to_dicts()}
    for k, idx in enumerate(pick):
        old = ids[int(idx)]
        bank = w.banks[k % len(w.banks)]
        r = cl_rows[old]
        new = w.new_client(bank, contract_date=r["contract_date"].replace(tzinfo=UTC) if r["contract_date"] else None,
                           contract_form=r["contract_form"], client_type=r["client_type"], country=r["client_country"], pep=r["pep"],
                           aml_risk=r["aml_risk"], expected_volume=r["expected_volume"], expected_count=r["expected_count"],
                           q2_volume=r["q2_volume"], q2_count=r["q2_count"], q2_max=r["q2_max"])
        remap[old] = new
        bank_of[old] = bank
        w.label(new, "background", "cnb_background")
    sub = tx.filter(pl.col("client_id").is_in(list(remap)))
    for r in sub.iter_rows(named=True):
        new = remap[r["client_id"]]
        w._n_tx += 1
        w.tx.append({**{k: r[k] for k in ("ts", "amount_czk", "amount_orig", "currency", "direction", "counterparty_token",
                                          "payer_country", "payee_country", "channel_type")},
                     "tx_id": f"RT{w._n_tx:08d}", "bank_id": bank_of[r["client_id"]], "client_id": new, "own_account": new,
                     "source_dataset": "redteam"})
    deg = sub.group_by("counterparty_token").agg(pl.col("client_id").n_unique().alias("d"))
    w.popular_tokens = deg.filter(pl.col("d") >= max(100, n_per_bank * len(w.banks) // 5))["counterparty_token"].sort().to_list()
    return len(remap)
