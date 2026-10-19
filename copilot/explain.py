"""Case explanation (CS + EN), triage justification and 'not a mom' text. The LLM only verbalises the structured case JSON."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from copilot.bedrock_client import LLM, sha
from copilot.budgets import Budget
from copilot.qa import validate_draft

PROMPT = Path(__file__).parent / "prompts" / "explain_system.txt"


class Sentence(BaseModel):
    text: str
    refs: list[str] = []


class Lang(BaseModel):
    en: list[Sentence]
    cs: list[Sentence]


class Just(BaseModel):
    en: Sentence
    cs: Sentence


class Explanation(BaseModel):
    en: list[Sentence]
    cs: list[Sentence]
    not_a_mom: Lang | None = None
    triage_justification: Just


_CACHE: dict[str, dict] = {}


def extract_json(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no JSON object in model output")
    return json.loads(text[a:b + 1])


def _violations(exp: Explanation, case: dict) -> list[dict]:
    out = []
    for name, sents in (("en", exp.en), ("cs", exp.cs), ("not_a_mom.en", exp.not_a_mom.en if exp.not_a_mom else []),
                        ("not_a_mom.cs", exp.not_a_mom.cs if exp.not_a_mom else []),
                        ("justification.en", [exp.triage_justification.en]), ("justification.cs", [exp.triage_justification.cs])):
        for v in validate_draft({"sentences": [s.model_dump() for s in sents]}, case, analyst_names=[]):
            out.append({**v, "part": name})
    return out


def explain_case(llm: LLM, case: dict, budget: Budget | None = None, max_retries: int = 2, role: str = "agent_primary") -> dict:
    key = sha(case)
    if key in _CACHE:
        return {**_CACHE[key], "cached": True}
    system = PROMPT.read_text(encoding="utf-8")
    user = "<CASE_JSON>\n" + json.dumps(case, ensure_ascii=False) + "\n</CASE_JSON>"
    messages = [{"role": "user", "content": [{"text": user}]}]
    last: list[dict] = []
    for attempt in range(max_retries + 1):
        r = llm.call(role, system, messages, max_tokens=4000, budget=budget, agent="narrative")
        try:
            exp = Explanation.model_validate(extract_json(r.text))
            last = _violations(exp, case)
            if not last:
                res = {"explanation": exp.model_dump(), "violations": [], "model_id": r.model_id, "attempts": attempt + 1, "case_hash": key}
                _CACHE[key] = res
                return {**res, "cached": False}
            fb = "Your JSON failed validation. Fix ONLY these problems and return the full JSON again:\n" + json.dumps(last[:12], ensure_ascii=False)
        except (ValueError, ValidationError) as e:
            fb = f"Your output was not valid for the schema ({str(e)[:300]}). Return STRICT JSON only."
            last = [{"kind": "schema", "detail": str(e)[:200]}]
        messages += [{"role": "assistant", "content": r.content}, {"role": "user", "content": [{"text": fb}]}]
    return {"explanation": None, "violations": last, "model_id": r.model_id, "attempts": max_retries + 1, "case_hash": key, "cached": False}
