"""Builds outbreak/data.json for the Outbreak demo view: per day, three bank-local skim x delay heatmaps, the collector total, flagged HOW windows
and the customers each bank raises for them. DEMO VIEW: the bank-local panels are shown in plain; in the real protocol the collector never sees them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, ".")
from collector.stats import how_test  # noqa: E402
from node.collector_cli import CONSORTIUM_KEY  # noqa: E402
from node.expansion import expand_how  # noqa: E402
from node.signatures import build_signatures, how_vectors  # noqa: E402

world = sys.argv[1]
tx = pl.read_parquet(f"{world}/tx.parquet")
cl = pl.read_parquet(f"{world}/clients.parquet").with_columns(pl.col("contract_date").dt.replace_time_zone(None))
meta = json.loads(Path(world, "meta.json").read_text(encoding="utf-8"))
banks = sorted(cl["bank_id"].unique().to_list())
sigs = {b: build_signatures(b, tx.filter(pl.col("bank_id") == b), cl.filter(pl.col("bank_id") == b), CONSORTIUM_KEY) for b in banks}
cb = {b: np.stack([how_vectors(sigs[b], d)["C"] for d in range(61)]).reshape(61, 30, 6, 2) for b in banks}
days = []
for t in range(1, 32):
    day = 29 + t
    ct = sum(cb[b][:day + 1].astype(np.int64) for b in banks)
    bt = sum((cb[b][:day + 1] > 0).astype(np.int64) for b in banks)
    hr = how_test(ct, bt, last_days=2)
    kept: list[dict] = []
    for w in sorted(hr.flagged, key=lambda w: w["p"]):      # non-maximum suppression: overlapping windows of the same delay bin/dormant value collapse to the strongest
        if not any(k["delay_bin"] == w["delay_bin"] and k["dormant"] == w["dormant"] and k["skim_lo"] <= w["skim_hi"] and w["skim_lo"] <= k["skim_hi"]
                   and k["day_lo"] <= w["day_hi"] and w["day_lo"] <= k["day_hi"] for k in kept):
            kept.append(w)
    hr.flagged = kept
    wins = [{**w, "id": f"w{t}-{i}"} for i, w in enumerate(kept)]
    raised = {}
    for b in banks:
        ex = expand_how(sigs[b], hr.flagged)
        raised[b] = [{"client": c, "evidence": e} for c, e in sorted(ex.items())]
    days.append({"t": t, "date": f"2026-07-{t:02d}",
                 "banks": {b: cb[b][day - 2:day + 1].sum(axis=(0, 3)).tolist() for b in banks},     # last 3 days, 30 skim bins x 6 delay bins (dormant summed)
                 "total": ct[day - 2:day + 1].sum(axis=(0, 3)).tolist(), "windows": wins, "raised": raised})
out = {"world": Path(world).name, "demo_view": True, "hub_mode": meta["hub_mode"], "script_jitter": meta["script_jitter"], "banks": banks,
       "delay_labels": ["0-15 min", "15-60 min", "1-4 h", "4-12 h", "12-24 h", "24-72 h"], "days": days}
Path("outbreak/public").mkdir(parents=True, exist_ok=True)
Path("outbreak/public/data.json").write_text(json.dumps(out), encoding="utf-8")
print(f"outbreak/public/data.json: {len(days)} days, flagged windows on {sum(1 for d in days if d['windows'])} days")
