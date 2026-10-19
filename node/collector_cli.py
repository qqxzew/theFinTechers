"""Bank CLI for the collector (runs INSIDE the bank; the raw data never leaves it).

python -m node.collector_cli submit --bank B1 --data data/collector/1_shared_none --round r1 --day 60 --peers demo/keys --collector http://127.0.0.1:8100
python -m node.collector_cli expand --bank B1 --data ... --round r1 --day 60 --collector ... --out demo/out/B1_raised.json

DH public keys are exchanged between the banks (a shared directory in the demo), never with the collector. The consortium HMAC key is shared by banks only.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.request
from pathlib import Path

import numpy as np
import polars as pl

from node.expansion import expand_how, expand_where
from node.secagg import BankKey, masked_vector
from node.signatures import build_signatures, how_vectors, where_vectors

CONSORTIUM_KEY = os.environ.get("CONSORTIUM_KEY", "demo-consortium-key").encode()
WINDOW = 30


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read())


def _load(bank: str, data: str):
    tx = pl.read_parquet(f"{data}/tx.parquet").filter(pl.col("bank_id") == bank)
    cl = pl.read_parquet(f"{data}/clients.parquet").with_columns(pl.col("contract_date").dt.replace_time_zone(None)).filter(pl.col("bank_id") == bank)
    return tx, cl


def _keys(bank: str, peers: Path, banks: list[str]) -> tuple[BankKey, dict[str, int]]:
    peers.mkdir(parents=True, exist_ok=True)
    kf = peers / f"{bank}.key"                      # local secret (a real bank keeps it in its own HSM)
    if kf.exists():
        key = BankKey(bank, int(kf.read_text()))
    else:
        key = BankKey(bank)
        kf.write_text(str(key._x))
    (peers / f"{bank}.pub").write_text(str(key.public))
    pubs: dict[str, int] = {}
    deadline = time.time() + 120
    while len(pubs) < len(banks) - 1 and time.time() < deadline:
        for b in banks:
            f = peers / f"{b}.pub"
            if b != bank and f.exists() and b not in pubs:
                pubs[b] = int(f.read_text())
        time.sleep(0.2)
    if len(pubs) < len(banks) - 1:
        raise SystemExit("peer public keys missing: a round needs all banks (no dropout recovery)")
    return key, pubs


def cmd_submit(a) -> None:
    banks = a.banks.split(",")
    tx, cl = _load(a.bank, a.data)
    sig = build_signatures(a.bank, tx, cl, CONSORTIUM_KEY)
    key, pubs = _keys(a.bank, Path(a.peers), banks)
    vecs = where_vectors(sig, a.day, WINDOW)
    for label in ("P", "K", "I"):
        mv = masked_vector(vecs[label], key, banks, pubs, a.round, label)
        _post(f"{a.collector}/rounds/{a.round}/submit", {"bank_id": a.bank, "label": label, "vector_b64": base64.b64encode(mv.astype("<u4").tobytes()).decode()})
    if a.how_days:
        for d in range(a.day - a.how_days + 1, a.day + 1):
            hv = how_vectors(sig, d)
            for label, name in (("C", f"C:{d}"), ("I", f"B:{d}")):
                mv = masked_vector(hv[label], key, banks, pubs, a.round, name)
                _post(f"{a.collector}/rounds/{a.round}/submit", {"bank_id": a.bank, "label": name, "vector_b64": base64.b64encode(mv.astype("<u4").tobytes()).decode()})
    print(f"[{a.bank}] submitted masked vectors for round {a.round}; raw data stayed in the bank", flush=True)


def cmd_expand(a) -> None:
    tx, cl = _load(a.bank, a.data)
    sig = build_signatures(a.bank, tx, cl, CONSORTIUM_KEY)
    fl = _get(f"{a.collector}/rounds/{a.round}/flags")
    where = [{"bucket": f["bucket"], "P": f["totals"]["P"], "K": f["totals"]["K"], "banks": f["banks"], "p": f["p"], "small": f["small"]} for f in fl["where"]["flagged"]]
    raised = expand_where(sig, where, a.day, WINDOW, {c: c for c in cl["client_id"].to_list()}, CONSORTIUM_KEY)
    for k, v in expand_how(sig, fl["how"]["flagged"]).items():
        raised.setdefault(k, v)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"bank": a.bank, "round": a.round, "raised": raised, "collector_flags": fl}, indent=1), encoding="utf-8")
    print(f"[{a.bank}] raised {len(raised)} customers locally (network_evidence attached); the analyst decides", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("submit", "expand"):
        p = sp.add_parser(name)
        p.add_argument("--bank", required=True)
        p.add_argument("--banks", default="B1,B2,B3")
        p.add_argument("--data", required=True)
        p.add_argument("--round", required=True)
        p.add_argument("--day", type=int, required=True)
        p.add_argument("--collector", default="http://127.0.0.1:8100")
        if name == "submit":
            p.add_argument("--peers", required=True)
            p.add_argument("--how-days", type=int, default=0)
        else:
            p.add_argument("--out", required=True)
    a = ap.parse_args()
    {"submit": cmd_submit, "expand": cmd_expand}[a.cmd](a)


if __name__ == "__main__":
    main()
