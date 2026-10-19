"""Run FINREG rules A/B/C on the ČNB data; for rule A report alert counts for every unit interpretation."""
from __future__ import annotations

import json
import sys
import time
from itertools import product

import yaml

from ingest.cnb_clients import load_clients
from ingest.cnb_tx import load_transactions
from ingest.fx import load_fx
from node.rules.rule_a import rule_a
from node.rules.rule_b import rule_b
from node.rules.rule_c import rule_c

UNITS = ["monthly", "quarterly", "yearly"]


def main(out: str = "eval/out/finreg_counts.json") -> dict:
    t0 = time.time()
    fx = load_fx("config/fx.yaml")
    th = yaml.safe_load(open("config/thresholds.yaml", encoding="utf-8"))
    hr = yaml.safe_load(open("config/high_risk_jurisdictions.yaml", encoding="utf-8"))
    hr_set = set(hr["eu"]["countries"]) | set(hr["fatf"]["call_for_action"]) | set(hr["fatf"]["increased_monitoring"])
    tx = load_transactions("data/raw/cnb/transactions.csv", fx)
    cl = load_clients("data/raw/cnb/clients.csv")
    res: dict = {"n_tx": tx.height, "n_clients": cl.height, "fx_placeholder": fx["placeholder"], "rule_a": {}}
    for eu, qu in product(UNITS, UNITS):
        a = rule_a(tx, cl, {**th["rule_a"], "expected_unit": eu, "q2_unit": qu})
        res["rule_a"][f"expected={eu},q2={qu}"] = a.height
    b = rule_b(tx, cl, hr_set, th["rule_b"])
    res["rule_b"] = {"alerts": b.height, "by_reason": {r["reason"]: r["len"] for r in b.group_by("reason").len().to_dicts()}}
    c = rule_c(tx, th["rule_c"])
    res["rule_c"] = {"alerts": c.height}
    c2 = rule_c(tx, {**th["rule_c"], "anchor": "first_inflow"})
    res["rule_c_first_inflow"] = {"alerts": c2.height}
    res["seconds"] = round(time.time() - t0, 1)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=2), file=sys.stdout)
