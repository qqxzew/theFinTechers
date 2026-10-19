"""API integration on a small world: queue, case card, governance on decisions (conflicts, four-eyes, override reason), audit chain."""
import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from api.state import build_state


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    st = build_state("data/redteam/seed909", audit_path=str(tmp_path_factory.mktemp("api") / "audit.jsonl"))
    return TestClient(create_app(st)), st


def test_queue_filters_and_case(client):
    c, st = client
    q = c.get("/api/queue?triage=REVIEW&limit=50").json()
    assert q["counts"]["cases"] == len(st.cases) and all(i["triage"] == "REVIEW" for i in q["items"])
    assert q["items"] == sorted(q["items"], key=lambda i: -i["priority"])
    only_victim = c.get("/api/queue?route=victim_protection").json()
    assert all(i["route"] == "victim_protection" for i in only_victim["items"])
    top = q["items"][0]["case_id"]
    case = c.get(f"/api/cases/{top}").json()
    assert case["case_id"] == top and case["escalation"]["matrix_is_placeholder"] is True and "feature_glossary" in case
    assert c.get("/api/cases/NOPE").status_code == 404


def test_governance_on_decisions(client):
    c, st = client
    item = next(i for i in c.get("/api/queue?min_priority=71&triage=REVIEW").json()["items"])
    cid = item["case_id"]
    case = st.cases[cid]
    owner = st.owner_of(case.client_id)
    base = {"action": "confirm", "role": "mlro", "reason": "", "approver": None}
    r = c.post(f"/api/cases/{cid}/decision", json={**base, "decider": owner}).json()
    assert r["ok"] is False and "decider_is_relationship_owner" in r["violations"]            # no self-review
    r = c.post(f"/api/cases/{cid}/decision", json={**base, "decider": "rob"}).json()
    assert "decider_is_rule_author" in r["violations"]
    other = next(n for n in ("zoe", "max", "eva", "jan", "lea") if n != owner)
    r = c.post(f"/api/cases/{cid}/decision", json={**base, "decider": other, "approver": None}).json()
    assert r["ok"] is False and "four_eyes_required" in r["violations"]                        # priority >= 70 needs an approver
    r = c.post(f"/api/cases/{cid}/decision", json={**base, "decider": other, "action": "override", "approver": "ann"}).json()
    assert "override_requires_written_reason" in r["violations"]
    r = c.post(f"/api/cases/{cid}/decision", json={**base, "decider": other, "role": "analyst_l1", "approver": "ann"}).json()
    assert "role_below_escalation_target" in r["violations"]
    ok = c.post(f"/api/cases/{cid}/decision", json={**base, "decider": other, "approver": "ann" if owner != "ann" else "tom"}).json()
    assert ok["ok"] is True and c.get(f"/api/cases/{cid}").json()["decision"]["decider"] == other


def test_audit_chain_is_intact_and_records_rejections(client):
    c, _ = client
    v = c.get("/api/audit/verify").json()
    assert v["ok"] is True and v["length"] > 0
    acts = [e["action"] for e in c.get("/api/audit?offset=0&limit=500").json()["entries"]]
    assert "case_built" in acts and "psi_session" in acts
    assert c.get("/api/audit/verify").json()["ok"] is True
    last = c.get(f"/api/audit?offset={max(0, v['length'] - 12)}&limit=12").json()["entries"]
    kinds = [e["action"] for e in last]
    assert "decision:confirm" in kinds and "decision_rejected" in kinds     # accepted and rejected human decisions are both on the chain


def test_honesty_and_files(client):
    c, _ = client
    h = c.get("/api/honesty").json()
    assert h["sources"] and h["limitations"] and "legal basis" in h["legal_note"]
    assert c.get("/api/files/not-allowed.txt").status_code == 404
    assert c.get("/api/meta").json()["matrix_placeholder"] is True
