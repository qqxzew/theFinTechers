"""Bank-side signature vectors for the collector (blue team; never imports redteam/ or eval/).

A bank turns its own transactions into two kinds of count vectors and nothing else leaves the bank:
  WHERE  per destination bucket d: P = distinct local payers, K = distinct local payers with >= 1 pass-through to d, I = 1 if K > 0
         bucket = HMAC-SHA256(consortium_key, normalised IBAN) mod 2^18 (the collector never has the key)
  HOW    per cell (skim bin x delay bin x dormant x day): C = distinct local customers with such an event, I = 1 if C > 0
Pass-through event: outgoing payment within 72 h after an incoming credit from an external counterparty (employer-like = recurring or popular
senders, and own-account counterparties are excluded with the existing degree/recurrence notions), out/in ratio in [0.70, 1.00]; skim = 1 - ratio.
"""
from __future__ import annotations

import bisect
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from node.features.degree import counterparty_degree

N_BUCKETS = 1 << 18
HIST_START = datetime(2026, 6, 1, tzinfo=UTC)          # day 0 of the replay clock (30 days of history, then the evaluation month)
EVAL_START = datetime(2026, 7, 1, tzinfo=UTC)
EVAL_DAY0 = 30                                          # day index of 2026-07-01
DELAY_EDGES_MIN = [0.0, 15.0, 60.0, 240.0, 720.0, 1440.0, 4320.0]   # 6 bins: 0-15 min, 15-60 min, 1-4 h, 4-12 h, 12-24 h, 24-72 h
N_DELAY, N_SKIM = 6, 30                                  # skim bins 1..30 (1-pp steps)
N_CELLS = N_SKIM * N_DELAY * 2
OUTFLOW = ("out", "remit_out")


def normalise(iban: str) -> str:
    return "".join(iban.split()).upper()


def bucket_index(key: bytes, token: str) -> int:
    return int.from_bytes(hmac.new(key, normalise(token).encode(), hashlib.sha256).digest(), "big") & (N_BUCKETS - 1)


def cell_id(skim_bin: int, delay_bin: int, dormant: int) -> int:
    """Dense, secret-free cell index in [0, N_CELLS)."""
    return ((skim_bin - 1) * N_DELAY + delay_bin) * 2 + dormant


def day_index(ts: datetime) -> int:
    return (ts - HIST_START).days


@dataclass
class BankSignatures:
    """Everything the bank derives once from its own transactions; vectors for a round are cut from it by day."""
    bank_id: str
    events: pl.DataFrame            # client_id, dest, bucket, ts_in, ts_out, skim, delay_min, dormant, skim_bin, delay_bin, day_out
    pairs: pl.DataFrame             # distinct (client_id, dest, bucket, day) outgoing payment pairs


def _dormant(ts_in: datetime, contract: datetime | None, all_ts: list[datetime]) -> bool:
    if contract is not None and (ts_in - contract).days < 30:
        return True
    lo = bisect.bisect_left(all_ts, ts_in - timedelta(days=30))
    hi = bisect.bisect_left(all_ts, ts_in)
    return (hi - lo) <= 3


def pass_through_events(tx: pl.DataFrame, clients: pl.DataFrame, popular_min: int = 100) -> pl.DataFrame:
    """tx: ONE bank's transactions (history + evaluation month). Pure function of the bank's own data."""
    deg_df = counterparty_degree(tx)
    deg = dict(zip(deg_df["counterparty_token"].to_list(), deg_df["degree"].to_list(), strict=True))
    contract = {r["client_id"]: r["contract_date"] for r in clients.select(["client_id", "contract_date"]).to_dicts()}
    cols = ["client_id", "ts", "amount_czk", "direction", "counterparty_token"]
    rows: list[dict] = []
    by_client: dict[str, list[tuple]] = {}
    for cid, ts, amt, dr, tok in tx.select(cols).sort(["client_id", "ts"]).iter_rows():
        by_client.setdefault(cid, []).append((ts, amt, dr, tok))
    for cid, rs in by_client.items():
        outs = [(ts, amt, tok) for ts, amt, dr, tok in rs if dr in OUTFLOW]
        if not outs:
            continue
        out_dest = {tok for _, _, tok in outs}
        used: set[int] = set()
        all_ts = [r[0] for r in rs]
        in_ts: dict[str, list[datetime]] = {}
        for ts, _, dr, tok in rs:
            if dr == "in":
                in_ts.setdefault(tok, []).append(ts)
        c_date = contract.get(cid)
        if c_date is not None and c_date.tzinfo is None:
            c_date = c_date.replace(tzinfo=UTC)
        for ts, amt, dr, tok in rs:
            if dr != "in":
                continue
            # employer-like = the same sender paid this client within the 35 days before; for history events (June) also within the 35 days after,
            # because the first payment of a monthly employer has no predecessor in the window
            recurring = any(0 < (ts - p).total_seconds() <= 35 * 86400 or (ts < EVAL_START and 0 < (p - ts).total_seconds() <= 35 * 86400)
                            for p in in_ts[tok])
            if recurring or deg.get(tok, 1) >= popular_min or tok in out_dest or amt <= 0:
                continue
            end = ts + timedelta(hours=72)
            for k, (ots, oamt, otok) in enumerate(outs):
                if ots <= ts or k in used:
                    continue
                if ots > end:
                    break
                ratio = oamt / amt
                if 0.70 <= ratio <= 1.0:
                    used.add(k)
                    skim = (1.0 - ratio) * 100.0
                    delay = (ots - ts).total_seconds() / 60.0
                    rows.append({"client_id": cid, "dest": otok, "ts_in": ts, "ts_out": ots, "skim": skim, "delay_min": delay,
                                 "dormant": int(_dormant(ts, c_date, all_ts)), "amount_in": amt, "amount_out": oamt})
                    break
    schema = {"client_id": pl.String, "dest": pl.String, "ts_in": pl.Datetime("us", "UTC"), "ts_out": pl.Datetime("us", "UTC"),
              "skim": pl.Float64, "delay_min": pl.Float64, "dormant": pl.Int64, "amount_in": pl.Float64, "amount_out": pl.Float64}
    ev = pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)
    edges = DELAY_EDGES_MIN[1:-1]
    return ev.with_columns(
        pl.col("skim").round(0).cast(pl.Int64).alias("skim_bin"),
        pl.col("delay_min").map_elements(lambda m: bisect.bisect_right(edges, m), return_dtype=pl.Int64).alias("delay_bin"),
        ((pl.col("ts_out") - pl.lit(HIST_START)).dt.total_days()).alias("day_out"),
    )


def build_signatures(bank_id: str, tx: pl.DataFrame, clients: pl.DataFrame, key: bytes, popular_min: int = 100) -> BankSignatures:
    ev = pass_through_events(tx, clients, popular_min)
    out = tx.filter(pl.col("direction").is_in(OUTFLOW)).select(
        "client_id", pl.col("counterparty_token").alias("dest"),
        ((pl.col("ts") - pl.lit(HIST_START)).dt.total_days()).alias("day_out")).unique()
    cache: dict[str, int] = {}

    def idx(tok: str) -> int:
        v = cache.get(tok)
        if v is None:
            v = cache[tok] = bucket_index(key, tok)
        return v

    toks = sorted(set(out["dest"].to_list()) | set(ev["dest"].to_list()))
    for t in toks:
        idx(t)
    mp = pl.DataFrame({"dest": toks, "bucket": [cache[t] for t in toks]}, schema={"dest": pl.String, "bucket": pl.Int64})
    return BankSignatures(bank_id, ev.join(mp, on="dest", how="left"), out.join(mp, on="dest", how="left"))


def where_vectors(sig: BankSignatures, day: int, window: int = 30) -> dict[str, np.ndarray]:
    """P, K, I vectors (uint32, length 2^18) for the trailing `window` days ending at replay day `day` (inclusive)."""
    lo = day - window + 1
    p = sig.pairs.filter((pl.col("day_out") >= lo) & (pl.col("day_out") <= day)).select("client_id", "dest", "bucket").unique()
    e = sig.events.filter((pl.col("day_out") >= lo) & (pl.col("day_out") <= day)).select("client_id", "dest", "bucket").unique()
    P = np.bincount(p["bucket"].to_numpy(), minlength=N_BUCKETS).astype(np.uint32) if p.height else np.zeros(N_BUCKETS, np.uint32)
    K = np.bincount(e["bucket"].to_numpy(), minlength=N_BUCKETS).astype(np.uint32) if e.height else np.zeros(N_BUCKETS, np.uint32)
    return {"P": P, "K": K, "I": (K > 0).astype(np.uint32)}


def how_vectors(sig: BankSignatures, day: int) -> dict[str, np.ndarray]:
    """C and I vectors over the dense cells for ONE day (skim 0 and skim > 30 excluded)."""
    e = sig.events.filter((pl.col("day_out") == day) & (pl.col("skim_bin") >= 1) & (pl.col("skim_bin") <= N_SKIM))
    C = np.zeros(N_CELLS, np.uint32)
    if e.height:
        u = e.select("client_id", "skim_bin", "delay_bin", "dormant").unique()
        cells = ((u["skim_bin"].to_numpy() - 1) * N_DELAY + u["delay_bin"].to_numpy()) * 2 + u["dormant"].to_numpy()
        C = np.bincount(cells, minlength=N_CELLS).astype(np.uint32)
    return {"C": C, "I": (C > 0).astype(np.uint32)}
