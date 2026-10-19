"""CNB evaluation (no ground truth exists: the dataset has no labelled mules). Reports alert counts, triage outcomes and a review sheet.

Everything is computed here and written to eval/out/cnb_eval.json; the UI and the pitch read only that file.
"""
from __future__ import annotations

import csv
import json
import random
from collections import Counter

import polars as pl

from eval.finreg_units import rule_a_counts
from ingest.cnb_clients import load_clients
from ingest.cnb_tx import load_transactions
from ingest.fx import load_fx
from node.pipeline import load_config, run_node


def main(out: str = "eval/out/cnb_eval.json", sheet: str = "eval/out/cnb_sample_30.csv") -> dict:
    cfg = load_config()
    fx = load_fx("config/fx.yaml")
    tx = load_transactions("data/raw/cnb/transactions.csv", fx)
    cl = load_clients("data/raw/cnb/clients.csv")
    r = run_node("CNB", tx, cl, cfg)
    cases = {c.client_id: c for c in r.cases}
    tau = cfg["cases"]["fp_max_priority"]
    alerts = r.alerts
    a_counts = alerts.group_by("alert_type").len().to_dicts()
    rc_clients = alerts.filter(pl.col("alert_type") == "C")["client_id"].to_list()
    rc_triage = Counter(cases[c].triage.value for c in rc_clients if c in cases)
    pr = [c.priority for c in r.cases]
    bins = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]
    hist = [{"bin": f"{a}-{b - 1}", "count": sum(1 for p in pr if a <= p < b)} for a, b in bins]
    feat = {row["client_id"]: row for row in r.features.to_dicts()}
    mom = [cid for cid, f in feat.items() if f["remit_top_recipient_count"] >= 2]
    mom_rev = [cid for cid in mom if cid in cases and cases[cid].triage.value == "REVIEW"]
    mom_act = [cid for cid in mom_rev if cases[cid].priority >= tau]
    rng = random.Random(0)
    review = sorted([c for c in r.cases if c.triage.value == "REVIEW"], key=lambda c: -c.priority)
    fps = [c for c in r.cases if c.triage.value == "FP"]
    pick = review[:10] + rng.sample(review[10:], min(10, max(0, len(review) - 10))) + rng.sample(fps, min(10, len(fps)))
    with open(sheet, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["client_id", "bank", "triage", "priority", "route", "suspicious_signals", "exculpatory_signals", "reasons", "analyst_verdict", "analyst_note"])
        for c in pick:
            w.writerow([c.client_id, c.bank_id, c.triage.value, c.priority, c.route, " ".join(s.signal_id for s in c.signals),
                        " ".join(s.signal_id for s in c.exculpatory), " | ".join(c.triage_reasons[:3]), "", ""])
    res = {
        "dataset": "CNB hackathon dataset (synthetic, no labels)", "synthetic": True, "n_clients": cl.height, "n_tx": tx.height,
        "rule_a_alerts_per_unit": rule_a_counts(tx, cl, cfg),
        "alerts_by_type": {d["alert_type"]: d["len"] for d in a_counts},
        "rule_b_alerts": next((d["len"] for d in a_counts if d["alert_type"] == "B"), 0),
        "rule_c_alerts": len(rc_clients), "rule_c_triage": {"FP": rc_triage.get("FP", 0), "REVIEW": rc_triage.get("REVIEW", 0)},
        "cases": len(r.cases), "triage": dict(Counter(c.triage.value for c in r.cases)), "routes": dict(Counter(c.route for c in r.cases)),
        "signals_by_detector": dict(Counter(s.detector_id for s in r.signals)),
        "priority_hist": hist, "operating_point_min_priority": tau,
        "actionable_review": sum(1 for c in r.cases if c.triage.value == "REVIEW" and c.priority >= tau),
        "mom_persona": {"definition": "client with >= 2 remittances to the same recipient (remit_top_recipient_count >= 2); 232 clients by our analysis of the CNB data", "n": len(mom),
                        "review_any_priority": len(mom_rev), "review_actionable": len(mom_act),
                        "fp_rate_any_priority": round(len(mom_rev) / len(mom), 4) if mom else None,
                        "fp_rate": round(len(mom_act) / len(mom), 4) if mom else None},
        "sample_sheet_url": sheet,
    }
    json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return res


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(main(), indent=1, ensure_ascii=False))
