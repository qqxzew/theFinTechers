"""Active-hour profile features."""

import polars as pl


def active_hour_profile(tx: pl.DataFrame) -> pl.DataFrame:
    """Per-client histogram of transaction counts over Prague local hours, normalised to sum 1."""
    counts = (
        tx.with_columns(
            pl.col("ts").dt.convert_time_zone("Europe/Prague").dt.hour().alias("hour")
        )
        .group_by("client_id", "hour")
        .len()
        .with_columns(pl.col("len") / pl.col("len").sum().over("client_id"))
    )
    grid = counts.select("client_id").unique().join(
        pl.DataFrame({"hour": list(range(24))}), how="cross"
    )
    return (
        grid.join(counts, on=["client_id", "hour"], how="left")
        .with_columns(pl.col("len").fill_null(0.0))
        .sort("hour")
        .group_by("client_id")
        .agg(pl.col("len").alias("hour_hist"))
    )
