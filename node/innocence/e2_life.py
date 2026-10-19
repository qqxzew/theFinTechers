"""E2: life — the client sends mainly to popular counterparties, consistent with ordinary living expenses."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E2"
VERSION = "1"
SOURCE = "own design (innocence layer)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when the share of outflows to popular counterparties exceeds the configured minimum."""
    cfg = ctx["cfg"][DETECTOR_ID]
    min_share = cfg["min_share"]
    share_popular = f["share_popular"]
    if share_popular < min_share:
        return []
    score = min(1.0, 0.5 + 0.5 * (share_popular - min_share) / (1 - min_share))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["share_popular"],
            explanation_template_key="e2_life",
            source=SOURCE,
            exculpatory=True,
        )
    ]
