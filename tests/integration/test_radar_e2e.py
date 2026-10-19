"""Integration: three bank nodes, planted shared exits; PSI result must equal the plain cross-bank match, and no plaintext token or
client id may appear in anything that crossed a node boundary."""
import json

from radar.guards import Guards
from radar.sessions import BankNode, run_radar

G = Guards({"min_set_size": 5, "max_tokens": 5000, "max_sessions_per_hour": 50, "max_unscored_share": 0.2})


def node(bank, groups):
    cands, rar, stats = [], {}, {}
    for ref, toks, lag, ret in groups:
        for t in toks:
            cands.append({"token": t, "cand_ref": ref, "score": 0.6})
            rar[t] = 0.5
        stats[ref] = {"lag_median_h": lag, "retention_median": ret}
    return BankNode(bank, cands, rar, stats)


def test_psi_clusters_and_no_plaintext_on_wire():
    def filler(b):   # 6 unique tokens per bank, never shared
        return [(f"{b}-f{i}", [f"SECRET-{b}-{i}"], 8.0 + i, 0.0) for i in range(6)]

    n1 = node("B1", [("a1", ["EXIT-1", "EXIT-2"], 2.5, 0.08), ("a2", ["EXIT-1"], 2.4, 0.08)] + filler("B1"))
    n2 = node("B2", [("b1", ["EXIT-1", "EXIT-2"], 2.6, 0.08), ("b2", ["EXIT-2"], 2.5, 0.08)] + filler("B2"))
    n3 = node("B3", [("c1", ["EXIT-2"], 2.4, 0.08)] + filler("B3"))
    res = run_radar([n1, n2, n3], G, epoch_key=b"epoch-1")
    disclosed = [c for c in res.clusters if c["disclosed"]]
    assert len(disclosed) == 1 and set(disclosed[0]["banks"]) == {"B1", "B2", "B3"} and len(disclosed[0]["candidates"]) == 5
    assert disclosed[0]["same_hand_global"] is True
    assert res.exposure["raw_records_exposed"] == 0 and res.exposure["bytes_exchanged"] > 0
    wire = json.dumps(res.wire)
    for forbidden in ("EXIT-1", "EXIT-2", "SECRET-"):
        assert forbidden not in wire
    pm = disclosed[0]["post_match"]["B1"]
    assert set(pm) == {"cluster_id", "n_other_banks", "n_other_candidates", "matched_tokens", "lag_ret_concentration"}
    assert pm["n_other_banks"] == 2 and pm["n_other_candidates"] == 3


def test_tiny_submission_refused():
    n1 = node("B1", [("a1", ["EXIT-1"], 2.5, 0.08)])
    n2 = node("B2", [("b1", ["EXIT-1"], 2.5, 0.08)] + [(f"b{i}", [f"T{i}"], 3.0, 0.0) for i in range(6)])
    res = run_radar([n1, n2], G, epoch_key=b"e")
    assert "B1" in res.refused and res.clusters == []
