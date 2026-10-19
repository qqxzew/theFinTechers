"""Evaluation on red-team data. The ONLY place (besides tests) that reads labels.parquet. Metrics are computed by code, never typed.

Modes: isolated (no sharing) | staj_psi (blinded exit-token matching) | naive_raw_sharing (all raw data pooled: upper bound).
"""
from __future__ import annotations

import collections
from datetime import UTC, datetime

import polars as pl

from audit.log import AuditLog
from node.pipeline import NodeResult, apply_clusters, load_config, run_node
from radar.guards import Guards
from radar.sessions import BankNode, run_radar


def load_world(path: str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    tx = pl.read_parquet(f"{path}/tx.parquet")
    cl = pl.read_parquet(f"{path}/clients.parquet").with_columns(pl.col("contract_date").dt.replace_time_zone(None))
    lab = pl.read_parquet(f"{path}/labels.parquet")
    return tx, cl, lab


def run_banks(tx: pl.DataFrame, cl: pl.DataFrame, cfg: dict, **kw) -> dict[str, NodeResult]:
    out = {}
    for b in sorted(cl["bank_id"].unique().to_list()):
        out[b] = run_node(b, tx.filter(pl.col("bank_id") == b), cl.filter(pl.col("bank_id") == b), cfg,
                          bank_secret=f"secret-{b}".encode(), **kw)
    return out


def to_bank_node(r: NodeResult) -> BankNode:
    feat = {row["client_id"]: row for row in r.features.select(["client_id", "lag_median_h", "retention_median"]).to_dicts()}
    stats = {ref: {k: feat[cid][k] for k in ("lag_median_h", "retention_median")} for ref, cid in r.ref_to_client.items()}
    rarity = {c["token"]: 1.0 / max(1, r.degree.get(c["token"], 1)) for c in r.candidates}
    return BankNode(r.bank_id, r.candidates, rarity, stats)


def _flag(c, min_priority: int) -> bool:
    return c.triage.value == "REVIEW" and c.route == "mule_review" and c.priority >= min_priority


def _metrics(cases: dict[str, object], labels: pl.DataFrame, clients_subset: set[str] | None = None, min_priority: int = 0) -> dict:
    lab = labels if clients_subset is None else labels.filter(pl.col("client_id").is_in(list(clients_subset)))
    mule_ids = set(lab.filter(pl.col("label") == "mule")["client_id"])
    all_ids = set(lab["client_id"])
    flagged = {cid for cid, c in cases.items() if cid in all_ids and _flag(c, min_priority)}
    tp, fp, fn = len(flagged & mule_ids), len(flagged - mule_ids), len(mule_ids - flagged)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
            "n_mules": len(mule_ids), "n_accounts": len(all_ids)}


def _breakdown(cases: dict[str, object], labels: pl.DataFrame, min_priority: int = 0) -> dict:
    by_scheme: dict[str, dict] = {}
    for (scheme, persona, label), g in labels.group_by(["scheme", "persona", "label"]):
        ids = g["client_id"].to_list()
        n = len(ids)
        review = sum(1 for i in ids if i in cases and _flag(cases[i], min_priority))
        victim = sum(1 for i in ids if i in cases and cases[i].route == "victim_protection")
        key = persona if persona else scheme
        by_scheme[f"{label}/{key}"] = {"n": n, "flagged_as_mule_case": review, "routed_to_victim_protection": victim,
                                      "rate": round(review / n, 4) if label != "victim" else round(victim / n, 4)}
    return by_scheme


def _worst(cases: dict[str, object], labels: pl.DataFrame, k: int = 8, min_priority: int = 0) -> dict:
    lab = {r["client_id"]: r for r in labels.to_dicts()}
    fps = [c for cid, c in cases.items() if lab[cid]["label"] != "mule" and _flag(c, min_priority)] if cases else []
    fps = sorted((c for c in fps if lab[c.client_id]["label"] in ("honest", "background")), key=lambda c: -c.priority)[:k]
    fns = []
    for cid, row in lab.items():
        if row["label"] == "mule":
            c = cases.get(cid)
            if c is None or not _flag(c, min_priority):
                fns.append((cid, row, c))
    def fmt(c, row):
        return {"client_id": c.client_id if c else row["client_id"], "label": row["label"], "scheme": row["scheme"], "persona": row["persona"],
                "priority": c.priority if c else None, "triage": c.triage.value if c else "no case",
                "signals": [s.signal_id for s in c.signals] if c else [], "exculpatory": [s.signal_id for s in c.exculpatory] if c else [],
                "reasons": c.triage_reasons[:4] if c else ["no signal fired"]}
    return {"worst_false_positives": [fmt(c, lab[c.client_id]) for c in fps], "false_negatives": [fmt(c, row) for _, row, c in fns[:k]]}


def evaluate(path: str, cfg: dict | None = None, audit_path: str | None = None) -> dict:
    cfg = cfg or load_config()
    tau = cfg["cases"]["fp_max_priority"]
    tx, cl, lab = load_world(path)
    t0 = datetime.now(UTC)
    iso = run_banks(tx, cl, cfg)
    cases_iso = {c.client_id: c for r in iso.values() for c in r.cases}
    audit = AuditLog(audit_path) if audit_path else None
    guards = Guards(cfg["radar_guards"])
    radar = run_radar([to_bank_node(r) for r in iso.values()], guards, epoch_key=b"epoch-eval", audit=audit, now=t0)
    cases_psi: dict[str, object] = {}
    for b, r in iso.items():
        for c in apply_clusters(r, radar.clusters):
            cases_psi[c.client_id] = c
    merged = run_node("ALL", tx, cl, cfg, bank_secret=b"secret-all")
    cases_naive = {c.client_id: c for c in merged.cases}
    sub = {b: set(cl.filter(pl.col("bank_id") == b)["client_id"]) for b in iso}
    per_bank = {b: _metrics({c.client_id: c for c in r.cases}, lab, sub[b], tau) for b, r in iso.items()}
    per_bank_any = {b: _metrics({c.client_id: c for c in r.cases}, lab, sub[b]) for b, r in iso.items()}
    out = {
        "world": path, "synthetic": True, "n_tx": tx.height, "n_clients": cl.height,
        "modes": {
            "isolated": {"overall": _metrics(cases_iso, lab, None, tau), "overall_any_priority": _metrics(cases_iso, lab), "per_bank": per_bank, "per_bank_any_priority": per_bank_any,
                         "best_single_bank_f1": max(m["f1"] for m in per_bank.values()),
                         "mean_bank_f1": round(sum(m["f1"] for m in per_bank.values()) / len(per_bank), 4),
                         "exposure": {"raw_records_exposed": 0, "bytes_exchanged": 0}},
            "staj_psi": {"overall": _metrics(cases_psi, lab, None, tau), "overall_any_priority": _metrics(cases_psi, lab), "exposure": radar.exposure,
                         "clusters_disclosed": sum(1 for c in radar.clusters if c["disclosed"]), "refused": radar.refused},
            "naive_raw_sharing": {"overall": _metrics(cases_naive, lab, None, tau), "overall_any_priority": _metrics(cases_naive, lab),
                                  "exposure": {"raw_records_exposed": tx.height, "bytes_exchanged": int(tx.estimated_size())}},
        },
        "operating_point": {"definition": f"case triage REVIEW, route mule_review and priority >= {tau}", "min_priority": tau},
        "breakdown_isolated": _breakdown(cases_iso, lab, tau),
        "breakdown_staj_psi": _breakdown(cases_psi, lab, tau),
        "breakdown_staj_psi_any_priority": _breakdown(cases_psi, lab),
        "failures_staj_psi": _worst(cases_psi, lab, 8, tau),
        "clusters": [{k: c[k] for k in ("cluster_id", "banks", "score", "disclosed", "same_hand_global", "lag_ret_concentration")} | {"n_candidates": len(c["candidates"])}
                     for c in radar.clusters if c["disclosed"]],
    }
    # ablations (same world, same seed)
    abl = {}
    no_inn = run_banks(tx, cl, cfg, use_innocence=False)
    abl["without_innocence_layer"] = _metrics({c.client_id: c for r in no_inn.values() for c in r.cases}, lab, None, tau)
    abl["without_radar"] = out["modes"]["isolated"]["overall"]
    no_d = run_banks(tx, cl, cfg, detectors_off=("D6", "D7"))
    abl["without_D6_D7"] = _metrics({c.client_id: c for r in no_d.values() for c in r.cases}, lab, None, tau)
    out["ablations"] = abl
    # ground-truth cluster quality: do disclosed clusters contain only mules?
    ref_lab = {}
    for b, r in iso.items():
        for ref, cid in r.ref_to_client.items():
            ref_lab[(b, ref)] = lab.filter(pl.col("client_id") == cid)["label"][0]
    purity = collections.Counter()
    for c in radar.clusters:
        if c["disclosed"]:
            for key in c["candidates"]:
                purity[ref_lab.get(key, "?")] += 1
    out["disclosed_cluster_candidate_labels"] = dict(purity)
    return out
