"""One local expansion of what the collector flagged (bank side; one round, no recursion). The analyst decides.

WHERE: the bank maps the flagged bucket ids to its own destinations and raises the customers who passed money through to them
(all payers of those destinations if the bucket is marked small). A customer whose OWN account falls in a flagged bucket is raised as a possible hub.
HOW: customers with a pass-through event in a flagged window are raised.
The result is {client_id: network_evidence}; raised customers enter the existing queue and only then export tokens to the PSI radar.
"""
from __future__ import annotations

import polars as pl

from node.signatures import BankSignatures, bucket_index


def expand_where(sig: BankSignatures, flagged: list[dict], day: int, window: int, own_accounts: dict[str, str], key: bytes) -> dict[str, dict]:
    by_bucket = {f["bucket"]: f for f in flagged}
    if not by_bucket:
        return {}
    lo = day - window + 1
    ids = list(by_bucket)
    out: dict[str, dict] = {}

    def ev(f: dict, role: str) -> dict:
        return {"type": "collector_where", "role": role, "totals": {"P": f["P"], "K": f["K"]}, "banks": f["banks"], "p_value": f["p"],
                "window": [lo, day], "small": f["small"]}

    ev_df = sig.events.filter(pl.col("bucket").is_in(ids) & (pl.col("day_out") >= lo) & (pl.col("day_out") <= day)).select("client_id", "bucket").unique()
    for cid, b in ev_df.iter_rows():
        out.setdefault(cid, ev(by_bucket[b], "pass_through_payer"))
    small = [b for b, f in by_bucket.items() if f["small"]]
    if small:
        pr = sig.pairs.filter(pl.col("bucket").is_in(small) & (pl.col("day_out") >= lo) & (pl.col("day_out") <= day)).select("client_id", "bucket").unique()
        for cid, b in pr.iter_rows():
            out.setdefault(cid, ev(by_bucket[b], "payer_of_small_bucket"))
    for cid, acct in own_accounts.items():
        b = bucket_index(key, acct)
        if b in by_bucket:
            out.setdefault(cid, ev(by_bucket[b], "possible_hub"))
    return out


def expand_how(sig: BankSignatures, windows: list[dict]) -> dict[str, dict]:
    """Raise this bank's customers that have an event inside a flagged HOW window (skim range x delay bin x dormant x day range)."""
    out: dict[str, dict] = {}
    for w in windows:
        e = sig.events.filter((pl.col("skim_bin") >= w["skim_lo"]) & (pl.col("skim_bin") <= w["skim_hi"]) & (pl.col("delay_bin") == w["delay_bin"])
                              & (pl.col("dormant") == w["dormant"]) & (pl.col("day_out") >= w["day_lo"]) & (pl.col("day_out") <= w["day_hi"]))
        for cid in e["client_id"].unique().to_list():
            out.setdefault(cid, {"type": "collector_how", "window": {k: w[k] for k in ("skim_lo", "skim_hi", "delay_bin", "dormant", "day_lo", "day_hi")},
                                 "totals": {"observed": w["obs"], "expected": round(w["expected"], 3)}, "banks": w["banks"], "p_value": w["p"],
                                 "strength": w["strength"]})
    return out
