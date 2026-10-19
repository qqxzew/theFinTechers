"""Fake-banker victim draining: planted red-team scheme, synthetic, designed from public descriptions of Czech/CEE money-mule schemes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redteam.world import World

JUL1 = datetime(2026, 7, 1, tzinfo=UTC)


def plant_victim(w: World, n: int = 4, instance: int = 0) -> None:
    """Plant victims of a fake-banker scheme who drain their own savings to new rare accounts."""
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        age_years = float(w.rng.uniform(2, 8))
        contract_date = JUL1 - timedelta(days=age_years * 365.25)
        expected_volume = float(w.rng.uniform(100000, 300000))
        cid = w.new_client(
            bank,
            contract_date=contract_date,
            contract_form="in person",
            expected_volume=expected_volume,
            q2_volume=3 * expected_volume,
            q2_count=float(w.rng.integers(60, 151)),
        )

        popular = [w.new_ext_account() for _ in range(4)]
        for _ in range(int(w.rng.integers(5, 16))):
            w.add_tx(cid, w.random_time(1, 31), float(w.rng.uniform(1000, 15000)), "in", popular[int(w.rng.integers(0, len(popular)))])
        for _ in range(int(w.rng.integers(5, 16))):
            w.add_tx(cid, w.random_time(1, 31), float(w.rng.uniform(500, 8000)), "out", popular[int(w.rng.integers(0, len(popular)))])

        start_day = int(w.rng.integers(5, 26))
        span_days = int(w.rng.integers(1, 4))
        n_drain = int(w.rng.integers(2, 6))
        amounts = [float(w.rng.uniform(40000, 250000)) for _ in range(n_drain)]
        total = sum(amounts)
        if total < 100000:
            amounts[0] += 100000 - total
        for amount in amounts:
            day = min(start_day + int(w.rng.integers(0, span_days)), 31)
            direction = "out" if w.rng.random() < 0.5 else "remit_out"
            w.add_tx(cid, w.random_time(day, day), amount, direction, w.new_ext_account())

        w.label(cid, "victim", "victim", instance=instance)
