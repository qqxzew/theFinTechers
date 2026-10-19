"""Token export to the radar: only clients in the configured band, never the whole customer base.

STRONG band: cases with probability >= min_prob on the mule route. WEAK band (weak_top_frac > 0): the top fraction of the bank's clients by a
local pass-through score among those that are not strong - this is what lets the radar collect weak evidence from accounts with no local
signal. The fraction is the privacy/recall knob. cand_ref is a bank-local pseudonym (HMAC of the client id under the bank's secret).
"""
from __future__ import annotations

import hashlib
import hmac


def cand_ref(bank_secret: bytes, client_id: str) -> str:
    return hmac.new(bank_secret, client_id.encode(), hashlib.sha256).hexdigest()[:12]


def weak_score(f: dict) -> float:
    """Local pass-through score 0..1: share of the largest inflow forwarded within 24 h, weighted by the share of outflow to low-degree exits."""
    return float(f.get("drained_24h_share") or 0.0) * (0.5 + 0.5 * float(f.get("share_low") or 0.0))


def export_candidates(cases: list, features: dict[str, dict], probs: dict[str, float], bank_secret: bytes, cfg: dict) -> list[dict]:
    """Return [{'token','cand_ref','score','kind','band'}] for the low-degree exit tokens of every exported candidate."""
    out: list[dict] = []
    strong: set[str] = set()
    for c in cases:
        p = probs[c.client_id]
        if p < cfg["min_prob"] or c.route != "mule_review":
            continue
        strong.add(c.client_id)
        ref = cand_ref(bank_secret, c.client_id)
        for t in features[c.client_id].get("exit_tokens_low") or []:
            out.append({"token": t, "cand_ref": ref, "score": round(p, 4), "kind": "exit", "band": "strong"})
    frac = float(cfg.get("weak_top_frac", 0.0))
    if frac > 0:
        eligible = [(weak_score(f), cid) for cid, f in features.items() if cid not in strong and f.get("exit_tokens_low") and f.get("n_in", 0) >= 1]
        k = int(round(frac * len(features)))
        for s, cid in sorted(eligible, key=lambda x: (-x[0], x[1]))[:k]:
            if s <= 0:
                break
            ref = cand_ref(bank_secret, cid)
            for t in features[cid]["exit_tokens_low"]:
                out.append({"token": t, "cand_ref": ref, "score": round(s, 4), "kind": "exit", "band": "weak"})
    return out
