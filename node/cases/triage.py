"""Rule-based triage: auto-close as FP only when every suspicion is explained."""
from __future__ import annotations

from common.schemas import Signal, Triage


def triage(suspicious: list[Signal], exculpatory: list[Signal], priority: int, route: str, cfg: dict) -> tuple[Triage, list[str]]:
    """Decide FP vs REVIEW with human-readable reasons referencing signal ids.

    FP requires: route is not ``victim_protection``, priority is below
    ``cfg['fp_max_priority']``, at least one suspicious signal exists, and every
    suspicious signal is explained by some exculpatory signal via
    ``cfg['explains']``.
    """
    fp_max = cfg["fp_max_priority"]
    explains = cfg["explains"]

    reasons: list[str] = []
    if priority < fp_max:
        reasons.append(f"priority {priority} < {fp_max}")
    else:
        reasons.append(f"priority {priority} >= {fp_max}")
    if route == "victim_protection":
        reasons.append("route victim_protection: never auto-closed")

    all_explained = True
    for s in suspicious:
        explainers = [e for e in exculpatory if s.detector_id in explains.get(e.detector_id, [])]
        if explainers:
            reasons.append(f"{s.signal_id} explained by {explainers[0].signal_id}")
        else:
            reasons.append(f"{s.signal_id} unexplained")
            all_explained = False

    if route != "victim_protection" and priority < fp_max and suspicious and all_explained:
        return Triage.FP, reasons
    return Triage.REVIEW, reasons
