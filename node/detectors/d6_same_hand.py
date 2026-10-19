"""D6 Same hand (local): groups of own clients that share low-degree exits AND have a similar inflow->outflow lag, retention ratio
and active hours. Scored against a shuffled baseline (the same similarity test after permuting lag/retention/hours across clients).
Source: own design (operator-fingerprint idea from public descriptions of mule-herding; no external citation).
Group function, not per-client: detect_group(rows, ctx) -> list[Signal].
"""
from __future__ import annotations

import math
import random

from common.schemas import Signal

DETECTOR_ID = "D6"
VERSION = "1"
SOURCE = "own design"


def _cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


def _similar(a: dict, b: dict, cfg: dict) -> bool:
    return (abs(a["lag_median_h"] - b["lag_median_h"]) <= cfg["lag_tol_h"] and abs(a["retention_median"] - b["retention_median"]) <= cfg["ret_tol"]
            and _cos(a["hour_hist"], b["hour_hist"]) >= cfg["hour_cos"])


def _pairs(rows: list[dict], cfg: dict, need_token: bool = True) -> list[tuple[int, int]]:
    out = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if need_token and not set(rows[i]["exit_tokens_low"]) & set(rows[j]["exit_tokens_low"]):
                continue
            if _similar(rows[i], rows[j], cfg):
                out.append((i, j))
    return out


def _components(n: int, pairs: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        parent[find(a)] = find(b)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def detect_group(rows: list[dict], ctx: dict) -> list[Signal]:
    cfg = ctx["cfg"][DETECTOR_ID]
    cand = [r for r in rows if r.get("n_cycles", 0) >= cfg["min_cycles"] and r.get("lag_median_h") is not None
            and r.get("retention_median") is not None and r["retention_median"] >= cfg.get("min_ret", 0.0)
            and r.get("exit_tokens_low") and r.get("hour_hist")
            and sum(sorted(r["hour_hist"], reverse=True)[:4]) >= cfg.get("min_hour_conc", 0.0)]
    if len(cand) < cfg["min_group"]:
        return []
    real = _pairs(cand, cfg)
    if not real:
        return []
    rng = random.Random(cfg.get("seed", 0))
    base = []
    for _ in range(cfg.get("baseline_runs", 20)):
        perm = list(range(len(cand)))
        rng.shuffle(perm)
        shuffled = [{**cand[i], "lag_median_h": cand[perm[i]]["lag_median_h"], "retention_median": cand[perm[i]]["retention_median"],
                     "hour_hist": cand[perm[i]]["hour_hist"]} for i in range(len(cand))]
        base.append(len(_pairs(shuffled, cfg)))
    baseline = sum(base) / len(base)
    lift = len(real) / (baseline + 1.0)
    if lift < cfg["min_lift"]:
        return []
    sigs = []
    for comp in _components(len(cand), real):
        if len(comp) < cfg["min_group"]:
            continue
        score = min(1.0, 0.5 + 0.1 * (len(comp) - cfg["min_group"]) + 0.1 * min(3.0, math.log(lift)))
        for i in comp:
            sigs.append(Signal(signal_id=f"D6:{cand[i]['client_id']}", detector_id=DETECTOR_ID, version=VERSION,
                               client_id=cand[i]["client_id"], score=round(score, 4),
                               evidence=["exit_tokens_low", "lag_median_h", "retention_median", "hour_hist",
                                         f"group_size={len(comp)}", f"lift_vs_shuffled={lift:.1f}"],
                               explanation_template_key="d6_same_hand", source=SOURCE))
    return sigs
