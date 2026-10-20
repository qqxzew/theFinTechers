"""The evaluation uses a plaintext-equivalent intersection instead of DH-PSI; show that run_radar gives the same clusters and the same wire sizes."""
from __future__ import annotations

from datetime import UTC, datetime

import radar.sessions as rs
from eval.collector_eval import PlainPsiParty
from radar.guards import Guards
from radar.psi.dh_psi import PsiParty
from radar.sessions import BankNode, run_radar


def _nodes():
    shared = [f"XSH{i}" for i in range(6)]
    nodes = []
    for b in ("B1", "B2", "B3"):
        cands = [{"token": t, "cand_ref": f"{b}-{i}", "score": 0.1, "kind": "exit"} for i, t in enumerate(shared[:4])]
        cands += [{"token": f"{b}-own{i}", "cand_ref": f"{b}-o{i}", "score": 0.1, "kind": "exit"} for i in range(6)]
        nodes.append(BankNode(b, cands, {c["token"]: 1.0 for c in cands}, {}, n_eligible=100, deg={c["token"]: 2 for c in cands}))
    return nodes


def test_plain_psi_equals_dh_psi_in_the_radar():
    g = Guards({"min_set_size": 5, "max_tokens": 5000, "max_sessions_per_hour": 20, "max_unscored_share": 0.2})
    now = datetime(2026, 7, 31, tzinfo=UTC)
    real = run_radar(_nodes(), g, b"k", now=now)
    rs.PsiParty = PlainPsiParty
    try:
        g2 = Guards({"min_set_size": 5, "max_tokens": 5000, "max_sessions_per_hour": 20, "max_unscored_share": 0.2})
        plain = run_radar(_nodes(), g2, b"k", now=now)
    finally:
        rs.PsiParty = PsiParty
    strip = lambda r: sorted((c["cluster_id"], tuple(sorted(c["candidates"])), c["disclosed"]) for c in r.clusters)  # noqa: E731
    assert strip(real) == strip(plain) and strip(real)
    assert real.exposure["bytes_exchanged"] == plain.exposure["bytes_exchanged"]
