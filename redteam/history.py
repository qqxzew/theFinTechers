"""30 days of honest history before the evaluation month (collector worlds). ISOLATED package (red team).

Every honest/background client's July activity is cloned 30 days back (decoy activity is planted separately per month). Incoming
payments from rare senders get a month-specific sender token so that one-off payers do not become 'recurring' senders by construction.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from redteam.world import World


def clone_history(w: World, days: int = 30) -> int:
    honest = {r["client_id"] for r in w.labels if r["label"] in ("honest", "background")}
    touch: dict[str, set] = defaultdict(set)
    for r in w.tx:
        touch[r["counterparty_token"]].add(r["client_id"])
    new = []
    for r in w.tx:
        if r["client_id"] not in honest or r["tx_id"] in w.decoy_tx or r["ts"] < w.START:
            continue
        ts = r["ts"] - timedelta(days=days)
        if ts >= w.START:
            continue
        tok = r["counterparty_token"]
        if r["direction"] == "in" and len(touch[tok]) < 5:
            tok = "H" + tok
        w._n_tx += 1
        new.append({**r, "tx_id": f"RT{w._n_tx:08d}", "ts": ts, "counterparty_token": tok})
    w.tx.extend(new)
    return len(new)
