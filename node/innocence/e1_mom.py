"""E1 (innocence layer): steady remitter supporting a relative abroad ("mom" pattern)."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "E1"
VERSION = "1"
SOURCE = "own design (innocence layer)"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire on repeated remittances to few recipients with stable amounts and recurring income."""
    cfg = ctx["cfg"][DETECTOR_ID]
    cv = f["remit_amount_cv"]
    if not (
        f["remit_top_recipient_count"] >= cfg["min_count"]
        and cv is not None
        and cv <= cfg["max_amount_cv"]
        and f["recurring_income_share"] >= cfg["min_recurring"]
    ):
        return []
    score = max(0.7, min(1.0, 0.7 + 0.3 * (1 - cv / cfg["max_amount_cv"])))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["remit_top_recipient_count", "remit_amount_cv", "recurring_income_share"],
            explanation_template_key="e1_mom",
            source=SOURCE,
            exculpatory=True,
        )
    ]
