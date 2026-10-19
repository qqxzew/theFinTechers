"""Fixed-skim mule scheme: planted red-team scheme, synthetic, designed from public descriptions of Czech/CEE money-mule schemes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World


def plant_fixed_skim(w: World, n: int = 4, k: float = 0.08, cycles: int = 4, instance: int = 0) -> None:
    """Plant accounts that forward a fixed share (1-k) of each inflow to exit accounts."""
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        contract_date = datetime(2026, 7, 1, tzinfo=UTC) - timedelta(
            days=int(w.rng.integers(30, 301)))
        cid = w.new_client(bank, contract_date=contract_date)
        exits = [w.new_ext_account() for _ in range(2)]
        days = sorted(w.rng.choice(range(1, 29), size=cycles, replace=False).tolist())
        for day in days:
            inflow = float(w.rng.uniform(10000, 60000))
            hour = int(w.rng.integers(6, 16))
            ts_in = datetime(2026, 7, day, hour, int(w.rng.integers(0, 60)),
                             int(w.rng.integers(0, 60)), tzinfo=UTC)
            payer = w.new_ext_account()
            w.add_tx(cid, ts_in, inflow, "in", payer)
            lag = timedelta(hours=int(w.rng.integers(1, 7)))
            noise = float(w.rng.uniform(-0.002, 0.002)) * inflow
            out_amount = inflow * (1 - k) + noise
            w.add_tx(cid, ts_in + lag, out_amount, "out",
                     exits[int(w.rng.integers(0, 2))])
        w.label(cid, "mule", "fixed_skim", instance=instance)
