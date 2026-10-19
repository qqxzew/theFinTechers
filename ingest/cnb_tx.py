"""CNB transaction ingest: load semicolon-separated bank export into canonical schema."""

from io import StringIO
from pathlib import Path
from typing import Any

import polars as pl

TX_COLUMNS: list[str] = [
    "tx_id",
    "bank_id",
    "client_id",
    "ts",
    "amount_czk",
    "amount_orig",
    "currency",
    "direction",
    "own_account",
    "counterparty_token",
    "payer_country",
    "payee_country",
    "channel_type",
    "source_dataset",
]

_SOURCE_COLUMNS = [
    "tx_id",
    "client_id",
    "date",
    "time",
    "volume",
    "currency",
    "payer_country",
    "payee_country",
    "account_payer",
    "account_payee",
    "channel_type",
]

_DIRECTION_MAP = {
    "outgoing payment": "out",
    "incoming payment": "in",
    "remittance": "remit_out",
}


def load_transactions(path: str | Path, fx: dict[str, Any], bank_id: str = "B0") -> pl.DataFrame:
    """Load a CNB transaction CSV (Prague-local timestamps) into the canonical UTC schema."""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    raw = pl.read_csv(StringIO(text), separator=";", encoding="utf8", infer_schema_length=0)
    raw.columns = _SOURCE_COLUMNS

    rates = fx["rates"]
    direction = pl.col("channel_type").replace_strict(_DIRECTION_MAP, return_dtype=pl.String)
    df = raw.with_columns(
        pl.lit(bank_id).alias("bank_id"),
        pl.col("client_id").alias("own_account"),
        (pl.col("date") + " " + pl.col("time"))
        .str.strptime(pl.Datetime, "%d.%m.%Y %H:%M:%S")
        .dt.replace_time_zone("Europe/Prague", ambiguous="earliest")
        .dt.convert_time_zone("UTC")
        .alias("ts"),
        pl.col("volume").cast(pl.Float64).alias("amount_orig"),
        pl.when(direction.is_in(["out", "remit_out"]))
        .then(pl.col("account_payee"))
        .otherwise(pl.col("account_payer"))
        .alias("counterparty_token"),
        direction.alias("direction"),
        pl.lit("cnb").alias("source_dataset"),
    ).with_columns(
        (pl.col("amount_orig") * pl.col("currency").replace_strict(rates, return_dtype=pl.Float64)).alias(
            "amount_czk"
        )
    )
    return df.select(TX_COLUMNS)
