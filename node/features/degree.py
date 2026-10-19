"""Counterparty degree feature."""

import polars as pl


def counterparty_degree(tx: pl.DataFrame) -> pl.DataFrame:
    """Count distinct client_id per counterparty_token across all directions."""
    return (
        tx.group_by("counterparty_token")
        .agg(pl.col("client_id").n_unique().alias("degree"))
        .select("counterparty_token", "degree")
    )
