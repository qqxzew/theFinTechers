import polars as pl

OUTFLOW_DIRECTIONS = ("out", "remit_out")


def outflow_shares(
    tx: pl.DataFrame,
    degree: pl.DataFrame,
    rare_max: int = 3,
    popular_min: int = 100,
) -> pl.DataFrame:
    """Split each client's outflow amount into rare/mid/popular counterparty shares."""
    out = (
        tx.filter(pl.col("direction").is_in(OUTFLOW_DIRECTIONS))
        .join(degree, on="counterparty_token", how="left")
        .with_columns(pl.col("degree").fill_null(1))
        .group_by("client_id")
        .agg(
            pl.col("amount_czk").sum().alias("out_total"),
            pl.col("amount_czk").filter(pl.col("degree") <= rare_max).sum().alias("_rare"),
            pl.col("amount_czk").filter(pl.col("degree") >= popular_min).sum().alias("_popular"),
        )
        .with_columns(
            (pl.col("_rare") / pl.col("out_total")).alias("share_rare"),
            (pl.col("_popular") / pl.col("out_total")).alias("share_popular"),
            ((pl.col("out_total") - pl.col("_rare") - pl.col("_popular")) / pl.col("out_total")).alias("share_mid"),
        )
        .select("client_id", "out_total", "share_rare", "share_mid", "share_popular")
        .sort("client_id")
    )
    return out
