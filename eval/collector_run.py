"""Generate + replay the collector grid on a list of seeds (process pool over worlds).

python -m eval.collector_run --split dev --seeds 1 2 3 4 5
Writes eval/out/collector/<split>/<seed>_<cell>.json (flagged sets per replay day; no labels in it).
"""
from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

CELLS = [(h, j) for h in ("shared", "rotating") for j in ("none", "medium", "high")] + [("crimefree", "none")]


def cell_name(hub: str, jit: str) -> str:
    return "crimefree" if hub == "crimefree" else f"{hub}_{jit}"


def _one(args: tuple) -> tuple:
    seed, hub, jit, split, times = args
    from eval.collector_eval import replay_world
    from redteam.generate_collector import generate_collector
    name = cell_name(hub, jit)
    world = f"data/collector/{seed}_{name}"
    t0 = time.time()
    if not Path(world, "tx.parquet").exists():
        generate_collector(seed, world, hub_mode="shared" if hub == "crimefree" else hub, script_jitter=jit, crime_free=hub == "crimefree")
    replay_world(world, f"eval/out/collector/{split}/{seed}_{name}.json", times=times)
    return seed, name, round(time.time() - t0, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["dev", "test"])
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--times", type=int, nargs="*", default=None)
    a = ap.parse_args()
    os.environ.setdefault("POLARS_MAX_THREADS", "2")
    jobs = [(s, h, j, a.split, a.times) for s in a.seeds for h, j in CELLS]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for seed, name, secs in ex.map(_one, jobs):
            print(f"done seed={seed} cell={name} {secs}s", flush=True)


if __name__ == "__main__":
    main()
