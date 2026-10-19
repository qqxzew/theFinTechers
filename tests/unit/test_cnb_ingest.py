from datetime import datetime

import polars as pl
import pytest

from ingest.cnb_clients import load_clients
from ingest.cnb_tx import TX_COLUMNS, load_transactions

FX = {"rates": {"CZK": 1.0, "EUR": 25.0}}
CANON = ["tx_id", "bank_id", "client_id", "ts", "amount_czk", "amount_orig", "currency", "direction", "own_account",
         "counterparty_token", "payer_country", "payee_country", "channel_type", "source_dataset"]


def test_columns_and_rowcount():
    df = load_transactions("tests/fixtures/cnb_tx_sample.csv", FX, bank_id="B0")
    assert TX_COLUMNS == CANON and df.columns == CANON and df.height == 12


def test_directions_and_tokens():
    df = load_transactions("tests/fixtures/cnb_tx_sample.csv", FX, bank_id="B0")
    r = df.filter(pl.col("tx_id") == "TX000000001").row(0, named=True)
    assert r["direction"] == "out" and r["own_account"] == "K003797" and r["counterparty_token"] == "ACZ00172"
    r = df.filter(pl.col("tx_id") == "TX000000004").row(0, named=True)
    assert r["direction"] == "in" and r["own_account"] == "K001159" and r["counterparty_token"] == "AIE00139"
    r = df.filter(pl.col("tx_id") == "TX000000003").row(0, named=True)
    assert r["direction"] == "remit_out" and r["own_account"] == "K005116" and r["counterparty_token"] == "AAT00116"
    assert r["amount_czk"] == pytest.approx(19889.43 * 25.0) and r["amount_orig"] == pytest.approx(19889.43)
    assert r["bank_id"] == "B0" and r["source_dataset"] == "cnb" and r["channel_type"] == "remittance"


def test_ts_is_utc_from_prague_local():
    df = load_transactions("tests/fixtures/cnb_tx_sample.csv", FX, bank_id="B0")
    ts = df.filter(pl.col("tx_id") == "TX000000001")["ts"][0]
    # 01.07.2026 00:00:43 Prague (CEST, UTC+2) -> 30.06.2026 22:00:43 UTC
    assert ts.replace(tzinfo=None) == datetime(2026, 6, 30, 22, 0, 43)


def test_clients():
    c = load_clients("tests/fixtures/cnb_clients_sample.csv", bank_id="B0")
    assert c.height == 7
    r = c.filter(pl.col("client_id") == "K000003").row(0, named=True)
    assert r["bank_id"] == "B0" and r["client_country"] == "CZ" and r["pep"] is False
    assert r["contract_form"] == "in person" and r["client_type"] == "natural person"
    assert r["expected_volume"] == pytest.approx(67526.24) and r["expected_count"] == 22
    assert r["q2_volume"] == pytest.approx(224064.35) and r["q2_count"] == 73 and r["q2_max"] == pytest.approx(24555.0)
    assert r["aml_risk"] == "low"
    assert r["source_dataset"] == "cnb" and r["derived"] is False
    assert r["contract_date"].date() == datetime(2020, 1, 14).date()
