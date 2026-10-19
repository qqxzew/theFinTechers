"""Detector unit tests on hand-built feature dicts. Each detector has a positive case and an honest look-alike that must NOT fire."""

from common.schemas import Signal

CTX = {"cfg": {
    "D1": {"inflow_min": 100000.0, "drained_min": 0.8, "tight_lag_iqr_h": 1.5, "min_cycles_repeat": 2, "min_score": 0.5},
    "D2": {"max_days": 60, "max_life_events": 3, "min_big": 100000.0, "drained_min": 0.9},
    "D3": {"gap_mult": 3.0},
    "D4": {"min_rare_senders": 8, "min_avg_in": 5000.0, "min_in_total": 50000.0},
    "D5": {"min_share_rare": 0.5, "max_recurring": 0.3, "max_popular_in": 0.3, "min_out": 50000.0},
    "D7": {"min_cycles": 3, "tol": 0.015, "min_k": 0.01},
    "D8": {"band": 0.1, "min_count": 3, "min_share": 0.3},
}, "pileup_thresholds": [10000.0]}

NORMAL = dict(
    client_id="K1", bank_id="B1", days_since_contract=1200.0, contract_form="in person", pep=False, client_type="natural person",
    aml_risk="low", n_in=30, n_out=40, in_total=80000.0, out_total=78000.0, n_senders=20, n_senders_rare=0, n_exits=20,
    exit_tokens_rare=[], share_rare=0.0, share_mid=0.2, share_popular=0.8, popular_inflow_share=0.9,
    recurring_income_share=0.9, reciprocity_share=0.1, max_single_in=9000.0, big_in_amount=9000.0, big_in_sender_degree=500,
    drained_24h_share=0.1, life_events_before_big=20, in_max_24h=15000.0, out_max_24h=15000.0, n_cycles=3,
    cycle_retentions=[0.3, 0.1, 0.5], cycle_lags_h=[8.0, 12.0, 3.0], retention_median=0.3, retention_iqr=0.2,
    lag_median_h=8.0, lag_iqr_h=4.5, expected_monthly=100000.0, july_total=158000.0, inflow_share_of_volume=0.5,
    out_amounts=[1500.0] * 40, life_payment_share=0.8, top_exit_share=0.05,
)


def F(**kw):
    return {**NORMAL, **kw}


def ids(sigs):
    return [s.detector_id for s in sigs]


def test_normal_client_fires_nothing():
    from node.detectors import ALL_DETECTORS

    for d in ALL_DETECTORS:
        assert d.detect(F(), CTX) == [], d.DETECTOR_ID


def test_d1_flow_through_plus():
    from node.detectors import d1_flow_through as d

    bad = F(in_max_24h=250000.0, drained_24h_share=0.95, n_senders=6, n_senders_rare=6, share_rare=0.9, n_cycles=3, lag_iqr_h=0.5,
            popular_inflow_share=0.0, recurring_income_share=0.0)
    s = d.detect(bad, CTX)
    assert len(s) == 1 and isinstance(s[0], Signal) and s[0].detector_id == "D1" and 0.5 <= s[0].score <= 1
    assert s[0].client_id == "K1" and "in_max_24h" in s[0].evidence and s[0].explanation_template_key
    # honest: a business receiving big inflows and paying suppliers, but from popular/recurring payers and popular exits
    honest = F(in_max_24h=250000.0, drained_24h_share=0.95, n_senders=6, n_senders_rare=0, share_rare=0.0, popular_inflow_share=0.9,
               recurring_income_share=0.9, n_cycles=1, lag_iqr_h=6.0)
    assert d.detect(honest, CTX) == []


def test_d2_day_zero():
    from node.detectors import d2_day_zero as d

    bad = F(days_since_contract=10.0, life_events_before_big=1, big_in_amount=300000.0, drained_24h_share=0.97, big_in_sender_degree=1,
            contract_form="distant form", max_single_in=300000.0)
    s = d.detect(bad, CTX)
    assert len(s) == 1 and s[0].detector_id == "D2"
    in_person = d.detect({**bad, "contract_form": "in person"}, CTX)
    assert in_person and in_person[0].score < s[0].score  # form is a modifier, not a verdict
    # honest: new client who receives salary-sized money and keeps it (not drained)
    assert d.detect(F(days_since_contract=10.0, life_events_before_big=1, big_in_amount=300000.0, drained_24h_share=0.2), CTX) == []
    # honest: old client with a big in/out
    assert d.detect(F(days_since_contract=900.0, big_in_amount=300000.0, drained_24h_share=0.97, life_events_before_big=1), CTX) == []


def test_d3_profile_discrepancy_plus():
    from node.detectors import d3_profile_gap as d

    s = d.detect(F(july_total=500000.0, inflow_share_of_volume=0.8), CTX)
    assert len(s) == 1 and s[0].detector_id == "D3" and "inflow_driven" in s[0].explanation_template_key
    s2 = d.detect(F(july_total=500000.0, inflow_share_of_volume=0.2), CTX)
    assert "spending_driven" in s2[0].explanation_template_key
    assert d.detect(F(july_total=250000.0), CTX) == []  # 2.5x only


def test_d4_new_sender_fan_in():
    from node.detectors import d4_fan_in as d

    bad = F(n_in=14, n_senders=14, n_senders_rare=12, in_total=140000.0)
    assert ids(d.detect(bad, CTX)) == ["D4"]
    # honest: second-hand seller with many small item-like sales
    seller = F(n_in=25, n_senders=24, n_senders_rare=22, in_total=40000.0)
    assert d.detect(seller, CTX) == []


def test_d5_rare_exit_concentration():
    from node.detectors import d5_rare_exit as d

    bad = F(share_rare=0.9, recurring_income_share=0.05, popular_inflow_share=0.0, out_total=120000.0)
    assert ids(d.detect(bad, CTX)) == ["D5"]
    # honest: sends to a rare account (a relative) but is funded by recurring salary
    assert d.detect(F(share_rare=0.9, recurring_income_share=0.95, popular_inflow_share=0.9, out_total=120000.0), CTX) == []


def test_d7_fixed_skim():
    from node.detectors import d7_fixed_skim as d

    bad = F(n_cycles=5, cycle_retentions=[0.08, 0.081, 0.079, 0.08, 0.082], retention_median=0.08)
    s = d.detect(bad, CTX)
    assert len(s) == 1 and s[0].detector_id == "D7"
    assert d.detect(F(n_cycles=5, cycle_retentions=[0.08, 0.2, 0.01, 0.5, 0.3], retention_median=0.2), CTX) == []  # unstable
    assert d.detect(F(n_cycles=2, cycle_retentions=[0.08, 0.08], retention_median=0.08), CTX) == []  # too few cycles
    assert d.detect(F(n_cycles=5, cycle_retentions=[0.0] * 5, retention_median=0.0), CTX) == []  # nothing retained


def test_d8_structuring_and_threshold_discovery():
    from node.detectors import d8_structuring as d

    bad = F(out_amounts=[9600.0, 9800.0, 9900.0, 9700.0, 500.0, 800.0])
    assert ids(d.detect(bad, CTX)) == ["D8"]
    assert d.detect(F(out_amounts=[9600.0, 500.0, 800.0, 1200.0, 3000.0]), CTX) == []
    # empirical threshold discovery: a pile-up just below 10000 vs almost nothing just above
    amounts = [9500.0 + i for i in range(450)] + [10050.0 + 10 * i for i in range(10)] + [1000.0 + 7 * i for i in range(3000)]
    th = d.find_pileup_thresholds(amounts)
    assert any(abs(t - 10000.0) <= 1.0 for t in th)
    flat = [100.0 + 3 * i for i in range(3000)]
    assert d.find_pileup_thresholds(flat) == []
