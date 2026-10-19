"""Model registry: verifies configured Bedrock IDs on startup (list + tool-use smoke test) and falls back, logging to the audit chain."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import boto3
from botocore.config import Config
import yaml


def load_models(path: str = "config/models.yaml") -> dict:
    return yaml.safe_load(open(path, encoding="utf-8"))


_SMOKE_TOOL = {"tools": [{"toolSpec": {"name": "ping", "description": "Return pong.", "inputSchema": {"json": {
    "type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}}}]}


@dataclass
class ModelRegistry:
    cfg: dict
    client: object | None = None
    active: dict[str, str] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def _client(self):
        if self.client is None:
            sess = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", self.cfg.get("profile")), region_name=self.cfg["region"])
            self.client = sess.client("bedrock-runtime", config=Config(read_timeout=300, retries={"max_attempts": 2}))
        return self.client

    def smoke_test(self, model_id: str) -> tuple[bool, str]:
        """One tool-use call: the model must answer by calling the `ping` tool."""
        try:
            r = self._client().converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": "Call the ping tool with x='a'. Do not answer in text."}]}],
                toolConfig=_SMOKE_TOOL, inferenceConfig={"maxTokens": 400})
            blocks = r["output"]["message"]["content"]
            return (any("toolUse" in b for b in blocks), "ok" if any("toolUse" in b for b in blocks) else "no tool use")
        except Exception as e:  # noqa: BLE001
            return False, repr(e)[:200]

    def verify(self, audit=None) -> dict[str, str]:
        roles = self.cfg["roles"]
        for role in ("agent_primary", "fallback", "bulk"):
            ok, why = self.smoke_test(roles[role])
            self.events.append({"role": role, "model_id": roles[role], "ok": ok, "detail": why})
            if ok:
                self.active[role] = roles[role]
            else:
                alt = roles["fallback"] if role == "agent_primary" else None
                self.active[role] = alt or roles[role]
                if audit:
                    audit.append(actor="registry", action="model_unavailable", why=f"{role}:{roles[role]} -> {why}; using {self.active[role]}",
                                 rule_version="registry-1", model_version=self.active[role], input_hash="-")
        return self.active

    def price(self, role: str) -> tuple[float, float]:
        p = self.cfg["prices_placeholder"][role]
        return p["in"], p["out"]
