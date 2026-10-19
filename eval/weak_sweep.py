"""Privacy-cost curve of the weak-evidence radar: python -m eval.weak_sweep seed [seed ...]  -> eval/out/weak_sweep_<tag>.json

For every weak_top_frac (the share of each bank's clients exported as weak candidates) it reports stealth recall, TP/FP/FN at the operating point,
the number of exported tokens/candidates, match rows seen by the coordinator and disclosed clusters that contain a non-mule candidate.
Variants: 'baseline' = master-prompt behaviour (frac 0, no significance); 'sig_only' = frac 0 with significance; 'weak_<f>' = frac f with significance.
"""
from __future__ import annotations

import copy
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import polars as pl

from eval.redteam_eval import _flag, apply_clusters, load_world, run_banks, run_radar, to_bank_node
from node.pipeline import load_config
from radar.guards import Guards

FRACS = [0.0, 0.05, 0.10, 0.20, 0.40]


def one(path: str, frac: float, significance: bool) -> dict:
    cfg = copy.deepcopy(load_config())
    cfg["token_export"]["weak_top_frac"] = frac
    cfg["radar"]["use_significance"] = significance
    tx, cl, lab = load_world(path)
    res = run_banks(tx, cl, cfg)
    rc = cfg["radar"]
    radar = run_radar([to_bank_node(r) for r in res.values()], Guards(cfg["radar_guards"]), epoch_key=b"epoch-sweep",
                      min_significance=rc["min_significance"] if significance else None, significance_cap=rc["significance_cap"])
    tau = cfg["cases"]["fp_max_priority"]
    cases_iso = {c.client_id: c for r in res.values() for c in r.cases}
    cases_psi = {c.client_id: c for r in res.values() for c in apply_clusters(r, radar.clusters)}
    mules = set(lab.filter(pl.col("label") == "mule")["client_id"])
    stealth = set(lab.filter(pl.col("scheme") == "same_hand_stealth")["client_id"])
    allc = set(lab["client_id"])
    ghost = set(lab.filter(pl.col("scheme") == "ghost_ring")["client_id"])
    original = mules - ghost

    def m(cases):
        flagged = {cid for cid, c in cases.items() if cid in allc and _flag(c, tau)}
        return {"tp": len(flagged & mules), "fp": len(flagged - mules), "fn": len(mules - flagged), "stealth_recall": round(len(flagged & stealth) / len(stealth), 4),
                "ghost_recall": round(len(flagged & ghost) / len(ghost), 4), "original_recall": round(len(flagged & original) / len(original), 4)}

    ref_label = {}
    for b, r in res.items():
        for ref, cid in r.ref_to_client.items():
            ref_label[(b, ref)] = cid in mules
    disclosed = [c for c in radar.clusters if c["disclosed"]]
    return {"isolated": m(cases_iso), "staj_psi": m(cases_psi),
            "exported_tokens": sum(len(r.candidates) for r in res.values()), "exported_candidates": sum(len({c["cand_ref"] for c in r.candidates}) for r in res.values()),
            "n_clients": sum(r.features.height for r in res.values()), "match_rows": radar.exposure["match_rows_to_coordinator"],
            "blinded_elements": radar.exposure["blinded_elements"], "bytes": radar.exposure["bytes_exchanged"],
            "clusters_disclosed": len(disclosed), "disclosed_candidates": sum(len(c["candidates"]) for c in disclosed),
            "disclosed_candidates_non_mule": sum(1 for c in disclosed for k in c["candidates"] if not ref_label.get(tuple(k), False)),
            "clusters_with_non_mule": sum(1 for c in disclosed if any(not ref_label.get(tuple(k), False) for k in c["candidates"]))}


def variants() -> list[tuple[str, float, bool]]:
    return [("baseline", 0.0, False), ("sig_only", 0.0, True)] + [(f"weak_{f:.2f}", f, True) for f in FRACS if f > 0]


def seed_job(seed: int) -> tuple[int, dict]:
    path = f"data/redteam/seed{seed}"
    return seed, {name: one(path, f, sig) for name, f, sig in variants()}


if __name__ == "__main__":
    seeds = [int(a) for a in sys.argv[1:]]
    tag = "_".join(str(s) for s in seeds)
    out = {}
    with ProcessPoolExecutor(max_workers=min(len(seeds), 6)) as ex:
        for seed, res in ex.map(seed_job, seeds):
            out[str(seed)] = res
            print(seed, {k: (v["staj_psi"]["stealth_recall"], v["staj_psi"]["fp"], v["exported_tokens"]) for k, v in res.items()}, flush=True)
    json.dump(out, open(f"eval/out/weak_sweep_{tag}.json", "w"), indent=1)
