"""E3 innocence detector: source of funds backed by recurring income."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E3"
VERSION = "1"
SOURCE = "own design (innocence layer)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when the recurring income share clears the configured minimum."""
    cfg = ctx["cfg"][DETECTOR_ID]
    thr = cfg["min_recurring"]
    v = f["recurring_income_share"]
    if v is None or v < thr:
        return []
    score = min(1.0, 0.5 + 0.5 * (v - thr) / (1 - thr))
    return [Signal(
        signal_id=f"{DETECTOR_ID}:{f['client_id']}",
        detector_id=DETECTOR_ID,
        version=VERSION,
        client_id=f["client_id"],
        score=score,
        evidence=["recurring_income_share"],
        explanation_template_key="e3_source",
        source=SOURCE,
        exculpatory=True,
    )]
