"""Assemble a Case from detector signals: score, prioritize, triage, route."""
from __future__ import annotations

from common.schemas import Case, Signal, Triage
from node.cases.priority import priority
from node.cases.scoring import score_case
from node.cases.triage import triage


def build_case(bank_id: str, client_id: str, signals: list[Signal], exculpatory: list[Signal], meta: dict, cfg: dict) -> Case:
    """Build a fully triaged case for one client at one bank.

    The VICTIM detector only routes the case to victim protection; it never
    contributes to scoring, priority, or triage explanations. Triage reasons
    are prefixed with the case id so each one references the case.
    """
    case_id = f"{bank_id}-{client_id}"
    suspicious = [s for s in signals if s.detector_id != "VICTIM"]
    route = "victim_protection" if any(s.detector_id == "VICTIM" for s in signals) else "mule_review"
    meta2 = {**meta, "n_distinct_detectors": len({s.detector_id for s in suspicious})}
    prob = score_case(suspicious, exculpatory, cfg["weights"])["prob"]
    prio = priority(prob, meta2, cfg)
    verdict, reasons = triage(suspicious, exculpatory, prio, route, cfg)
    if meta.get("in_cluster"):
        verdict = Triage.REVIEW
        reasons = [*reasons, f"member of disclosed cluster {meta.get('cluster_id')}: never auto-closed"]
    return Case(
        case_id=case_id,
        bank_id=bank_id,
        client_id=client_id,
        signals=signals,
        exculpatory=exculpatory,
        priority=prio,
        triage=verdict,
        triage_reasons=[f"{case_id}: {r}" for r in reasons],
        route=route,
        cluster_id=meta.get("cluster_id"),
    )
