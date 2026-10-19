"""Max sliding-window inflow/outflow sums per client."""

from collections import defaultdict

import polars as pl

_OUT_DIRECTIONS = ("out", "remit_out")


def _max_window(ts_hours: list[float], amounts: list[float], window_h: float) -> float:
    """Max sum over windows (ts_i - window_h, ts_i] ending at each index."""
    best = 0.0
    cur = 0.0
    left = 0
    for right, t in enumerate(ts_hours):
        cur += amounts[right]
        while ts_hours[left] <= t - window_h:
            cur -= amounts[left]
            left += 1
        if cur > best:
            best = cur
    return best


def max_window_sums(tx: pl.DataFrame, windows_h: list[int]) -> pl.DataFrame:
    """Compute in_max_{w}h / out_max_{w}h per client for each window in windows_h."""
    by_client: dict[str, tuple[list[tuple[float, float]], list[tuple[float, float]]]] = defaultdict(lambda: ([], []))
    for client, ts, amount, direction in tx.sort("client_id", "ts").select(
        "client_id", "ts", "amount_czk", "direction"
    ).iter_rows():
        inflows, outflows = by_client[client]
        hour = ts.timestamp() / 3600.0
        if direction == "in":
            inflows.append((hour, amount))
        elif direction in _OUT_DIRECTIONS:
            outflows.append((hour, amount))

    columns = ["client_id"] + [f"in_max_{w}h" for w in windows_h] + [f"out_max_{w}h" for w in windows_h]
    rows = []
    for client, (inflows, outflows) in by_client.items():
        in_ts = [t for t, _ in inflows]
        in_amt = [a for _, a in inflows]
        out_ts = [t for t, _ in outflows]
        out_amt = [a for _, a in outflows]
        row: dict[str, object] = {"client_id": client}
        for w in windows_h:
            row[f"in_max_{w}h"] = _max_window(in_ts, in_amt, float(w)) if inflows else 0.0
        for w in windows_h:
            row[f"out_max_{w}h"] = _max_window(out_ts, out_amt, float(w)) if outflows else 0.0
        rows.append(row)

    return pl.DataFrame(rows).select(columns)
