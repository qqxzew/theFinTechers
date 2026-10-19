import random

import pytest

from node.tokens.export import export_candidates, weak_score
from radar.clustering import build_clusters
from radar.significance import adjusted_minus_log10, bank_tail, token_p


def test_more_evidence_is_more_significant_and_popular_tokens_are_discounted():
    base = token_p([(2, 1000, 5, 100), (2, 1000, 5, 100)])
    assert token_p([(3, 1000, 5, 100), (3, 1000, 5, 100)]) < base                      # more candidates behind the token
    assert token_p([(2, 1000, 5, 100), (2, 1000, 5, 100), (2, 1000, 5, 100)]) < base    # more banks
    assert token_p([(2, 1000, 50, 100), (2, 1000, 50, 100)]) > base                     # popular token: same count, weaker evidence
    assert bank_tail(1, 1000, 1, 100) == pytest.approx(0.1, rel=1e-6)                   # one of 100 random picks out of 1000 touches a K=1 token
    assert adjusted_minus_log10(1e-6, 1000) == pytest.approx(3.0)


def _rows(banks, shared_x, k, n_elig, n_cands, token="T"):
    out = []
    for b in banks:
        for i in range(shared_x):
            out.append({"token_id": token, "bank_id": b, "cand_ref": f"{b}{i}", "rarity": 0.5, "deg": k, "n_eligible": n_elig, "n_cands": n_cands})
    return out


def test_cluster_significance_gate_withholds_chance_overlaps_only():
    strong = build_clusters(_rows(["B1", "B2", "B3"], 3, 3, 1000, 60), n_tests=3000, min_significance=2.0)[0]
    assert strong["disclosed"] and strong["significance"] >= 2.0 and 0 < strong["x_score"] <= 1
    chance = build_clusters(_rows(["B1", "B2"], 2, 400, 1000, 600) + _rows(["B1"], 1, 400, 1000, 600, token="U"), n_tests=3000, min_significance=2.0)
    assert all(not c["disclosed"] for c in chance)                       # >= 2 banks and >= 3 candidates, but expected by chance
    no_stats = build_clusters([{k: v for k, v in r.items() if k not in ("deg", "n_eligible", "n_cands")} for r in _rows(["B1", "B2"], 2, 4, 10, 10)])
    assert no_stats[0]["significance"] is None and no_stats[0]["disclosed"]   # without counts the master-prompt rule alone applies


def test_null_calibration_random_overlap_is_rarely_significant():
    """Banks export RANDOM candidates over a shared pool of low-degree tokens: the family-wise false-alarm rate must stay below ~1 %."""
    rng = random.Random(0)
    false_alarms = 0
    sims = 150
    for _ in range(sims):
        banks, n_tests = {}, 0
        for b in ("B1", "B2", "B3"):
            n_elig, n_cands = 600, 60
            clients = [rng.sample(range(300), rng.randint(1, 3)) for _ in range(n_elig)]
            deg: dict[int, int] = {}
            for toks in clients:
                for t in toks:
                    deg[t] = deg.get(t, 0) + 1
            chosen = rng.sample(range(n_elig), n_cands)
            by_tok: dict[int, list[int]] = {}
            for ci in chosen:
                for t in clients[ci]:
                    by_tok.setdefault(t, []).append(ci)
            banks[b] = (by_tok, deg, n_elig, n_cands)
            n_tests += len(by_tok)
        rows = []
        for t in range(300):
            holders = [b for b, (bt, *_rest) in banks.items() if t in bt]
            if len(holders) >= 2:
                for b in holders:
                    bt, deg, n_elig, n_cands = banks[b]
                    rows += [{"token_id": str(t), "bank_id": b, "cand_ref": f"{b}{ci}", "rarity": 0.5, "deg": deg[t], "n_eligible": n_elig, "n_cands": n_cands}
                             for ci in bt[t]]
        if any(c["significance"] is not None and c["significance"] >= 2.0 for c in build_clusters(rows, n_tests=n_tests)):
            false_alarms += 1
    assert false_alarms <= 3, false_alarms      # nominal <= 1 % of 150 simulations (Bonferroni is conservative)


class _C:
    def __init__(self, cid, route="mule_review"):
        self.client_id, self.route = cid, route


def test_weak_band_is_a_bounded_fraction_and_never_the_whole_base():
    feats = {f"K{i}": {"exit_tokens_low": [f"X{i}"], "n_in": 3, "drained_24h_share": i / 100, "share_low": 1.0} for i in range(100)}
    strong_case = _C("K5")
    rows = export_candidates([strong_case], feats, {"K5": 0.5}, b"s", {"min_prob": 0.05, "weak_top_frac": 0.10})
    weak = {r["cand_ref"] for r in rows if r["band"] == "weak"}
    assert len(weak) == 10 and len({r["cand_ref"] for r in rows if r["band"] == "strong"}) == 1
    top_weak = sorted(feats, key=lambda c: -weak_score(feats[c]))[:11]
    assert "K99" in top_weak and "K0" not in top_weak
    none = export_candidates([strong_case], feats, {"K5": 0.5}, b"s", {"min_prob": 0.05, "weak_top_frac": 0.0})
    assert {r["band"] for r in none} == {"strong"}
