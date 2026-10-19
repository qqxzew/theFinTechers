"""E5: reciprocity — the client's counterparties also receive from them, suggesting genuine two-way relationships."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E5"
VERSION = "1"
SOURCE = "own design (innocence layer)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when the share of reciprocal counterparties meets the configured minimum."""
    thr = ctx["cfg"][DETECTOR_ID]["min_reciprocity"]
    v = f["reciprocity_share"]
    if v < thr:
        return []
    score = min(1.0, 0.5 + 0.5 * (v - thr) / (1 - thr))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["reciprocity_share"],
            explanation_template_key="e5_reciprocity",
            source=SOURCE,
            exculpatory=True,
        )
    ]
