"""Per-agent toolboxes over case-scoped data. All tools are read-only except propose_* / draft_*, which only record PROPOSALS.

No tool returns raw transaction dumps: timelines are capped aggregates, graphs are top-N counterparties.
"""
from __future__ import annotations

import copy
from typing import Any

from copilot.qa import validate_draft
from copilot.tools.case_tools import CaseTools, _str_schema
from node.innocence import e1_mom, e6_pooling, e7_cohost, e8_earner

# persona -> (separator module, what an honest instance looks like)
PERSONAS = {
    "migrant_remit": (e1_mom, "regular remittances of stable amounts to ONE recipient, funded by recurring income"),
    "students_rent": (e6_pooling, "small amounts from several flatmates, one payment to the landlord, established account with ordinary life"),
    "group_collection": (e6_pooling, "many small contributions, one payment to a venue, established account with ordinary life"),
    "fundraiser": (e6_pooling, "many small donations, one transfer to the beneficiary, established account with ordinary life"),
    "middleman_cohost": (e7_cohost, "fixed 6-18 % commission, always the same host, established account with ordinary life"),
    "freelancer": (e8_earner, "few payers, money kept and spent in ordinary life"),
}


class Toolbox(CaseTools):
    EXTRA = {
        "get_timeline": ("Get the capped, aggregated flow timeline of the case (max 60 events).", {"case_id": "Id of the case."}, ["case_id"]),
        "get_local_graph": ("Get the local counterparty graph (top counterparties by amount).", {"case_id": "Id of the case."}, ["case_id"]),
        "get_cluster_context": ("Get the radar cluster context (other banks, other candidates) or 'not available'.", {"case_id": "Id of the case."}, ["case_id"]),
        "check_lookalike": ("Check whether the case matches an HONEST look-alike persona separator. persona is one of: " + ", ".join(PERSONAS) + ".",
                            {"case_id": "Id of the case.", "persona": "Persona name."}, ["case_id", "persona"]),
        "draft_opo_section": ("Store a DRAFT of an OPO section for a human to review (validated against the case JSON). Sentences: JSON list of {text, refs}.",
                              {"case_id": "Id of the case.", "section": "Section number, e.g. V.", "sentences_json": "JSON list of {text, refs}."},
                              ["case_id", "section", "sentences_json"]),
        "validate_draft": ("Validate a draft against the case JSON (unsupported claims, missing refs, analyst names, tipping-off wording).",
                           {"case_id": "Id of the case.", "sentences_json": "JSON list of {text, refs}.", "customer_facing": "'true' or 'false'."},
                           ["case_id", "sentences_json"]),
    }

    def __init__(self, cases: dict[str, dict], rules: dict[str, str], cfg: dict | None = None, analyst_names: list[str] | None = None,
                 allowed: set[str] | None = None) -> None:
        super().__init__(cases, rules)
        self.cfg = cfg or {}
        self.analyst_names = analyst_names or []
        self.allowed = allowed
        self.drafts: list[dict[str, Any]] = []

    def get_timeline(self, case_id: str) -> list[dict]:
        return copy.deepcopy(self._case(case_id).get("timeline", []))[:60]

    def get_local_graph(self, case_id: str) -> dict:
        return copy.deepcopy(self._case(case_id).get("local_graph", {"nodes": [], "edges": []}))

    def get_cluster_context(self, case_id: str) -> Any:
        return self._case(case_id).get("cluster") or "not available"

    def check_lookalike(self, case_id: str, persona: str) -> dict:
        if persona not in PERSONAS:
            return {"persona": persona, "error": "unknown persona", "known": sorted(PERSONAS)}
        mod, description = PERSONAS[persona]
        c = self._case(case_id)
        f = {**c["features"], "client_id": c["case_id"]}
        missing = [k for k in ("top_exit_share", "life_payment_share", "n_senders") if k not in f]
        fires = bool(mod.detect(f, {"cfg": self.cfg})) if not missing and self.cfg else None
        return {"persona": persona, "honest_pattern": description, "separator": mod.DETECTOR_ID, "separator_fires": fires,
                "missing_features": missing, "note": "A separator firing lowers suspicion but never closes the case by itself."}

    def draft_opo_section(self, case_id: str, section: str, sentences_json: str) -> dict:
        import json

        sents = json.loads(sentences_json)
        viol = validate_draft({"sentences": sents}, self._case(case_id), self.analyst_names)
        d = {"status": "proposal", "final": False, "case_id": case_id, "section": section, "sentences": sents, "violations": viol}
        self.drafts.append(d)
        return d

    def validate_draft_tool(self, case_id: str, sentences_json: str, customer_facing: str = "false") -> dict:
        import json

        viol = validate_draft({"sentences": json.loads(sentences_json)}, self._case(case_id), self.analyst_names, customer_facing.lower() == "true")
        return {"valid": not viol, "violations": viol}

    def spec(self) -> dict[str, Any]:
        base = super().spec()["tools"]
        extra = [{"toolSpec": {"name": n, "description": d, "inputSchema": {"json": _str_schema(p, r)}}} for n, (d, p, r) in self.EXTRA.items()]
        tools = base + extra
        if self.allowed is not None:
            tools = [t for t in tools if t["toolSpec"]["name"] in self.allowed]
        return {"tools": tools}

    def call(self, name: str, args: dict) -> Any:
        if self.allowed is not None and name not in self.allowed:
            raise ValueError(f"tool not allowed for this agent: {name}")
        extra = {
            "get_timeline": lambda a: self.get_timeline(a["case_id"]),
            "get_local_graph": lambda a: self.get_local_graph(a["case_id"]),
            "get_cluster_context": lambda a: self.get_cluster_context(a["case_id"]),
            "check_lookalike": lambda a: self.check_lookalike(a["case_id"], a["persona"]),
            "draft_opo_section": lambda a: self.draft_opo_section(a["case_id"], a["section"], a["sentences_json"]),
            "validate_draft": lambda a: self.validate_draft_tool(a["case_id"], a["sentences_json"], a.get("customer_facing", "false")),
        }
        if name in extra:
            return extra[name](args)
        return super().call(name, args)
