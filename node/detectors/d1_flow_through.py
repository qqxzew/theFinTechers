"""D1: flow-through+ — large inflow drained within 24h, boosted by rare senders/exits, repetition, tight lags."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "D1"
VERSION = "1"
SOURCE = "FINREG rule C (flow-through) extended; own design"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when a client passes large inflows straight through, with mule-like corroboration."""
    cfg = ctx["cfg"][DETECTOR_ID]
    if not (f["in_max_24h"] >= cfg["inflow_min"] and f["drained_24h_share"] >= cfg["drained_min"]):
        return []

    score = 0.4
    evidence = ["in_max_24h", "drained_24h_share"]
    if f["n_senders"] > 0 and f["n_senders_rare"] / f["n_senders"] >= 0.5:
        score += 0.15
        evidence += ["n_senders", "n_senders_rare"]
    if f["share_rare"] >= 0.5:
        score += 0.15
        evidence.append("share_rare")
    if f["n_cycles"] >= cfg["min_cycles_repeat"]:
        score += 0.15
        evidence.append("n_cycles")
    if f["n_cycles"] >= 3 and f["lag_iqr_h"] is not None and f["lag_iqr_h"] <= cfg["tight_lag_iqr_h"]:
        score += 0.15
        evidence += ["n_cycles", "lag_iqr_h"]
    if score < cfg["min_score"]:
        return []

    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=min(1.0, score),
            evidence=list(dict.fromkeys(evidence)),
            explanation_template_key="d1_flow_through",
            source=SOURCE,
        )
    ]
