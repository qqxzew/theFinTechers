"""VICTIM: small incoming transfers drained by large outgoing flows (victim route, not exculpatory)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "VICTIM"
VERSION = "1"
SOURCE = "own design (innocence layer)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when inflows are small but outflows heavily outweigh inflows; routes to victim protection."""
    cfg = ctx["cfg"][DETECTOR_ID]
    in_total = max(f["in_total"], 1.0)
    out_total = f["out_total"]
    if not (
        f["max_single_in"] < cfg["max_single_in"]
        and out_total >= cfg["min_out"]
        and out_total >= cfg["min_out_in_ratio"] * in_total
        and f.get("share_rare", 0.0) >= cfg.get("min_share_rare", 0.0)
    ):
        return []
    ratio = cfg["min_out_in_ratio"]
    score = min(1.0, 0.6 + 0.1 * (out_total / in_total - ratio) / ratio)
    score = max(0.6, min(1.0, score))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["max_single_in", "out_total", "in_total", "share_rare"],
            explanation_template_key="victim",
            source=SOURCE,
            exculpatory=False,
        )
    ]
