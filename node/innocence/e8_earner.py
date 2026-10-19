"""E8 earner: established account with few payers whose money is NOT passed on quickly and which has an ordinary spending life (freelancer / small business on a personal account)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E8"
VERSION = "1"
SOURCE = "own design (innocence layer; persona separator, validated only on synthetic personas)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    cfg = ctx["cfg"][DETECTOR_ID]
    if not (f["n_senders"] <= cfg["max_senders"] and f["drained_24h_share"] <= cfg["max_drained"] and f["life_payment_share"] >= cfg["min_life"] and f["days_since_contract"] >= cfg["min_tenure"]):
        return []
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=0.7,
            evidence=["n_senders", "drained_24h_share", "life_payment_share", "days_since_contract"],
            explanation_template_key="e8_earner",
            source=SOURCE,
            exculpatory=True,
        )
    ]
