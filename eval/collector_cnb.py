"""7b: ČNB sandbox as an external control. Clients are split at random (seeded) into 3 pseudo-banks, the collector WHERE test runs on the month,
and we report the flags and whether they touch the Rule C cases. NO detection claim: the dataset has no labelled mules and no history
(July only), so HOW is not run and the WHERE window is the month. Written to eval/out/collector/cnb_control.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from collector.stats import where_test
from eval.collector_eval import KEY
from ingest.cnb_clients import load_clients
from ingest.cnb_tx import load_transactions
from ingest.fx import load_fx
from node.expansion import expand_where
from node.pipeline import load_config
from node.rules.rule_c import rule_c
from node.signatures import build_signatures, where_vectors


def run(seeds: tuple[int, ...] = (0, 1, 2), p_inst: int = 30) -> dict:
    cfg = load_config()
    tx = load_transactions("data/raw/cnb/transactions.csv", load_fx("config/fx.yaml"))
    cl = load_clients("data/raw/cnb/clients.csv")
    rc = set(rule_c(tx, cfg["rule_c"])["client_id"].to_list())
    out: dict = {"n_clients": cl.height, "n_tx": tx.height, "rule_c_clients": len(rc), "p_inst": p_inst, "runs": []}
    ids = cl["client_id"].to_list()
    for seed in seeds:
        rng = np.random.default_rng(seed)
        bank_of = {c: f"P{int(b) + 1}" for c, b in zip(ids, rng.integers(0, 3, len(ids)), strict=True)}
        tx_b = tx.with_columns(pl.col("client_id").replace_strict(bank_of, default="P1").alias("bank_id"))
        cl_b = cl.with_columns(pl.col("client_id").replace_strict(bank_of, default="P1").alias("bank_id"))
        banks = sorted(set(bank_of.values()))
        sigs = {b: build_signatures(b, tx_b.filter(pl.col("bank_id") == b), cl_b.filter(pl.col("bank_id") == b), KEY, cfg["features"]["popular_min"]) for b in banks}
        day = 60
        vecs = {b: where_vectors(sigs[b], day, 31) for b in banks}
        tot = {k: sum(vecs[b][k].astype(np.uint64) for b in banks) for k in ("P", "K", "I")}
        wr = where_test(tot["P"], tot["K"], tot["I"], p_inst=p_inst)
        raised: dict[str, dict] = {}
        for b in banks:
            raised.update(expand_where(sigs[b], wr.flagged, day, 31, {c: c for c in cl_b.filter(pl.col("bank_id") == b)["client_id"].to_list()}, KEY))
        out["runs"].append({"split_seed": seed, "p0": wr.p0, "n_tested": wr.n_tested, "n_flagged_buckets": len(wr.flagged),
                            "n_suppressed_buckets": len(wr.suppressed), "n_raised_customers": len(raised),
                            "raised_in_rule_c": len(set(raised) & rc), "flagged": wr.flagged[:20]})
    Path("eval/out/collector").mkdir(parents=True, exist_ok=True)
    Path("eval/out/collector/cnb_control.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for x in r["runs"]:
        print({k: v for k, v in x.items() if k != "flagged"})
