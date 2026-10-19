"""D2: day-zero handover — a fresh contract takes one big inflow and drains it within 24h."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "D2"
VERSION = "1"
SOURCE = "own design from public descriptions of day-zero handover mule accounts"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when a new client with little history receives a big inflow that is immediately drained."""
    cfg = ctx["cfg"][DETECTOR_ID]
    if not (
        f["days_since_contract"] <= cfg["max_days"]
        and f["life_events_before_big"] <= cfg["max_life_events"]
        and f["big_in_amount"] >= cfg["min_big"]
        and f["drained_24h_share"] >= cfg["drained_min"]
    ):
        return []
    score = 0.6
    evidence = ["days_since_contract", "life_events_before_big", "big_in_amount", "drained_24h_share"]
    if f["contract_form"] == "distant form":
        score += 0.2
        evidence.append("contract_form")
    if f["days_since_contract"] <= 30:
        score += 0.1
    if f["big_in_sender_degree"] is not None and f["big_in_sender_degree"] <= 3:
        score += 0.1
        evidence.append("big_in_sender_degree")
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=min(1.0, score),
            evidence=evidence,
            explanation_template_key="d2_day_zero",
            source=SOURCE,
        )
    ]
