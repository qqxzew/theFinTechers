"""CNB client master data ingestion."""

from pathlib import Path

import polars as pl

CLIENT_COLUMNS = [
    "client_id",
    "client_country",
    "contract_date",
    "contract_form",
    "pep",
    "client_type",
    "expected_volume",
    "expected_count",
    "q2_volume",
    "q2_count",
    "q2_max",
    "aml_risk",
]


def load_clients(path: str | Path, bank_id: str = "B0") -> pl.DataFrame:
    """Load CNB client data; all fields read as strings, renamed by position."""
    raw = pl.read_csv(
        path,
        separator=";",
        encoding="utf-8-sig",
        has_header=True,
        new_columns=CLIENT_COLUMNS,
        infer_schema_length=0,
    )
    df = raw.select(
        pl.col("client_id"),
        pl.lit(bank_id).alias("bank_id"),
        pl.col("client_country"),
        pl.col("contract_date")
        .str.strip_chars()
        .str.strptime(pl.Datetime, "%d.%m.%Y", strict=False)
        .alias("contract_date"),
        pl.col("contract_form"),
        (pl.col("pep").str.strip_chars() == "Y").alias("pep"),
        pl.col("client_type"),
        pl.col("expected_volume").cast(pl.Float64),
        pl.col("expected_count").cast(pl.Float64),
        pl.col("q2_volume").cast(pl.Float64),
        pl.col("q2_count").cast(pl.Float64),
        pl.col("q2_max").cast(pl.Float64),
        pl.col("aml_risk"),
        pl.lit("cnb").alias("source_dataset"),
        pl.lit(False).alias("derived"),
    )
    return df
