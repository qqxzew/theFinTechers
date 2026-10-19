"""Deterministic, explainable priority score (0-100) for a case."""
from __future__ import annotations

import math


def priority(prob: float, meta: dict, cfg: dict) -> int:
    """Combine the model probability with fixed business-rule factors.

    Every additive term comes from ``cfg['priority_factors']``; the result is
    clipped to [0, 100] and rounded half-up to an integer.
    """
    f = cfg["priority_factors"]
    total = cfg["prob_scale"] * prob

    total += f["aml_risk"][meta["aml_risk"]]
    if meta["pep"]:
        total += f["pep"]
    if meta["high_risk_country"]:
        total += f["high_risk_country"]

    days = meta["days_since_contract"]
    if days < f["new_client_days"][0]:
        total += f["new_client_points"][0]
    elif days < f["new_client_days"][1]:
        total += f["new_client_points"][1]

    if meta["contract_form"] == "distant form":
        total += f["distant_form"]

    n = meta["n_distinct_detectors"]
    if n >= 3:
        total += f["multi_flag"]["3"]
    elif n == 2:
        total += f["multi_flag"]["2"]

    if meta["in_cluster"]:
        total += f["cluster"]

    big_amount = meta["big_amount"]
    if big_amount > 0:
        amount_pts = f["amount_log_points"] * math.log10(big_amount / f["amount_ref"]) / 2
        total += min(max(amount_pts, 0.0), f["amount_log_points"])

    return int(math.floor(min(max(total, 0.0), 100.0) + 0.5))
