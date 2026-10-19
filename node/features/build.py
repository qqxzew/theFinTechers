"""Assemble the frozen per-client feature table used by detectors (blue team; never reads labels or redteam code).

Counterparty degree is computed within ONE bank only (a bank cannot see other banks' customers).
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta

import polars as pl

from ingest.units import projected_monthly
from node.features.cycles import inflow_cycles
from node.features.degree import counterparty_degree
from node.features.hours import active_hour_profile
from node.features.shares import outflow_shares
from node.features.turnover import max_window_sums

WINDOWS = [1, 6, 24, 168]
OUTFLOW = ("out", "remit_out")


def _cv(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = statistics.fmean(xs)
    return statistics.pstdev(xs) / m if m else None


def _iqr(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return q[2] - q[0]


def _client_row(cid: str, rows: list[dict], deg: dict[str, int], cfg: dict, cyc: list[dict]) -> dict:
    rows = sorted(rows, key=lambda r: r["ts"])
    ins = [r for r in rows if r["direction"] == "in"]
    outs = [r for r in rows if r["direction"] in OUTFLOW]
    rare_max, pop_min = cfg["rare_max"], cfg["popular_min"]
    senders = {r["counterparty_token"] for r in ins}
    rec = {s for s in senders if sum(1 for r in ins if r["counterparty_token"] == s) >= 2}
    in_total = sum(r["amount_czk"] for r in ins)
    out_total = sum(r["amount_czk"] for r in outs)
    pop_in = sum(r["amount_czk"] for r in ins if deg.get(r["counterparty_token"], 1) >= pop_min)
    rec_in = sum(r["amount_czk"] for r in ins if r["counterparty_token"] in rec or deg.get(r["counterparty_token"], 1) >= pop_min)
    out_tokens = {r["counterparty_token"] for r in outs}
    row: dict = {
        "n_in": len(ins), "n_out": len(outs), "in_total": in_total, "out_total": out_total,
        "n_senders": len(senders), "n_senders_rare": sum(1 for s in senders if deg.get(s, 1) <= rare_max),
        "n_exits": len(out_tokens),
        "exit_tokens_rare": sorted(t for t in out_tokens if deg.get(t, 1) <= rare_max),
        "exit_tokens_low": sorted(t for t in out_tokens if deg.get(t, 1) <= cfg.get("low_max", 12)),
        "popular_inflow_share": pop_in / in_total if in_total else 0.0,
        "recurring_income_share": rec_in / in_total if in_total else 0.0,
        "reciprocity_share": (sum(r["amount_czk"] for r in rows if r["counterparty_token"] in senders & out_tokens) / (in_total + out_total))
        if (in_total + out_total) else 0.0,
        "max_single_in": max((r["amount_czk"] for r in ins), default=0.0),
        "out_amounts": [r["amount_czk"] for r in outs],
    }
    # biggest inflow and how fast it is drained
    if ins:
        big = max(ins, key=lambda r: r["amount_czk"])
        end = big["ts"] + timedelta(hours=24)
        drained = sum(r["amount_czk"] for r in outs if big["ts"] < r["ts"] <= end)
        row.update({
            "big_in_amount": big["amount_czk"], "big_in_ts": big["ts"],
            "big_in_sender_degree": deg.get(big["counterparty_token"], 1),
            "drained_24h_share": min(1.0, drained / big["amount_czk"]) if big["amount_czk"] else 0.0,
            "life_events_before_big": sum(1 for r in rows if r["ts"] < big["ts"]),
        })
    else:
        row.update({"big_in_amount": 0.0, "big_in_ts": None, "big_in_sender_degree": None, "drained_24h_share": 0.0,
                    "life_events_before_big": len(rows)})
    # remittance regularity
    rem = [r for r in outs if r["direction"] == "remit_out"]
    top = max({r["counterparty_token"] for r in rem}, key=lambda t: sum(1 for r in rem if r["counterparty_token"] == t), default=None)
    trem = sorted((r for r in rem if r["counterparty_token"] == top), key=lambda r: r["ts"]) if top else []
    gaps = [(b["ts"] - a["ts"]).total_seconds() / 86400 for a, b in zip(trem, trem[1:], strict=False)]
    row.update({"remit_top_recipient_count": len(trem), "remit_interval_cv": _cv(gaps), "remit_amount_cv": _cv([r["amount_czk"] for r in trem])})
    # cycles
    rets = [c["retention"] for c in cyc if c["retention"] is not None and c["out_amount"] > 0]
    lags = [c["lag_h"] for c in cyc if c["lag_h"] is not None]
    row.update({
        "n_cycles": len(cyc), "cycle_retentions": rets, "cycle_lags_h": lags,
        "retention_median": statistics.median(rets) if rets else None, "retention_iqr": _iqr(rets),
        "lag_median_h": statistics.median(lags) if lags else None, "lag_iqr_h": _iqr(lags),
    })
    return row


def build_features(tx: pl.DataFrame, clients: pl.DataFrame, cfg: dict, asof: datetime, expected_unit: str = "monthly") -> pl.DataFrame:
    """tx: canonical transactions of ONE bank; clients: canonical clients of that bank. Returns one row per client with activity."""
    deg_df = counterparty_degree(tx)
    deg = dict(zip(deg_df["counterparty_token"].to_list(), deg_df["degree"].to_list(), strict=True))
    shares = outflow_shares(tx, deg_df, cfg["rare_max"], cfg["popular_min"])
    turn = max_window_sums(tx, WINDOWS)
    hours = active_hour_profile(tx)
    cycles = inflow_cycles(tx, cfg.get("cycle_gap_h", 6), cfg.get("cycle_out_window_h", 24))
    cyc_by: dict[str, list[dict]] = {}
    for c in cycles.to_dicts():
        cyc_by.setdefault(c["client_id"], []).append(c)
    by_client: dict[str, list[dict]] = {}
    for r in tx.select(["client_id", "ts", "amount_czk", "direction", "counterparty_token"]).to_dicts():
        by_client.setdefault(r["client_id"], []).append(r)
    rows = [{"client_id": cid, **_client_row(cid, rs, deg, cfg, cyc_by.get(cid, []))} for cid, rs in by_client.items()]
    feat = pl.DataFrame(rows, infer_schema_length=None)
    cl = clients.select(["client_id", "bank_id", "contract_date", "contract_form", "pep", "client_type", "aml_risk",
                         "expected_volume", "q2_volume"])
    feat = feat.join(cl, on="client_id", how="left")
    feat = feat.join(shares.drop("out_total"), on="client_id", how="left").join(turn, on="client_id", how="left").join(hours, on="client_id", how="left")
    feat = feat.with_columns(
        ((pl.lit(asof) - pl.col("contract_date").dt.replace_time_zone("UTC")).dt.total_days()).alias("days_since_contract"),
        (pl.col("in_total") + pl.col("out_total")).alias("july_total"),
        (pl.col("in_total") / (pl.col("in_total") + pl.col("out_total"))).alias("inflow_share_of_volume"),
        pl.col("expected_volume").map_elements(lambda v: projected_monthly(v, expected_unit), return_dtype=pl.Float64).alias("expected_monthly"),
    )
    return feat
