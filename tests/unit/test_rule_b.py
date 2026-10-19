from datetime import UTC, datetime

import polars as pl

from node.rules.rule_b import rule_b

CFG = {"min_amount_hr": 10000.0, "pep_outgoing_min": 100000.0}
HR = {"IR", "KP"}


def _tx(rows):
    # (tx_id, client_id, amount, direction, payer_country, payee_country)
    return pl.DataFrame({"tx_id": [r[0] for r in rows], "client_id": [r[1] for r in rows],
                         "amount_czk": [float(r[2]) for r in rows], "direction": [r[3] for r in rows],
                         "payer_country": [r[4] for r in rows], "payee_country": [r[5] for r in rows],
                         "ts": [datetime(2026, 7, 1, tzinfo=UTC)] * len(rows)})


def _cl(rows):  # (client_id, country, pep)
    return pl.DataFrame({"client_id": [r[0] for r in rows], "client_country": [r[1] for r in rows], "pep": [r[2] for r in rows]})


def test_hr_country_over_threshold_fires_per_tx():
    tx = _tx([("T1", "K1", 15000, "out", "CZ", "IR"), ("T2", "K1", 9000, "out", "CZ", "IR"), ("T3", "K1", 50000, "out", "CZ", "DE")])
    out = rule_b(tx, _cl([("K1", "CZ", False)]), HR, CFG)
    assert out["tx_id"].to_list() == ["T1"] and out["alert_type"].to_list() == ["B"]
    assert out["reason"].to_list() == ["high_risk_country"]


def test_client_country_on_list_counts():
    tx = _tx([("T1", "K1", 20000, "in", "CZ", "CZ")])
    assert rule_b(tx, _cl([("K1", "KP", False)]), HR, CFG).height == 1


def test_pep_outgoing_over_100k():
    tx = _tx([("T1", "K1", 150000, "out", "CZ", "DE"), ("T2", "K1", 150000, "in", "DE", "CZ"),
              ("T3", "K1", 150000, "remit_out", "CZ", "FR"), ("T4", "K1", 90000, "out", "CZ", "DE")])
    out = rule_b(tx, _cl([("K1", "CZ", True)]), HR, CFG)
    assert sorted(out["tx_id"].to_list()) == ["T1", "T3"] and set(out["reason"].to_list()) == {"pep_large_outgoing"}


def test_non_pep_same_amount_no_alert():
    tx = _tx([("T1", "K1", 150000, "out", "CZ", "DE")])
    assert rule_b(tx, _cl([("K1", "CZ", False)]), HR, CFG).height == 0


def test_one_alert_per_tx_when_both_conditions_hold():
    tx = _tx([("T1", "K1", 150000, "out", "CZ", "IR")])
    out = rule_b(tx, _cl([("K1", "CZ", True)]), HR, CFG)
    assert out.height == 1 and out["reason"][0] == "high_risk_country+pep_large_outgoing"
