from datetime import UTC, datetime, timedelta

import pytest

from radar.clustering import build_clusters
from radar.guards import Guards


def row(tok, bank, cand, rarity=0.9):
    return {"token_id": tok, "bank_id": bank, "cand_ref": cand, "rarity": rarity}


def test_cluster_disclosure_rules():
    # cluster 1: 2 banks, 3 candidates sharing token T1 -> disclosed
    # cluster 2: 2 banks but only 2 candidates -> NOT disclosed
    # cluster 3: 1 bank only (can't be produced by PSI, but must not be disclosed)
    rows = [row("T1", "B1", "c1"), row("T1", "B1", "c2"), row("T1", "B2", "c3"),
            row("T2", "B1", "c9"), row("T2", "B2", "c8"),
            row("T3", "B3", "c5"), row("T3", "B3", "c6"), row("T3", "B3", "c7")]
    cl = {frozenset(c["tokens"]): c for c in build_clusters(rows)}
    assert cl[frozenset({"T1"})]["disclosed"] is True
    assert cl[frozenset({"T2"})]["disclosed"] is False
    assert cl[frozenset({"T3"})]["disclosed"] is False
    c = cl[frozenset({"T1"})]
    assert set(c["banks"]) == {"B1", "B2"} and len(c["candidates"]) == 3 and 0 < c["score"] <= 1
    assert len(c["cluster_id"]) == 12


def test_components_merge_through_shared_candidates():
    rows = [row("T1", "B1", "c1"), row("T1", "B2", "c2"), row("T2", "B1", "c1"), row("T2", "B3", "c4"), row("T2", "B3", "c5")]
    out = build_clusters(rows)
    assert len(out) == 1 and set(out[0]["tokens"]) == {"T1", "T2"} and set(out[0]["banks"]) == {"B1", "B2", "B3"}
    assert out[0]["disclosed"] is True


def test_score_monotone_and_deterministic_id():
    small = build_clusters([row("T1", "B1", "c1"), row("T1", "B1", "c2"), row("T1", "B2", "c3")])[0]
    big = build_clusters([row("T1", "B1", "c1"), row("T1", "B1", "c2"), row("T1", "B2", "c3"), row("T1", "B3", "c4"), row("T1", "B3", "c5")])[0]
    common = build_clusters([row("T1", "B1", "c1", 0.1), row("T1", "B1", "c2", 0.1), row("T1", "B2", "c3", 0.1)])[0]
    assert big["score"] > small["score"] > common["score"]
    again = build_clusters([row("T1", "B2", "c3"), row("T1", "B1", "c2"), row("T1", "B1", "c1")])[0]
    assert again["cluster_id"] == small["cluster_id"]


G_CFG = {"min_set_size": 5, "max_tokens": 1000, "max_sessions_per_hour": 3, "max_unscored_share": 0.2}
NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


def sub(n, scored=True):
    return [{"token": f"t{i}", "score": 0.7 if scored else None} for i in range(n)]


def test_guards_accept_normal_and_refuse_bad():
    g = Guards(G_CFG)
    assert g.check("B1", sub(10), NOW).allowed
    d = g.check("B1", sub(3), NOW)
    assert not d.allowed and "min_set_size" in d.reason  # singleton / tiny probes refused
    d = g.check("B2", sub(2000), NOW)
    assert not d.allowed and "max_tokens" in d.reason
    d = g.check("B3", sub(10, scored=False), NOW)
    assert not d.allowed and "unscored" in d.reason
    d = g.check("B4", sub(8) + [{"token": "x", "score": None}, {"token": "y", "score": None}, {"token": "z", "score": None}], NOW)
    assert not d.allowed and "unscored" in d.reason


def test_guards_rate_limit_per_bank_and_hour():
    g = Guards(G_CFG)
    for i in range(3):
        assert g.check("B1", sub(10), NOW + timedelta(minutes=i)).allowed
    d = g.check("B1", sub(10), NOW + timedelta(minutes=5))
    assert not d.allowed and "rate" in d.reason
    assert g.check("B2", sub(10), NOW + timedelta(minutes=5)).allowed  # other bank unaffected
    assert g.check("B1", sub(10), NOW + timedelta(hours=2)).allowed  # window passed
