"""E4: institutional counterparty (inflows dominated by popular hubs or a very high-degree sender)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E4"
VERSION = "1"
SOURCE = "own design (innocence layer)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when inflows come from popular counterparties, suggesting institutional payments."""
    cfg = ctx["cfg"][DETECTOR_ID]
    popular_in = f["popular_inflow_share"] >= cfg["min_popular_in"]
    popular_sender = f["big_in_sender_degree"] is not None and f["big_in_sender_degree"] >= cfg["popular_sender_degree"]
    if not (popular_in or popular_sender):
        return []
    score = 0.8 if popular_in and popular_sender else 0.6
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["popular_inflow_share", "big_in_sender_degree"],
            explanation_template_key="e4_institutional",
            source=SOURCE,
            exculpatory=True,
        )
    ]
