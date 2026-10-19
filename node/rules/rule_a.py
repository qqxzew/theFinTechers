"""Rule A: daily-volume anomaly alerts."""

import polars as pl

from ingest.units import projected_monthly, q2_daily_average

_REASON_FIELDS = ("max_daily", "max_single", "projected_monthly", "q2_volume", "q2_daily", "q2_max")


def _reasons(row: dict, cfg: dict) -> list[str]:
    """Return breach reasons for one client row, in spec order."""
    out = []
    if row["max_daily"] > cfg["daily_share_of_projected"] * row["projected_monthly"]:
        out.append("daily_gt_share_of_projected")
    if row["q2_volume"] > 0 and row["max_daily"] > cfg["daily_vs_q2_avg_mult"] * row["q2_daily"]:
        out.append("daily_gt_mult_of_q2_avg")
    if row["q2_max"] > 0 and row["max_single"] > cfg["single_vs_q2_max_mult"] * row["q2_max"]:
        out.append("single_gt_mult_of_q2_max")
    return out


def rule_a(tx: pl.DataFrame, clients: pl.DataFrame, cfg: dict) -> pl.DataFrame:
    """Emit one alert per client whose daily activity breaches configured thresholds."""
    daily = (
        tx.with_columns(pl.col("ts").dt.convert_time_zone("Europe/Prague").dt.date().alias("day"))
        .group_by("client_id", "day")
        .agg(pl.col("amount_czk").sum().alias("daily_volume"))
    )
    stats = daily.group_by("client_id").agg(pl.col("daily_volume").max().alias("max_daily")).join(
        tx.group_by("client_id").agg(pl.col("amount_czk").max().alias("max_single")),
        on="client_id",
    )
    df = (
        stats.join(clients, on="client_id", how="inner")
        .with_columns(
            pl.col("expected_volume")
            .map_elements(lambda v: projected_monthly(v, cfg["expected_unit"]), return_dtype=pl.Float64)
            .alias("projected_monthly"),
            pl.col("q2_volume")
            .map_elements(lambda v: q2_daily_average(v, cfg["q2_unit"]), return_dtype=pl.Float64)
            .alias("q2_daily"),
        )
        .with_columns(
            pl.struct(*_REASON_FIELDS)
            .map_elements(lambda row: _reasons(row, cfg), return_dtype=pl.Object)
            .alias("reasons")
        )
        .filter(pl.col("reasons").map_elements(lambda rs: len(rs) > 0, return_dtype=pl.Boolean))
    )
    return df.select(
        pl.col("client_id"),
        pl.lit("A").alias("alert_type"),
        pl.col("reasons"),
        pl.col("max_daily"),
        pl.col("projected_monthly"),
    )
