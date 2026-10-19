from node.detectors.d6_same_hand import detect_group

CTX = {"cfg": {"D6": {"min_cycles": 2, "min_group": 3, "lag_tol_h": 0.75, "ret_tol": 0.02, "hour_cos": 0.8, "min_lift": 3.0, "seed": 0, "baseline_runs": 20}}}


def hist(h):
    v = [0.0] * 24
    v[h] = 1.0
    return v


def row(cid, lag, ret, hour, tokens):
    return {"client_id": cid, "n_cycles": 4, "lag_median_h": lag, "retention_median": ret, "hour_hist": hist(hour), "exit_tokens_low": tokens}


def test_group_with_same_hand_fires():
    gang = [row(f"G{i}", 2.5 + 0.1 * i, 0.08 + 0.002 * i, 19, ["X1", "X2"]) for i in range(5)]
    # honest others: different lag/retention/hours, mostly different exits
    others = [row(f"H{i}", 5 + 3 * i, 0.3 + 0.1 * i, 8 + i, [f"Y{i}"]) for i in range(8)]
    s = detect_group(gang + others, CTX)
    assert sorted(x.client_id for x in s) == [f"G{i}" for i in range(5)]
    assert all(x.detector_id == "D6" and 0.5 <= x.score <= 1 for x in s)


def test_shared_exit_alone_is_not_enough():
    # same exits (e.g. a popular landlord/utility) but different behaviour -> no group
    rows = [row(f"H{i}", 2 + 5 * i, 0.05 + 0.2 * i, 6 + 4 * i, ["U1"]) for i in range(4)]
    assert detect_group(rows, CTX) == []


def test_similar_behaviour_without_shared_exit_is_not_enough():
    rows = [row(f"H{i}", 2.5, 0.08, 19, [f"Z{i}"]) for i in range(5)]
    assert detect_group(rows, CTX) == []
