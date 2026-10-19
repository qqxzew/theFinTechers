from tests.unit.test_detectors import F

CTX = {"cfg": {
    "E1": {"min_count": 3, "max_amount_cv": 0.1, "min_recurring": 0.5},
    "E2": {"min_share": 0.3},
    "E3": {"min_recurring": 0.7},
    "E4": {"min_popular_in": 0.7, "popular_sender_degree": 100},
    "E5": {"min_reciprocity": 0.4},
    "VICTIM": {"max_single_in": 50000.0, "min_out": 100000.0, "min_out_in_ratio": 3.0, "min_share_rare": 0.5},
    "E6": {"min_top_exit": 0.85, "max_single_in": 9000.0, "min_senders": 3, "min_life": 0.4, "min_tenure": 180, "max_cycles": 2},
    "E7": {"min_top_exit": 0.95, "min_k": 0.06, "max_k": 0.18, "min_in": 4, "min_life": 0.4, "min_tenure": 180},
    "E8": {"max_senders": 5, "max_drained": 0.6, "min_life": 0.5, "min_tenure": 365},
}}


def test_e1_mom():
    from node.innocence import e1_mom as m

    s = m.detect(F(remit_top_recipient_count=4, remit_amount_cv=0.02, recurring_income_share=0.9), CTX)
    assert len(s) == 1 and s[0].exculpatory is True and s[0].detector_id == "E1" and s[0].client_id == "K1"
    assert 0.7 <= s[0].score <= 1.0 and "remit_top_recipient_count" in s[0].evidence
    assert m.detect(F(remit_top_recipient_count=1, remit_amount_cv=None, recurring_income_share=0.9), CTX) == []
    assert m.detect(F(remit_top_recipient_count=4, remit_amount_cv=0.5, recurring_income_share=0.9), CTX) == []
    assert m.detect(F(remit_top_recipient_count=4, remit_amount_cv=0.02, recurring_income_share=0.1), CTX) == []


def test_e2_life():
    from node.innocence import e2_life as m

    s = m.detect(F(share_popular=0.5), CTX)
    assert len(s) == 1 and s[0].exculpatory and s[0].detector_id == "E2"
    assert m.detect(F(share_popular=0.1), CTX) == []


def test_e3_source_of_funds():
    from node.innocence import e3_source as m

    s = m.detect(F(recurring_income_share=0.8), CTX)
    assert len(s) == 1 and s[0].exculpatory and s[0].detector_id == "E3"
    assert m.detect(F(recurring_income_share=0.2), CTX) == []


def test_e4_institutional():
    from node.innocence import e4_institutional as m

    assert m.detect(F(popular_inflow_share=0.8), CTX)[0].detector_id == "E4"
    assert m.detect(F(popular_inflow_share=0.1, big_in_sender_degree=2), CTX) == []
    assert m.detect(F(popular_inflow_share=0.1, big_in_sender_degree=500), CTX)[0].exculpatory is True


def test_e5_reciprocity():
    from node.innocence import e5_reciprocity as m

    assert m.detect(F(reciprocity_share=0.5), CTX)[0].detector_id == "E5"
    assert m.detect(F(reciprocity_share=0.1), CTX) == []


def test_victim_route():
    from node.innocence import victim as m

    s = m.detect(F(max_single_in=8000.0, in_total=30000.0, out_total=400000.0, share_rare=0.9), CTX)
    assert len(s) == 1 and s[0].detector_id == "VICTIM" and s[0].exculpatory is False  # routes the case, it does not exonerate
    assert m.detect(F(max_single_in=300000.0, in_total=300000.0, out_total=290000.0), CTX) == []
    assert m.detect(F(max_single_in=8000.0, in_total=100000.0, out_total=120000.0), CTX) == []
    assert m.detect(F(max_single_in=8000.0, in_total=30000.0, out_total=400000.0, share_rare=0.0), CTX) == []  # big spending to popular accounts


def test_e6_pooling_one_off():
    from node.innocence import e6_pooling as m

    ok = F(top_exit_share=0.95, max_single_in=3000.0, n_senders=12, life_payment_share=0.7, days_since_contract=900.0, n_cycles=1)
    s = m.detect(ok, CTX)
    assert len(s) == 1 and s[0].exculpatory and s[0].detector_id == "E6"
    for bad in (dict(life_payment_share=0.0), dict(max_single_in=60000.0), dict(days_since_contract=20.0), dict(top_exit_share=0.3),
                dict(n_senders=1), dict(n_cycles=5)):
        assert m.detect({**ok, **bad}, CTX) == [], bad


def test_e7_cohost():
    from node.innocence import e7_cohost as m

    ok = F(top_exit_share=1.0, retention_median=0.12, n_in=6, life_payment_share=0.6, days_since_contract=700.0)
    assert m.detect(ok, CTX)[0].detector_id == "E7"
    for bad in (dict(top_exit_share=0.5), dict(retention_median=0.3), dict(retention_median=0.01), dict(n_in=2), dict(life_payment_share=0.0),
                dict(days_since_contract=30.0)):
        assert m.detect({**ok, **bad}, CTX) == [], bad


def test_e8_earner():
    from node.innocence import e8_earner as m

    ok = F(n_senders=3, drained_24h_share=0.2, life_payment_share=0.8, days_since_contract=900.0)
    assert m.detect(ok, CTX)[0].detector_id == "E8"
    for bad in (dict(n_senders=9), dict(drained_24h_share=0.95), dict(life_payment_share=0.1), dict(days_since_contract=100.0)):
        assert m.detect({**ok, **bad}, CTX) == [], bad
