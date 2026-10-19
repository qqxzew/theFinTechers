import polars as pl

from escalation.conflicts import check_decision, validate_approval
from escalation.matrix import route
from export.finreg_csv import FINREG_COLUMNS, to_finreg_rows

CFG = {"four_eyes_min_priority": 70}
CASE = {"client_id": "K1", "relationship_owner": "ann", "rule_authors": ["rob"], "first_triager": "tom", "priority": 80}


def test_no_self_review():
    assert check_decision("zoe", CASE, CFG) == []
    assert check_decision("ann", CASE, CFG) == ["decider_is_relationship_owner"]
    assert check_decision("rob", CASE, CFG) == ["decider_is_rule_author"]
    assert check_decision("tom", CASE, CFG) == ["decider_is_first_triager"]
    assert set(check_decision("ann", {**CASE, "first_triager": "ann"}, CFG)) == {"decider_is_relationship_owner", "decider_is_first_triager"}


def test_approval_rules():
    # four-eyes above the threshold: approver must differ from decider; approver != executor always
    assert validate_approval(decider="zoe", approver="max", executor="zoe", priority=80, cfg=CFG) == []
    assert validate_approval(decider="zoe", approver="zoe", executor="zoe", priority=80, cfg=CFG) == ["four_eyes_required", "approver_is_executor"]
    assert validate_approval(decider="zoe", approver="zoe", executor="zoe", priority=50, cfg=CFG) == ["approver_is_executor"]
    assert validate_approval(decider="zoe", approver="max", executor="max", priority=50, cfg=CFG) == ["approver_is_executor"]
    assert validate_approval(decider="zoe", approver=None, executor="zoe", priority=80, cfg=CFG) == ["four_eyes_required"]


MATRIX = {"roles": ["analyst_l1", "analyst_l2", "aml_officer", "mlro"], "placeholder": True, "rules": [
    {"when": {"pep": True}, "role": "aml_officer"},
    {"when": {"cluster": True, "priority_min": 70}, "role": "mlro"},
    {"when": {"priority_min": 70}, "role": "aml_officer"},
    {"when": {"priority_min": 40}, "role": "analyst_l2"},
    {"when": {}, "role": "analyst_l1"},
]}


def test_routing_first_match_wins():
    assert route({"priority": 10, "pep": False, "cluster": False, "alert_type": "A"}, MATRIX)["role"] == "analyst_l1"
    assert route({"priority": 45, "pep": False, "cluster": False, "alert_type": "A"}, MATRIX)["role"] == "analyst_l2"
    assert route({"priority": 75, "pep": False, "cluster": False, "alert_type": "C"}, MATRIX)["role"] == "aml_officer"
    assert route({"priority": 75, "pep": False, "cluster": True, "alert_type": "C"}, MATRIX)["role"] == "mlro"
    r = route({"priority": 5, "pep": True, "cluster": False, "alert_type": "B"}, MATRIX)
    assert r["role"] == "aml_officer" and r["matrix_is_placeholder"] is True


def test_finreg_csv_rows():
    alerts = pl.DataFrame({"alert_type": ["A", "C", "B", "B"], "client_id": ["K1", "K1", "K2", "K2"],
                           "transaction_id": [None, None, "T1", "T2"]})
    cases = {"K1": {"triage": "REVIEW", "priority": 81, "reasons": ["D1:K1 flow-through with rare exits"], "log": "abc123"},
             "K2": {"triage": "FP", "priority": 12, "reasons": ["E1:K2 recurring remittances"], "log": "def456"}}
    decisions = {"K1": {"executive_role": "aml_officer", "executive_person": "zoe", "approver": "max"}}
    df = to_finreg_rows(alerts, cases, decisions)
    assert df.columns == FINREG_COLUMNS == ["alert_id", "alert_type", "client_id", "transaction_id", "triage", "priority",
                                            "executive_role", "executive_person", "approver", "reason", "log"]
    assert df.height == 4 and df["alert_id"].n_unique() == 4
    k1 = df.filter(pl.col("client_id") == "K1")
    assert set(k1["triage"]) == {"REVIEW"} and set(k1["priority"]) == {81} and set(k1["executive_person"]) == {"zoe"}
    k2 = df.filter(pl.col("client_id") == "K2")
    assert set(k2["triage"]) == {"FP"} and k2["executive_person"].null_count() == 2 or set(k2["executive_person"]) == {""}
    assert "D1:K1" in k1["reason"][0] and k1["log"][0] == "abc123"
