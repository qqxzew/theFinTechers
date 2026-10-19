"""D4: new-sender fan-in (many rare senders paying non-item-like amounts)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "D4"
VERSION = "1"
SOURCE = "own design"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when many rare senders pay in amounts that are not item-like."""
    cfg = ctx["cfg"][DETECTOR_ID]
    n_in = f["n_in"]
    avg_in = f["in_total"] / n_in if n_in else 0
    if not (
        f["n_senders_rare"] >= cfg["min_rare_senders"]
        and f["in_total"] >= cfg["min_in_total"]
        and avg_in >= cfg["min_avg_in"]
    ):
        return []
    score = min(1.0, 0.5 + 0.05 * (f["n_senders_rare"] - cfg["min_rare_senders"]))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["n_senders_rare", "in_total", "n_in"],
            explanation_template_key="d4_fan_in",
            source=SOURCE,
        )
    ]
