"""Agent loop with a scripted fake Bedrock client: tool dispatch, proposals-only, hard limits, audit trail."""
import json

from audit.log import AuditLog, verify_chain
from copilot.agents.agents import run_case_agent
from copilot.bedrock_client import LLM
from copilot.budgets import Budget
from copilot.model_registry import ModelRegistry
from tests.unit.test_copilot_core import CASE

MODELS = {"region": "eu-central-1", "roles": {"agent_primary": "global.moonshotai.kimi-k3", "fallback": "f", "bulk": "b"},
          "prices_placeholder": {r: {"in": 1e-6, "out": 2e-6} for r in ("agent_primary", "fallback", "bulk")}}


class FakeClient:
    """Returns scripted assistant messages; records the requests."""

    def __init__(self, script):
        self.script, self.calls = list(script), []

    def converse(self, **kw):
        self.calls.append(kw)
        for m in kw["messages"]:                      # reproduce Bedrock validation: toolResult.json must be an object
            for b in m["content"]:
                for c in b.get("toolResult", {}).get("content", []):
                    assert "json" not in c or isinstance(c["json"], dict), "toolResult.json must be a JSON object"
        msg = self.script.pop(0)
        return {"output": {"message": {"role": "assistant", "content": [{"reasoningContent": {"reasoningText": {"text": "hidden"}}}, *msg]}},
                "stopReason": "tool_use" if any("toolUse" in b for b in msg) else "end_turn",
                "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}}


def tu(i, name, **args):
    return {"toolUse": {"toolUseId": f"t{i}", "name": name, "input": args}}


def make(script, tmp_path):
    reg = ModelRegistry(MODELS, client=FakeClient(script))
    reg.active = dict(MODELS["roles"])
    audit = AuditLog(tmp_path / "a.jsonl")
    return LLM(reg, audit, client=reg.client), audit


def test_triage_agent_proposes_but_cannot_decide(tmp_path):
    llm, audit = make([[tu(1, "get_signals", case_id="B1-R00001")],
                       [tu(2, "propose_triage", case_id="B1-R00001", triage="REVIEW", reason="D1:R00001 unexplained")],
                       [{"text": "Proposal REVIEW because D1:R00001 is unexplained."}]], tmp_path)
    run, tools = run_case_agent(llm, "triage", "B1-R00001", {"B1-R00001": CASE}, {}, {}, Budget(12, 10**5, 1.0, 60), audit)
    assert run.status == "done" and "REVIEW" in run.final_text and run.tool_calls == 2
    assert tools.proposals[0]["final"] is False and CASE["triage"] == "REVIEW"
    # reasoning blocks never go back to the model
    assert all("reasoningContent" not in json.dumps(c["messages"]) for c in llm.client.calls)
    # every model call and tool call is in the hash-chained audit log
    actions = [json.loads(x)["action"] for x in open(tmp_path / "a.jsonl", encoding="utf-8")]
    assert actions.count("model_call") == 3 and "tool:get_signals" in actions and "tool:propose_triage" in actions
    assert verify_chain(tmp_path / "a.jsonl") == (True, None)


def test_agent_cannot_call_tools_outside_its_toolbox_or_other_cases(tmp_path):
    llm, _ = make([[tu(1, "propose_triage", case_id="B1-R00001", triage="FP", reason="x")],   # QA agent has no propose_triage
                   [tu(2, "get_case", case_id="B2-OTHER")],                                  # other bank's case
                   [{"text": "done"}]], tmp_path)
    run, tools = run_case_agent(llm, "qa", "B1-R00001", {"B1-R00001": CASE}, {}, {}, Budget(12, 10**5, 1.0, 60))
    results = [m for m in run.transcript if m["role"] == "user" and "toolResult" in m["content"][0]]
    assert all(r["content"][0]["toolResult"]["status"] == "error" for r in results) and tools.proposals == []


def test_step_limit_hands_case_to_human(tmp_path):
    llm, audit = make([[tu(i, "get_signals", case_id="B1-R00001")] for i in range(1, 6)], tmp_path)
    run, _ = run_case_agent(llm, "triage", "B1-R00001", {"B1-R00001": CASE}, {}, {}, Budget(2, 10**5, 1.0, 60), audit)
    assert run.status == "handed_to_human" and "max_steps" in run.stop_reason
    assert "limit_reached" in [json.loads(x)["action"] for x in open(tmp_path / "a.jsonl", encoding="utf-8")]


def test_qa_agent_flags_analyst_name(tmp_path):
    bad = json.dumps([{"text": "Detected by Jana Nováková.", "refs": ["D1:R00001"]}])
    llm, _ = make([[tu(1, "validate_draft", case_id="B1-R00001", sentences_json=bad)], [{"text": "Violation: analyst_name"}]], tmp_path)
    run, tools = run_case_agent(llm, "qa", "B1-R00001", {"B1-R00001": CASE}, {}, {}, Budget(12, 10**5, 1.0, 60), analyst_names=["Jana Nováková"])
    tool_res = [m for m in run.transcript if m["role"] == "user"][1]["content"][0]["toolResult"]["content"][0]["json"]
    assert tool_res["valid"] is False and tool_res["violations"][0]["kind"] == "analyst_name"


def test_hallucinated_signal_reference_is_flagged(tmp_path):
    llm, audit = make([[{"text": "Story: D1:R00001 fired and D4:R00001 too."}]], tmp_path)
    run, _ = run_case_agent(llm, "investigation", "B1-R00001", {"B1-R00001": CASE}, {}, {}, Budget(12, 10**5, 1.0, 60), audit)
    assert run.ungrounded_refs == ["D4:R00001"]          # D1:R00001 exists in CASE, D4 does not
    assert "ungrounded_reference" in [json.loads(x)["action"] for x in open(tmp_path / "a.jsonl", encoding="utf-8")]
