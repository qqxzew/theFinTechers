"""Invoice mule: planted red-team scheme, synthetic, designed from public descriptions of Czech/CEE money-mule schemes."""
from __future__ import annotations

from datetime import timedelta

from redteam.world import World

EXIT_COUNTRIES = ["LT", "BG", "CY", "HU", "PL"]


def plant_invoice_mule(w: World, n: int = 3, instance: int = 0) -> None:
    """Plant n business-to-personal invoice mules.

    Planted red-team scheme, synthetic, designed from public descriptions of Czech/CEE money-mule schemes.
    Each mule is a natural person with a distant-form contract who receives several company
    'invoice' inflows within one July week and rapidly remits 85-98% of each abroad.
    """
    for _ in range(n):
        bank = w.banks[int(w.rng.integers(0, len(w.banks)))]
        cid = w.new_client(
            bank,
            contract_date=w.START - timedelta(days=int(w.rng.integers(5, 61))),
            contract_form="distant form",
            client_type="natural person",
        )
        week_start = int(w.rng.integers(2, 21))
        for _ in range(int(w.rng.integers(3, 7))):
            inflow = float(w.rng.integers(40000, 200001))
            in_ts = w.random_time(day_from=week_start, day_to=week_start + 6)
            w.add_tx(cid, in_ts, inflow, "in", w.new_ext_account())
            total_out = inflow * float(w.rng.uniform(0.85, 0.98))
            n_out = int(w.rng.integers(1, 3))
            parts = [total_out] if n_out == 1 else [round(total_out * float(w.rng.uniform(0.3, 0.7)), 2)]
            if n_out == 2:
                parts.append(round(total_out - parts[0], 2))
            for part in parts:
                country = EXIT_COUNTRIES[int(w.rng.integers(0, len(EXIT_COUNTRIES)))]
                out_ts = in_ts + timedelta(hours=float(w.rng.uniform(0.1, 12)))
                w.add_tx(cid, out_ts, part, "remit_out", w.new_ext_account(country), country=country)
        w.label(cid, "mule", "invoice_mule", instance=instance)
