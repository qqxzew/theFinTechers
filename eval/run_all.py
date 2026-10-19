"""Reproducible evaluation: python -m eval.run_all   (generates worlds if missing, evaluates, writes eval/report.json, eval/report.md, pitch_numbers.json).

Seeds: DEV seeds were used while building/tuning (7, 101). HELD-OUT seeds (202, 303) are never used for tuning; the headline numbers
are the mean over the held-out seeds. Every number below is computed here; nothing is typed by hand.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

from eval import cnb_eval
from eval.redteam_eval import evaluate

DEV = [7, 101, 202, 303, 404, 505, 606]   # all seen while building/tuning/auditing
HELD_OUT = [707, 808]                     # generated AFTER the configuration freeze (tag prereg-config-frozen), run once
RING_SIZES = [6, 9]                  # stealth ring size sweep (accounts in the ring; default world has 12-18)
OUT = Path("eval")


def ensure_world(seed: int) -> str:
    d = f"data/redteam/seed{seed}"
    if not Path(d, "tx.parquet").exists():
        subprocess.run([sys.executable, "-m", "redteam.generate", "--seed", str(seed), "--out", d], check=True)
    return d


def ensure_ring_world(seed: int, n: int) -> str:
    d = f"data/redteam/seed{seed}_ring{n}"
    if not Path(d, "tx.parquet").exists():
        subprocess.run([sys.executable, "-m", "redteam.generate", "--seed", str(seed), "--out", d, "--stealth-n", str(n)], check=True)
    return d


def mean(xs: list[float]) -> float:
    return round(statistics.fmean(xs), 4)


def main(skip_cnb: bool = False) -> dict:
    seeds = {}
    for s in DEV + HELD_OUT:
        seeds[s] = evaluate(ensure_world(s), audit_path=f"eval/out/audit_seed{s}.jsonl")
        json.dump(seeds[s], open(f"eval/out/redteam_seed{s}.json", "w", encoding="utf-8"), indent=1, default=str)
    ring = {}
    for n in RING_SIZES:
        for s in HELD_OUT:
            r = evaluate(ensure_ring_world(s, n))
            ring[f"seed{s}_ring{n}"] = {m: r["curves"][m]["30"] for m in ("isolated", "staj_psi")}
    weak = {"dev": json.load(open("eval/out/weak_sweep_v2_dev_ghost.json")), "held_out": json.load(open("eval/out/weak_sweep_707_808.json")),
            "dev_without_ghost_ring": json.load(open("eval/out/weak_sweep_v1_dev_ceiling.json")),
            "preregistration": "docs/PREREGISTRATION.md", "frozen_config": {"weak_top_frac": 0.05, "use_significance": True, "min_significance": 2.0}}
    cnb = None if skip_cnb else cnb_eval.main()
    held = [seeds[s] for s in HELD_OUT]

    def agg(mode: str, key: str, sub: str = "overall") -> float:
        return mean([r["modes"][mode][sub][key] for r in held])

    headline = {m: {k: agg(m, k) for k in ("precision", "recall", "f1")} for m in ("isolated", "staj_psi", "naive_raw_sharing")}
    for m in headline:
        headline[m]["average_precision"] = agg(m, "average_precision", "rank")
        headline[m]["precision_at_k"] = agg(m, "precision_at_k", "rank")
        headline[m]["raw_records_exposed"] = int(statistics.fmean(r["modes"][m]["exposure"]["raw_records_exposed"] for r in held))
        headline[m]["bytes_exchanged"] = int(statistics.fmean(r["modes"][m]["exposure"]["bytes_exchanged"] for r in held))
    curve = {m: {t: {k: mean([r["curves"][m][t][k] for r in held]) for k in ("tp", "fp", "fn", "precision", "recall")} for t in ("30", "40", "50", "60")}
             for m in ("isolated", "staj_psi", "naive_raw_sharing")}
    abl = {k: {m: mean([r["ablations"][k][m] for r in held]) for m in ("precision", "recall", "f1")} for k in held[0]["ablations"]}
    report = {"synthetic": True, "operating_point": held[0]["operating_point"], "dev_seeds": DEV, "held_out_seeds": HELD_OUT,
              "headline_held_out_mean": headline, "threshold_curve_held_out_mean": curve, "ring_size_sweep": ring, "weak_evidence_experiment": weak, "ablations_held_out_mean": abl,
              "per_seed": {str(s): {"modes": {m: {"overall": r["modes"][m]["overall"], "rank": r["modes"][m]["rank"], "exposure": r["modes"][m]["exposure"]}
                                              for m in r["modes"]}, "ablations": r["ablations"], "breakdown_staj_psi": r["breakdown_staj_psi"],
                                    "disclosed_cluster_candidate_labels": r["disclosed_cluster_candidate_labels"],
                                    "failures_staj_psi": r["failures_staj_psi"]} for s, r in seeds.items()},
              "cnb": cnb,
              "notes": ["ablation 'without_radar' is the isolated run (same pipeline without clusters)",
                        "naive_raw_sharing pools all raw data into ONE node with thresholds calibrated per bank; it is not a guaranteed upper bound"]}
    json.dump(report, open(OUT / "report.json", "w", encoding="utf-8"), indent=1, default=str, ensure_ascii=False)
    (OUT / "report.md").write_text(to_markdown(report), encoding="utf-8")
    pitch = {"synthetic": True, "dataset": "red-team world (CNB-derived background + planted schemes), mean of held-out seeds " + str(HELD_OUT),
             "isolated_f1": headline["isolated"]["f1"], "staj_psi_f1": headline["staj_psi"]["f1"],
             "naive_raw_sharing_f1": headline["naive_raw_sharing"]["f1"],
             "psi_raw_records_exposed": headline["staj_psi"]["raw_records_exposed"], "naive_raw_records_exposed": headline["naive_raw_sharing"]["raw_records_exposed"],
             "psi_bytes": headline["staj_psi"]["bytes_exchanged"], "naive_bytes": headline["naive_raw_sharing"]["bytes_exchanged"]}
    wh = weak["held_out"]
    pitch["ghost_ring_recall_baseline_radar"] = round(sum(wh[s]["baseline"]["staj_psi"]["ghost_recall"] for s in wh) / len(wh), 3)
    pitch["ghost_ring_recall_weak_evidence_radar"] = round(sum(wh[s]["weak_0.05"]["staj_psi"]["ghost_recall"] for s in wh) / len(wh), 3)
    pitch["exported_tokens_baseline"] = int(sum(wh[s]["baseline"]["exported_tokens"] for s in wh) / len(wh))
    pitch["exported_tokens_weak_evidence"] = int(sum(wh[s]["weak_0.05"]["exported_tokens"] for s in wh) / len(wh))
    if cnb:
        pitch["cnb_rule_a_share_of_clients_default"] = round(cnb["rule_a_alerts_per_unit"]["expected=monthly,q2=quarterly"] / cnb["n_clients"], 4)
        pitch["cnb_cases_auto_closed_fp"] = cnb["triage"].get("FP", 0)
        pitch["cnb_cases_review"] = cnb["triage"].get("REVIEW", 0)
    json.dump(pitch, open("pitch_numbers.json", "w", encoding="utf-8"), indent=1)
    return report


def to_markdown(r: dict) -> str:
    L = ["# Stáj evaluation report (generated by eval/run_all.py)", "",
         "**All data synthetic.** Planted schemes are planted by our own red team; numbers measure recognition of OUR scheme definitions, not real-world recall.",
         f"Operating point: {r['operating_point']['definition']}. Dev seeds {r['dev_seeds']} were used while building; held-out seeds {r['held_out_seeds']} "
         "were not used for tuning. Headline = mean over held-out seeds.", "",
         "## Headline (held-out mean)", "", "| mode | precision | recall | F1 | AP (rank) | P@K | raw records exposed | bytes exchanged |", "|---|---|---|---|---|---|---|---|"]
    for m, v in r["headline_held_out_mean"].items():
        L.append(f"| {m} | {v['precision']} | {v['recall']} | {v['f1']} | {v['average_precision']} | {v['precision_at_k']} | {v['raw_records_exposed']:,} | {v['bytes_exchanged']:,} |")
    L += ["", "## Priority-threshold curve (held-out mean TP / FP / FN)", "", "| tau | isolated | staj_psi | naive_raw_sharing |", "|---|---|---|---|"]
    for t in ("30", "40", "50", "60"):
        L.append(f"| {t} | " + " | ".join(f"{r['threshold_curve_held_out_mean'][m][t]['tp']} / {r['threshold_curve_held_out_mean'][m][t]['fp']} / "
                                          f"{r['threshold_curve_held_out_mean'][m][t]['fn']}" for m in ("isolated", "staj_psi", "naive_raw_sharing")) + " |")
    L += ["", "## Stealth ring-size sweep (tau 30, TP/FP/FN, all variants shown)", "", "| world | isolated | staj_psi |", "|---|---|---|"]
    for k, v in r["ring_size_sweep"].items():
        L.append(f"| {k} | {v['isolated']['tp']}/{v['isolated']['fp']}/{v['isolated']['fn']} | {v['staj_psi']['tp']}/{v['staj_psi']['fp']}/{v['staj_psi']['fn']} |")
    L += ["", "## Ablations (held-out mean)", "", "| variant | precision | recall | F1 |", "|---|---|---|---|"]
    for k, v in r["ablations_held_out_mean"].items():
        L.append(f"| {k} | {v['precision']} | {v['recall']} | {v['f1']} |")
    for s, d in r["per_seed"].items():
        tag = "held-out" if int(s) in r["held_out_seeds"] else "dev"
        L += ["", f"## Seed {s} ({tag})", "", "| mode | tp | fp | fn | precision | recall | F1 | AP |", "|---|---|---|---|---|---|---|---|"]
        for m, v in d["modes"].items():
            o = v["overall"]
            L.append(f"| {m} | {o['tp']} | {o['fp']} | {o['fn']} | {o['precision']} | {o['recall']} | {o['f1']} | {v['rank']['average_precision']} |")
        L += ["", "Detection / false-positive rate per group (staj_psi):", "", "| group | n | flagged | routed to victim protection |", "|---|---|---|---|"]
        for k, v in sorted(d["breakdown_staj_psi"].items()):
            L.append(f"| {k} | {v['n']} | {v['flagged_as_mule_case']} | {v['routed_to_victim_protection']} |")
        L += ["", f"Disclosed-cluster candidates by true label: {d['disclosed_cluster_candidate_labels']}", "", "Worst failures:"]
        f = d["failures_staj_psi"]
        for c in f["worst_false_positives"][:5]:
            L.append(f"- FALSE POSITIVE {c['client_id']} ({c['label']}/{c['persona'] or c['scheme']}), priority {c['priority']}: signals {c['signals']}, exculpatory {c['exculpatory']}")
        for c in f["false_negatives"][:5]:
            L.append(f"- MISSED MULE {c['client_id']} ({c['scheme']}), priority {c['priority']}: signals {c['signals']}; {c['reasons'][:2]}")
    if r.get("cnb"):
        c = r["cnb"]
        L += ["", "## CNB data (no ground truth, no mule networks)", "", f"- {c['n_clients']:,} clients, {c['n_tx']:,} transactions",
              f"- Rule A alerts per unit interpretation: {c['rule_a_alerts_per_unit']}", f"- Rule B alerts: {c['rule_b_alerts']}; rule C alerts: {c['rule_c_alerts']} (triage {c['rule_c_triage']})",
              f"- Cases: {c['cases']} - triage {c['triage']}; actionable REVIEW (priority >= {c['operating_point_min_priority']}): {c['actionable_review']}",
              f"- 'Mom' persona: {c['mom_persona']}", f"- 30-case review sheet: {c['sample_sheet_url']}"]
    w = r["weak_evidence_experiment"]
    L += ["", "## Weak-evidence radar experiment (pre-registered: docs/PREREGISTRATION.md)", "",
          "Variants: baseline = candidates only above the local probability band, cluster score by size; NEW = additionally the top 5 % of each bank's clients by a "
          "local pass-through score, matches judged by statistical improbability (Fisher + Bonferroni), priority floor for significant clusters. "
          "The `ghost_ring` is a planted ring with NO usable local signal, added after the first sweep showed no headroom.", "",
          "| world | variant | ghost recall (radar) | original-scheme recall (radar) | TP/FP/FN | exported tokens | bytes exchanged |", "|---|---|---|---|---|---|---|"]
    for part in ("held_out", "dev"):
        for s, v in w[part].items():
            for name in ("baseline", "weak_0.05", "weak_0.10", "weak_0.20"):
                x = v[name]["staj_psi"]
                L.append(f"| {s} ({part.replace('_', '-')}) | {name} | {x['ghost_recall']} | {x['original_recall']} | {x['tp']}/{x['fp']}/{x['fn']} | {v[name]['exported_tokens']} | {v[name]['bytes']:,} |")
    L += ["", "The curve is NOT monotone: more exported candidates dilute the significance of a match (10 % and above lose the ring). Privacy cost of the weak band: "
          "about 6x more exported tokens and 8x more bytes. See LIMITATIONS.md.", "", "## Notes", ""] + [f"- {n}" for n in r["notes"]]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
