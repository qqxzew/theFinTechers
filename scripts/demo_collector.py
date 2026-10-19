"""make demo-collector: starts the collector and three bank processes locally and runs one round.

The logs show that the collector only ever holds masked vectors and sums. Output for the Outbreak page: outbreak/data.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WORLD = os.environ.get("DEMO_WORLD", "data/collector/1_rotating_medium")
DAY = 60          # 2026-07-31 on the replay clock (day 0 = 2026-06-01)
PORT = 8100
PY = sys.executable
ENV = {**os.environ, "PYTHONPATH": ".", "PYTHONIOENCODING": "utf-8", "COLLECTOR_BANKS": "B1,B2,B3", "COLLECTOR_P_INST": "30"}


def main() -> None:
    if not Path(WORLD, "tx.parquet").exists():
        seed, cell = Path(WORLD).name.split("_", 1)
        hub, jit = ("shared", "none") if cell == "crimefree" else cell.split("_")
        subprocess.run([PY, "-m", "redteam.generate_collector", "--seed", seed, "--hub", hub, "--jitter", jit, "--out", WORLD], check=True, env=ENV)
    shutil.rmtree("demo", ignore_errors=True)
    peers = Path("demo/keys")
    peers.mkdir(parents=True)
    coll = subprocess.Popen([PY, "-m", "uvicorn", "collector.service:app", "--port", str(PORT), "--log-level", "warning"], env=ENV)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/docs", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        # consortium operator publishes the allowlist as bucket ids (no account numbers) - computed with the shared key
        from node.collector_cli import CONSORTIUM_KEY
        from node.signatures import bucket_index
        reg = json.loads(Path(WORLD, "public_registry.json").read_text(encoding="utf-8"))
        body = json.dumps({"buckets": [bucket_index(CONSORTIUM_KEY, t) for t in reg]}).encode()
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/config/allowlist", body, {"Content-Type": "application/json"}))
        common = ["--data", WORLD, "--round", "demo", "--day", str(DAY), "--collector", f"http://127.0.0.1:{PORT}"]
        procs = [subprocess.Popen([PY, "-m", "node.collector_cli", "submit", "--bank", b, "--peers", str(peers), "--how-days", "61", *common], env=ENV)
                 for b in ("B1", "B2", "B3")]
        for p in procs:
            p.wait()
        for b in ("B1", "B2", "B3"):
            subprocess.run([PY, "-m", "node.collector_cli", "expand", "--bank", b, "--out", f"demo/out/{b}_raised.json", *common], check=True, env=ENV)
        subprocess.run([PY, "scripts/build_outbreak_data.py", WORLD], check=True, env=ENV)
        print("\nOpen outbreak/index.html through a static server:  python -m http.server 8200 -d outbreak  ->  http://127.0.0.1:8200")
    finally:
        coll.terminate()


if __name__ == "__main__":
    main()
