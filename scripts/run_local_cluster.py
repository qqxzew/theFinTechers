"""Start 3 bank-node services + 1 radar coordinator as REAL separate processes (uvicorn, ports 8101-8103 and 8200), run one radar
round over HTTP, print the disclosed clusters and the traffic summary, check the recorded wire for leaks, tear everything down.

    python scripts/run_local_cluster.py [world_dir] [--json]
    (default world: data/redteam/seed101; small/fast: data/redteam/seed909)

Each node process gets its bank id, its own bank secret and the shared epoch key (STAJ_EPOCH_KEY, random per run) through its
environment. The radar process gets only the node URLs - it never receives the epoch key or any secret. This is still ONE machine;
see docs/DISTRIBUTED.md for what is real and what is simulated.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx
import polars as pl

ROOT = Path(__file__).resolve().parent.parent
NODE_BASE_PORT, RADAR_PORT = 8101, 8200
OUT = ROOT / "eval" / "out" / "dist"


def _wait_health(url: str, proc: subprocess.Popen, name: str, timeout: float = 1200) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"{name} exited with code {proc.returncode}; see {OUT / (name + '.log')}")
        try:
            r = httpx.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(1.0)
    raise TimeoutError(f"{name} did not become healthy within {timeout}s")


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv if not a.startswith("--")]
    world = args[0] if args else "data/redteam/seed101"
    banks = sorted(pl.read_parquet(ROOT / world / "clients.parquet", columns=["bank_id"])["bank_id"].unique().to_list())
    OUT.mkdir(parents=True, exist_ok=True)
    epoch_key = secrets.token_hex(16)                       # shared by the banks only
    base_env = {k: v for k, v in os.environ.items() if not k.startswith("STAJ_")}
    base_env |= {"PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    procs: list[tuple[str, subprocess.Popen, object]] = []
    urls = {b: f"http://127.0.0.1:{NODE_BASE_PORT + i}" for i, b in enumerate(banks)}
    say = (lambda *a: print(*a, file=sys.stderr)) if as_json else print
    try:
        for i, b in enumerate(banks):
            audit = OUT / f"audit_node_{b}.jsonl"
            audit.unlink(missing_ok=True)
            env = base_env | {"STAJ_EPOCH_KEY": epoch_key, "STAJ_BANK_SECRET": f"secret-{b}", "STAJ_NODE_AUDIT": str(audit)}
            log = open(OUT / f"node_{b}.log", "w", encoding="utf-8")
            p = subprocess.Popen([sys.executable, "-m", "node.service", "--bank", b, "--world", world, "--port", str(NODE_BASE_PORT + i)],
                                 cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            procs.append((f"node_{b}", p, log))
        radar_audit = OUT / "audit_radar.jsonl"
        radar_audit.unlink(missing_ok=True)
        log = open(OUT / "radar.log", "w", encoding="utf-8")
        nodes_spec = ",".join(f"{b}={u}" for b, u in urls.items())
        p = subprocess.Popen([sys.executable, "-m", "radar.service", "--nodes", nodes_spec, "--port", str(RADAR_PORT)], cwd=ROOT,
                             env=base_env | {"STAJ_RADAR_AUDIT": str(radar_audit)}, stdout=log, stderr=subprocess.STDOUT)
        procs.append(("radar", p, log))
        say(f"started {len(banks)} node processes + radar (pids {[q.pid for _, q, _ in procs]}); world {world}; waiting for /health ...")
        t0 = time.time()
        for (name, proc, _), url in zip(procs, [*urls.values(), f"http://127.0.0.1:{RADAR_PORT}"], strict=True):
            h = _wait_health(url, proc, name)
            say(f"  {name:8s} healthy at {url}  {h}  (+{time.time() - t0:.0f}s)")
        radar = f"http://127.0.0.1:{RADAR_PORT}"
        t1 = time.time()
        summary = httpx.post(f"{radar}/run", timeout=3600).raise_for_status().json()
        say(f"\nround {summary['round_id']} done in {time.time() - t1:.1f}s; live={summary['live']} refused={summary['refused']}")
        for s in summary["sessions"]:
            say(f"  PSI {s['session']}: ok={s['ok']} elements={s.get('elements')} {s.get('refused', '')}")
        cl = httpx.get(f"{radar}/clusters", params={"disclosed_only": True}, timeout=60).json()["clusters"]
        say(f"\n{len(cl)} disclosed clusters:")
        for c in cl:
            say(f"  {c['cluster_id']}  banks={','.join(c['banks'])}  candidates={len(c['candidates'])}  tokens={len(c['tokens'])}  "
                f"score={c['score']:.3f}  same_hand_global={c['same_hand_global']}")
        wire = httpx.get(f"{radar}/wire", timeout=600).json()
        say(f"\ntraffic relayed by the radar: {wire['messages']} HTTP exchanges, {wire['bytes_total']:,} bytes (truncated={wire['truncated']})")
        for path, v in sorted(wire["by_path"].items()):
            say(f"  {path:32s} {v['messages']:4d} msgs {v['bytes']:>12,} bytes")
        # leak check on the recorded wire (this harness reads the world to know what must NOT appear; the services never do)
        tx = pl.read_parquet(ROOT / world / "tx.parquet", columns=["counterparty_token", "client_id", "tx_id"])
        forbidden = set(tx["counterparty_token"].unique().to_list()) | set(tx["client_id"].unique().to_list())
        corpus = "\n".join(e.get("request", "") + e.get("response", "") for e in wire["entries"])
        words = set(re.findall(r"[A-Za-z0-9_]+", corpus))
        leaks = sorted(words & forbidden)[:5]
        leak = "clean" if not leaks and not wire["truncated"] and epoch_key not in corpus else f"LEAK {leaks}"
        say(f"leak check (tokens, client ids, epoch key on the wire): {leak}")
        audits = {b: httpx.get(f"{u}/audit/verify", timeout=30).json() for b, u in urls.items()}
        audits["radar"] = httpx.get(f"{radar}/audit/verify", timeout=30).json()
        say("audit chains: " + ", ".join(f"{k}={'ok' if v['ok'] else 'BROKEN'}({v['length']})" for k, v in audits.items()))
        if as_json:
            print(json.dumps({"round_id": summary["round_id"], "clusters_disclosed": len(cl), "raw_records_exposed": summary["exposure"]["raw_records_exposed"],
                              "exposure": summary["exposure"], "leak_check": leak, "audit_ok": all(v["ok"] for v in audits.values())}))
        return 0 if leak == "clean" and all(v["ok"] for v in audits.values()) else 1
    finally:
        for _, proc, _ in procs:
            if proc.poll() is None:
                proc.terminate()
        for _, proc, log in procs:
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()
        say("all processes stopped")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
