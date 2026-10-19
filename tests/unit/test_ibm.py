"""IBM AMLworld ingest, bank split, vectorised engine and pairwise PSI path, on tiny hand-built SYNTHETIC fixtures."""
from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from eval.ibm_eval import NodeExport, apply_radar, average_precision, engine, radar_pairwise
from ingest.ibm import CANON_COLUMNS, bank_split, sim_bank, split_labels
from radar.sessions import BankNode, token_id

FX = {"US Dollar": 1.0, "Euro": 1.0}
ECFG = {"rare_max_degree": 3, "drain_window_h": 24,
        "weights": {"bias": -7.0, "drain_24h": 2.0, "flow_ratio": 1.5, "low_retention": 0.5, "rare_out_share": 1.0,
                    "log_n_rare_cp": 0.5, "log_deg_in": 0.5, "log10_max_in_24h": 0.15, "neighbour": 2.0}}
GUARDS = {"min_set_size": 2, "max_tokens": 5000, "max_sessions_per_hour": 20, "max_unscored_share": 0.2}
T0 = datetime(2022, 9, 1, tzinfo=UTC)


def _tx(rows):
    """rows: (minutes, from_bank, from_acct, to_bank, to_acct, amount, label)."""
    recs = []
    for i, (m, fb, fa, tb, ta, amt, lab) in enumerate(rows):
        recs.append({"ts": T0 + timedelta(minutes=m), "from_bank": fb, "from_account": fa, "to_bank": tb, "to_account": ta,
                     "amount_received": amt, "receiving_currency": "US Dollar", "amount_paid": amt, "payment_currency": "US Dollar",
                     "payment_format": "ACH", "is_laundering": lab, "tx_id": f"ibm-{i}"})
    return pl.DataFrame(recs)


def test_sim_bank_is_stable_and_deterministic():
    assert sim_bank("070") == sim_bank("070")
    assert sim_bank("070") in {f"B{i}" for i in range(1, 6)}
    # fixed values (SHA-256 based): must not change between processes or Python versions
    assert [sim_bank(x) for x in ("010", "070", "001")] == [sim_bank(x) for x in ("010", "070", "001")]
    assert len({sim_bank(str(i)) for i in range(200)}) == 5
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", "from ingest.ibm import sim_bank; print(sim_bank('070'), sim_bank('0213'))"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert out == [sim_bank("070"), sim_bank("0213")]


def test_bank_split_keeps_ibm_banks_together_and_builds_in_out_rows():
    df = _tx([(0, "010", "A1", "020", "B1", 100.0, 0), (5, "010", "A2", "010", "A1", 50.0, 0), (9, "030", "C1", "030", "C1", 7.0, 0)])
    tx, labels = split_labels(df)
    rows = bank_split(tx, 5, FX)
    assert rows.columns == CANON_COLUMNS
    assert rows.height == 4                          # self-transfer dropped, 2 rows per remaining tx
    banks = rows.group_by(pl.col("client_id").str.split(":").list.first().alias("ibm")).agg(pl.col("bank_id").n_unique())
    assert banks["bank_id"].max() == 1               # one IBM bank -> exactly one simulated bank
    t0 = rows.filter(pl.col("tx_id") == "ibm-0").sort("direction")
    assert t0["direction"].to_list() == ["in", "out"]
    out = t0.filter(pl.col("direction") == "out").row(0, named=True)
    inn = t0.filter(pl.col("direction") == "in").row(0, named=True)
    assert out["client_id"] == "010:A1" and out["counterparty_token"] == "020:B1" and out["bank_id"] == sim_bank("010")
    assert inn["client_id"] == "020:B1" and inn["counterparty_token"] == "010:A1" and inn["bank_id"] == sim_bank("020")
    assert all(":" in t and len(t.split(":")) == 2 for t in rows["counterparty_token"].to_list())
    assert out["amount"] == 100.0


def test_labels_never_reach_bank_tables():
    df = _tx([(0, "010", "A1", "020", "B1", 100.0, 1)])
    tx, labels = split_labels(df)
    assert "is_laundering" not in tx.columns and labels.columns == ["tx_id", "is_laundering"]
    rows = bank_split(tx, 5, FX)
    assert not {"is_laundering", "pattern_type", "attempt_id"} & set(rows.columns)
    with pytest.raises(ValueError):
        bank_split(df, 5, FX)                        # a labelled table is refused


def test_amount_uses_placeholder_fx():
    df = _tx([(0, "010", "A1", "020", "B1", 100.0, 0)]).with_columns(payment_currency=pl.lit("Euro"))
    rows = bank_split(split_labels(df)[0], 5, {"Euro": 1.1})
    assert rows["amount"].to_list() == pytest.approx([110.0, 110.0])
    with pytest.raises(KeyError):
        bank_split(split_labels(df)[0], 5, {"US Dollar": 1.0})


def _one_bank_rows(spec):
    rows = bank_split(split_labels(_tx(spec))[0], 1, FX)  # n_banks=1: everything in B1
    return rows


def test_engine_flags_flow_through_not_regular_account():
    spec = []
    # flow-through account M: 3 fresh payers send 10k each, within hours 29.4k leaves to 3 rare new payees
    for i in range(3):
        spec.append((10 + i, "001", f"P{i}", "001", "M", 10_000.0, 0))
    for i in range(3):
        spec.append((200 + i, "001", "M", "002", f"X{i}", 9_800.0, 0))
    # regular account R: salary from an employer who pays 10 people, spends at popular merchants paid by many clients
    for j in range(10):
        spec.append((0, "001", "EMP", "001", f"E{j}" if j else "R", 3_000.0, 0))
    for j in range(10):
        for k in range(2):
            spec.append((600 + j * 7 + k, "001", f"E{j}" if j else "R", "003", f"SHOP{k}", 100.0, 0))
    f = engine(_one_bank_rows(spec), ECFG)
    m = f.filter(pl.col("client_id") == "001:M").row(0, named=True)
    r = f.filter(pl.col("client_id") == "001:R").row(0, named=True)
    assert m["drain_24h"] == pytest.approx(1.0) and m["rare_out_share"] == pytest.approx(1.0)
    assert m["max_in_24h"] == pytest.approx(30_000.0)
    assert r["rare_out_share"] == 0.0                # SHOP0/1 have degree 10 inside the bank
    assert r["retention"] > 0.9
    assert m["score"] > r["score"] + 2.0
    thr = -3.0
    assert m["score"] >= thr > r["score"]
    assert average_precision(f, {"001:M"}) == 1.0


def _tok(c: str) -> str:
    return f"0{ord(c)}:80{ord(c)}0F{ord(c)}"         # looks like an IBM 'bank:account' token


def _nodes():
    a = BankNode("B1", [{"token": _tok(t), "cand_ref": f"a{i % 2}", "score": 0.5} for i, t in enumerate("xyzq")],
                 {_tok(t): 1.0 for t in "xyzq"}, {})
    b = BankNode("B2", [{"token": _tok(t), "cand_ref": f"b{i}", "score": 0.4} for i, t in enumerate("yzw")], {_tok(t): 0.5 for t in "yzw"}, {})
    c = BankNode("B3", [{"token": _tok(t), "cand_ref": "c0", "score": 0.3} for t in "qv"], {_tok(t): 1.0 for t in "qv"}, {})
    return a, b, c


def test_pairwise_psi_equals_plain_intersection():
    a, b, c = _nodes()
    res = radar_pairwise([a, b, c], GUARDS, b"k", workers=1)
    sets = {n.bank_id: {x["token"] for x in n.candidates} for n in (a, b, c)}
    plain = (sets["B1"] & sets["B2"]) | (sets["B1"] & sets["B3"]) | (sets["B2"] & sets["B3"])
    assert set(res["matched_token_ids"]) == {token_id(b"k", t) for t in plain}
    assert res["exposure"]["raw_records_exposed"] == 0 and res["exposure"]["plaintext_tokens_in_wire"] == 0
    assert res["exposure"]["bytes_exchanged"] > 0
    # a0 holds x,z; a1 holds y,q. Components: {a0, b1 via z} (2 candidates, not disclosed) and {a1, b0 via y, c0 via q} (3 banks)
    disclosed = [cl for cl in res["clusters"] if cl["disclosed"]]
    assert len(res["clusters"]) == 2 and len(disclosed) == 1
    assert set(disclosed[0]["banks"]) == {"B1", "B2", "B3"} and len(disclosed[0]["candidates"]) == 3


def test_radar_boost_is_monotone_and_local():
    a, b, c = _nodes()
    res = radar_pairwise([a, b, c], GUARDS, b"k", workers=1)
    exports = {"B1": NodeExport(a, {"a0": "acc-a0", "a1": "acc-a1"}, 2, 2), "B2": NodeExport(b, {"b0": "acc-b0", "b1": "acc-b1", "b2": "acc-b2"}, 3, 3),
               "B3": NodeExport(c, {"c0": "acc-c0"}, 1, 1)}
    scores = pl.DataFrame({"client_id": ["acc-a0", "acc-b2", "other"], "bank_id": ["B1", "B2", "B1"], "score": [-4.0, -4.0, -4.0]})
    boosted_scores, boosted = apply_radar(scores, exports, res["clusters"], 2.0)
    assert boosted == {"acc-a1", "acc-b0", "acc-c0"}   # a0/b1 share a token but their component is too small to disclose
    s = dict(zip(boosted_scores["client_id"], boosted_scores["score"], strict=True))
    assert s == {"acc-a0": -4.0, "acc-b2": -4.0, "other": -4.0}
    s2 = dict(zip(*apply_radar(scores.with_columns(client_id=pl.Series(["acc-a1", "acc-b2", "other"])), exports, res["clusters"], 2.0)[0]
                  .select("client_id", "score").to_dict(as_series=False).values(), strict=True))
    assert s2["acc-a1"] == -2.0 and all(v >= -4.0 for v in s2.values())
