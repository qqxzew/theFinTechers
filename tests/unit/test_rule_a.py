from datetime import UTC, datetime

import polars as pl

from node.rules.rule_a import rule_a

CFG = {"expected_unit": "monthly", "q2_unit": "quarterly", "daily_share_of_projected": 0.25, "daily_vs_q2_avg_mult": 3.0,
       "single_vs_q2_max_mult": 2.0}


def _tx(rows):
    return pl.DataFrame(
        {"client_id": [r[0] for r in rows], "ts": [datetime(2026, 7, r[1], 12, tzinfo=UTC) for r in rows],
         "amount_czk": [float(r[2]) for r in rows]}
    ).with_columns(pl.col("ts").dt.replace_time_zone("UTC"))


def _clients(rows):
    return pl.DataFrame({"client_id": [r[0] for r in rows], "expected_volume": [float(r[1]) for r in rows],
                         "q2_volume": [float(r[2]) for r in rows], "q2_max": [float(r[3]) for r in rows]})


def test_daily_over_25pct_of_projected_fires():
    tx = _tx([("K1", 3, 30000)])
    cl = _clients([("K1", 100000, 0, 0)])  # inactive in Q2 -> only projected compare
    out = rule_a(tx, cl, CFG)
    assert out["client_id"].to_list() == ["K1"] and out["alert_type"].to_list() == ["A"]
    assert "daily_gt_share_of_projected" in out["reasons"][0]


def test_inactive_q2_below_threshold_no_alert():
    tx = _tx([("K1", 3, 20000)])
    out = rule_a(tx, _clients([("K1", 100000, 0, 0)]), CFG)
    assert out.height == 0


def test_q2_average_multiple_fires():
    # q2 quarterly 9100 -> daily avg 100; daily July 400 > 3*100, projected 1e9 so cond 1 is off
    tx = _tx([("K1", 3, 400)])
    out = rule_a(tx, _clients([("K1", 1e9, 9100, 1e9)]), CFG)
    assert out["reasons"][0] == ["daily_gt_mult_of_q2_avg"]


def test_single_tx_over_2x_q2_max_fires_one_alert_per_client():
    tx = _tx([("K1", 3, 250), ("K1", 4, 250)])
    out = rule_a(tx, _clients([("K1", 1e9, 91000, 100)]), CFG)  # daily avg 1000: cond2 off; 250>2*100 -> cond3
    assert out.height == 1 and out["reasons"][0] == ["single_gt_mult_of_q2_max"]


def test_normal_client_no_alert():
    tx = _tx([("K1", 3, 50), ("K1", 9, 60)])
    assert rule_a(tx, _clients([("K1", 1e9, 91000, 1000)]), CFG).height == 0


def test_daily_sums_all_transactions_in_a_day():
    tx = _tx([("K1", 3, 15000), ("K1", 3, 15000)])  # 30000 in one day > 25% of 100000
    out = rule_a(tx, _clients([("K1", 100000, 0, 0)]), CFG)
    assert out.height == 1
