"""Read-only, case-scoped tools for the copilot agent."""

from __future__ import annotations

import copy
from typing import Any


def _str_schema(properties: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {k: {"type": "string", "description": v} for k, v in properties.items()},
        "required": required,
    }


class CaseTools:
    """Read-only tools over structured case data, scoped to known case ids."""

    def __init__(self, cases: dict[str, dict], rules: dict[str, str]) -> None:
        self.cases = cases
        self.rules = rules
        self.proposals: list[dict[str, Any]] = []

    def _case(self, case_id: str) -> dict:
        if case_id not in self.cases:
            raise KeyError(case_id)
        return self.cases[case_id]

    def get_case(self, case_id: str) -> dict:
        """Return a copy of the full structured case."""
        return copy.deepcopy(self._case(case_id))

    def get_signals(self, case_id: str) -> list[dict]:
        """Return the case's detector signals."""
        return self._case(case_id)["signals"]

    def get_exculpatory(self, case_id: str) -> list[dict]:
        """Return the case's exculpatory findings."""
        return self._case(case_id)["exculpatory"]

    def get_features(self, case_id: str) -> dict:
        """Return a copy of the case's aggregated features."""
        return copy.deepcopy(self._case(case_id)["features"])

    def explain_rule(self, rule_id: str) -> str:
        """Return the rule explanation, or 'not available' if unknown."""
        return self.rules.get(rule_id, "not available")

    def propose_triage(self, case_id: str, triage: str, reason: str) -> dict[str, Any]:
        """Record a non-binding triage proposal; the case itself is never changed."""
        self._case(case_id)
        proposal = {
            "status": "proposal",
            "final": False,
            "case_id": case_id,
            "triage": triage,
            "reason": reason,
        }
        self.proposals.append(proposal)
        return dict(proposal)

    def spec(self) -> dict[str, Any]:
        """Return the Amazon Bedrock Converse toolConfig for these tools."""
        case_id_prop = {"case_id": "Id of the case to read."}
        tools = [
            ("get_case", "Get the full structured case (signals, features, triage context).",
             _str_schema(case_id_prop, ["case_id"])),
            ("get_signals", "Get the detector signals attached to the case.",
             _str_schema(case_id_prop, ["case_id"])),
            ("get_exculpatory", "Get exculpatory findings attached to the case.",
             _str_schema(case_id_prop, ["case_id"])),
            ("get_features", "Get the aggregated case features.",
             _str_schema(case_id_prop, ["case_id"])),
            ("explain_rule", "Get a human-readable explanation of a triage/detection rule.",
             _str_schema({"rule_id": "Id of the rule to explain."}, ["rule_id"])),
            ("propose_triage", "Propose a triage decision for the case (non-binding proposal).",
             _str_schema({"case_id": "Id of the case.", "triage": "Proposed triage label.",
                          "reason": "Reason for the proposal."},
                         ["case_id", "triage", "reason"])),
        ]
        return {
            "tools": [
                {
                    "toolSpec": {
                        "name": name,
                        "description": description,
                        "inputSchema": {"json": schema},
                    }
                }
                for name, description, schema in tools
            ]
        }

    def call(self, name: str, args: dict) -> Any:
        """Dispatch a tool call by name; raise ValueError for unknown tools."""
        handlers = {
            "get_case": lambda a: self.get_case(a["case_id"]),
            "get_signals": lambda a: self.get_signals(a["case_id"]),
            "get_exculpatory": lambda a: self.get_exculpatory(a["case_id"]),
            "get_features": lambda a: self.get_features(a["case_id"]),
            "explain_rule": lambda a: self.explain_rule(a["rule_id"]),
            "propose_triage": lambda a: self.propose_triage(a["case_id"], a["triage"], a["reason"]),
        }
        if name not in handlers:
            raise ValueError(f"unknown tool: {name}")
        return handlers[name](args)
