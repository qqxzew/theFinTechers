"""Generic tool-use agent loop with hard limits. Tools are read-only except propose_*, which only record proposals.

On any limit (steps, tokens, cost, timeout) the loop stops and hands the case to a human with what was found so far.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from copilot.bedrock_client import LLM, sha
from copilot.budgets import Budget, BudgetExceeded
from copilot.tools.case_tools import CaseTools


@dataclass
class AgentRun:
    agent: str
    status: str                       # 'done' | 'handed_to_human'
    final_text: str
    transcript: list[dict] = field(default_factory=list)
    stop_reason: str = ""
    tool_calls: int = 0
    cost_usd: float = 0.0
    ungrounded_refs: list = field(default_factory=list)   # signal ids cited in the final text that do not exist in the case


def run_agent(llm: LLM, agent: str, role: str, system: str, task: str, tools: CaseTools, budget: Budget, audit=None) -> AgentRun:
    messages: list[dict] = [{"role": "user", "content": [{"text": task}]}]
    run = AgentRun(agent=agent, status="done", final_text="")
    try:
        while True:
            r = llm.call(role, system, messages, tools=tools.spec(), budget=budget, agent=agent)
            run.cost_usd += r.cost_usd
            messages.append({"role": "assistant", "content": r.content})
            if not r.tool_uses:
                run.final_text = r.text
                return run
            results = []
            for u in r.tool_uses:
                try:
                    out = tools.call(u["name"], u["input"])
                    if isinstance(out, dict):
                        payload = {"json": out}
                    elif isinstance(out, list):
                        payload = {"json": {"result": out}}      # Bedrock requires a JSON OBJECT in toolResult.json
                    else:
                        payload = {"text": str(out)}
                    status = "success"
                except Exception as e:  # noqa: BLE001 - a bad tool call is returned to the model, not fatal
                    payload, status = {"text": f"ERROR: {e}"}, "error"
                run.tool_calls += 1
                if audit:
                    audit.append(actor=f"agent:{agent}", action=f"tool:{u['name']}", why=status, rule_version="copilot-1", model_version=None,
                                 input_hash=sha(u["input"]), output_hash=sha(payload))
                results.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [payload], "status": status}})
            messages.append({"role": "user", "content": results})
    except BudgetExceeded as e:
        run.status, run.stop_reason = "handed_to_human", str(e)
        run.final_text = "Agent stopped at a hard limit; the case is handed to a human. " + str(e)
        if audit:
            audit.append(actor=f"agent:{agent}", action="limit_reached", why=str(e), rule_version="copilot-1", model_version=None, input_hash="-")
        return run
    finally:
        run.transcript = messages
