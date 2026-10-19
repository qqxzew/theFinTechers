import math

import pytest

from common.schemas import Case, Signal, Triage

W = {"bias": -4.0, "points": {"D1": 3.0, "D2": 3.5, "D3": 1.0, "D4": 2.0, "D5": 2.0, "D6": 3.0, "D7": 3.0, "D8": 1.5,
                              "R-A": 0.5, "R-B": 1.0, "R-C": 2.0, "E1": -3.0, "E2": -1.5, "E3": -2.0, "E4": -1.5, "E5": -1.5}}
EXPLAINS = {"E1": ["D1", "D5", "D8"], "E3": ["D1", "D2", "D5", "D3", "D4", "R-C", "R-A"], "E4": ["D1", "D3", "D4", "R-C", "R-A"]}
CFG = {"weights": W, "explains": EXPLAINS, "fp_max_priority": 30, "prob_scale": 60.0,
       "priority_factors": {"aml_risk": {"low": 0, "medium": 5, "high": 12}, "pep": 10, "high_risk_country": 10, "new_client_days": [90, 365],
                            "new_client_points": [8, 4], "distant_form": 4, "multi_flag": {"2": 4, "3": 8}, "cluster": 15,
                            "amount_log_points": 15, "amount_ref": 10000.0}}


def sig(did, cid="K1", score=1.0, exc=False):
    return Signal(signal_id=f"{did}:{cid}", detector_id=did, version="1", client_id=cid, score=score, evidence=["x"],
                  explanation_template_key=did.lower(), source="own design", exculpatory=exc)


def test_score_additive_logodds():
    from node.cases.scoring import score_case

    r = score_case([sig("D1", score=1.0), sig("D5", score=0.5)], [sig("E3", score=0.5, exc=True)], W)
    # -4 + 3.0*1.0 + 2.0*0.5 - 2.0*0.5 = -1.0
    assert r["logit"] == pytest.approx(-1.0) and r["prob"] == pytest.approx(1 / (1 + math.exp(1.0)))
    assert r["points"]["D1:K1"] == pytest.approx(3.0) and r["points"]["E3:K1"] == pytest.approx(-1.0)
    assert score_case([], [], W)["prob"] == pytest.approx(1 / (1 + math.exp(4.0)))


def test_priority_factors():
    from node.cases.priority import priority

    base = {"aml_risk": "low", "pep": False, "high_risk_country": False, "days_since_contract": 2000, "contract_form": "in person",
            "n_distinct_detectors": 1, "in_cluster": False, "big_amount": 10000.0}
    p0 = priority(0.5, base, CFG)
    assert p0 == 30  # 60*0.5, every factor zero (amount at reference -> 0 points)
    assert priority(0.5, {**base, "aml_risk": "high"}, CFG) == 42
    assert priority(0.5, {**base, "pep": True}, CFG) == 40
    assert priority(0.5, {**base, "days_since_contract": 30}, CFG) == 38
    assert priority(0.5, {**base, "days_since_contract": 200}, CFG) == 34
    assert priority(0.5, {**base, "contract_form": "distant form"}, CFG) == 34
    assert priority(0.5, {**base, "n_distinct_detectors": 3}, CFG) == 38
    assert priority(0.5, {**base, "in_cluster": True}, CFG) == 45
    assert priority(0.5, {**base, "big_amount": 1000000.0}, CFG) == 45  # 15 points at 100x the reference (log10=2 -> capped 15)
    assert priority(1.0, {**base, "aml_risk": "high", "pep": True, "in_cluster": True, "high_risk_country": True}, CFG) == 100  # clipped
    assert priority(0.0, base, CFG) == 0


def test_triage_fp_only_when_every_suspicion_is_explained():
    from node.cases.triage import triage

    sus = [sig("D1"), sig("D5")]
    exc = [sig("E1", exc=True), sig("E3", exc=True)]
    t, reasons = triage(sus, exc, priority=20, route="mule_review", cfg=CFG)
    assert t == Triage.FP and any("D1:K1" in r and "E" in r for r in reasons) and any("D5:K1" in r for r in reasons)
    # a suspicion nobody explains (D7) -> REVIEW
    t, reasons = triage(sus + [sig("D7")], exc, priority=20, route="mule_review", cfg=CFG)
    assert t == Triage.REVIEW and any("D7:K1" in r and "unexplained" in r for r in reasons)
    # priority too high -> REVIEW even if everything is explained
    assert triage(sus, exc, priority=55, route="mule_review", cfg=CFG)[0] == Triage.REVIEW
    # no exculpatory signal -> REVIEW
    assert triage(sus, [], priority=10, route="mule_review", cfg=CFG)[0] == Triage.REVIEW
    # victim route is never auto-closed
    assert triage(sus, exc, priority=5, route="victim_protection", cfg=CFG)[0] == Triage.REVIEW


def test_build_case():
    from node.cases.builder import build_case

    meta = {"aml_risk": "low", "pep": False, "high_risk_country": False, "days_since_contract": 20, "contract_form": "distant form",
            "big_amount": 300000.0, "in_cluster": False, "cluster_id": None}
    c = build_case("B1", "K1", [sig("D2", score=0.9), sig("D1", score=0.8)], [], meta, CFG)
    assert isinstance(c, Case) and c.case_id == "B1-K1" and c.bank_id == "B1" and c.triage == Triage.REVIEW and c.route == "mule_review"
    assert 0 <= c.priority <= 100 and c.priority >= 50 and len(c.signals) == 2 and all("K1" in r or ":" in r for r in c.triage_reasons)
    v = build_case("B1", "K2", [sig("D5", cid="K2"), sig("VICTIM", cid="K2", score=0.8)], [], {**meta, "days_since_contract": 2000}, CFG)
    assert v.route == "victim_protection" and v.triage == Triage.REVIEW
    ok = build_case("B1", "K3", [sig("D1", cid="K3")], [sig("E3", cid="K3", exc=True)], {**meta, "days_since_contract": 2000, "contract_form": "in person", "big_amount": 10000.0}, CFG)
    assert ok.triage == Triage.FP and ok.priority < 30
