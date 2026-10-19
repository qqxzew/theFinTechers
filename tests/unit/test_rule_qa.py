import json

from audit.log import AuditLog
from copilot.bedrock_client import LLM
from copilot.model_registry import ModelRegistry
from copilot.rule_qa import answer_question
from tests.unit.test_agents import MODELS, FakeClient
from tests.unit.test_copilot_core import CASE

CASE2 = {**CASE, "rule_definitions": {"D1": "D1 flow-through+: rule C extended with new senders, rare exits, repetition and a tight lag."}}


def make(texts, tmp_path):
    reg = ModelRegistry(MODELS, client=FakeClient([[{"text": t}] for t in texts]))
    reg.active = dict(MODELS["roles"])
    return LLM(reg, AuditLog(tmp_path / "a.jsonl"), client=reg.client)


def test_grounded_answer_passes(tmp_path):
    good = json.dumps({"sentences": [{"text": "D1 fired because the 24 h inflow reached 250000 CZK and 95 % left within a day.", "refs": ["D1:R00001"]}]})
    r = answer_question(make([good], tmp_path), CASE2, "why did D1 fire?", {"D1": {"inflow_min": 100000}}, role="fallback")
    assert r["violations"] == [] and r["attempts"] == 1 and r["answer"][0]["refs"] == ["D1:R00001"]


def test_unsupported_number_is_retried_then_fixed(tmp_path):
    bad = json.dumps({"sentences": [{"text": "Inflow was 777777 CZK.", "refs": ["D1:R00001"]}]})
    good = json.dumps({"sentences": [{"text": "Inflow was 250000 CZK.", "refs": ["D1:R00001"]}]})
    r = answer_question(make([bad, good], tmp_path), CASE2, "how much?", {}, role="fallback")
    assert r["attempts"] == 2 and r["violations"] == []


def test_persistent_violation_is_returned_not_hidden(tmp_path):
    bad = json.dumps({"sentences": [{"text": "It is obviously a criminal.", "refs": []}]})
    r = answer_question(make([bad, bad, bad], tmp_path), CASE2, "who?", {}, role="fallback")
    assert r["answer"] == [] and r["violations"] and r["violations"][0]["kind"] == "missing_reference"
