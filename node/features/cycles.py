"""Group inflows into cycles and measure outflow retention and lag."""

from datetime import timedelta

import polars as pl

_SCHEMA = {
    "client_id": pl.String,
    "cycle_id": pl.Int64,
    "start": pl.Datetime(time_zone="UTC"),
    "end": pl.Datetime(time_zone="UTC"),
    "in_amount": pl.Float64,
    "out_amount": pl.Float64,
    "retention": pl.Float64,
    "lag_h": pl.Float64,
}


def inflow_cycles(tx: pl.DataFrame, gap_h: float = 6, out_window_h: float = 24) -> pl.DataFrame:
    """Split each client's inflows into gap-delimited cycles and attribute outflows.

    A new cycle starts when the gap since the previous inflow exceeds ``gap_h``
    hours. Each outflow joins the latest cycle whose start is at or before the
    outflow timestamp and whose end plus ``out_window_h`` hours covers it.
    """
    inflows = tx.filter(pl.col("direction") == "in").sort("client_id", "ts")
    outflows = tx.filter(pl.col("direction").is_in(["out", "remit_out"])).sort("ts")
    if inflows.is_empty():
        return pl.DataFrame(schema=_SCHEMA)

    rows: list[dict] = []
    out_by_client: dict[str, list[tuple]] = {}
    for client_id, ts, amount in outflows.select("client_id", "ts", "amount_czk").iter_rows():
        out_by_client.setdefault(client_id, []).append((ts, amount))

    gap = timedelta(hours=gap_h)
    window = timedelta(hours=out_window_h)
    for key, group in inflows.group_by("client_id", maintain_order=True):
        client_id = key[0]
        cycles: list[dict] = []
        for ts, amount in zip(group["ts"].to_list(), group["amount_czk"].to_list()):
            if cycles and ts - cycles[-1]["end"] <= gap:
                cycles[-1]["end"] = ts
                cycles[-1]["in_amount"] += amount
            else:
                cycles.append({"cycle_id": len(cycles), "start": ts, "end": ts, "in_amount": amount})

        for cycle in cycles:
            cycle["out_amount"] = 0.0
            cycle["_lag_weighted"] = 0.0

        for ts, amount in out_by_client.get(client_id, []):
            assigned = None
            for cycle in cycles:
                if cycle["start"] <= ts <= cycle["end"] + window:
                    assigned = cycle
            if assigned is not None:
                assigned["out_amount"] += amount
                assigned["_lag_weighted"] += amount * max((ts - assigned["end"]).total_seconds() / 3600.0, 0.0)

        for cycle in cycles:
            out_amount = cycle["out_amount"]
            lag_h = cycle["_lag_weighted"] / out_amount if out_amount > 0 else None
            rows.append({
                "client_id": client_id,
                "cycle_id": cycle["cycle_id"],
                "start": cycle["start"],
                "end": cycle["end"],
                "in_amount": cycle["in_amount"],
                "out_amount": out_amount,
                "retention": max(0.0, 1.0 - out_amount / cycle["in_amount"]),
                "lag_h": lag_h,
            })

    return pl.DataFrame(rows, schema=_SCHEMA)
