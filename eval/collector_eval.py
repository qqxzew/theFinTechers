"""Replay of one collector world by day: methods (a) bank alone, (b) current radar, (c) + collector WHERE, (e) central register (upper bound).
((d) WHERE+HOW is added in P1.) Writes flagged sets per replay day; metrics are computed by eval/collector_metrics.py from this file and the labels.

Evaluation uses plain sums (justified by tests/unit/test_secagg.py: masked sum == plain sum) and a plaintext-equivalent intersection instead of
DH-PSI (justified by tests/property/test_psi.py and tests/unit/test_plain_psi.py). Only this module and collector_metrics read labels.
"""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

import radar.sessions as rs
from collector.stats import where_test
from eval.redteam_eval import _flag, load_world, to_bank_node
from node.expansion import expand_where
from node.pipeline import NodeResult, apply_clusters, load_config, run_node
from node.signatures import EVAL_DAY0, HIST_START, N_BUCKETS, bucket_index, build_signatures, where_vectors
from radar.guards import Guards
from radar.sessions import BankNode, run_radar

KEY = b"consortium-key-eval"          # shared by the banks, never by the collector
REPLAY_T = list(range(2, 31, 2)) + [31]   # 31 = end of month (all data)
WINDOW = 30
P_INST_VARIANTS = (30, 50, 80)
JULY1 = datetime(2026, 7, 1, tzinfo=UTC)


class _Msg(list):
    inter: set


class PlainPsiParty:
    """Plaintext-equivalent stand-in for radar.psi.dh_psi.PsiParty (same interface and message sizes, no exponentiation)."""

    def __init__(self, tokens, domain: str = "") -> None:
        self.tokens = list(tokens)

    def blind(self):
        m = _Msg(["0" * 512] * len(self.tokens))
        m.inter = set(self.tokens)
        return m

    def respond(self, m1, cardinality_only: bool = False):
        inter = set(m1.inter) & set(self.tokens)
        m2, m3 = _Msg(["0" * 512] * len(m1)), _Msg(["0" * 512] * len(self.tokens))
        m2.inter = m3.inter = inter
        return m2, m3

    def finish(self, m2, m3, cardinality_only: bool = False):
        back = _Msg(["0" * 512] * len(m3))
        back.inter = m2.inter
        return sorted(m2.inter), back

    def learn_from_return(self, back):
        return sorted(back.inter)


def use_plain_psi() -> None:
    rs.PsiParty = PlainPsiParty


def flag_set(cases: dict, tau: int) -> set[str]:
    return {cid for cid, c in cases.items() if _flag(c, tau)}


def extend_node(r: NodeResult, raised: set[str], secret: bytes) -> tuple[NodeResult, BankNode]:
    """Raised customers enter the queue and export their low-degree exit tokens to the PSI radar (one round)."""
    from node.tokens.export import cand_ref
    r2 = copy.copy(r)
    r2.candidates = list(r.candidates)
    r2.ref_to_client = dict(r.ref_to_client)
    r2.client_meta = dict(r.client_meta)
    have = {c["cand_ref"] for c in r.candidates}
    for cid in sorted(raised):
        f = r.feat_by_id.get(cid)
        if not f:
            continue
        ref = cand_ref(secret, cid)
        if ref in have:
            continue
        toks = f.get("exit_tokens_low") or []
        for t in toks:
            r2.candidates.append({"token": t, "cand_ref": ref, "score": 0.05, "kind": "exit", "band": "raised"})
        if toks:
            r2.ref_to_client[ref] = cid
            r2.client_meta[cid] = r.metas.get(cid) or _meta(r, cid)
    return r2, to_bank_node(r2)


def _meta(r: NodeResult, cid: str) -> dict:
    f = r.feat_by_id[cid]
    return {"aml_risk": f["aml_risk"] or "low", "pep": bool(f["pep"]), "high_risk_country": False,
            "days_since_contract": f["days_since_contract"] if f["days_since_contract"] is not None else 9999,
            "contract_form": f["contract_form"], "in_cluster": False, "big_amount": f["big_in_amount"] or f["max_single_in"] or 0.0, "cluster_id": None}


def _radar(nodes: list[BankNode], cfg: dict):
    rcfg = cfg.get("radar", {})
    return run_radar(nodes, Guards(cfg["radar_guards"]), epoch_key=b"epoch-eval", now=datetime(2026, 7, 31, tzinfo=UTC),
                     min_significance=rcfg.get("min_significance") if rcfg.get("use_significance") else None,
                     significance_cap=rcfg.get("significance_cap", 8.0))


def replay_world(path: str, out_json: str | None = None, times: list[int] | None = None, p_inst_variants: tuple[int, ...] = P_INST_VARIANTS,
                 q: float = 0.01) -> dict:
    use_plain_psi()
    cfg = load_config()
    tau = cfg["cases"]["fp_max_priority"]
    tx, cl, _ = load_world(path, with_labels=False)
    registry = json.loads((Path(path) / "public_registry.json").read_text(encoding="utf-8"))
    allow = {bucket_index(KEY, t) for t in registry}
    banks = sorted(cl["bank_id"].unique().to_list())
    sigs = {b: build_signatures(b, tx.filter(pl.col("bank_id") == b), cl.filter(pl.col("bank_id") == b), KEY, cfg["features"]["popular_min"]) for b in banks}
    own = {b: {c: c for c in cl.filter(pl.col("bank_id") == b)["client_id"].to_list()} for b in banks}
    tx_month = tx.filter(pl.col("ts") >= JULY1)
    out: dict = {"world": path, "banks": banks, "times": {}, "variants": list(p_inst_variants)}
    for t in times or REPLAY_T:
        day = EVAL_DAY0 + t - 1
        cutoff = HIST_START + timedelta(days=day + 1)
        asof = cutoff - timedelta(seconds=1)
        txc = tx_month.filter(pl.col("ts") < cutoff)
        iso: dict[str, NodeResult] = {}
        for b in banks:
            iso[b] = run_node(b, txc.filter(pl.col("bank_id") == b), cl.filter(pl.col("bank_id") == b), cfg, bank_secret=f"secret-{b}".encode(), asof=asof)
        cases_a = {c.client_id: c for r in iso.values() for c in r.cases}
        probs_a = {cid: p for r in iso.values() for cid, p in r.probs.items()}
        radar_b = _radar([to_bank_node(r) for r in iso.values()], cfg)
        cases_b = {c.client_id: c for b, r in iso.items() for c in apply_clusters(r, radar_b.clusters)}
        pooled = run_node("ALL", txc, cl, cfg, bank_secret=b"secret-all", asof=asof)
        cases_e = {c.client_id: c for c in pooled.cases}
        # ---- collector WHERE: plain sums of the bank vectors ----
        vecs = {b: where_vectors(sigs[b], day, WINDOW) for b in banks}
        tot = {k: sum(vecs[b][k].astype(np.uint64) for b in banks) for k in ("P", "K", "I")}
        rec = {"a": sorted(flag_set(cases_a, tau)), "b": sorted(flag_set(cases_b, tau)), "e": sorted(flag_set(cases_e, tau)),
               "probs_a": {k: round(v, 4) for k, v in probs_a.items()} if t == 31 else None,
               "psi_bytes_b": radar_b.exposure["bytes_exchanged"], "c": {}}
        for pi in p_inst_variants:
            wr = where_test(tot["P"], tot["K"], tot["I"], q=q, p_inst=pi, allowlist_buckets=allow)
            raised: dict[str, dict] = {}
            per_bank_raised: dict[str, set[str]] = {}
            for b in banks:
                ex = expand_where(sigs[b], wr.flagged, day, WINDOW, own[b], KEY)
                per_bank_raised[b] = set(ex)
                raised.update(ex)
            nodes = []
            cases_c: dict = {}
            ext = {}
            for b in banks:
                r2, bn = extend_node(iso[b], per_bank_raised[b], f"secret-{b}".encode())
                ext[b] = r2
                nodes.append(bn)
            radar_c = _radar(nodes, cfg)
            for b in banks:
                for c in apply_clusters(ext[b], radar_c.clusters):
                    cases_c[c.client_id] = c
            by_prio = flag_set(cases_c, tau)
            rec["c"][str(pi)] = {"flag_by_priority": sorted(by_prio), "flag_by_raise": sorted(by_prio | set(raised)), "raised": sorted(raised),
                                 "evidence": {k: raised[k] for k in sorted(raised)[:50]},
                                 "n_tested": wr.n_tested, "p0": wr.p0, "n_flagged_buckets": len(wr.flagged), "n_suppressed_buckets": len(wr.suppressed),
                                 "suppressed": wr.suppressed[:20], "flagged": wr.flagged[:50]}
        out["times"][str(t)] = rec
    # bytes per bank for the collector: P, K, I vectors of 2^18 uint32 per round, one round per day of the evaluation month
    out["bytes_collector_per_bank_per_month"] = 3 * N_BUCKETS * 4 * 31
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps(out), encoding="utf-8")
    return out
