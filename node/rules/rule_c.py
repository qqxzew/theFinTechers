"""Rule C: rapid inflow aggregation followed by outflow to new counterparties."""

from datetime import timedelta

import polars as pl

_COLUMNS = ["client_id", "alert_type", "inflow_amount", "outflow_amount", "anchor_ts"]


def rule_c(tx: pl.DataFrame, cfg: dict) -> pl.DataFrame:
    """Emit at most one alert per client for threshold-crossing inflows with fast outflow."""
    schema = {
        "client_id": pl.String,
        "alert_type": pl.String,
        "inflow_amount": pl.Float64,
        "outflow_amount": pl.Float64,
        "anchor_ts": tx.schema["ts"],
    }
    inflow_window = timedelta(hours=cfg["inflow_window_h"])
    outflow_window = timedelta(hours=cfg["outflow_window_h"])
    alerts: list[dict] = []
    for client_id in tx["client_id"].unique().to_list():
        rows = tx.filter(pl.col("client_id") == client_id).to_dicts()
        ins = sorted((r for r in rows if r["direction"] == "in"), key=lambda r: r["ts"])
        outs = sorted(
            (r for r in rows if r["direction"] in ("out", "remit_out")), key=lambda r: r["ts"]
        )
        for i, current in enumerate(ins):
            window = [
                r for r in ins[: i + 1] if current["ts"] - inflow_window < r["ts"] <= current["ts"]
            ]
            inflow_amount = sum(r["amount_czk"] for r in window)
            if inflow_amount <= cfg["inflow_threshold"]:
                continue
            payers = {r["counterparty_token"] for r in window}
            if cfg["anchor"] == "threshold_crossing":
                anchor_ts = current["ts"]
            else:
                anchor_ts = window[0]["ts"]
            outflow_amount = sum(
                r["amount_czk"]
                for r in outs
                if anchor_ts <= r["ts"] <= anchor_ts + outflow_window
                and r["counterparty_token"] not in payers
            )
            if outflow_amount >= cfg["outflow_share"] * inflow_amount:
                alerts.append(
                    {
                        "client_id": client_id,
                        "alert_type": "C",
                        "inflow_amount": inflow_amount,
                        "outflow_amount": outflow_amount,
                        "anchor_ts": anchor_ts,
                    }
                )
                break
    if not alerts:
        return pl.DataFrame(schema=schema)  # type: ignore[arg-type]
    return pl.DataFrame(alerts, schema=schema, orient="row").select(_COLUMNS)  # type: ignore[arg-type]
