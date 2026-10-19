"""Structural tests for the honest look-alike personas (RED team side)."""
import numpy as np
import polars as pl

from redteam.world import World


def _run(fn, **kw):
    w = World(rng=np.random.default_rng(11), banks=["B1", "B2", "B3"])
    fn(w, **kw)
    return pl.DataFrame(w.tx), pl.DataFrame(w.clients), pl.DataFrame(w.labels)


def _ids(lab, persona):
    sub = lab.filter(pl.col("persona") == persona)
    assert (sub["label"] == "honest").all() or (sub["label"] == "organiser").all()
    return sub["client_id"].unique().to_list()


def test_migrant_remit():
    from redteam.lookalikes.migrant_remit import plant_migrant_remit

    tx, cl, lab = _run(plant_migrant_remit, n=5)
    ids = _ids(lab, "migrant_remit")
    assert len(ids) == 5
    for c in ids:
        t = tx.filter(pl.col("client_id") == c)
        r = t.filter(pl.col("direction") == "remit_out")
        assert r.height >= 3 and r["counterparty_token"].n_unique() == 1  # same recipient
        assert r["amount_czk"].std() / r["amount_czk"].mean() < 0.1  # stable amounts
        assert t.filter(pl.col("direction") == "in").height >= 2  # funded by recurring income


def test_students_rent():
    from redteam.lookalikes.students_rent import plant_students_rent

    tx, cl, lab = _run(plant_students_rent, n=4)
    ids = _ids(lab, "students_rent")
    assert len(ids) == 4
    for c in ids:
        t = tx.filter(pl.col("client_id") == c)
        i, o = t.filter(pl.col("direction") == "in"), t.filter(pl.col("direction") != "in")
        assert i["counterparty_token"].n_unique() >= 3
        assert o.height >= 1 and 0.9 <= o["amount_czk"].sum() / i["amount_czk"].sum() <= 1.0001
        assert i["amount_czk"].sum() < 100000


def test_second_hand_seller():
    from redteam.lookalikes.second_hand_seller import plant_second_hand_seller

    tx, cl, lab = _run(plant_second_hand_seller, n=5)
    for c in _ids(lab, "second_hand_seller"):
        i = tx.filter((pl.col("client_id") == c) & (pl.col("direction") == "in"))
        assert i.height >= 10 and i["counterparty_token"].n_unique() >= 8 and i["amount_czk"].max() <= 3500


def test_group_collection():
    from redteam.lookalikes.group_collection import plant_group_collection

    tx, cl, lab = _run(plant_group_collection, n=4)
    ids = _ids(lab, "group_collection")
    assert len(ids) == 4
    for c in ids:
        t = tx.filter(pl.col("client_id") == c)
        i, o = t.filter(pl.col("direction") == "in"), t.filter(pl.col("direction") != "in")
        assert i["counterparty_token"].n_unique() >= 10 and o.height == 1
        assert 0.9 <= o["amount_czk"][0] / i["amount_czk"].sum() <= 1.0001


def test_middleman_cohost():
    from redteam.lookalikes.middleman_cohost import plant_middleman_cohost

    tx, cl, lab = _run(plant_middleman_cohost, n=3)
    for c in _ids(lab, "middleman_cohost"):
        t = tx.filter(pl.col("client_id") == c)
        i, o = t.filter(pl.col("direction") == "in"), t.filter(pl.col("direction") != "in")
        assert i.height >= 4 and o["counterparty_token"].n_unique() == 1  # always the same host
        k = 1 - o["amount_czk"].sum() / i["amount_czk"].sum()
        assert 0.08 <= k <= 0.16


def test_freelancer():
    from redteam.lookalikes.freelancer import plant_freelancer

    tx, cl, lab = _run(plant_freelancer, n=4)
    for c in _ids(lab, "freelancer"):
        t = tx.filter(pl.col("client_id") == c)
        i = t.filter(pl.col("direction") == "in")
        assert 2 <= i["counterparty_token"].n_unique() <= 4 and i["amount_czk"].min() >= 20000
        assert t.filter(pl.col("direction") != "in").height >= 5


def test_fundraiser():
    from redteam.lookalikes.fundraiser import plant_fundraiser

    tx, cl, lab = _run(plant_fundraiser, n=3)
    ids = _ids(lab, "fundraiser")
    assert len(ids) == 3
    for c in ids:
        t = tx.filter(pl.col("client_id") == c)
        i, o = t.filter(pl.col("direction") == "in"), t.filter(pl.col("direction") != "in")
        assert i["counterparty_token"].n_unique() >= 15 and i["amount_czk"].max() <= 5000
        assert o.height == 1 and o["amount_czk"][0] >= 0.9 * i["amount_czk"].sum()
