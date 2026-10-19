"""IBM AMLworld (HI-Small) evaluation of Staj: isolated vs staj_psi vs naive_raw_sharing. SYNTHETIC data, generic laundering
patterns (not Czech mule schemes). Every number in eval/out/ibm_eval.json and docs/IBM_EVAL.md is computed here.

Separation: labels (`is_laundering`, pattern types) are loaded by `main` and used only in the metric functions at the bottom.
The bank-side part (`engine`, `bank_nodes`, `radar_pairwise`) receives label-free canonical rows from `ingest.ibm.bank_split`.

Bank-side engine = IBM-scale vectorised variant of D1 (flow-through+) and D5 (rare-exit concentration), own design. The per-client
python pipeline in node/pipeline.py does not scale to 515k accounts, so the same ideas are recomputed with polars per node:
counterparty degree within the node, in/out totals and counts, max 24 h inflow window, share of the largest inflow sent on within
24 h, share of outflow to rare counterparties (degree <= 3 within the node), distinct rare counterparties, retention, and a second
pass that looks at the first-pass score of counterparties that are the node's OWN clients. Score = additive log-odds with
hand-set weights from config/ibm.yaml.

Radar = the project's code: radar.sessions.run_radar (DH-PSI via radar.psi.dh_psi.PsiParty) for each bank pair, radar.guards.Guards
for admission, radar.clustering.build_clusters for the cross-pair union. Pair sessions run in parallel processes (PSI cost is
measured in every run, see `psi_benchmark`).

Run:  python -m eval.ibm_eval
"""
from __future__ import annotations

import hashlib
import hmac
import io
import itertools
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import yaml

from ingest.ibm import bank_split, load_config, load_ibm, load_patterns, split_labels, tx_patterns
from radar.clustering import build_clusters
from radar.guards import Guards
from radar.sessions import BankNode, run_radar, token_id

PATTERN_TYPES = ["fan-out", "fan-in", "gather-scatter", "scatter-gather", "cycle", "random", "bipartite", "stack"]
FIXED_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
FEATURES = ["n_in", "n_out", "sum_in", "sum_out", "deg_in", "deg_out", "max_in_24h", "drain_24h", "lag_h", "flow_ratio",
            "retention", "rare_out_share", "n_rare_cp", "nbr"]


# ----------------------------------------------------------------------------------------------------------------------------------
# Bank side (label-free)
# ----------------------------------------------------------------------------------------------------------------------------------

def _sigmoid(e: pl.Expr) -> pl.Expr:
    return 1.0 / (1.0 + (-e).exp())


def engine(rows: pl.DataFrame, ecfg: dict) -> pl.DataFrame:
    """Per-account features and score for ONE node (one simulated bank, or the pooled node in naive mode).

    `rows` = that node's canonical rows (client_id is always an own account). Returns one row per own account with the features,
    `score1` (first pass), `nbr` (max first-pass probability of counterparties that are own clients of this node) and `score`."""
    w = ecfg["weights"]
    rare_max = ecfg["rare_max_degree"]
    win = f"{int(ecfg['drain_window_h'])}h"
    deg = rows.group_by("counterparty_token").agg(cp_degree=pl.col("client_id").n_unique())
    r = rows.select("client_id", "ts", "amount", "direction", "counterparty_token").join(deg, on="counterparty_token", how="left")
    is_in, is_out = pl.col("direction") == "in", pl.col("direction") == "out"
    rare = pl.col("cp_degree") <= rare_max
    agg = r.group_by("client_id").agg(
        n_in=is_in.sum(), n_out=is_out.sum(),
        sum_in=pl.col("amount").filter(is_in).sum(), sum_out=pl.col("amount").filter(is_out).sum(),
        deg_in=pl.col("counterparty_token").filter(is_in).n_unique(), deg_out=pl.col("counterparty_token").filter(is_out).n_unique(),
        rare_out=pl.col("amount").filter(is_out & rare).sum(), n_rare_cp=pl.col("counterparty_token").filter(rare).n_unique(),
    )
    inr = r.filter(is_in).sort("client_id", "ts")
    roll = (inr.rolling(index_column="ts", period=win, group_by="client_id").agg(s=pl.col("amount").sum())
            .group_by("client_id").agg(max_in_24h=pl.col("s").max()))
    big = (inr.sort(["client_id", "amount", "ts"], descending=[False, True, False]).group_by("client_id", maintain_order=True).first()
           .select("client_id", t0=pl.col("ts"), a0=pl.col("amount"), payer=pl.col("counterparty_token")))
    drain = (r.filter(is_out).select("client_id", "ts", "amount", "counterparty_token").join(big, on="client_id")
             .filter((pl.col("ts") >= pl.col("t0")) & (pl.col("ts") <= pl.col("t0") + pl.duration(hours=ecfg["drain_window_h"]))
                     & (pl.col("counterparty_token") != pl.col("payer")))
             .group_by("client_id").agg(drained=pl.col("amount").sum(), first_out=pl.col("ts").min(), a0=pl.col("a0").first(),
                                         t0=pl.col("t0").first()))
    f = (agg.join(roll, on="client_id", how="left").join(drain, on="client_id", how="left")
         .with_columns(
             max_in_24h=pl.col("max_in_24h").fill_null(0.0),
             drain_24h=pl.when(pl.col("a0") > 0).then((pl.col("drained") / pl.col("a0")).clip(0, 1)).otherwise(0.0).fill_null(0.0),
             lag_h=((pl.col("first_out") - pl.col("t0")).dt.total_minutes() / 60.0),
             flow_ratio=pl.when(pl.max_horizontal("sum_in", "sum_out") > 0)
             .then(pl.min_horizontal("sum_in", "sum_out") / pl.max_horizontal("sum_in", "sum_out")).otherwise(0.0),
             retention=pl.when(pl.col("sum_in") > 0).then(1 - (pl.col("sum_out") / pl.col("sum_in")).clip(0, 1)).otherwise(None),
             rare_out_share=pl.when(pl.col("sum_out") > 0).then(pl.col("rare_out") / pl.col("sum_out")).otherwise(0.0),
         ).drop("drained", "first_out", "a0", "t0", "rare_out"))
    score1 = (w["bias"] + w["drain_24h"] * pl.col("drain_24h") + w["flow_ratio"] * pl.col("flow_ratio")
              + w["low_retention"] * ((pl.col("retention") <= 0.1).fill_null(False)).cast(pl.Float64)
              + w["rare_out_share"] * pl.col("rare_out_share") + w["log_n_rare_cp"] * pl.col("n_rare_cp").cast(pl.Float64).log1p()
              + w["log_deg_in"] * pl.col("deg_in").cast(pl.Float64).log1p()
              + w["log10_max_in_24h"] * (1 + pl.col("max_in_24h")).log10())
    f = f.with_columns(score1=score1)
    p1 = f.select(counterparty_token=pl.col("client_id"), nprob=_sigmoid(pl.col("score1")))
    nbr = (r.select("client_id", "counterparty_token").unique().join(p1, on="counterparty_token", how="inner")
           .group_by("client_id").agg(nbr=pl.col("nprob").max()))
    f = f.join(nbr, on="client_id", how="left").with_columns(nbr=pl.col("nbr").fill_null(0.0))
    f = f.with_columns(score=pl.col("score1") + w["neighbour"] * pl.col("nbr"))
    return f.sort("client_id")


def run_isolated(rows: pl.DataFrame, ecfg: dict) -> pl.DataFrame:
    """Each simulated bank runs the engine on its own rows only."""
    out = []
    for b in sorted(rows["bank_id"].unique().to_list()):
        out.append(engine(rows.filter(pl.col("bank_id") == b), ecfg).with_columns(bank_id=pl.lit(b)))
    return pl.concat(out).sort("client_id")


def cand_ref(bank_secret: bytes, client_id: str) -> str:
    return hmac.new(bank_secret, client_id.encode(), hashlib.sha256).hexdigest()[:12]


@dataclass
class NodeExport:
    node: BankNode
    ref_to_client: dict[str, str]      # stays inside the bank
    n_in_band: int
    n_submitted_candidates: int


def bank_nodes(rows: pl.DataFrame, scores: pl.DataFrame, threshold: float, rcfg: dict) -> dict[str, NodeExport]:
    """Per bank: candidate band (score >= threshold - offset), rare counterparty tokens of the candidates' transfers, capped."""
    out: dict[str, NodeExport] = {}
    lo = threshold - rcfg["candidate_offset"]
    for b in sorted(scores["bank_id"].unique().to_list()):
        rb = rows.filter(pl.col("bank_id") == b)
        sb = scores.filter((pl.col("bank_id") == b) & (pl.col("score") >= lo)).sort(["score", "client_id"], descending=[True, False])
        deg = rb.group_by("counterparty_token").agg(cp_degree=pl.col("client_id").n_unique())
        ct = (rb.join(sb.select("client_id"), on="client_id").join(deg, on="counterparty_token")
              .filter(pl.col("cp_degree") <= rcfg["token_max_degree"])
              .group_by("client_id", "counterparty_token").agg(amt=pl.col("amount").sum(), cp_degree=pl.col("cp_degree").first())
              .sort(["client_id", "amt", "counterparty_token"], descending=[False, True, False])
              .group_by("client_id", maintain_order=True).head(rcfg["tokens_per_candidate"]))
        toks: dict[str, list[tuple[str, int]]] = {}
        for row in ct.iter_rows(named=True):
            toks.setdefault(row["client_id"], []).append((row["counterparty_token"], row["cp_degree"]))
        secret = (rcfg["bank_secret_prefix"] + b).encode()
        cands, rarity, ref_to_client, seen = [], {}, {}, set()
        n_sub = 0
        for cid, sc in zip(sb["client_id"].to_list(), sb["score"].to_list(), strict=True):
            mine = toks.get(cid, [])
            new = [t for t, _ in mine if t not in seen]
            if not mine or len(seen) + len(new) > rcfg["max_tokens_per_bank"]:
                if len(seen) >= rcfg["max_tokens_per_bank"]:
                    break
                continue
            ref = cand_ref(secret, cid)
            ref_to_client[ref] = cid
            prob = 1 / (1 + math.exp(-sc))
            for t, d in mine:
                cands.append({"token": t, "cand_ref": ref, "score": round(prob, 6)})
                rarity[t] = 1.0 / max(1, d)
                seen.add(t)
            n_sub += 1
        out[b] = NodeExport(BankNode(b, cands, rarity, {}), ref_to_client, sb.height, n_sub)
    return out


def _pair_session(args: tuple) -> dict:
    a, b, gcfg, key = args
    t = time.perf_counter()
    res = run_radar([a, b], Guards(gcfg), key, now=FIXED_NOW)
    elapsed = time.perf_counter() - t
    wire_dump = json.dumps(res.wire)
    plain = {c["token"] for c in a.candidates} | {c["token"] for c in b.candidates}
    leaks = sum(1 for tok in plain if tok in wire_dump)
    return {"pair": f"{a.bank_id}:{b.bank_id}", "seconds": round(elapsed, 2), "exposure": res.exposure, "refused": res.refused,
            "clusters": [{"candidates": [list(x) for x in c["candidates"]], "tokens": c["tokens"]} for c in res.clusters],
            "plaintext_tokens_in_wire": leaks, "n_tokens": [len(a.submission()), len(b.submission())]}


def radar_pairwise(nodes: list[BankNode], guards_cfg: dict, epoch_key: bytes, workers: int = 1) -> dict:
    """Admission by Guards, then one radar.sessions.run_radar call per bank pair (in parallel processes when workers > 1),
    then the coordinator unions the per-pair matches and calls build_clusters once. Connected components of the union are the
    same as in a single run_radar over all banks, because every per-pair component is connected in the true candidate/token graph."""
    guards = Guards(guards_cfg)
    live, refused = [], {}
    for n in nodes:
        d = guards.check(n.bank_id, n.submission(), FIXED_NOW)
        if d.allowed:
            live.append(n)
        else:
            refused[n.bank_id] = d.reason
    jobs = [(a, b, guards_cfg, epoch_key) for a, b in itertools.combinations(live, 2)]
    t = time.perf_counter()
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as ex:
            pairs = list(ex.map(_pair_session, jobs))
    else:
        pairs = [_pair_session(j) for j in jobs]
    wall = time.perf_counter() - t
    rar: dict[str, float] = {}
    for n in live:
        for tok, r in n.rarity.items():
            tid = token_id(epoch_key, tok)
            rar[tid] = max(rar.get(tid, 0.0), r)
    rows, seen = [], set()
    for p in pairs:
        for c in p["clusters"]:
            for bank, ref in c["candidates"]:
                for tid in c["tokens"]:
                    if (tid, bank, ref) not in seen:
                        seen.add((tid, bank, ref))
                        rows.append({"token_id": tid, "bank_id": bank, "cand_ref": ref, "rarity": rar.get(tid, 0.5)})
    clusters = build_clusters(rows) if rows else []
    exp = {"raw_records_exposed": 0,
           "blinded_elements": sum(p["exposure"]["blinded_elements"] for p in pairs),
           "bytes_exchanged": sum(p["exposure"]["bytes_exchanged"] for p in pairs),
           "match_rows_to_coordinator": sum(p["exposure"]["match_rows_to_coordinator"] for p in pairs),
           "plaintext_tokens_in_wire": sum(p["plaintext_tokens_in_wire"] for p in pairs)}
    return {"clusters": clusters, "refused": refused, "exposure": exp, "wall_seconds": round(wall, 2),
            "sequential_seconds": round(sum(p["seconds"] for p in pairs), 2),
            "pairs": [{k: p[k] for k in ("pair", "seconds", "n_tokens", "refused")} | {"bytes": p["exposure"]["bytes_exchanged"]} for p in pairs],
            "matched_token_ids": sorted({r["token_id"] for r in rows})}


def apply_radar(scores: pl.DataFrame, exports: dict[str, NodeExport], clusters: list[dict], boost: float) -> tuple[pl.DataFrame, set[str]]:
    """Each bank maps its own cand_refs in disclosed clusters back to accounts and adds the boost (never subtracts)."""
    boosted = {exports[b].ref_to_client[ref] for c in clusters if c["disclosed"] for b, ref in c["candidates"]}
    s = scores.with_columns(radar=pl.col("client_id").is_in(list(boosted)))
    return s.with_columns(score=pl.col("score") + pl.when(pl.col("radar")).then(boost).otherwise(0.0)), boosted


# ----------------------------------------------------------------------------------------------------------------------------------
# Evaluation side (labels allowed below this line)
# ----------------------------------------------------------------------------------------------------------------------------------

def in_window(df: pl.DataFrame, w: dict) -> pl.DataFrame:
    s = datetime.fromisoformat(w["start"]).replace(tzinfo=UTC)
    e = datetime.fromisoformat(w["end"]).replace(tzinfo=UTC)
    return df.filter((pl.col("ts") >= s) & (pl.col("ts") < e))


def truth_tables(raw: pl.DataFrame, txp: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(laundering tx [tx_id, sender, receiver, amount_paid], account pattern rows [client_id, pattern_type, attempt_id]).
    Self-transfers are excluded (they are dropped by the bank split)."""
    lt = raw.filter((pl.col("is_laundering") == 1) & ~((pl.col("from_bank") == pl.col("to_bank")) & (pl.col("from_account") == pl.col("to_account"))))
    lt = lt.select("tx_id", "ts", sender=pl.col("from_bank") + ":" + pl.col("from_account"),
                   receiver=pl.col("to_bank") + ":" + pl.col("to_account"), amount_paid="amount_paid")
    p = lt.join(txp, on="tx_id", how="inner")
    acc_pat = pl.concat([p.select(client_id="sender", pattern_type="pattern_type", attempt_id="attempt_id"),
                         p.select(client_id="receiver", pattern_type="pattern_type", attempt_id="attempt_id")]).unique()
    return lt, acc_pat


def prf(flagged: set[str], truth: set[str], universe: set[str] | None = None) -> dict:
    if universe is not None:
        flagged, truth = flagged & universe, truth & universe
    tp, fp, fn = len(flagged & truth), len(flagged - truth), len(truth - flagged)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "flagged": tp + fp, "positives": tp + fn, "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def average_precision(scores: pl.DataFrame, truth: set[str], col: str = "score") -> float:
    s = (scores.select("client_id", col).sort([col, "client_id"], descending=[True, False])
         .with_columns(pos=pl.col("client_id").is_in(list(truth)).cast(pl.Int64)))
    s = s.with_row_index("rank", offset=1).with_columns(cum=pl.col("pos").cum_sum())
    npos = int(s["pos"].sum())
    if npos == 0:
        return 0.0
    return round(float(s.filter(pl.col("pos") == 1).select((pl.col("cum") / pl.col("rank")).sum()).item()) / npos, 4)


def precision_at(scores: pl.DataFrame, truth: set[str], ks: tuple[int, ...] = (50, 100, 500, 1000), col: str = "score") -> dict:
    s = scores.sort([col, "client_id"], descending=[True, False])["client_id"].to_list()
    return {str(k): round(len(set(s[:k]) & truth) / k, 4) for k in ks}


REF_COLS = ["drain_24h", "flow_ratio", "lowret", "rare_out_share", "l_rare", "l_deg_in", "l_max24", "nbr", "l_n_in", "l_n_out", "l_deg_out"]


def _design(f: pl.DataFrame):
    import numpy as np  # noqa: PLC0415
    d = f.select(drain_24h="drain_24h", flow_ratio="flow_ratio", lowret=(pl.col("retention") <= 0.1).fill_null(False).cast(pl.Float64),
                 rare_out_share="rare_out_share", l_rare=pl.col("n_rare_cp").cast(pl.Float64).log1p(),
                 l_deg_in=pl.col("deg_in").cast(pl.Float64).log1p(), l_max24=(1 + pl.col("max_in_24h")).log10(), nbr="nbr",
                 l_n_in=pl.col("n_in").cast(pl.Float64).log1p(), l_n_out=pl.col("n_out").cast(pl.Float64).log1p(),
                 l_deg_out=pl.col("deg_out").cast(pl.Float64).log1p())
    return np.nan_to_num(d.to_numpy().astype(float))


def fit_reference(f_cal: pl.DataFrame, truth_cal: set[str], l2: float = 1.0, iters: int = 30) -> dict:
    """EVALUATION-ONLY reference: L2 logistic regression (Newton/IRLS, numpy) on the same features, fitted on the calibration
    window labels. Never used in the decision path; answers 'is the weakness in the hand-set weights or in the features?'."""
    import numpy as np  # noqa: PLC0415
    X = _design(f_cal)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.hstack([np.ones((X.shape[0], 1)), (X - mu) / sd])
    y = f_cal["client_id"].is_in(list(truth_cal)).to_numpy().astype(float)
    w = np.zeros(Z.shape[1])
    reg = l2 * np.eye(Z.shape[1])
    reg[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Z @ w)))
        g = Z.T @ (p - y) + reg @ w
        H = (Z * (p * (1 - p))[:, None]).T @ Z + reg
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return {"mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(), "columns": REF_COLS}


def reference_scores(f: pl.DataFrame, model: dict) -> pl.DataFrame:
    import numpy as np  # noqa: PLC0415
    X = (_design(f) - np.array(model["mu"])) / np.array(model["sd"])
    z = model["w"][0] + X @ np.array(model["w"][1:])
    return f.select("client_id").with_columns(ref=pl.Series(z))


def top_k(scores: pl.DataFrame, k: int, col: str) -> set[str]:
    return set(scores.sort([col, "client_id"], descending=[True, False]).head(k)["client_id"].to_list())


def tx_level(lt_all_window: pl.DataFrame, flagged: set[str]) -> dict:
    """Transaction flagged if its sender or receiver account is flagged."""
    fl = list(flagged)
    t = lt_all_window.with_columns(f=pl.col("sender").is_in(fl) | pl.col("receiver").is_in(fl))
    tp = t.filter(pl.col("f") & (pl.col("is_laundering") == 1)).height
    fp = t.filter(pl.col("f") & (pl.col("is_laundering") == 0)).height
    fn = t.filter(~pl.col("f") & (pl.col("is_laundering") == 1)).height
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def per_pattern(acc_pat: pl.DataFrame, flagged: set[str], truth: set[str]) -> dict:
    fl = list(flagged)
    out = {}
    ap = acc_pat.with_columns(f=pl.col("client_id").is_in(fl))
    for pt in PATTERN_TYPES:
        g = ap.filter(pl.col("pattern_type") == pt)
        accts = g.select("client_id", "f").unique()
        att = g.group_by("attempt_id").agg(pl.col("f").any())
        out[pt] = {"accounts": accts.height, "accounts_flagged": int(accts["f"].sum()),
                   "account_recall": round(float(accts["f"].mean()), 4) if accts.height else None,
                   "attempts": att.height, "attempts_with_a_flagged_account": int(att["f"].sum()),
                   "attempt_recall": round(float(att["f"].mean()), 4) if att.height else None}
    un = truth - set(acc_pat["client_id"].to_list())
    out["unattributed"] = {"accounts": len(un), "accounts_flagged": len(un & flagged),
                           "account_recall": round(len(un & flagged) / len(un), 4) if un else None,
                           "note": "laundering accounts whose laundering transactions are not listed in the patterns file"}
    return out


def _feat_row(r: dict) -> dict:
    o = {k: (round(r[k], 3) if isinstance(r[k], float) else r[k]) for k in ["client_id", "bank_id", "score"] + FEATURES if k in r}
    return o


def failures(scores: pl.DataFrame, truth: set[str], flagged: set[str], acc_pat: pl.DataFrame, lt: pl.DataFrame, k: int = 8) -> dict:
    tl = list(truth)
    fps = scores.filter(~pl.col("client_id").is_in(tl) & pl.col("client_id").is_in(list(flagged))).sort(["score", "client_id"], descending=[True, False]).head(k)
    lam = pl.concat([lt.select(client_id="sender", a="amount_paid"), lt.select(client_id="receiver", a="amount_paid")]) \
        .group_by("client_id").agg(laundering_tx=pl.len())
    pats = acc_pat.group_by("client_id").agg(patterns=pl.col("pattern_type").unique().sort())
    missed = (scores.filter(pl.col("client_id").is_in(tl) & ~pl.col("client_id").is_in(list(flagged)))
              .join(lam, on="client_id", how="left").join(pats, on="client_id", how="left")
              .sort(["laundering_tx", "client_id"], descending=[True, False]).head(k))
    miss = []
    for r in missed.iter_rows(named=True):
        miss.append(_feat_row(r) | {"laundering_tx": r["laundering_tx"], "patterns": r["patterns"] or ["unattributed"]})
    return {"worst_false_positives": [_feat_row(r) for r in fps.iter_rows(named=True)],
            "missed_laundering_accounts_most_laundering_tx": miss}


def choose_threshold(scores: pl.DataFrame, truth: set[str], n_q: int) -> dict:
    qs = sorted({round(float(scores["score"].quantile(i / n_q)), 4) for i in range(1, n_q)})
    s = scores.with_columns(pos=pl.col("client_id").is_in(list(truth)))
    best = None
    curve = []
    for q in qs:
        f = s.filter(pl.col("score") >= q)
        tp = int(f["pos"].sum())
        fp = f.height - tp
        fn = len(truth) - tp
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        curve.append((q, f1))
        if best is None or f1 > best[1] or (f1 == best[1] and q > best[0]):
            best = (q, f1, p, r, f.height)
    return {"threshold": best[0], "calibration_f1": round(best[1], 4), "calibration_precision": round(best[2], 4),
            "calibration_recall": round(best[3], 4), "calibration_flagged": best[4], "grid_size": len(qs),
            "rule": "argmax pooled account-level F1 of the isolated mode on the calibration window; ties -> higher threshold"}


def evaluate_window(name: str, raw: pl.DataFrame, rows_all: pl.DataFrame, txp: pl.DataFrame, cfg: dict, threshold: float,
                    guards_cfg: dict, with_radar: bool = True, ref_model: dict | None = None) -> dict:
    t_start = time.perf_counter()
    w = cfg["windows"][name]
    rows = in_window(rows_all, w)
    rw = in_window(raw, w)
    lt, acc_pat = truth_tables(rw, txp)
    truth = set(lt["sender"].to_list()) | set(lt["receiver"].to_list())
    allw = rw.filter(~((pl.col("from_bank") == pl.col("to_bank")) & (pl.col("from_account") == pl.col("to_account")))) \
        .select("is_laundering", sender=pl.col("from_bank") + ":" + pl.col("from_account"), receiver=pl.col("to_bank") + ":" + pl.col("to_account"))
    ecfg, rcfg = cfg["engine"], cfg["radar"]

    t = time.perf_counter()
    iso = run_isolated(rows, ecfg)
    t_iso = time.perf_counter() - t
    t = time.perf_counter()
    naive = engine(rows, ecfg).join(iso.select("client_id", "bank_id"), on="client_id")
    t_naive = time.perf_counter() - t
    universe = set(iso["client_id"].to_list())
    banks = sorted(iso["bank_id"].unique().to_list())
    flag = lambda s: set(s.filter(pl.col("score") >= threshold)["client_id"].to_list())  # noqa: E731
    f_iso = flag(iso)

    per_bank = {}
    for b in banks:
        ub = set(iso.filter(pl.col("bank_id") == b)["client_id"].to_list())
        per_bank[b] = prf(f_iso, truth, ub) | {"accounts": len(ub), "average_precision": average_precision(iso.filter(pl.col("bank_id") == b), truth & ub),
                                               "rows": rows.filter(pl.col("bank_id") == b).height}
    modes: dict[str, dict] = {}
    modes["isolated"] = {
        "overall": prf(f_iso, truth), "average_precision": average_precision(iso, truth), "precision_at_k": precision_at(iso, truth),
        "tx_level": tx_level(allw, f_iso), "per_bank": per_bank,
        "best_single_bank": max(per_bank, key=lambda b: (per_bank[b]["f1"], b)),
        "best_single_bank_f1": max(m["f1"] for m in per_bank.values()),
        "mean_bank_precision": round(sum(m["precision"] for m in per_bank.values()) / len(banks), 4),
        "mean_bank_recall": round(sum(m["recall"] for m in per_bank.values()) / len(banks), 4),
        "mean_bank_f1": round(sum(m["f1"] for m in per_bank.values()) / len(banks), 4),
        "per_pattern": per_pattern(acc_pat, f_iso, truth),
        "exposure": {"raw_records_exposed": 0, "bytes_exchanged": 0}, "engine_seconds": round(t_iso, 2)}

    radar_info = None
    if with_radar:
        exports = bank_nodes(rows, iso, threshold, rcfg)
        rr = radar_pairwise([e.node for e in exports.values()], guards_cfg, rcfg["epoch_key"].encode(), rcfg["workers"])
        psi, boosted = apply_radar(iso, exports, rr["clusters"], rcfg["cluster_boost"])
        f_psi = flag(psi) | f_iso
        disclosed = [c for c in rr["clusters"] if c["disclosed"]]
        modes["staj_psi"] = {
            "overall": prf(f_psi, truth), "average_precision": average_precision(psi, truth), "precision_at_k": precision_at(psi, truth),
            "tx_level": tx_level(allw, f_psi),
            "per_pattern": per_pattern(acc_pat, f_psi, truth),
            "exposure": rr["exposure"] | {"psi_wall_seconds": rr["wall_seconds"], "psi_sequential_seconds": rr["sequential_seconds"]},
            "radar": {"refused": rr["refused"], "pairs": rr["pairs"], "clusters_total": len(rr["clusters"]), "clusters_disclosed": len(disclosed),
                      "matched_tokens": len(rr["matched_token_ids"]),
                      "boosted_accounts": len(boosted), "boosted_laundering": len(boosted & truth),
                      "newly_flagged_by_radar": len(f_psi - f_iso), "newly_flagged_laundering": len((f_psi - f_iso) & truth),
                      "candidates_in_band": {b: e.n_in_band for b, e in exports.items()},
                      "candidates_submitted": {b: e.n_submitted_candidates for b, e in exports.items()},
                      "submitted_candidates_laundering_share": round(sum(1 for e in exports.values() for c in e.ref_to_client.values() if c in truth)
                                                                     / max(1, sum(len(e.ref_to_client) for e in exports.values())), 4),
                      "tokens_submitted": {b: len(e.node.submission()) for b, e in exports.items()},
                      "disclosed_cluster_sizes": sorted((len(c["candidates"]) for c in disclosed), reverse=True)[:20],
                      "disclosed_cluster_laundering_share": [round(sum(1 for b, r in c["candidates"] if exports[b].ref_to_client[r] in truth) / len(c["candidates"]), 3)
                                                              for c in sorted(disclosed, key=lambda c: -len(c["candidates"]))[:20]]},
            "failures": failures(psi, truth, f_psi, acc_pat, lt)}
        radar_info = True
    f_nv = flag(naive)
    t = time.perf_counter()
    buf = io.BytesIO()
    rows.write_parquet(buf)
    t_ser = time.perf_counter() - t
    modes["naive_raw_sharing"] = {
        "overall": prf(f_nv, truth), "average_precision": average_precision(naive, truth), "precision_at_k": precision_at(naive, truth),
        "tx_level": tx_level(allw, f_nv),
        "per_pattern": per_pattern(acc_pat, f_nv, truth),
        "exposure": {"raw_records_exposed": rows.height, "raw_source_transactions": allw.height,
                     "bytes_exchanged_parquet": buf.getbuffer().nbytes, "bytes_in_memory_arrow": int(rows.estimated_size()),
                     "serialize_seconds": round(t_ser, 2)},
        "engine_seconds": round(t_naive, 2)}
    if radar_info is None:
        modes["isolated"]["failures"] = failures(iso, truth, f_iso, acc_pat, lt)

    k = len(f_iso)
    feats = iso.with_columns(n_tx=pl.col("n_in") + pl.col("n_out"))
    rnd = iso.select("client_id").with_columns(rnd=pl.Series(range(iso.height)).shuffle(seed=cfg["baselines"]["random_seed"]).cast(pl.Float64))
    baselines = {
        "k_equals_isolated_flagged": k,
        "tx_count_topk": prf(top_k(feats, k, "n_tx"), truth) | {"average_precision": average_precision(feats, truth, "n_tx")},
        "distinct_counterparties_topk": prf(top_k(feats.with_columns(dc=pl.col("deg_in") + pl.col("deg_out")), k, "dc"), truth)
        | {"average_precision": average_precision(feats.with_columns(dc=pl.col("deg_in") + pl.col("deg_out")), truth, "dc")},
        "random_topk_seeded": prf(top_k(rnd, k, "rnd"), truth) | {"average_precision": average_precision(rnd, truth, "rnd")},
        "prevalence": round(len(truth) / len(universe), 5)}
    feats = feats.with_columns(dc=pl.col("deg_in") + pl.col("deg_out"))
    for bname, bscores, bcol in (("tx_count", feats, "n_tx"), ("distinct_counterparties", feats, "dc"), ("random", rnd, "rnd")):
        baselines[f"{bname}_precision_at_k"] = precision_at(bscores, truth, col=bcol)
    if ref_model is not None:
        rs = reference_scores(iso, ref_model)
        baselines["fitted_reference_isolated"] = {
            "what": "EVALUATION-ONLY logistic regression on the same isolated-mode features, fitted on calibration-window labels; not in the decision path",
            "average_precision": average_precision(rs, truth, "ref"), "precision_at_k": precision_at(rs, truth, col="ref")}
    return {"window": w, "rows": rows.height, "flagged_share_isolated": round(len(f_iso) / len(universe), 4), "source_transactions_non_self": allw.height, "accounts": len(universe),
            "laundering_accounts": len(truth), "laundering_transactions_non_self": lt.height,
            "accounts_per_bank": {b: per_bank[b]["accounts"] for b in banks},
            "laundering_accounts_per_bank": {b: per_bank[b]["positives"] for b in banks},
            "modes": modes, "baselines": baselines, "seconds": round(time.perf_counter() - t_start, 1)}


def psi_benchmark(n: int = 300) -> dict:
    """Measured cost of one complete two-party PsiParty session (both sides learn the intersection), n tokens per side."""
    from radar.psi.dh_psi import PsiParty  # noqa: PLC0415
    a = PsiParty([f"bench-a-{i}" for i in range(n)], "staj-psi-bench")
    b = PsiParty([f"bench-a-{i}" for i in range(n // 2, n + n // 2)], "staj-psi-bench")
    t = time.perf_counter()
    m1 = a.blind()
    m2, m3 = b.respond(m1)
    hits, back = a.finish(m2, m3)
    hb = b.learn_from_return(back)
    el = time.perf_counter() - t
    assert len(hits) == len(hb) == n - n // 2
    return {"n_tokens": n, "seconds": round(el, 3), "ms_per_token_per_pair_session": round(1000 * el / n, 2)}


def fx_check(raw: pl.DataFrame, table: dict[str, float]) -> dict:
    a = raw.filter((pl.col("receiving_currency") == "US Dollar") & (pl.col("payment_currency") != "US Dollar")) \
        .group_by("payment_currency").agg(implied=(pl.col("amount_received") / pl.col("amount_paid")).median(), n=pl.len())
    out = {}
    for r in a.sort("payment_currency").iter_rows(named=True):
        ph = table[r["payment_currency"]]
        out[r["payment_currency"]] = {"placeholder": ph, "dataset_implied_median": round(r["implied"], 6), "n_rows": r["n"],
                                      "relative_deviation": round(ph / r["implied"] - 1, 3)}
    return out


def main(out_path: str = "eval/out/ibm_eval.json", md_path: str = "docs/IBM_EVAL.md", cfg_path: str = "config/ibm.yaml") -> dict:
    t0 = time.perf_counter()
    cfg = load_config(cfg_path)
    cfg_hash = hashlib.sha256(Path(cfg_path).read_bytes()).hexdigest()
    with open(cfg["radar"]["guards_from"], encoding="utf-8") as f:
        guards_cfg = yaml.safe_load(f)["radar_guards"]
    raw = load_ibm(cfg["dataset"]["transactions"])
    pats = load_patterns(cfg["dataset"]["patterns"])
    txp = tx_patterns(raw, pats)
    tx, _labels = split_labels(raw)                  # banks get `tx` only
    rows_all = bank_split(tx, cfg["n_banks"], cfg["fx"]["usd_per_unit"])
    t_ingest = time.perf_counter() - t0
    print(f"ingest {t_ingest:.1f}s rows={rows_all.height}", flush=True)

    selfmask = (pl.col("from_bank") == pl.col("to_bank")) & (pl.col("from_account") == pl.col("to_account"))
    lt_all, _ = truth_tables(raw, txp)
    truth_all = set(lt_all["sender"].to_list()) | set(lt_all["receiver"].to_list())
    l_self = raw.filter((pl.col("is_laundering") == 1) & selfmask)
    self_only = set((l_self["from_bank"] + ":" + l_self["from_account"]).to_list()) - truth_all
    tail = raw.filter(pl.col("ts") >= datetime(2022, 9, 11, tzinfo=UTC))

    psi_bench = psi_benchmark()
    print(f"psi benchmark {psi_bench}", flush=True)
    # 1. threshold choice on the calibration window (isolated mode, pooled)
    w = cfg["windows"]["calibration"]
    rows_cal = in_window(rows_all, w)
    lt_cal, _ = truth_tables(in_window(raw, w), txp)
    truth_cal = set(lt_cal["sender"].to_list()) | set(lt_cal["receiver"].to_list())
    iso_cal = run_isolated(rows_cal, cfg["engine"])
    thr = choose_threshold(iso_cal, truth_cal, cfg["engine"]["threshold_grid_quantiles"])
    thr |= {"calibration_average_precision": average_precision(iso_cal, truth_cal), "calibration_accounts": iso_cal.height,
            "calibration_laundering_accounts": len(truth_cal)}
    print(f"threshold {thr}", flush=True)
    ref_model = fit_reference(iso_cal, truth_cal)
    thr["fitted_reference_calibration_average_precision"] = average_precision(reference_scores(iso_cal, ref_model), truth_cal, "ref")

    # 2. held-out window and full period, all three modes
    windows = {}
    for name in ("heldout", "full"):
        windows[name] = evaluate_window(name, raw, rows_all, txp, cfg, thr["threshold"], guards_cfg, ref_model=ref_model)
        print(f"{name} done in {windows[name]['seconds']}s", flush=True)

    bank_sizes = rows_all.group_by("bank_id").agg(rows=pl.len(), accounts=pl.col("client_id").n_unique()).sort("bank_id")
    result = {
        "synthetic": True,
        "dataset": cfg["dataset"]["name"],
        "note": "Generic laundering patterns from the AMLworld generator, NOT Czech money-mule schemes. Placeholder FX table. Hand-set weights.",
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "config_path": cfg_path, "config_sha256": cfg_hash,
        "split": {"calibration": cfg["windows"]["calibration"], "heldout": cfg["windows"]["heldout"], "full": cfg["windows"]["full"],
                  "rule": "labels of the calibration window are used for exactly one choice (the flag threshold); weights are hand-set; "
                          "the held-out window was never used for any choice; 'full' contains the calibration days and is labelled so",
                  "features_per_window": "features are computed only from rows inside the window"},
        "ingest": {"source_rows": raw.height, "self_transfers_dropped": raw.filter(selfmask).height,
                   "accounts_in_source": len(set((raw["from_bank"] + ":" + raw["from_account"]).to_list()) | set((raw["to_bank"] + ":" + raw["to_account"]).to_list())),
                   "tail_days_2022_09_11_to_18": {"rows": tail.height, "laundering": int(tail["is_laundering"].sum())},
                   "laundering_self_transfers_dropped": l_self.height,
                   "accounts_labelled_only_via_self_transfers": len(self_only),
                   "canonical_rows": rows_all.height, "accounts": rows_all["client_id"].n_unique(),
                   "ibm_banks": len(set(tx["from_bank"].to_list()) | set(tx["to_bank"].to_list())),
                   "laundering_accounts_non_self": len(truth_all),
                   "pattern_lines": pats.height, "pattern_lines_matched_to_transactions": txp.height,
                   "attempts": int(pats["attempt_id"].n_unique()),
                   "attempts_per_type": {r["pattern_type"]: r["n"] for r in pats.group_by("pattern_type").agg(n=pl.col("attempt_id").n_unique()).sort("pattern_type").iter_rows(named=True)},
                   "simulated_banks": {r["bank_id"]: {"rows": r["rows"], "accounts": r["accounts"]} for r in bank_sizes.iter_rows(named=True)},
                   "seconds": round(t_ingest, 1)},
        "fx_placeholder_check": fx_check(raw, cfg["fx"]["usd_per_unit"]),
        "psi_benchmark": psi_bench,
        "threshold": thr,
        "engine": {"name": "IBM-scale vectorised variant of D1 flow-through+ / D5 rare-exit concentration (own design)",
                   "weights": cfg["engine"]["weights"], "features": FEATURES},
        "radar_config": cfg["radar"], "guards": guards_cfg,
        "fitted_reference_model": {"columns": ref_model["columns"], "standardised_weights": [round(x, 4) for x in ref_model["w"]],
                                   "note": "evaluation-only; fitted on calibration labels; not used for any flag"},
        "windows": windows,
        "total_seconds": round(time.perf_counter() - t0, 1),
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if md_path:
        Path(md_path).write_text(render_md(result), encoding="utf-8")
    print(f"total {result['total_seconds']}s -> {out_path}", flush=True)
    return result


def _cmp(a: float, b: float) -> str:
    return "higher than" if a > b else ("lower than" if a < b else "equal to")


def render_md(r: dict) -> str:
    """docs/IBM_EVAL.md, generated from the result dict. No number in this file is typed by hand."""
    L: list[str] = []
    a = L.append
    ing, thr = r["ingest"], r["threshold"]
    a("# IBM AMLworld evaluation (SYNTHETIC data)\n")
    a(f"> Generated by `python -m eval.ibm_eval` at {r['generated_at_utc']} from `eval/out/ibm_eval.json` (config `{r['config_path']}`, "
      f"sha256 `{r['config_sha256'][:16]}…`). **Every number below is computed by code.** Dataset: {r['dataset']}. "
      "**Synthetic data. Generic laundering patterns from the AMLworld generator, NOT Czech money-mule schemes.**\n")
    a("## 1. What was done\n")
    a(f"* **Ingest** (`ingest/ibm.py`): {ing['source_rows']:,} source rows; {ing['self_transfers_dropped']:,} self-transfers dropped "
      f"({ing['laundering_self_transfers_dropped']} of them labelled laundering; {ing['accounts_labelled_only_via_self_transfers']} account(s) were laundering only through a self-transfer and so leave the truth set). "
      f"{ing['ibm_banks']:,} IBM bank ids → 5 simulated banks by SHA-256 of the id (all accounts of one IBM bank stay together). "
      f"Each transaction → one OUT row at the sender's bank and one IN row at the receiver's bank: {ing['canonical_rows']:,} canonical rows, {ing['accounts']:,} accounts. "
      "Own account = `client_id` `<ibm bank>:<account>`; the counterparty is only an external token of the same form (like an IBAN).")
    a("* **Amounts**: Amount Paid × a hand-typed **PLACEHOLDER** USD table (`config/ibm.yaml`, `placeholder: true`). See §6 for its deviation from the rates implied by the dataset itself.")
    a(f"* **Labels** (`Is Laundering`, pattern types) are split off before the bank split and read only by the metric code in `eval/ibm_eval.py`; `bank_split` refuses a labelled table (unit test). "
      f"Account truth = sender or receiver of ≥ 1 laundering transaction. Pattern types: {ing['pattern_lines']:,} lines of the patterns file, "
      f"{ing['pattern_lines_matched_to_transactions']:,} matched to transactions on (timestamp, both accounts, amount, currency, format), {ing['attempts']} attempts. "
      "Laundering accounts not covered by the patterns file are reported as `unattributed`.")
    a("* **Bank-side engine** (own design, IBM-scale vectorised variant of D1 flow-through+ / D5 rare-exit concentration; polars, no python loop per client): "
      "per own account inside ONE node — counterparty degree within the node, in/out totals and counts, max 24 h inflow window, share of the largest inflow sent on within 24 h "
      "(to others than its payer), share of outflow to rare counterparties (degree ≤ 3 within the node), distinct rare counterparties, retention, and a second pass with the max first-pass "
      "probability of counterparties that are the node's OWN clients. Score = additive log-odds with **hand-set** weights (no fitting):")
    a("")
    a("| weight | value |\n|---|---|")
    for k, v in r["engine"]["weights"].items():
        a(f"| `{k}` | {v} |")
    a("")
    a(f"* **Split / threshold** (the only use of labels for a choice): {r['split']['rule']}. Calibration window {r['split']['calibration']['start']} … < {r['split']['calibration']['end']}; "
      f"threshold grid = {thr['grid_size']} score quantiles; chosen logit threshold **{thr['threshold']}** (calibration F1 {thr['calibration_f1']}, P {thr['calibration_precision']}, "
      f"R {thr['calibration_recall']}, {thr['calibration_flagged']:,} of {thr['calibration_accounts']:,} accounts flagged; calibration AP {thr['calibration_average_precision']}). "
      f"Features are computed only from rows inside each window.")
    a(f"* **Radar** (`staj_psi`): candidate band = score ≥ threshold − {r['radar_config']['candidate_offset']} (weakly suspicious included, never all accounts); per candidate the top "
      f"{r['radar_config']['tokens_per_candidate']} counterparty tokens by amount with in-bank degree ≤ {r['radar_config']['token_max_degree']}; at most {r['radar_config']['max_tokens_per_bank']} tokens per bank "
      f"(highest scores first; measured PSI cost in this run: {r['psi_benchmark']['ms_per_token_per_pair_session']} ms per token per pair session, "
      f"{r['psi_benchmark']['n_tokens']} tokens per side). Admission by `radar.guards.Guards` (config from `config/thresholds.yaml`); every bank pair runs "
      "`radar.sessions.run_radar` (real `PsiParty` DH-PSI) in its own process; the coordinator unions the per-pair matches and calls `radar.clustering.build_clusters` once "
      "(same connected components as one all-bank run). Disclosure needs ≥ 2 banks and ≥ 3 candidates. Each bank maps its own `cand_ref`s in disclosed clusters back to accounts and adds "
      f"{r['radar_config']['cluster_boost']} logit points; a flag is never removed. The post-match lag/retention exchange (§6.4 'same hand global') is **not** used on IBM.")
    a("* **naive_raw_sharing**: all canonical rows pooled into one node, same engine (global counterparty degree, neighbours across banks). Exposure = all rows; bytes = parquet serialisation.")
    a("* **Baselines** on the same accounts: top-k by transaction count, by distinct counterparties, seeded random (k = number flagged by `isolated`). "
      "An **evaluation-only** logistic regression fitted on calibration labels over the same features is reported as a reference, never used for a flag.\n")

    for wname, title in (("heldout", "Held-out window (never used for any choice)"), ("full", "Full period (CONTAINS the 9 calibration days)")):
        w = r["windows"][wname]
        m = w["modes"]
        a(f"## 2{'a' if wname == 'heldout' else 'b'}. {title}: {w['window']['start']} … < {w['window']['end']}\n")
        a(f"{w['source_transactions_non_self']:,} transactions, {w['accounts']:,} accounts, {w['laundering_accounts']:,} laundering accounts "
          f"(prevalence {w['baselines']['prevalence']}), {w['laundering_transactions_non_self']:,} laundering transactions. Runtime {w['seconds']} s.\n")
        a("| mode | precision | recall | F1 | flagged | AP (rank) | P@100 | P@1000 | tx-level P / R | records exposed | bytes exposed |")
        a("|---|---|---|---|---|---|---|---|---|---|---|")
        iso = m["isolated"]
        for name, mm in (("isolated (all banks, pooled count)", iso), ("staj_psi", m["staj_psi"]), ("naive_raw_sharing", m["naive_raw_sharing"])):
            o, ex = mm["overall"], mm["exposure"]
            rec = ex.get("raw_records_exposed", 0)
            byt = ex.get("bytes_exchanged", ex.get("bytes_exchanged_parquet", 0))
            a(f"| {name} | {o['precision']} | {o['recall']} | {o['f1']} | {o['flagged']:,} | {mm['average_precision']} | {mm['precision_at_k']['100']} | "
              f"{mm['precision_at_k']['1000']} | {mm['tx_level']['precision']} / {mm['tx_level']['recall']} | {rec:,} | {byt:,} |")
        a(f"| isolated: best single bank ({iso['best_single_bank']}) | {iso['per_bank'][iso['best_single_bank']]['precision']} | {iso['per_bank'][iso['best_single_bank']]['recall']} | "
          f"{iso['best_single_bank_f1']} | {iso['per_bank'][iso['best_single_bank']]['flagged']:,} | {iso['per_bank'][iso['best_single_bank']]['average_precision']} | | | | 0 | 0 |")
        a(f"| isolated: mean over banks | {iso['mean_bank_precision']} | {iso['mean_bank_recall']} | {iso['mean_bank_f1']} | | | | | | 0 | 0 |")
        b = w["baselines"]
        for bn, label in (("tx_count_topk", "baseline: top-k by transaction count"), ("distinct_counterparties_topk", "baseline: top-k by distinct counterparties"),
                          ("random_topk_seeded", "baseline: random top-k (seeded)")):
            o = b[bn]
            pk = b.get({"tx_count_topk": "tx_count_precision_at_k", "random_topk_seeded": "random_precision_at_k",
                        "distinct_counterparties_topk": "distinct_counterparties_precision_at_k"}[bn], {})
            a(f"| {label} | {o['precision']} | {o['recall']} | {o['f1']} | {o['flagged']:,} | {o['average_precision']} | {pk.get('100', '')} | {pk.get('1000', '')} | | | |")
        if "fitted_reference_isolated" in b:
            fr = b["fitted_reference_isolated"]
            a(f"| reference: logistic fit on calibration labels (eval only) | | | | | {fr['average_precision']} | {fr['precision_at_k']['100']} | {fr['precision_at_k']['1000']} | | | |")
        a("")
        a("Per bank (isolated):\n")
        a("| bank | accounts | laundering accounts | precision | recall | F1 | AP |\n|---|---|---|---|---|---|---|")
        for bk, pb in iso["per_bank"].items():
            a(f"| {bk} | {pb['accounts']:,} | {pb['positives']:,} | {pb['precision']} | {pb['recall']} | {pb['f1']} | {pb['average_precision']} |")
        a("")
        a("Detection per pattern type (account recall; attempts with ≥ 1 flagged account):\n")
        a("| pattern | accounts | isolated | staj_psi | naive | attempts | attempts hit (isolated / staj_psi / naive) |\n|---|---|---|---|---|---|---|")
        for pt in PATTERN_TYPES + ["unattributed"]:
            pi, pp, pn = (m[x]["per_pattern"][pt] for x in ("isolated", "staj_psi", "naive_raw_sharing"))
            att = "" if pt == "unattributed" else f"{pi['attempts']}"
            hits = "" if pt == "unattributed" else f"{pi['attempts_with_a_flagged_account']} / {pp['attempts_with_a_flagged_account']} / {pn['attempts_with_a_flagged_account']}"
            a(f"| {pt} | {pi['accounts']} | {pi['account_recall']} | {pp['account_recall']} | {pn['account_recall']} | {att} | {hits} |")
        a("")
        rd = m["staj_psi"]["radar"]
        ex = m["staj_psi"]["exposure"]
        a(f"Radar: tokens submitted per bank {rd['tokens_submitted']}; candidates submitted {rd['candidates_submitted']} out of {rd['candidates_in_band']} in the band; "
          f"refused {rd['refused'] or 'none'}. {len(rd['pairs'])} pair sessions, {ex['blinded_elements']:,} blinded group elements, **{ex['bytes_exchanged']:,} bytes**, "
          f"PSI wall time **{ex['psi_wall_seconds']} s** (parallel; {ex['psi_sequential_seconds']} s summed over pairs), plaintext tokens found in wire messages: {ex['plaintext_tokens_in_wire']}. "
          f"{rd['matched_tokens']} matched tokens, {rd['clusters_total']} clusters, **{rd['clusters_disclosed']} disclosed**, {rd['boosted_accounts']} accounts boosted "
          f"of which {rd['boosted_laundering']} laundering; newly flagged by the radar: {rd['newly_flagged_by_radar']} ({rd['newly_flagged_laundering']} laundering). "
          f"Disclosed cluster sizes {rd['disclosed_cluster_sizes']}, laundering share per disclosed cluster {rd['disclosed_cluster_laundering_share']}.\n")
        a(f"Reading: staj_psi AP {m['staj_psi']['average_precision']} is {_cmp(m['staj_psi']['average_precision'], iso['average_precision'])} isolated AP {iso['average_precision']}; "
          f"naive AP {m['naive_raw_sharing']['average_precision']} is {_cmp(m['naive_raw_sharing']['average_precision'], iso['average_precision'])} isolated; "
          f"the best simple baseline AP is {max(b['tx_count_topk']['average_precision'], b['distinct_counterparties_topk']['average_precision'])} "
          f"and random AP {b['random_topk_seeded']['average_precision']}.\n")
        fl = m["staj_psi"]["failures"]
        a("Worst false positives (staj_psi, highest score among non-laundering flagged accounts):\n")
        a("| account | bank | score | n_in | n_out | deg_in | deg_out | drain_24h | flow_ratio | rare_out_share | n_rare_cp | nbr |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
        for x in fl["worst_false_positives"]:
            a(f"| {x['client_id']} | {x['bank_id']} | {x['score']} | {x['n_in']} | {x['n_out']} | {x['deg_in']} | {x['deg_out']} | {x['drain_24h']} | {x['flow_ratio']} | {x['rare_out_share']} | {x['n_rare_cp']} | {x['nbr']} |")
        a("\nMissed laundering accounts with the most laundering transactions (staj_psi):\n")
        a("| account | bank | score | laundering tx | patterns | n_in | n_out | deg_in | deg_out | drain_24h | flow_ratio |\n|---|---|---|---|---|---|---|---|---|---|---|")
        for x in fl["missed_laundering_accounts_most_laundering_tx"]:
            a(f"| {x['client_id']} | {x['bank_id']} | {x['score']} | {x['laundering_tx']} | {', '.join(x['patterns'])} | {x['n_in']} | {x['n_out']} | {x['deg_in']} | {x['deg_out']} | {x['drain_24h']} | {x['flow_ratio']} |")
        a("")

    a("## 3. Simulated banks\n")
    a("| bank | canonical rows | accounts |\n|---|---|---|")
    for bk, v in ing["simulated_banks"].items():
        a(f"| {bk} | {v['rows']:,} | {v['accounts']:,} |")
    a(f"\nAttempts per pattern type in the patterns file: {ing['attempts_per_type']}.\n")
    a("## 4. Honest assessment\n")
    h, fu = r["windows"]["heldout"], r["windows"]["full"]
    hi, fi = h["modes"]["isolated"], fu["modes"]["isolated"]
    a(f"* **The bank-side engine is weak on AMLworld.** Held-out AP {hi['average_precision']} vs prevalence {h['baselines']['prevalence']} "
      f"(×{round(hi['average_precision'] / h['baselines']['prevalence'], 1)}); full-period AP {fi['average_precision']} vs prevalence {fu['baselines']['prevalence']} "
      f"(×{round(fi['average_precision'] / fu['baselines']['prevalence'], 1)}). F1 at the calibrated threshold: {hi['overall']['f1']} held-out, {fi['overall']['f1']} full. "
      f"The F1-optimal threshold flags {round(100 * h['flagged_share_isolated'], 1)} % (held-out) and {round(100 * fu['flagged_share_isolated'], 1)} % (full) of all accounts: "
      "**not a usable alert volume**. A one-line baseline, distinct counterparties, reaches AP "
      f"{h['baselines']['distinct_counterparties_topk']['average_precision']} (held-out) and {fu['baselines']['distinct_counterparties_topk']['average_precision']} (full), "
      f"i.e. it is {_cmp(h['baselines']['distinct_counterparties_topk']['average_precision'], hi['average_precision'])} the isolated engine on the held-out window and "
      f"{_cmp(fu['baselines']['distinct_counterparties_topk']['average_precision'], fi['average_precision'])} it on the full period.")
    if "fitted_reference_isolated" in h["baselines"]:
        fr = h["baselines"]["fitted_reference_isolated"]["average_precision"]
        a(f"* The evaluation-only logistic fit on the same features reaches held-out AP {fr} (×{round(fr / hi['average_precision'], 1)} the hand-set engine) and P@1000 "
          f"{h['baselines']['fitted_reference_isolated']['precision_at_k']['1000']}: the hand-set weights leave signal on the table, but even fitted these features stay far from a usable detector.")
    for wn, wv in (("held-out", h), ("full", fu)):
        rd = wv["modes"]["staj_psi"]["radar"]
        sp, iso_ = wv["modes"]["staj_psi"], wv["modes"]["isolated"]
        share = round(100 * rd["submitted_candidates_laundering_share"], 1)
        if rd["clusters_disclosed"]:
            a(f"* **Radar, {wn}**: {rd['clusters_disclosed']} disclosed clusters, {rd['boosted_laundering']} of {rd['boosted_accounts']} boosted accounts are laundering. "
              f"Ranking effect: AP {iso_['average_precision']} → {sp['average_precision']} ({'lifted' if sp['average_precision'] > iso_['average_precision'] else 'no lift'}), "
              f"P@100 {iso_['precision_at_k']['100']} → {sp['precision_at_k']['100']}; boosted-account precision {round(rd['boosted_laundering'] / rd['boosted_accounts'], 3)} "
              f"vs flag precision {iso_['overall']['precision']}. The radar "
              f"adds {rd['newly_flagged_by_radar']} new flags: the boosted accounts were already above the threshold, so precision/recall/F1 do not change. "
              f"{share} % of the submitted candidates are laundering accounts.")
        else:
            a(f"* **Radar, {wn}**: **no cluster was disclosed** ({rd['matched_tokens']} matched tokens, {rd['clusters_total']} clusters, none spanning ≥ 2 banks with ≥ 3 candidates); "
              f"staj_psi equals isolated. The token budget covers only the top {min(rd['candidates_submitted'].values())}–{max(rd['candidates_submitted'].values())} candidates per bank "
              f"(of {min(rd['candidates_in_band'].values()):,}–{max(rd['candidates_in_band'].values()):,} in the band), and only {share} % of the submitted candidates are laundering accounts.")
    nh, nf = h["modes"]["naive_raw_sharing"], fu["modes"]["naive_raw_sharing"]
    a(f"* **naive_raw_sharing is not an upper bound** with this engine: F1 {nh['overall']['f1']} vs isolated {hi['overall']['f1']} (held-out), {nf['overall']['f1']} vs {fi['overall']['f1']} (full). "
      "Pooling changes counterparty degrees (fewer tokens count as 'rare') and lets the neighbour pass see every account. It exposes "
      f"{nf['exposure']['raw_records_exposed']:,} rows ({nf['exposure']['bytes_exchanged_parquet']:,} bytes as parquet) over the full period; staj_psi exposes 0 raw records and "
      f"{fu['modes']['staj_psi']['exposure']['bytes_exchanged']:,} bytes of blinded group elements.")
    pp = {k: v["account_recall"] for k, v in hi["per_pattern"].items() if k in PATTERN_TYPES and v["account_recall"] is not None}
    best = sorted(pp, key=lambda k: -pp[k])[:2]
    worst = sorted(pp, key=lambda k: pp[k])[:3]
    a(f"* **Pattern types (held-out, isolated)**: best account recall {', '.join(f'{k} {pp[k]}' for k in best)}; worst {', '.join(f'{k} {pp[k]}' for k in worst)}. "
      "Pass-through members (e.g. of cycles) look like flow-through accounts and are found more often. The most-missed accounts are the patterns' endpoints: pure senders "
      "(n_in = 0, e.g. fan-out and scatter-gather sources) and pure receivers (n_out = 0, e.g. fan-in sinks), for which every flow-through feature is 0 (see the missed-accounts tables). "
      "Token matching on shared counterparties cannot link a chain across banks (consecutive hops share no counterparty); submitting the candidate's OWN account token would, "
      "but discloses more and was not evaluated.")
    wf = fu["modes"]["staj_psi"]["failures"]["worst_false_positives"]
    hi_nbr = sum(1 for x in wf if x["nbr"] >= 0.9)
    hi_drain = sum(1 for x in wf if x["drain_24h"] >= 0.95 and x["rare_out_share"] >= 0.95)
    a(f"* **Worst false positives** (full period): {hi_nbr} of the top {len(wf)} have a neighbour score ≥ 0.9 (groups of mutually high-scoring accounts inside one simulated bank "
      f"reinforce each other through the neighbour pass); {hi_drain} of {len(wf)} send ≥ 95 % of their largest inflow on within 24 h, ≥ 95 % of outflow to rare counterparties. "
      "Under these features they are indistinguishable from mules; that is a weakness of the features and of the second pass.")
    tl = r["ingest"]["tail_days_2022_09_11_to_18"]
    a(f"* The held-out window is unusual: 2022-09-10 is a partial day and 2022-09-11 … 09-18 hold only {tl['rows']:,} rows, {tl['laundering']:,} of them laundering (tail of attempts). "
      "Features see only rows inside the window, so held-out accounts have at most ~9 days of history.\n")
    a("## 4b. Deviations from the design brief (and why)\n")
    a("1. **Split**: the brief allows 'report on the later days'. Days 10–18 hold only "
      f"{h['source_transactions_non_self']:,} of {r['ingest']['source_rows'] - r['ingest']['self_transfers_dropped']:,} non-self transactions, so the full period is reported as well, "
      "labelled as containing the calibration days.")
    a("2. **PSI orchestration**: one `run_radar` over all 5 banks runs its 10 pair sessions sequentially "
      f"(~{round(fu['modes']['staj_psi']['exposure']['psi_sequential_seconds'])} s of PSI summed over pairs in the full window). Each pair therefore calls `run_radar` on that pair in its own process, and the "
      "coordinator re-clusters the union with `build_clusters` (identical connected components, unit-tested on a 3-bank example). Token budget "
      f"{r['radar_config']['max_tokens_per_bank']} per bank, kept below `radar.psi.dh_psi.PARALLEL_MIN` so the per-pair processes do not start nested process pools. "
      "Note: `radar/psi/dh_psi.py` was changed by another engineer during this work (256-bit secret exponents, Jacobi-symbol subgroup check, optional process pool); "
      "the numbers here come from the version on disk at generation time, and the per-run benchmark above is the measured cost.")
    a(f"3. **Accounts**: the source has {r['ingest']['accounts_in_source']:,} accounts; {r['ingest']['accounts_in_source'] - r['ingest']['accounts']:,} of them appear only in self-transfers, "
      f"which are dropped, leaving {r['ingest']['accounts']:,}. Laundering accounts lost that way: {r['ingest']['accounts_labelled_only_via_self_transfers']}.")
    a(f"4. **Patterns file** lines matched to {r['ingest']['pattern_lines_matched_to_transactions']:,} laundering transactions; laundering accounts outside the file are reported as `unattributed`.")
    a("5. **Post-match lag/retention exchange** ('same hand global') is not used on IBM; it would add disclosure without a tested benefit here.\n")
    a("## 5. Limitations (exact)\n")
    a("1. Synthetic data; generic AMLworld laundering patterns, **not** Czech mule schemes; results say nothing about real portfolios.")
    a("2. FX is a hand-typed **placeholder** table (approximate public rates); it differs from the dataset's own implied rates (§6). Amounts enter only ratios and log-materiality.")
    a("3. Weights are hand-set; only the flag threshold was chosen on calibration labels (days 1–9). The engine design (D1/D5 features) predates this run; the payment-format/label crosstab was "
      "seen during data exploration and payment format is deliberately NOT a feature.")
    a("4. The simulated bank split is a hash of IBM bank ids; real banks differ in size and customer mix.")
    fr_ = r["windows"]["full"]["modes"]["staj_psi"]["radar"]
    a(f"5. The radar is limited by DH-PSI cost and the token budget: {min(fr_['candidates_submitted'].values())}–{max(fr_['candidates_submitted'].values())} candidates per bank enter PSI "
      f"(full period) out of {min(fr_['candidates_in_band'].values()):,}–{max(fr_['candidates_in_band'].values()):,} in the band, so most of the band never enters PSI. "
      "Pair sessions run in parallel processes on one laptop; nodes are not separate machines.")
    a("6. Security model is semi-honest. A malicious bank could submit arbitrary tokens to probe whether an account is a candidate elsewhere, inject fake tokens to create or enlarge "
      "clusters (poisoning), or abort after learning its result. Mitigations in this code: Guards (minimum set size, max tokens, rate limit, share of unscored tokens), disclosure only "
      "for ≥ 2 banks and ≥ 3 candidates, only keyed token ids reach the coordinator, humans decide. Not mitigated: a bank that scores fake accounts to pass the 'scored' check, collusion "
      "of two banks, traffic analysis by the coordinator. PSI minimises disclosure; it is **not a legal basis** for sharing.")
    a("7. `naive_raw_sharing` is a privacy-exposure reference, not a detection upper bound.\n")
    a("## 6. Placeholder FX vs rates implied by the dataset\n")
    a("| currency | placeholder USD/unit | dataset-implied median | relative deviation | rows |\n|---|---|---|---|---|")
    for c, v in r["fx_placeholder_check"].items():
        a(f"| {c} | {v['placeholder']} | {v['dataset_implied_median']} | {v['relative_deviation']} | {v['n_rows']} |")
    a("\n## 7. Reproduce\n")
    a("```bash\ncd staj\nPYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python -m pytest tests/unit/test_ibm.py -q\n"
      "PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python -m eval.ibm_eval   # writes eval/out/ibm_eval.json and docs/IBM_EVAL.md\n```\n")
    a(f"Total runtime of the generating run: {r['total_seconds']} s. Deterministic except wall times (PSI exponents are fresh per session; matches do not depend on them).\n")
    return "\n".join(L)


if __name__ == "__main__":
    main(*sys.argv[1:])
