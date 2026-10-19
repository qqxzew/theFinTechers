"""D7: fixed skim — every cycle retains the same small fraction, like a fixed-commission mule payout."""
from __future__ import annotations

from statistics import median

from common.schemas import Signal

DETECTOR_ID = "D7"
VERSION = "1"
SOURCE = "own design (fixed-commission mule payout)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when cycle retentions are stable near a fixed rate above the minimum skim."""
    cfg = ctx["cfg"][DETECTOR_ID]
    tol = cfg["tol"]
    r = f["cycle_retentions"]
    if len(r) < cfg["min_cycles"]:
        return []
    med = median(r)
    if med < cfg["min_k"]:
        return []
    max_dev = max(abs(x - med) for x in r)
    if max_dev > tol:
        return []
    score = min(1.0, max(0.6, 0.6 + 0.4 * (1 - max_dev / tol)))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["cycle_retentions"],
            explanation_template_key="d7_fixed_skim",
            source=SOURCE,
        )
    ]
