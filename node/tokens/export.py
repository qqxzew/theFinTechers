"""Token export to the radar: only clients in the configured score band, never the whole customer base.

cand_ref is a bank-local pseudonym (HMAC of the client id under the bank's secret); the radar never sees client ids.
"""
from __future__ import annotations

import hashlib
import hmac


def cand_ref(bank_secret: bytes, client_id: str) -> str:
    return hmac.new(bank_secret, client_id.encode(), hashlib.sha256).hexdigest()[:12]


def export_candidates(cases: list, features: dict[str, dict], probs: dict[str, float], bank_secret: bytes, cfg: dict) -> list[dict]:
    """Return [{'token','cand_ref','score'}] for every rare/low-degree exit token of every candidate case in the band."""
    out = []
    for c in cases:
        p = probs[c.client_id]
        if p < cfg["min_prob"] or c.route != "mule_review":
            continue
        ref = cand_ref(bank_secret, c.client_id)
        for t in features[c.client_id].get("exit_tokens_low") or []:
            out.append({"token": t, "cand_ref": ref, "score": round(p, 4)})
    return out
