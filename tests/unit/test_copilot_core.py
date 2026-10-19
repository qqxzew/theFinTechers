import json

import pytest

from copilot.budgets import Budget, BudgetExceeded
from copilot.qa import validate_draft

CASE = {
    "case_id": "B1-R00001", "client_ref": "c-9f2a", "bank_id": "B1", "priority": 82, "triage": "REVIEW", "route": "mule_review",
    "signals": [
        {"signal_id": "D1:R00001", "detector_id": "D1", "score": 0.9, "evidence": {"in_max_24h": 250000.0, "drained_24h_share": 0.95},
         "template": "d1_flow_through"},
        {"signal_id": "D5:R00001", "detector_id": "D5", "score": 0.7, "evidence": {"share_rare": 0.9}, "template": "d5_rare_exit"},
    ],
    "exculpatory": [],
    "features": {"days_since_contract": 12.0, "contract_form": "distant form", "in_total": 250000.0, "out_total": 238000.0, "n_in": 3},
    "triage_reasons": ["B1-R00001: priority 82 >= 30", "B1-R00001: D1:R00001 unexplained"],
    "cluster": {"cluster_id": "5c64f48f0d60", "n_other_banks": 2, "n_other_candidates": 9},
}
GOOD = {
    "sentences": [
        {"text": "Inflow of 250000 CZK within 24 h was 95 % passed on.", "refs": ["D1:R00001"]},
        {"text": "Most outflow goes to rare accounts.", "refs": ["D5:R00001"]},
        {"text": "The account was opened 12 days before the event.", "refs": ["features.days_since_contract"]},
    ],
    "free_text": "",
}


def test_valid_draft_passes():
    assert validate_draft(GOOD, CASE, analyst_names=["Jana Nováková"]) == []


def test_unsupported_claims_and_bad_refs_are_reported():
    bad = {"sentences": [{"text": "The client is a criminal.", "refs": []},
                         {"text": "Large inflow.", "refs": ["D9:R00001"]},
                         {"text": "Amount 777777 CZK.", "refs": ["D1:R00001"]}]}
    v = validate_draft(bad, CASE, analyst_names=[])
    kinds = sorted(x["kind"] for x in v)
    assert "missing_reference" in kinds and "unknown_reference" in kinds and "number_not_in_case" in kinds


def test_analyst_name_and_tipping_off_are_blocked():
    d = {"sentences": [{"text": "Detected by Jana Nováková on Monday.", "refs": ["D1:R00001"]}]}
    assert any(x["kind"] == "analyst_name" for x in validate_draft(d, CASE, analyst_names=["Jana Nováková"]))
    t = {"sentences": [{"text": "We will report you to the FIU, do not tell anyone.", "refs": ["D1:R00001"]},
                       {"text": "Vaše transakce bude oznámena FAÚ.", "refs": ["D1:R00001"]}]}
    kinds = [x["kind"] for x in validate_draft(t, CASE, analyst_names=[], customer_facing=True)]
    assert kinds.count("tipping_off") == 2


def test_not_available_is_allowed_without_refs():
    d = {"sentences": [{"text": "Source of funds: not available.", "refs": []}]}
    assert validate_draft(d, CASE, analyst_names=[]) == []


def test_budget_limits():
    b = Budget(max_steps=2, max_tokens=1000, max_cost_usd=0.01, timeout_s=60)
    b.charge_step()
    b.charge_usage({"inputTokens": 300, "outputTokens": 100}, price_in=0.000001, price_out=0.000002)
    assert b.tokens == 400 and b.steps == 1 and b.cost_usd == pytest.approx(0.0005)
    b.charge_step()
    with pytest.raises(BudgetExceeded) as e:
        b.charge_step()
    assert "max_steps" in str(e.value)
    b2 = Budget(max_steps=10, max_tokens=500, max_cost_usd=1.0, timeout_s=60)
    with pytest.raises(BudgetExceeded):
        b2.charge_usage({"inputTokens": 400, "outputTokens": 200}, 0.0, 0.0)
    b3 = Budget(max_steps=10, max_tokens=10**6, max_cost_usd=0.001, timeout_s=60)
    with pytest.raises(BudgetExceeded):
        b3.charge_usage({"inputTokens": 1000, "outputTokens": 1000}, price_in=0.0001, price_out=0.0001)


def test_tools_are_case_scoped_and_return_no_raw_dumps():
    from copilot.tools.case_tools import CaseTools

    tools = CaseTools({"B1-R00001": CASE}, rules={"R-C": "Flow-through: inflow above 100000 CZK in 24 h and >=80 % out in 6 h."})
    assert tools.get_case("B1-R00001")["case_id"] == "B1-R00001"
    assert [s["signal_id"] for s in tools.get_signals("B1-R00001")] == ["D1:R00001", "D5:R00001"]
    assert tools.get_exculpatory("B1-R00001") == []
    assert "in_total" in tools.get_features("B1-R00001")
    assert "R-C" in tools.explain_rule("R-C") or "Flow-through" in tools.explain_rule("R-C")
    with pytest.raises(KeyError):
        tools.get_case("B2-OTHER")  # an agent cannot read another bank's / unknown case
    p = tools.propose_triage("B1-R00001", "REVIEW", "unexplained D1")
    assert p["status"] == "proposal" and p["final"] is False
    assert json.dumps(tools.spec())  # JSON-serialisable Converse toolConfig
    assert all(t["toolSpec"]["name"] in {"get_case", "get_signals", "get_exculpatory", "get_features", "explain_rule", "propose_triage"}
               for t in tools.spec()["tools"])


def test_reference_inside_a_signal_is_valid():
    d = {"sentences": [{"text": "Rare exits.", "refs": ["D5:R00001.evidence.share_rare", "D1:R00001.notes"]},
                       {"text": "Bad.", "refs": ["D9:R00001.notes", "D1:R00001.nonsense"]}]}
    kinds = [(v["sentence"], v["kind"]) for v in validate_draft(d, CASE, analyst_names=[])]
    assert kinds == [(1, "unknown_reference"), (1, "unknown_reference")]
