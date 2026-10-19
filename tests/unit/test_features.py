from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from node.features.cycles import inflow_cycles
from node.features.degree import counterparty_degree
from node.features.hours import active_hour_profile
from node.features.shares import outflow_shares
from node.features.turnover import max_window_sums

T0 = datetime(2026, 7, 5, 8, 0, tzinfo=UTC)


def _tx(rows):  # (client, hours_offset, amount, direction, cp)
    return pl.DataFrame({"client_id": [r[0] for r in rows], "ts": [T0 + timedelta(hours=r[1]) for r in rows],
                         "amount_czk": [float(r[2]) for r in rows], "direction": [r[3] for r in rows],
                         "counterparty_token": [r[4] for r in rows]})


def test_degree_counts_distinct_clients():
    tx = _tx([("K1", 0, 1, "out", "X"), ("K1", 1, 1, "out", "X"), ("K2", 0, 1, "in", "X"), ("K3", 0, 1, "in", "Y")])
    d = counterparty_degree(tx).sort("counterparty_token")
    assert d.columns == ["counterparty_token", "degree"]
    assert d["degree"].to_list() == [2, 1]


def test_outflow_shares():
    tx = _tx([("K1", 0, 100, "in", "S"), ("K1", 1, 30, "out", "RARE"), ("K1", 2, 50, "remit_out", "POP"), ("K1", 3, 20, "out", "MID")])
    deg = pl.DataFrame({"counterparty_token": ["S", "RARE", "POP", "MID"], "degree": [5, 2, 150, 10]})
    r = outflow_shares(tx, deg, rare_max=3, popular_min=100).row(0, named=True)
    assert r["client_id"] == "K1" and r["out_total"] == 100
    assert r["share_rare"] == pytest.approx(0.3) and r["share_popular"] == pytest.approx(0.5) and r["share_mid"] == pytest.approx(0.2)


def test_max_window_sums():
    tx = _tx([("K1", 0, 10, "in", "A"), ("K1", 0.5, 20, "in", "B"), ("K1", 10, 5, "in", "C"), ("K1", 0.2, 7, "out", "D")])
    r = max_window_sums(tx, [1, 24]).row(0, named=True)
    assert r["in_max_1h"] == 30 and r["in_max_24h"] == 35 and r["out_max_1h"] == 7 and r["out_max_24h"] == 7


def test_inflow_cycles_lag_and_retention():
    # two inflows 1h apart (one cycle, total 100); outflows of 90 at +3h after the last inflow -> retention 0.10, lag 3h
    tx = _tx([("K1", 0, 40, "in", "A"), ("K1", 1, 60, "in", "B"), ("K1", 4, 90, "out", "X")])
    c = inflow_cycles(tx, gap_h=6, out_window_h=24)
    assert c.height == 1
    r = c.row(0, named=True)
    assert r["client_id"] == "K1" and r["in_amount"] == 100 and r["out_amount"] == 90
    assert r["retention"] == pytest.approx(0.10) and r["lag_h"] == pytest.approx(3.0)


def test_inflow_cycles_split_on_gap_and_no_double_assign():
    tx = _tx([("K1", 0, 100, "in", "A"), ("K1", 2, 100, "out", "X"), ("K1", 20, 100, "in", "B"), ("K1", 22, 100, "out", "Y")])
    c = inflow_cycles(tx, gap_h=6, out_window_h=24).sort("cycle_id")
    assert c.height == 2 and c["out_amount"].to_list() == [100, 100] and c["retention"].to_list() == [0, 0]


def test_active_hour_profile_normalised_and_prague_local():
    # 08:00 UTC on 5 Jul 2026 = 10:00 Prague (CEST)
    tx = _tx([("K1", 0, 1, "out", "A"), ("K1", 0, 1, "out", "B"), ("K1", 1, 1, "out", "C"), ("K1", 1, 1, "in", "D")])
    r = active_hour_profile(tx).row(0, named=True)
    assert r["client_id"] == "K1" and len(r["hour_hist"]) == 24 and sum(r["hour_hist"]) == pytest.approx(1.0)
    assert r["hour_hist"][10] == pytest.approx(0.5) and r["hour_hist"][11] == pytest.approx(0.5)
