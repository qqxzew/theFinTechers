"""Metrics for the collector evaluation (labels live here and in collector_eval only). Input: replay JSON of one world + its hidden labels.

Definitions: eval/prereg_collector.md section 3. 'flag' for (a), (b), (e) = existing operating point; for (c), (d) = flag_by_raise (operating
point OR raised by the collector expansion). Stealth set = low-and-slow ring mules whose local probability under (a) at month end is < min_prob.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

MIN_PROB = 0.05
CENSOR_DAY = 32
RING_SCHEME = "low_slow_ring"


def method_sets(rec: dict, method: str, p_inst: str, how: str | None = None) -> set[str]:
    if method in ("a", "b", "e"):
        return set(rec[method])
    if method == "c":
        return set(rec["c"][p_inst]["flag_by_raise"])
    if method in ("d", "d2"):
        return set(rec[method][p_inst]["flag_by_raise"])
    raise KeyError(method)


def _czk_before(flows: pl.DataFrame, clients: set[str], day: int | None, inclusive: bool = False) -> float:
    """CZK forwarded by the given ring mules before day `day` (original column) or up to and including the end of the flag day (inclusive=True)."""
    f = flows.filter(pl.col("client_id").is_in(list(clients)))
    if day is not None:
        f = f.filter(pl.col("ts_out") < datetime(2026, 7, day + (1 if inclusive else 0), tzinfo=UTC))
    return float(f["amount_out"].sum()) if f.height else 0.0


def world_metrics(replay: dict, path: str, p_inst: str, methods: tuple[str, ...] = ("a", "b", "c", "e"), cumulative: bool = False) -> dict:
    """cumulative=True (Amendment 2, P1): a raised/flagged customer stays in the queue, so the flag set at day t is the union of the days <= t."""
    p = Path(path)
    lab = pl.read_parquet(p / "labels.parquet")
    meta = json.loads((p / "meta.json").read_text(encoding="utf-8"))
    flows = pl.read_parquet(p / "ring_flows.parquet") if (p / "ring_flows.parquet").exists() else None
    mules = set(lab.filter(pl.col("label") == "mule")["client_id"])
    nonmule = set(lab.filter(pl.col("label").is_in(["honest", "background"]))["client_id"])
    ring_rows = lab.filter(pl.col("scheme") == RING_SCHEME)
    rings = {int(i): set(g["client_id"]) for (i,), g in ring_rows.group_by("instance")}
    ring_mules = set().union(*rings.values()) if rings else set()
    times = sorted(int(t) for t in replay["times"])
    cache: dict[tuple[str, int], set[str]] = {}

    def sets_at(rec_t: dict, m: str, t: int) -> set[str]:
        if not cumulative:
            return method_sets(rec_t, m, p_inst)
        if (m, t) not in cache:
            cache[(m, t)] = set().union(*(method_sets(replay["times"][str(u)], m, p_inst) for u in times if u <= t))
        return cache[(m, t)]
    final = replay["times"][str(max(times))]
    probs_a = final["probs_a"] or {}
    stealth = {m for m in ring_mules if probs_a.get(m, 0.0) < MIN_PROB}
    fa = sets_at(final, "a", max(times))
    out: dict = {"world": path, "hub_mode": meta["hub_mode"], "script_jitter": meta["script_jitter"], "crime_free": meta["crime_free"],
                 "n_ring_mules": len(ring_mules), "n_stealth": len(stealth), "methods": {}}
    e_final = sets_at(final, "e", max(times))
    for m in methods:
        fl = sets_at(final, m, max(times))
        raised = (fl - fa)
        tp = len(fl & mules)
        rec = {
            "n_flagged": len(fl),
            "stealth_recall": (len(fl & stealth) / len(stealth)) if stealth else None,
            "stealth_hit": len(fl & stealth), "n_stealth": len(stealth),
            "recall": tp / len(mules) if mules else None,
            "precision": tp / len(fl) if fl else None,
            "honest_raised": len(raised & nonmule),
            "network_only_errors": len(raised & nonmule),
            "local_false_flags_a": len(fa & nonmule),
            "reach_of_e": (len(fl & mules & e_final) / len(mules & e_final)) if (mules & e_final) else None,
        }
        # time evaluation
        first: dict[int, int | None] = {}
        czk: dict[int, float] = {}
        czk_incl: dict[int, float] = {}
        per_mule: dict[str, dict] = {}
        for ring, ms in rings.items():
            ft = next((t for t in times if sets_at(replay["times"][str(t)], m, t) & ms), None)
            first[ring] = ft
            czk[ring] = _czk_before(flows, ms, ft) if flows is not None else 0.0
            czk_incl[ring] = _czk_before(flows, ms, ft, True) if flows is not None else 0.0
        for mid in ring_mules:
            ft = next((t for t in times if mid in sets_at(replay["times"][str(t)], m, t)), None)
            per_mule[mid] = {"first_day": ft, "czk_before": _czk_before(flows, {mid}, ft) if flows is not None else 0.0}
        rec["first_flag_day_by_ring"] = {str(k): v for k, v in first.items()}
        rec["czk_before_first_flag_by_ring"] = {str(k): v for k, v in czk.items()}
        rec["czk_through_flag_day_by_ring"] = {str(k): v for k, v in czk_incl.items()}
        rec["per_mule"] = per_mule
        out["methods"][m] = rec
    fc = final["c"][p_inst]
    out["collector"] = {"n_flagged_buckets": fc["n_flagged_buckets"], "n_suppressed_buckets": fc["n_suppressed_buckets"], "n_tested": fc["n_tested"]}
    out["collector_by_day"] = {t: {k: replay["times"][t]["c"][p_inst][k] for k in ("n_flagged_buckets", "n_suppressed_buckets", "n_tested")}
                               for t in replay["times"]}
    out["bytes_collector_per_bank_per_month"] = replay["bytes_collector_per_bank_per_month"]
    out["bytes_psi_b_total"] = final["psi_bytes_b"]
    return out


def bootstrap_median(values: list[float], n: int = 2000, seed: int = 20261020) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    v = np.asarray(values, float)
    if len(v) == 0:
        return (float("nan"),) * 3
    meds = np.median(v[rng.integers(0, len(v), size=(n, len(v)))], axis=1)
    return float(np.median(v)), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))
