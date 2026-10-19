"""E6 pooled one-off: an established account with an ordinary life collects small amounts from several senders and pays almost everything on to ONE payee (rent split, group collection, fundraiser)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E6"
VERSION = "1"
SOURCE = "own design (innocence layer; persona separator, validated only on synthetic personas)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    cfg = ctx["cfg"][DETECTOR_ID]
    if not (f["top_exit_share"] >= cfg["min_top_exit"] and f["max_single_in"] <= cfg["max_single_in"] and f["n_senders"] >= cfg["min_senders"] and f["life_payment_share"] >= cfg["min_life"] and f["days_since_contract"] >= cfg["min_tenure"] and f["n_cycles"] <= cfg["max_cycles"]):
        return []
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=0.8,
            evidence=["top_exit_share", "max_single_in", "n_senders", "life_payment_share", "days_since_contract", "n_cycles"],
            explanation_template_key="e6_pooling",
            source=SOURCE,
            exculpatory=True,
        )
    ]
