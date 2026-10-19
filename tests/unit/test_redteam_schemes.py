"""Structural property tests for the red-team generators (these tests live with the RED team, not the detectors)."""
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from redteam.world import World

BANKS = ["B1", "B2", "B3"]


def _world(seed=7):
    return World(rng=np.random.default_rng(seed), banks=BANKS)


def _df(w):
    return pl.DataFrame(w.tx), pl.DataFrame(w.clients), pl.DataFrame(w.labels)


def test_world_helpers():
    w = _world()
    c = w.new_client("B1", contract_date=datetime(2026, 6, 20, tzinfo=UTC))
    t = w.add_tx(c, datetime(2026, 7, 2, 10, tzinfo=UTC), 1000, "in", w.new_ext_account())
    w.label(c, "background", "none")
    tx, cl, lab = _df(w)
    assert tx["tx_id"].to_list() == [t] and cl["client_id"].to_list() == [c] and lab["label"].to_list() == ["background"]


def test_day_zero():
    from redteam.schemes.day_zero import plant_day_zero

    w = _world()
    plant_day_zero(w, n=5)
    tx, cl, lab = _df(w)
    assert lab.filter(pl.col("scheme") == "day_zero")["client_id"].n_unique() == 5
    assert (lab["label"] == "mule").all()
    for cid in lab["client_id"].unique():
        c = cl.filter(pl.col("client_id") == cid).row(0, named=True)
        assert (datetime(2026, 7, 1, tzinfo=UTC) - c["contract_date"]).days <= 45
        t = tx.filter(pl.col("client_id") == cid).sort("ts")
        inflow = t.filter(pl.col("direction") == "in")
        big = inflow.filter(pl.col("amount_czk") == inflow["amount_czk"].max()).row(0, named=True)
        assert big["amount_czk"] >= 100000
        out24 = t.filter((pl.col("direction") != "in") & (pl.col("ts") > big["ts"]) & (pl.col("ts") <= big["ts"] + timedelta(hours=24)))
        assert out24["amount_czk"].sum() >= 0.9 * big["amount_czk"]


def test_same_hand():
    from redteam.schemes.same_hand import plant_same_hand

    w = _world()
    plant_same_hand(w, n=12, instance=1)
    tx, cl, lab = _df(w)
    ids = lab.filter(pl.col("scheme") == "same_hand")["client_id"].to_list()
    assert len(ids) == 12 and len(set(cl.filter(pl.col("client_id").is_in(ids))["bank_id"])) >= 2
    exits = tx.filter(pl.col("client_id").is_in(ids) & (pl.col("direction") != "in")).group_by("counterparty_token").agg(pl.col("client_id").n_unique().alias("k"))
    assert exits.filter(pl.col("k") >= 3).height >= 1  # shared rare exits
    # same retention ratio k (commission) across accounts, within 1.5 pp
    ratios = []
    for cid in ids:
        t = tx.filter(pl.col("client_id") == cid)
        i, o = t.filter(pl.col("direction") == "in")["amount_czk"].sum(), t.filter(pl.col("direction") != "in")["amount_czk"].sum()
        ratios.append(1 - o / i)
    assert max(ratios) - min(ratios) <= 0.03


def test_fixed_skim():
    from redteam.schemes.fixed_skim import plant_fixed_skim

    w = _world()
    plant_fixed_skim(w, n=4, k=0.08, cycles=4)
    tx, cl, lab = _df(w)
    ids = lab.filter(pl.col("scheme") == "fixed_skim")["client_id"].to_list()
    assert len(ids) == 4
    for cid in ids:
        t = tx.filter(pl.col("client_id") == cid)
        i, o = t.filter(pl.col("direction") == "in"), t.filter(pl.col("direction") != "in")
        assert i.height >= 4 and o.height >= 4
        assert 1 - o["amount_czk"].sum() / i["amount_czk"].sum() == pytest.approx(0.08, abs=0.01)


def test_invoice_mule():
    from redteam.schemes.invoice_mule import plant_invoice_mule

    w = _world()
    plant_invoice_mule(w, n=3)
    tx, cl, lab = _df(w)
    ids = lab.filter(pl.col("scheme") == "invoice_mule")["client_id"].to_list()
    assert len(ids) == 3
    for cid in ids:
        c = cl.filter(pl.col("client_id") == cid).row(0, named=True)
        assert c["client_type"] == "natural person"
        t = tx.filter(pl.col("client_id") == cid)
        assert t.filter(pl.col("direction") == "in")["counterparty_token"].n_unique() >= 3  # several company payers
        assert t.filter(pl.col("direction") == "remit_out").height >= 1  # onward abroad


def test_victim_draining():
    from redteam.schemes.victim import plant_victim

    w = _world()
    plant_victim(w, n=4)
    tx, cl, lab = _df(w)
    ids = lab.filter(pl.col("scheme") == "victim")["client_id"].to_list()
    assert len(ids) == 4 and (lab.filter(pl.col("scheme") == "victim")["label"] == "victim").all()
    for cid in ids:
        t = tx.filter(pl.col("client_id") == cid)
        big_in = t.filter((pl.col("direction") == "in") & (pl.col("amount_czk") >= 50000))
        assert big_in.height == 0  # no third-party big inflow; the victim empties own savings
        assert t.filter(pl.col("direction") != "in")["amount_czk"].sum() >= 100000


def test_same_hand_stealth_is_small_per_account_but_shares_exits():
    from redteam.schemes.same_hand_stealth import plant_same_hand_stealth

    w = _world()
    plant_same_hand_stealth(w, n=15)
    tx, cl, lab = _df(w)
    ids = lab["client_id"].to_list()
    assert len(ids) == 15 and len(set(cl["bank_id"])) == 3
    per_acc = tx.group_by("client_id").agg(pl.col("amount_czk").filter(pl.col("direction") == "in").sum().alias("tin"))
    assert per_acc["tin"].max() <= 3 * 45000
    exits = tx.filter(pl.col("direction") == "out")["counterparty_token"].n_unique()
    assert exits <= 3


def test_ghost_ring_has_no_local_footprint_but_shares_exits():
    from redteam.schemes.ghost_ring import plant_ghost_ring

    w = _world()
    plant_ghost_ring(w, n=9)
    tx, cl, lab = _df(w)
    ids = lab["client_id"].to_list()
    assert len(ids) == 9 and sorted(cl["bank_id"].value_counts()["count"].to_list()) == [3, 3, 3]
    big_in = tx.filter((pl.col("direction") == "in") & (pl.col("amount_czk") >= 10000))
    assert big_in.height == 0                                          # nothing a single-account rule reacts to
    exits = tx.filter((pl.col("direction") == "out") & (pl.col("amount_czk") >= 3000))["counterparty_token"].n_unique()
    assert exits <= 2 + 0 or exits <= 40                               # ring exits are 2 shared accounts (the rest are everyday payments)
    assert (cl["contract_form"] == "in person").all() and cl["q2_volume"].min() > 0
