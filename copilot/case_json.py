"""Structured case JSON: the ONLY input the LLM ever sees. Aggregates and pseudonyms; no raw transaction dumps, no names."""
from __future__ import annotations

import hashlib
import hmac

from common.schemas import Case

FEATURE_WHITELIST = [
    "days_since_contract", "contract_form", "client_type", "aml_risk", "pep", "n_in", "n_out", "in_total", "out_total", "n_senders",
    "n_senders_rare", "n_exits", "share_rare", "share_mid", "share_popular", "popular_inflow_share", "recurring_income_share",
    "reciprocity_share", "big_in_amount", "max_single_in", "drained_24h_share", "life_events_before_big", "n_cycles", "retention_median",
    "lag_median_h", "top_exit_share", "life_payment_share", "july_total", "expected_monthly", "inflow_share_of_volume", "in_max_24h",
    "remit_top_recipient_count", "remit_amount_cv",
]

FEATURE_DOC = {
    "days_since_contract": "days between contract date and 2026-07-31",
    "contract_form": "'in person' or 'distant form' (modifier only, never a verdict)",
    "in_total": "sum of incoming amounts in July, CZK", "out_total": "sum of outgoing amounts in July, CZK",
    "n_in": "number of incoming transactions", "n_out": "number of outgoing transactions", "n_senders": "distinct sender accounts",
    "n_senders_rare": "senders that at most 3 clients of this bank ever interact with",
    "n_exits": "distinct receiving accounts", "share_rare": "share (0-1) of outgoing amount sent to rare accounts (<=3 clients of this bank)",
    "share_popular": "share (0-1) of outgoing amount sent to popular accounts (>=100 clients of this bank: utilities, shops, employers)",
    "popular_inflow_share": "share (0-1) of incoming amount from popular accounts", "recurring_income_share": "share (0-1) of incoming amount from repeat or popular payers",
    "big_in_amount": "largest single incoming amount, CZK", "max_single_in": "largest single incoming amount, CZK",
    "drained_24h_share": "share (0-1) of the largest inflow sent out within 24 h after it",
    "n_cycles": "number of inflow->outflow cycles", "retention_median": "median share (0-1) of an inflow that stays on the account (the commission); NOT a duration",
    "lag_median_h": "median hours between the end of an inflow cycle and the outflow", "top_exit_share": "share (0-1) of outgoing amount to the single largest receiver",
    "life_payment_share": "share (0-1) of outgoing PAYMENT COUNT that goes to popular accounts (ordinary spending life)",
    "july_total": "in_total + out_total, CZK", "expected_monthly": "projected monthly volume from the client profile, CZK",
    "inflow_share_of_volume": "share (0-1) of July volume that is incoming", "in_max_24h": "largest sum of inflows inside any 24 h window, CZK",
    "life_events_before_big": "number of transactions before the largest inflow", "reciprocity_share": "share (0-1) of volume with accounts that are both sender and receiver",
}

RULES_TEXT = {
    "R-A": "FINREG rule A (profile discrepancy): July daily volume above 25 % of projected monthly volume, or above 3x the average daily Q2 volume, or a single transaction above 2x the Q2 maximum.",
    "R-B": "FINREG rule B (high-risk jurisdiction / PEP): a transaction above CZK 10,000 involving an EU/FATF high-risk country, or an outgoing transaction above CZK 100,000 by a PEP.",
    "R-C": "FINREG rule C (flow-through): incoming above CZK 100,000 within 24 h and, within 6 h, at least 80 % of it sent on to accounts other than the payers.",
    "D1": "D1 flow-through+: rule C extended with new senders, rare exits, repetition and a tight inflow-to-outflow lag.",
    "D2": "D2 day-zero handover: a recently opened account with almost no earlier life receives a large third-party inflow and drains >= 90 % within 24 h.",
    "D3": "D3 profile discrepancy+: July volume at least 3x the projected monthly volume, labelled inflow-driven or spending-driven.",
    "D4": "D4 new-sender fan-in: many unrelated, previously unseen senders in a short window with amounts that are not item-like.",
    "D5": "D5 rare-exit concentration: most of the outflow goes to rare counterparties although the money did not come from recurring income.",
    "D6": "D6 same hand: own clients sharing low-degree exits AND similar lag AND similar retention ratio AND similar active hours, scored against a shuffled baseline.",
    "D7": "D7 fixed skim: outflow ~ inflow x (1 - k) with k stable (+- 1.5 pp) over >= 3 cycles, k >= 1 %.",
    "D8": "D8 structuring: amounts pile up just below an empirically discovered threshold.",
    "X": "Radar cluster membership: an exit token of this client matched, in a blinded PSI exchange, exit tokens of candidates at other banks.",
    "E1": "E1 'mom': recurring remittances of stable amounts to the same recipient, funded by recurring income.",
    "E2": "E2 life: a meaningful share of outflow goes to popular counterparties.",
    "E3": "E3 source of funds: money leaving came from the client's recurring income.",
    "E4": "E4 institutional counterparty: payers are high-degree institutions (employer, insurer, platform).",
    "E5": "E5 reciprocity: money flows in both directions with the same counterparties.",
    "E6": "E6 pooled one-off: established account collects small amounts and pays nearly all to one payee (rent split, collection, fundraiser).",
    "E7": "E7 co-host middleman: established account forwards to a single host after a fixed commission.",
    "E8": "E8 earner: few payers, money kept and spent in ordinary life (freelancer).",
    "VICTIM": "Victim route: the client drains own savings to new rare accounts with no large third-party inflow; routed to victim protection, never labelled a mule.",
}


def client_ref(secret: bytes, bank_id: str, client_id: str) -> str:
    return "c-" + hmac.new(secret, f"{bank_id}:{client_id}".encode(), hashlib.sha256).hexdigest()[:8]


def _sig(s, feat: dict) -> dict:
    ev = {k: feat[k] for k in s.evidence if k in feat}
    notes = [k for k in s.evidence if k not in feat]
    return {"signal_id": s.signal_id, "detector_id": s.detector_id, "score": s.score, "evidence": ev, "notes": notes,
            "template": s.explanation_template_key, "source": s.source}


def build_case_json(case: Case, feat: dict, cluster: dict | None, secret: bytes = b"copilot-secret") -> dict:
    features = {k: feat.get(k) for k in FEATURE_WHITELIST if feat.get(k) is not None}
    used = {s.detector_id for s in [*case.signals, *case.exculpatory]}
    out = {
        "case_id": case.case_id, "client_ref": client_ref(secret, case.bank_id, case.client_id), "bank_id": case.bank_id,
        "priority": case.priority, "triage": case.triage.value, "route": case.route,
        "signals": [_sig(s, feat) for s in case.signals], "exculpatory": [_sig(s, feat) for s in case.exculpatory],
        "features": features, "triage_reasons": case.triage_reasons,
        "rule_definitions": {k: RULES_TEXT[k] for k in sorted(used) if k in RULES_TEXT},
        "feature_glossary": {k: FEATURE_DOC[k] for k in features if k in FEATURE_DOC},
        "data_label": "SYNTHETIC DATA - no real customer",
    }
    if cluster:
        out["cluster"] = {"cluster_id": cluster["cluster_id"], "n_other_banks": cluster["n_other_banks"],
                          "n_other_candidates": cluster["n_other_candidates"], "lag_ret_concentration": cluster.get("lag_ret_concentration"),
                          "matched_exit_accounts": cluster.get("matched_exit_accounts", [])}
    return out
