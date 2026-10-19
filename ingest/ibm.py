"""IBM AMLworld (HI-Small) ingestion and simulated bank split. SYNTHETIC data (Altman et al., NeurIPS 2023 D&B).

These are GENERIC laundering patterns produced by the AMLworld generator, NOT Czech money-mule schemes.

Bank-side vs evaluation-side:
  * `load_ibm` returns the parsed file INCLUDING the `is_laundering` label.
  * `split_labels` separates it: bank-side code receives only the label-free transaction table; labels and pattern types
    (`load_patterns`, `tx_patterns`) are consumed only by `eval/ibm_eval.py`.
  * `bank_split` builds canonical IN/OUT rows per simulated bank from a label-free table and refuses tables that still carry labels.

Bank split: each IBM bank id is mapped to a simulated bank B1..Bn by SHA-256 of the id (stable across processes and Python versions,
unlike `hash()`), so all accounts of one IBM bank stay in one simulated bank. Every transaction yields an OUT row at the sender's
simulated bank and an IN row at the receiver's simulated bank. The own account is `client_id = "<ibm bank>:<account>"`; the
counterparty is visible only as an external token in the same `"<ibm bank>:<account>"` form, exactly like an IBAN.
Self-transfers (same account on both sides) are dropped.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl
import yaml

SOURCE = "ibm_amlworld_hi_small"
RAW_COLUMNS = ["ts_raw", "from_bank", "from_account", "to_bank", "to_account", "amount_received", "receiving_currency",
               "amount_paid", "payment_currency", "payment_format", "is_laundering"]
LABEL_COLUMNS = ("is_laundering", "pattern_type", "attempt_id")
CANON_COLUMNS = ["tx_id", "bank_id", "client_id", "ts", "amount", "amount_orig", "currency", "direction", "own_account",
                 "counterparty_token", "channel_type", "source_dataset"]
_STR = {c: pl.Utf8 for c in ("from_bank", "from_account", "to_bank", "to_account")}


def load_config(path: str | Path = "config/ibm.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(ts=pl.col("ts_raw").str.strptime(pl.Datetime("us"), "%Y/%m/%d %H:%M").dt.replace_time_zone("UTC"))


def load_ibm(path: str | Path) -> pl.DataFrame:
    """Read HI-Small_Trans.csv. The header has two columns called `Account`, so it is skipped and columns are named explicitly.
    Bank and account ids are strings (leading zeros matter). Timestamps are read as UTC (the source gives no zone)."""
    df = pl.read_csv(path, has_header=False, skip_rows=1, new_columns=RAW_COLUMNS, schema_overrides=_STR)
    df = _parse(df).with_row_index("row")
    return df.with_columns(tx_id=pl.format("ibm-{}", pl.col("row"))).drop("row")


def split_labels(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(label-free transactions for the banks, labels [tx_id, is_laundering] for the evaluation only)."""
    return df.drop("is_laundering"), df.select("tx_id", "is_laundering")


def load_patterns(path: str | Path) -> pl.DataFrame:
    """Parse HI-Small_Patterns.txt: `BEGIN LAUNDERING ATTEMPT - <TYPE>: <detail>` blocks of CSV lines, closed by `END ...`."""
    recs: list[list[str]] = []
    attempt, ptype, detail = -1, None, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("BEGIN LAUNDERING ATTEMPT"):
                attempt += 1
                head = s.split(" - ", 1)[1]
                ptype, _, detail = head.partition(":")
                ptype, detail = ptype.strip().lower(), detail.strip()
                continue
            if s.startswith("END LAUNDERING ATTEMPT"):
                ptype = None
                continue
            if ptype is None:
                continue
            parts = s.split(",")
            recs.append([str(attempt), ptype, detail] + parts)
    cols = ["attempt_id", "pattern_type", "pattern_detail"] + RAW_COLUMNS
    df = pl.DataFrame(recs, schema=cols, orient="row")
    df = df.with_columns(pl.col("attempt_id").cast(pl.Int64), pl.col("amount_paid").cast(pl.Float64),
                         pl.col("amount_received").cast(pl.Float64), pl.col("is_laundering").cast(pl.Int64))
    return _parse(df)


def tx_patterns(df: pl.DataFrame, patterns: pl.DataFrame) -> pl.DataFrame:
    """Match pattern lines to transactions on (timestamp, from bank/account, to bank/account, amount paid, currency, format).
    Returns [tx_id, attempt_id, pattern_type]. EVALUATION ONLY."""
    keys = ["ts", "from_bank", "from_account", "to_bank", "to_account", "amount_paid", "payment_currency", "payment_format"]
    return patterns.select(keys + ["attempt_id", "pattern_type"]).join(df.select(keys + ["tx_id"]), on=keys, how="inner") \
        .select("tx_id", "attempt_id", "pattern_type").unique().sort("tx_id", "attempt_id")


def sim_bank(ibm_bank_id: str, n_banks: int = 5) -> str:
    """Stable map IBM bank id -> simulated bank B1..Bn (SHA-256, not Python's salted hash())."""
    h = int.from_bytes(hashlib.sha256(f"staj-ibm-bank-split-v1:{ibm_bank_id}".encode()).digest()[:8], "big")
    return f"B{h % n_banks + 1}"


def bank_map(ibm_bank_ids: list[str], n_banks: int = 5) -> pl.DataFrame:
    ids = sorted(set(ibm_bank_ids))
    return pl.DataFrame({"ibm_bank": ids, "sim_bank": [sim_bank(i, n_banks) for i in ids]})


def bank_split(tx: pl.DataFrame, n_banks: int = 5, usd_per_unit: dict[str, float] | None = None) -> pl.DataFrame:
    """Canonical rows for all simulated banks (filter on `bank_id` to get one bank's own table).

    Input must be LABEL-FREE (raises otherwise). `amount` = Amount Paid converted to USD with the placeholder table
    (`config/ibm.yaml: fx.usd_per_unit`); both rows of a transaction carry the same amount."""
    leaked = [c for c in LABEL_COLUMNS if c in tx.columns]
    if leaked:
        raise ValueError(f"bank_split received label columns {leaked}; bank-side tables must be label-free")
    tx = tx.filter(~((pl.col("from_bank") == pl.col("to_bank")) & (pl.col("from_account") == pl.col("to_account"))))
    bm = bank_map(tx["from_bank"].to_list() + tx["to_bank"].to_list(), n_banks)
    lut = dict(zip(bm["ibm_bank"], bm["sim_bank"], strict=True))
    if usd_per_unit is None:
        usd_per_unit = load_config()["fx"]["usd_per_unit"]
    missing = set(tx["payment_currency"].unique()) - set(usd_per_unit)
    if missing:
        raise KeyError(f"no placeholder FX rate for {sorted(missing)}")
    base = tx.with_columns(
        sender=pl.col("from_bank") + ":" + pl.col("from_account"),
        receiver=pl.col("to_bank") + ":" + pl.col("to_account"),
        amount=pl.col("amount_paid") * pl.col("payment_currency").replace_strict(usd_per_unit, return_dtype=pl.Float64),
        s_bank=pl.col("from_bank").replace_strict(lut), r_bank=pl.col("to_bank").replace_strict(lut),
    )
    common = [pl.col("tx_id"), pl.col("ts"), pl.col("amount"), pl.col("amount_paid").alias("amount_orig"),
              pl.col("payment_currency").alias("currency")]
    out = base.select(pl.col("s_bank").alias("bank_id"), pl.col("sender").alias("client_id"), *common,
                      pl.lit("out").alias("direction"), pl.col("from_account").alias("own_account"),
                      pl.col("receiver").alias("counterparty_token"), pl.col("payment_format").alias("channel_type"))
    inn = base.select(pl.col("r_bank").alias("bank_id"), pl.col("receiver").alias("client_id"), *common,
                      pl.lit("in").alias("direction"), pl.col("to_account").alias("own_account"),
                      pl.col("sender").alias("counterparty_token"), pl.col("payment_format").alias("channel_type"))
    rows = pl.concat([out, inn]).with_columns(source_dataset=pl.lit(SOURCE))
    return rows.select(CANON_COLUMNS).sort("bank_id", "client_id", "ts", "tx_id", "direction")


def bank_tables(rows: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """One table per simulated bank: only rows where one side is that bank's own account."""
    return {b: rows.filter(pl.col("bank_id") == b) for b in sorted(rows["bank_id"].unique().to_list())}
