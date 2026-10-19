"""E7 co-host middleman: established account with an ordinary life that always forwards to the same single host after keeping a fixed commission (6-18 %)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E7"
VERSION = "1"
SOURCE = "own design (innocence layer; persona separator, validated only on synthetic personas)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    cfg = ctx["cfg"][DETECTOR_ID]
    if not (f["top_exit_share"] >= cfg["min_top_exit"] and f["retention_median"] is not None and cfg["min_k"] <= f["retention_median"] <= cfg["max_k"] and f["n_in"] >= cfg["min_in"] and f["life_payment_share"] >= cfg["min_life"] and f["days_since_contract"] >= cfg["min_tenure"]):
        return []
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=0.65,
            evidence=["top_exit_share", "retention_median", "n_in", "life_payment_share", "days_since_contract"],
            explanation_template_key="e7_cohost",
            source=SOURCE,
            exculpatory=True,
        )
    ]
