"""D5: rare-exit concentration — outflows go to rare counterparties while income is neither recurring nor popular."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "D5"
VERSION = "1"
SOURCE = "own design"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when a client's outflows concentrate on rare exits without recurring/popular funding."""
    cfg = ctx["cfg"][DETECTOR_ID]
    min_share_rare = cfg["min_share_rare"]
    if not (
        f["share_rare"] >= min_share_rare
        and f["recurring_income_share"] <= cfg["max_recurring"]
        and f["popular_inflow_share"] <= cfg["max_popular_in"]
        and f["out_total"] >= cfg["min_out"]
    ):
        return []
    score = min(1.0, 0.5 + 0.5 * (f["share_rare"] - min_share_rare) / (1 - min_share_rare))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["share_rare", "recurring_income_share", "popular_inflow_share", "out_total"],
            explanation_template_key="d5_rare_exit_concentration",
            source=SOURCE,
        )
    ]
