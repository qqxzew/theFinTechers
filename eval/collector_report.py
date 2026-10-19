"""Aggregate replay JSONs over seeds/cells: tuning rule, success criteria S1-S5 (prereg section 7), markdown tables.

python -m eval.collector_report tune   --split dev
python -m eval.collector_report report --split dev|test --p-inst 50 --methods a b c
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from eval.collector_metrics import CENSOR_DAY, world_metrics
from eval.collector_run import CELLS, cell_name

OUT = Path("eval/out/collector")
RING_CELLS = [cell_name(h, j) for h, j in CELLS if h != "crimefree"]


def load(split: str, p_inst: str, methods: tuple[str, ...], cumulative: bool = False) -> dict[str, dict[int, dict]]:
    res: dict[str, dict[int, dict]] = defaultdict(dict)
    for f in sorted((OUT / split).glob("*.json")):
        seed_s, cell = f.stem.split("_", 1)
        rep = json.loads(f.read_text(encoding="utf-8"))
        res[cell][int(seed_s)] = world_metrics(rep, rep["world"], p_inst, methods, cumulative)
    return res


def _boot_two_stage(per_seed: dict[int, list[float]], n: int = 2000, seed: int = 20261020) -> tuple[float, float, float]:
    """Median with 95 % interval; resample seeds, then rings within the drawn seed."""
    rng = np.random.default_rng(seed)
    seeds = [s for s in per_seed if per_seed[s]]
    allv = [v for s in seeds for v in per_seed[s]]
    if not allv:
        return (float("nan"),) * 3
    meds = []
    for _ in range(n):
        draw = []
        for s in rng.choice(seeds, size=len(seeds)):
            vs = per_seed[int(s)]
            draw.extend(rng.choice(vs, size=len(vs)))
        meds.append(np.median(draw))
    return float(np.median(allv)), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def cell_summary(cell_res: dict[int, dict], methods: tuple[str, ...]) -> dict:
    out: dict = {"seeds": sorted(cell_res)}
    for m in methods:
        rows = [cell_res[s]["methods"][m] for s in sorted(cell_res)]
        hit = sum(r["stealth_hit"] for r in rows)
        n = sum(r["n_stealth"] for r in rows)
        firsts: dict[int, list[float]] = {s: [] for s in cell_res}
        czk: dict[int, list[float]] = {s: [] for s in cell_res}
        never = tot = 0
        for s in cell_res:
            r = cell_res[s]["methods"][m]
            for ring, ft in r["first_flag_day_by_ring"].items():
                tot += 1
                never += ft is None
                firsts[s].append(CENSOR_DAY if ft is None else ft)
                czk[s].append(r["czk_before_first_flag_by_ring"][ring])
        mule_first = [CENSOR_DAY if v["first_day"] is None else v["first_day"] for s in cell_res for v in cell_res[s]["methods"][m]["per_mule"].values()]
        mule_czk = [v["czk_before"] for s in cell_res for v in cell_res[s]["methods"][m]["per_mule"].values()]
        mean = lambda k: float(np.mean([r[k] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None  # noqa: E731
        out[m] = {
            "stealth_recall": hit / n if n else None, "stealth_hit": hit, "n_stealth": n,
            "recall": mean("recall"), "precision": mean("precision"),
            "honest_raised_mean": float(np.mean([r["honest_raised"] for r in rows])), "honest_raised_max": max(r["honest_raised"] for r in rows),
            "network_only_errors_mean": float(np.mean([r["network_only_errors"] for r in rows])),
            "local_false_flags_a_mean": float(np.mean([r["local_false_flags_a"] for r in rows])),
            "n_flagged_mean": float(np.mean([r["n_flagged"] for r in rows])), "reach_of_e": mean("reach_of_e"),
            "first_flag_day": _boot_two_stage(firsts), "czk_before_first_flag": _boot_two_stage(czk), "rings": tot, "rings_never_flagged": never,
            "per_mule_first_day_median": float(np.median(mule_first)) if mule_first else None,
            "per_mule_czk_before_median": float(np.median(mule_czk)) if mule_czk else None,
        }
    out["buckets"] = {k: float(np.mean([cell_res[s]["collector"][k] for s in cell_res])) for k in ("n_flagged_buckets", "n_suppressed_buckets", "n_tested")}
    out["bytes_collector_per_bank_per_month"] = next(iter(cell_res.values()))["bytes_collector_per_bank_per_month"]
    out["bytes_psi_b_total_mean"] = float(np.mean([cell_res[s]["bytes_psi_b_total"] for s in cell_res]))
    return out


def tune(split: str = "dev", variants: tuple[str, ...] = ("30", "50", "80")) -> dict:
    """Prereg section 6: maximise dev-mean (c) stealth recall over shared cells subject to S1 definition <= 1 and honest raised <= 5 on every seed."""
    table = {}
    for v in variants:
        res = load(split, v, ("a", "b", "c"))
        shared = [cell_summary(res[c], ("a", "b", "c")) for c in RING_CELLS if c.startswith("shared") and c in res]
        sr = float(np.mean([c["c"]["stealth_recall"] for c in shared if c["c"]["stealth_recall"] is not None]))
        cf = res.get("crimefree", {})
        s1 = float(np.mean([cf[s]["methods"]["c"]["network_only_errors"] for s in cf])) if cf else float("nan")
        hr_max = max(cell_res[s]["methods"]["c"]["honest_raised"] for c in RING_CELLS if c in res for cell_res in [res[c]] for s in cell_res)
        table[v] = {"dev_mean_shared_stealth_recall_c": sr, "crimefree_network_only_errors_mean": s1, "honest_raised_max_any_seed_cell": hr_max,
                    "admissible": s1 <= 1.0 and hr_max <= 5}
    ok = [v for v in variants if table[v]["admissible"]]
    best = max(ok, key=lambda v: (round(table[v]["dev_mean_shared_stealth_recall_c"], 6), int(v))) if ok else None
    return {"table": table, "chosen": best}


def criteria(summ: dict[str, dict], methods_d: bool = False) -> dict:
    """S1-S5 per prereg section 7 (+ owner edits). Returns {criterion: {cell: {...pass/fail/inconclusive}}}."""
    out: dict = {"S1": {}, "S2": {}, "S3": {}, "S4": {}, "S5": {}}
    cf = summ.get("crimefree")
    if cf:
        for m in ("c", "d"):
            if m in cf:
                out["S1"][m] = {"value": cf[m]["network_only_errors_mean"], "pass": cf[m]["network_only_errors_mean"] <= 1.0}
    for cell, s in summ.items():
        if cell == "crimefree":
            continue
        n = s["c"]["n_stealth"]
        if cell.startswith("shared"):
            ok = (s["c"]["stealth_recall"] or 0) >= 0.5 and (s["c"]["stealth_recall"] or 0) >= (s["b"]["stealth_recall"] or 0) + 0.3
            out["S2"][cell] = {"c": s["c"]["stealth_recall"], "b": s["b"]["stealth_recall"], "a": s["a"]["stealth_recall"], "n": n,
                               "result": "inconclusive" if n < 10 else ("pass" if ok else "fail")}
        if cell.startswith("rotating") and "d" in s and not cell.endswith("high"):
            diff = (s["d"]["stealth_recall"] or 0) - (s["c"]["stealth_recall"] or 0)
            out["S3"][cell] = {"d": s["d"]["stealth_recall"], "c": s["c"]["stealth_recall"], "diff": diff, "n": n,
                               "result": "inconclusive" if n < 10 else ("pass" if diff >= 0.4 else "fail")}
        for m in ("c", "d"):
            if m in s:
                out["S4"][f"{cell}/{m}"] = {"mean": s[m]["honest_raised_mean"], "max": s[m]["honest_raised_max"], "pass": s[m]["honest_raised_mean"] <= 5}
        m5 = "c" if cell.startswith("shared") else "d"
        if m5 in s and not (cell.startswith("rotating") and cell.endswith("high")):
            fa, fm = s["a"]["first_flag_day"], s[m5]["first_flag_day"]
            out["S5"][cell] = {"method": m5, "a_median": fa[0], "m_median": fm[0], "a_ci": fa[1:], "m_ci": fm[1:],
                               "a_never": s["a"]["rings_never_flagged"], "m_never": s[m5]["rings_never_flagged"], "rings": s["a"]["rings"],
                               "pass": (fa[0] - fm[0]) >= 2}
    return out


def fmt(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def markdown(summ: dict[str, dict], crit: dict, methods: tuple[str, ...], title: str) -> str:
    L = [f"### {title}", "", "| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag median [CI] |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for cell in [cell_name(h, j) for h, j in CELLS]:
        if cell not in summ:
            continue
        for m in methods:
            r = summ[cell][m]
            ff, cz = r["first_flag_day"], r["czk_before_first_flag"]
            L.append(f"| {cell} | {m} | {fmt(r['stealth_recall'])} ({r['stealth_hit']}/{r['n_stealth']}) | {fmt(r['recall'])} | {fmt(r['precision'])} | "
                     f"{fmt(r['honest_raised_mean'], 1)} / {r['honest_raised_max']} | {fmt(r['network_only_errors_mean'], 1)} | "
                     f"{fmt(ff[0], 1)} [{fmt(ff[1], 1)}, {fmt(ff[2], 1)}] | {r['rings_never_flagged']}/{r['rings']} | {fmt(cz[0], 0)} [{fmt(cz[1], 0)}, {fmt(cz[2], 0)}] |")
    L += ["", "Collector buckets per world at month end (mean): " + "; ".join(
        f"{c}: tested {fmt(s['buckets']['n_tested'], 0)}, flagged {fmt(s['buckets']['n_flagged_buckets'], 1)}, institutional-suppressed {fmt(s['buckets']['n_suppressed_buckets'], 1)}"
        for c, s in summ.items()), ""]
    L += ["| criterion | cell | value | result |", "|---|---|---|---|"]
    for k, v in crit["S1"].items():
        L.append(f"| S1 | crimefree/{k} | net-only errors {fmt(v['value'], 2)} per seed | {'pass' if v['pass'] else 'FAIL'} |")
    for k, v in crit["S2"].items():
        L.append(f"| S2 | {k} | (c) {fmt(v['c'])} vs (b) {fmt(v['b'])}, (a) {fmt(v['a'])}, n={v['n']} | {v['result']} |")
    for k, v in crit["S3"].items():
        L.append(f"| S3 | {k} | (d)-(c) = {fmt(v['diff'])}, n={v['n']} | {v['result']} |")
    for k, v in crit["S4"].items():
        L.append(f"| S4 | {k} | honest raised mean {fmt(v['mean'], 1)}, max {v['max']} | {'pass' if v['pass'] else 'FAIL'} |")
    for k, v in crit["S5"].items():
        L.append(f"| S5 | {k} | median first day (a) {fmt(v['a_median'], 1)} vs ({v['method']}) {fmt(v['m_median'], 1)}; never flagged (a) {v['a_never']}/{v['rings']}, ({v['method']}) {v['m_never']}/{v['rings']} | {'pass' if v['pass'] else 'FAIL'} |")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tune", "report"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--p-inst", default="50")
    ap.add_argument("--cumulative", action="store_true")
    ap.add_argument("--methods", nargs="+", default=["a", "b", "c"])
    a = ap.parse_args()
    if a.cmd == "tune":
        t = tune(a.split)
        (OUT / f"{a.split}_tuning.json").write_text(json.dumps(t, indent=1), encoding="utf-8")
        print(json.dumps(t, indent=1))
        return
    methods = tuple(a.methods)
    res = load(a.split, a.p_inst, methods + (("e",) if "e" not in methods else ()), a.cumulative)
    summ = {c: cell_summary(r, methods + (("e",) if "e" not in methods else ())) for c, r in res.items()}
    crit = criteria(summ)
    (OUT / f"{a.split}{'_cum' if a.cumulative else ''}_summary.json").write_text(json.dumps({"p_inst": a.p_inst, "summary": summ, "criteria": crit}, indent=1, default=str), encoding="utf-8")
    md = markdown(summ, crit, methods + ("e",), f"{a.split} seeds, p_inst={a.p_inst}")
    (OUT / f"{a.split}{'_cum' if a.cumulative else ''}_tables.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
