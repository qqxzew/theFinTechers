"""D3: profile discrepancy+ — July volume far exceeds the declared expected monthly volume, with gap direction."""
from __future__ import annotations

from common.schemas import Signal

DETECTOR_ID = "D3"
VERSION = "1"
SOURCE = "FINREG rule A (profile discrepancy) extended with direction of the gap"


def detect(f: dict, ctx: dict) -> list[Signal]:
    """Fire when july_total / expected_monthly exceeds the configured gap multiplier."""
    cfg = ctx["cfg"][DETECTOR_ID]
    expected = f["expected_monthly"]
    if not expected:
        return []
    ratio = f["july_total"] / expected
    gap_mult = cfg["gap_mult"]
    if ratio < gap_mult:
        return []
    share = f["inflow_share_of_volume"]
    if share >= 0.6:
        direction = "inflow_driven"
    elif share <= 0.4:
        direction = "spending_driven"
    else:
        direction = "balanced"
    score = max(0.3, min(1.0, 0.3 + 0.07 * (ratio - gap_mult)))
    return [
        Signal(
            signal_id=f"{DETECTOR_ID}:{f['client_id']}",
            detector_id=DETECTOR_ID,
            version=VERSION,
            client_id=f["client_id"],
            score=score,
            evidence=["july_total", "expected_monthly", "inflow_share_of_volume"],
            explanation_template_key=f"d3_profile_gap_{direction}",
            source=SOURCE,
        )
    ]
