"""Rule B: high-risk country exposure and PEP large outgoing alerts."""

import polars as pl


def rule_b(tx: pl.DataFrame, clients: pl.DataFrame, hr_countries: set[str], cfg: dict) -> pl.DataFrame:
    """Emit one alert per transaction breaching high-risk-country or PEP thresholds."""
    df = tx.join(clients, on="client_id", how="left")
    hr_list = list(hr_countries)
    hr = (pl.col("amount_czk") > cfg["min_amount_hr"]) & (
        pl.col("payer_country").is_in(hr_list)
        | pl.col("payee_country").is_in(hr_list)
        | pl.col("client_country").is_in(hr_list)
    ).fill_null(False)
    pep = (
        pl.col("pep").fill_null(False)
        & pl.col("direction").is_in(["out", "remit_out"])
        & (pl.col("amount_czk") > cfg["pep_outgoing_min"])
    ).fill_null(False)
    reason = (
        pl.when(hr & pep)
        .then(pl.lit("high_risk_country+pep_large_outgoing"))
        .when(hr)
        .then(pl.lit("high_risk_country"))
        .when(pep)
        .then(pl.lit("pep_large_outgoing"))
        .otherwise(None)
        .alias("reason")
    )
    return (
        df.with_columns(reason)
        .filter(pl.col("reason").is_not_null())
        .select("tx_id", "client_id", pl.lit("B").alias("alert_type"), "reason", "amount_czk")
    )
