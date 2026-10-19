"""D8: structuring — outflow amounts pile up just below an empirical round-number threshold."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "D8"
VERSION = "1"
SOURCE = "own design (empirical pile-up discovery, no hard-coded threshold)"


def find_pileup_thresholds(amounts: list[float]) -> list[float]:
    """Discover round-number thresholds with a pile-up just below and a gap just above."""
    selected: list[float] = []
    for t in range(1000, 100001, 500):
        tf = float(t)
        below = sum(1 for a in amounts if 0.95 * tf <= a < tf)
        above = sum(1 for a in amounts if tf <= a < 1.05 * tf)
        if below >= 50 and below >= 5 * max(above, 1):
            if any(tf - s <= 0.05 * s for s in selected):
                continue
            selected.append(tf)
    return selected


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when out_amounts pile up below a discovered threshold in count and share."""
    cfg = ctx["cfg"][DETECTOR_ID]
    amounts = f["out_amounts"]
    if not amounts:
        return []
    best_count = 0
    fired = False
    for t in ctx["pileup_thresholds"]:
        lo = (1 - cfg["band"]) * t
        count = sum(1 for a in amounts if lo <= a < t)
        if count > best_count:
            best_count = count
            fired = True
    if not fired or best_count < cfg["min_count"] or best_count / len(amounts) < cfg["min_share"]:
        return []
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=min(1.0, 0.4 + 0.1 * best_count),
            evidence=["out_amounts"],
            explanation_template_key="d8_structuring_pileup",
            source=SOURCE,
        )
    ]
