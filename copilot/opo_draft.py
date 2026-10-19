"""Draft suspicious-transaction report (OPO) per FAÚ Methodological Guideline No. 4 (10 sections). A DRAFT for a human: only section V is
model-written (and QA-validated); everything else is deterministic. The analyst's name never appears; the contact person comes from settings."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from copilot.bedrock_client import LLM, sha
from copilot.budgets import Budget
from copilot.explain import Sentence, extract_json
from copilot.qa import validate_draft

PROMPT = Path(__file__).parent / "prompts" / "opo_section_v_system.txt"
SECTIONS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
TITLES = {
    "I": "Identifikace oznámení (reference)", "II": "Povinná osoba (odesílatel)", "III": "Subjekt obchodu",
    "IV": "Druh podezření", "V": "Popis podezřelého obchodu a podstatných okolností", "VI": "Provedení / neprovedení / odklad obchodu",
    "VII": "Výjimka z identifikace a kontroly klienta", "VIII": "Kontaktní osoba povinné osoby", "IX": "Podání oznámení", "X": "Přílohy",
}


def load_settings(path: str = "config/bank_settings.yaml") -> dict:
    return yaml.safe_load(open(path, encoding="utf-8"))


def draft_section_v(llm: LLM, case: dict, budget: Budget | None = None, max_retries: int = 2, role: str = "agent_primary") -> dict:
    system = PROMPT.read_text(encoding="utf-8")
    messages = [{"role": "user", "content": [{"text": "<CASE_JSON>\n" + json.dumps(case, ensure_ascii=False) + "\n</CASE_JSON>"}]}]
    last: list[dict] = []
    for attempt in range(max_retries + 1):
        r = llm.call(role, system, messages, max_tokens=4000, budget=budget, agent="narrative")
        try:
            sents = [Sentence.model_validate(s) for s in extract_json(r.text)["sentences"]]
            last = validate_draft({"sentences": [s.model_dump() for s in sents]}, case, analyst_names=[])
            if not last:
                return {"sentences": [s.model_dump() for s in sents], "violations": [], "model_id": r.model_id, "attempts": attempt + 1}
            fb = "Fix ONLY these problems and return the full JSON again:\n" + json.dumps(last[:12], ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            fb = f"Invalid output ({str(e)[:200]}). Return STRICT JSON only."
            last = [{"kind": "schema", "detail": str(e)[:200]}]
        messages += [{"role": "assistant", "content": r.content}, {"role": "user", "content": [{"text": fb}]}]
    return {"sentences": [], "violations": last, "model_id": r.model_id, "attempts": max_retries + 1}


def build_opo(case: dict, section_v: dict, settings: dict, audit_head: str, today: str) -> dict:
    """Assemble the ten sections. Section V text is editable; VI and IX are left to the human."""
    cl = case.get("cluster")
    body_v = " ".join(s["text"] for s in section_v["sentences"]) or "Popis není k dispozici (návrh se nepodařilo ověřit) – vyplní odpovědná osoba."
    sec = {
        "I": f"Interní reference případu: {case['case_id']} (pseudonym klienta {case['client_ref']}). Datum návrhu: {today}. "
             f"Stav: NÁVRH – syntetická data, nejde o skutečné oznámení.",
        "II": f"{settings['sender']['bank_name']}, IČO: {settings['sender']['ico']}, adresa: {settings['sender']['address']}.",
        "III": f"Identifikační údaje subjektu: z KYC banky (v syntetických datech nejsou k dispozici). Pseudonym: {case['client_ref']}.",
        "IV": "Podezření na legalizaci výnosů z trestné činnosti (kandidátní případ; konečné posouzení provádí odpovědná osoba).",
        "V": body_v,
        "VI": "Obchod proveden / neproveden / odložen: DOPLNÍ ČLOVĚK. Návrh systému: neprovádí se žádné rozhodnutí. Pokus o obchod se oznamuje také.",
        "VII": "Výjimka z identifikace a kontroly klienta: nebyla zaznamenána.",
        "VIII": f"{settings['contact']['role']}; e-mail: {settings['contact']['email']}; telefon: {settings['contact']['phone']}.",
        "IX": "Způsob a datum podání: DOPLNÍ ČLOVĚK (podání není součástí systému).",
        "X": "Přílohy: (1) strukturovaný JSON případu, hash " + sha(case)[:16] + "; (2) seznam signálů: "
             + ", ".join(s["signal_id"] for s in case["signals"]) + "; (3) hlava auditního řetězce: " + audit_head[:16]
             + (f"; (4) klastr radaru {cl['cluster_id']} (bez cizích klientských údajů)" if cl else ""),
    }
    return {"title": "NÁVRH oznámení o podezřelém obchodu (FAÚ, Metodický pokyn č. 4) – SYNTETICKÁ DATA",
            "sections": [{"no": k, "title": TITLES[k], "text": sec[k]} for k in SECTIONS],
            "section_v_sentences": section_v["sentences"], "section_v_violations": section_v["violations"]}


def to_markdown(opo: dict) -> str:
    lines = [f"# {opo['title']}", ""]
    for s in opo["sections"]:
        lines += [f"## {s['no']}. {s['title']}", s["text"], ""]
    if opo.get("section_v_violations"):
        lines += ["## Upozornění kontroly (QA) – k vyřešení člověkem před použitím", ""]
        lines += [f"- {v.get('kind')}: {v.get('detail', '')} (věta {v.get('sentence')})" for v in opo["section_v_violations"]] + [""]
    return "\n".join(lines)
