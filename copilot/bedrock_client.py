"""Thin Amazon Bedrock Converse wrapper: retries, cost tracking, budget enforcement and audit logging of every model call.

The `client` argument lets tests inject a fake Converse client. Reasoning blocks (Kimi) are never sent back and never stored.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

from botocore.exceptions import ClientError

from copilot.budgets import Budget
from copilot.model_registry import ModelRegistry

RETRYABLE = ("ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException", "InternalServerException")


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


@dataclass
class LLMResult:
    text: str
    tool_uses: list[dict]
    content: list[dict]          # assistant content blocks without reasoning, ready to be appended to the conversation
    usage: dict
    stop_reason: str
    model_id: str
    cost_usd: float
    latency_ms: int


class LLM:
    def __init__(self, registry: ModelRegistry, audit=None, client=None) -> None:
        self.registry = registry
        self.audit = audit
        self.client = client or registry._client()

    def call(self, role: str, system: str, messages: list[dict], tools: dict | None = None, max_tokens: int = 3000,
             budget: Budget | None = None, agent: str = "-", temperature: float | None = None) -> LLMResult:
        model_id = self.registry.active.get(role) or self.registry.cfg["roles"][role]
        if budget:
            budget.check_time()
            budget.charge_step()
        kwargs: dict = {"modelId": model_id, "messages": messages, "system": [{"text": system}],
                        "inferenceConfig": {"maxTokens": max_tokens}}
        if temperature is not None and not model_id.startswith("global.moonshotai"):
            kwargs["inferenceConfig"]["temperature"] = temperature   # Kimi rejects this field
        if tools:
            kwargs["toolConfig"] = tools
        t0 = time.monotonic()
        resp = None
        for attempt in range(6):
            try:
                resp = self.client.converse(**kwargs)
                break
            except ClientError as e:
                if e.response["Error"]["Code"] in RETRYABLE and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise
        assert resp is not None
        content = [b for b in resp["output"]["message"]["content"] if "reasoningContent" not in b]
        text = "".join(b.get("text", "") for b in content)
        uses = [b["toolUse"] for b in content if "toolUse" in b]
        usage = resp.get("usage", {})
        p_in, p_out = self.registry.price(role)
        cost = usage.get("inputTokens", 0) * p_in + usage.get("outputTokens", 0) * p_out
        if self.audit:
            self.audit.append(actor=f"agent:{agent}", action="model_call", why=f"role={role}", rule_version="copilot-1", model_version=model_id,
                              input_hash=sha({"system": system, "messages": messages}), output_hash=sha(content), cost_usd=round(cost, 6),
                              tokens=usage.get("totalTokens", 0))
        if budget:
            budget.charge_usage(usage, p_in, p_out)
        return LLMResult(text, uses, content, usage, resp.get("stopReason", ""), model_id, cost, int((time.monotonic() - t0) * 1000))
