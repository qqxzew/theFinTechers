from datetime import UTC, datetime, timedelta

import polars as pl

from node.rules.rule_c import rule_c

CFG = {"inflow_threshold": 100000.0, "inflow_window_h": 24, "outflow_window_h": 6, "outflow_share": 0.8,
       "anchor": "threshold_crossing"}
T0 = datetime(2026, 7, 5, 8, 0, tzinfo=UTC)


def _tx(rows):  # (client, hours_offset, amount, direction, cp)
    return pl.DataFrame({"client_id": [r[0] for r in rows], "ts": [T0 + timedelta(hours=r[1]) for r in rows],
                         "amount_czk": [float(r[2]) for r in rows], "direction": [r[3] for r in rows],
                         "counterparty_token": [r[4] for r in rows]})


def test_flow_through_fires():
    tx = _tx([("K1", 0, 60000, "in", "P1"), ("K1", 1, 60000, "in", "P2"), ("K1", 3, 100000, "out", "X1")])
    out = rule_c(tx, CFG)
    assert out["client_id"].to_list() == ["K1"] and out["alert_type"].to_list() == ["C"]
    assert out["inflow_amount"][0] == 120000 and out["outflow_amount"][0] == 100000


def test_outflow_too_slow_no_alert():
    tx = _tx([("K1", 0, 120000, "in", "P1"), ("K1", 7, 120000, "out", "X1")])  # 7h after crossing at 0h
    assert rule_c(tx, CFG).height == 0


def test_outflow_to_payer_does_not_count():
    tx = _tx([("K1", 0, 120000, "in", "P1"), ("K1", 2, 120000, "out", "P1")])
    assert rule_c(tx, CFG).height == 0


def test_below_threshold_no_alert():
    tx = _tx([("K1", 0, 90000, "in", "P1"), ("K1", 1, 90000, "out", "X1")])
    assert rule_c(tx, CFG).height == 0


def test_inflows_outside_24h_not_aggregated():
    tx = _tx([("K1", 0, 60000, "in", "P1"), ("K1", 30, 60000, "in", "P2"), ("K1", 31, 120000, "out", "X1")])
    assert rule_c(tx, CFG).height == 0


def test_anchor_first_inflow_changes_result():
    # crossing at +20h; outflow at +22h. threshold_crossing: window [20,26] has it. first_inflow(0h): window [0,6] misses it.
    tx = _tx([("K1", 0, 60000, "in", "P1"), ("K1", 20, 60000, "in", "P2"), ("K1", 22, 120000, "out", "X1")])
    assert rule_c(tx, CFG).height == 1
    assert rule_c(tx, {**CFG, "anchor": "first_inflow"}).height == 0


def test_remit_out_counts_as_outflow():
    tx = _tx([("K1", 0, 120000, "in", "P1"), ("K1", 2, 120000, "remit_out", "X9")])
    assert rule_c(tx, CFG).height == 1


def test_one_alert_per_client():
    tx = _tx([("K1", 0, 120000, "in", "P1"), ("K1", 2, 120000, "out", "X1"),
              ("K1", 50, 120000, "in", "P3"), ("K1", 52, 120000, "out", "X2")])
    assert rule_c(tx, CFG).height == 1
