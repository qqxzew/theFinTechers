"""Distributed mode: one FastAPI app per bank node + a radar coordinator talking HTTP/JSON (in-memory ASGI transport, no ports).

(a) the distributed run discloses the same clusters as the in-process radar.sessions.run_radar on the same node results;
(b) traffic inspection: nothing raw (counterparty tokens, client ids, tx columns/values, secrets) appears in anything that crossed a
    node boundary, and every PSI element is a valid group element of the right length;
(c) a node refuses a singleton probe at /psi/respond and logs it;
(d) every node's own audit chain verifies and has one entry per PSI call it served;
(e) compromised-coordinator thought experiment.
The slow test at the end starts real uvicorn subprocesses (set STAJ_SLOW_TESTS=1).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx
import polars as pl
import pytest

from audit.log import verify_chain
from node.pipeline import apply_clusters, load_config
from node.service import PSI_DOMAIN, create_node_app
from radar.guards import Guards
from radar.psi.dh_psi import HEX_LEN, P, Q, hash_to_group
from radar.service import create_radar_app
from radar.sessions import BankNode, run_radar
from radar.transport import AsgiTransport

WORLD = "data/redteam/seed909"
EPOCH = b"epoch-test-909"
PSI_FIELDS = ("blind", "incoming", "double", "back", "returned")
RAW_TX_COLUMNS = {"ts", "amount_czk", "amount_orig", "currency", "direction", "counterparty_token", "payer_country", "payee_country",
                  "channel_type", "tx_id", "client_id", "own_account", "source_dataset", "client_country", "contract_date", "pep",
                  "expected_volume", "q2_volume", "q2_max", "aml_risk", "timeline", "features", "client_ref"}
ALLOWED_KEYS = {"ok", "role", "bank_id", "token_count", "unscored_count", "scored_share", "session_id", "peer", "incoming", "double",
                "blind", "back", "returned", "round_id", "rows", "stats", "token_id", "cand_ref", "rarity", "lag_bucket_h",
                "retention_bucket", "clusters", "cluster_id", "disclosed", "score", "same_hand_global", "candidates", "post_match",
                "n_other_banks", "n_other_candidates", "matched_tokens", "lag_ret_concentration", "n_cases_in_cluster", "detail"}


def _ensure_world() -> None:
    if not Path(WORLD, "tx.parquet").exists():
        subprocess.run([sys.executable, "-m", "redteam.generate", "--seed", "909", "--out", WORLD, "--n-per-bank", "300"], check=True)


async def _radar_call(app, method: str, path: str):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://radar", timeout=600) as c:
        r = await c.request(method, path)
        return r.status_code, r.json()


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    _ensure_world()
    d = tmp_path_factory.mktemp("dist")
    cfg = load_config()
    banks = sorted(pl.read_parquet(f"{WORLD}/clients.parquet", columns=["bank_id"])["bank_id"].unique().to_list())
    apps = {b: create_node_app(b, WORLD, f"secret-{b}", epoch_key=EPOCH, audit_path=str(d / f"audit_{b}.jsonl"), cfg=cfg) for b in banks}
    transport = AsgiTransport(apps)
    radar = create_radar_app(cfg={"radar_guards": cfg["radar_guards"]}, transport=transport, audit_path=str(d / "audit_radar.jsonl"))
    status, summary = asyncio.run(_radar_call(radar, "POST", "/run"))
    assert status == 200, summary
    first_round_log = len(transport.log)
    return {"apps": apps, "banks": banks, "transport": transport, "radar": radar, "summary": summary, "cfg": cfg,
            "first_round_log": first_round_log, "dir": d}


def _key(c) -> tuple:
    return (frozenset(tuple(x) for x in c["candidates"]), frozenset(c["tokens"]))


def _bodies(entries: list[dict]) -> list:
    out = []
    for e in entries:
        for k in ("request", "response"):
            if e.get(k):
                out.append(json.loads(e[k]))
    return out


def _keys(obj, acc: set) -> set:
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, acc)
    return acc


def _psi_elements(entries: list[dict]) -> list[str]:
    out = []
    for body in _bodies(entries):
        if isinstance(body, dict):
            for f in PSI_FIELDS:
                if isinstance(body.get(f), list):
                    out.extend(body[f])
    return out


# ------------------------------------------------------------------------------------------------------------------------------ (a)
def test_same_clusters_as_in_process(dist):
    nodes = []
    for b in dist["banks"]:
        v = dist["apps"][b].state.node.view
        nodes.append(BankNode(b, v.candidates, v.rarity, v.stats))
    ref = run_radar(nodes, Guards(dist["cfg"]["radar_guards"]), epoch_key=EPOCH)
    got = dist["radar"].state.coordinator.clusters
    assert dist["summary"]["refused"] == ref.refused == {}
    assert {_key(c) for c in got} == {_key(c) for c in ref.clusters}
    assert {_key(c) for c in got if c["disclosed"]} == {_key(c) for c in ref.clusters if c["disclosed"]}
    assert sum(c["disclosed"] for c in got) >= 1, "test world must produce at least one disclosed cluster"
    by_id = {c["cluster_id"]: c for c in ref.clusters}
    for c in got:
        r = by_id[c["cluster_id"]]
        assert (c["score"], c["same_hand_global"], c["lag_ret_concentration"]) == (r["score"], r["same_hand_global"], r["lag_ret_concentration"])
        assert c["post_match"] == r["post_match"]
    # the node-side cases after the minimal push equal the in-process apply_clusters
    for b in dist["banks"]:
        st = dist["apps"][b].state.node
        exp = {c.case_id: (c.priority, c.cluster_id, c.triage) for c in apply_clusters(st.result, ref.clusters)}
        assert {cid: (c.priority, c.cluster_id, c.triage) for cid, c in st.cases.items()} == exp


# ------------------------------------------------------------------------------------------------------------------------------ (b)
def test_traffic_has_no_raw_data(dist):
    radar_log = dist["transport"].log
    node_logs = [e for b in dist["banks"] for e in dist["apps"][b].state.traffic]
    assert radar_log and node_logs and not any(e.get("truncated") for e in radar_log + node_logs)
    corpus = "\n".join(e.get(k, "") for e in radar_log + node_logs for k in ("path", "request", "response"))
    words = set(re.findall(r"[A-Za-z0-9_]+", corpus))
    tx = pl.read_parquet(f"{WORLD}/tx.parquet")
    cl = pl.read_parquet(f"{WORLD}/clients.parquet")
    tokens = set(tx["counterparty_token"].unique().to_list())
    clients = set(cl["client_id"].to_list()) | set(tx["own_account"].unique().to_list())
    assert not words & tokens, "plaintext counterparty token on the wire"
    assert not words & clients, "client id on the wire"
    assert not words & set(tx["tx_id"].to_list()), "tx id on the wire"
    exported = {c["token"] for b in dist["banks"] for c in dist["apps"][b].state.node.view.candidates}
    assert exported and all(t not in corpus for t in exported)            # substring check for the tokens that actually went into PSI
    for secret in [f"secret-{b}" for b in dist["banks"]] + [EPOCH.decode(), EPOCH.hex()]:
        assert secret not in corpus
    assert not re.search(r"20\d\d-\d\d-\d\d", corpus), "timestamp on the wire"
    amounts = {f"{a:.2f}" for a in tx["amount_czk"].to_list() if a >= 100 and round(a, 2) != int(a)}
    assert not set(re.findall(r"\d+\.\d\d", corpus)) & amounts, "transaction amount on the wire"
    bodies = _bodies(radar_log + node_logs)
    keys = _keys(bodies, set())
    assert not keys & RAW_TX_COLUMNS
    assert keys <= ALLOWED_KEYS, keys - ALLOWED_KEYS
    r1 = radar_log[:dist["first_round_log"]]
    psi = [e for e in r1 if e["path"].startswith("/psi/")]
    sent = [x for e in psi for f in PSI_FIELDS for x in (json.loads(e["response"]).get(f) or [])]
    relayed = [x for e in psi for f in PSI_FIELDS for x in (json.loads(e["request"]).get(f) or [])]
    assert len(sent) == dist["summary"]["exposure"]["blinded_elements"] > 0
    assert set(relayed) <= set(sent), "the relay forwards node output verbatim and never injects elements"
    elems = _psi_elements(radar_log)
    for e in set(elems):
        assert len(e) == HEX_LEN and re.fullmatch(r"[0-9a-f]+", e)
        x = int(e, 16)
        assert 1 < x < P - 1 and pow(x, Q, P) == 1, "not an element of the prime-order subgroup"


# ------------------------------------------------------------------------------------------------------------------------------ (c)
def test_singleton_probe_refused_and_logged(dist):
    b1, b2 = dist["banks"][0], dist["banks"][1]
    app = dist["apps"][b2]
    probe = format(pow(hash_to_group("ACZ00001", PSI_DOMAIN), 12345, P), "0512x")
    sid = f"probe1:{b1}:{b2}"

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://n") as c:
            return await c.post("/psi/respond", json={"session_id": sid, "peer": b1, "incoming": [probe]})
    r = asyncio.run(go())
    assert r.status_code == 403 and "min_set_size" in r.json()["detail"]
    lines = [json.loads(x) for x in app.state.node.audit.path.read_text(encoding="utf-8").splitlines()]
    hit = [e for e in lines if e["action"] == "psi_refused" and e["extra"].get("session") == sid]
    assert len(hit) == 1 and hit[0]["extra"]["call"] == "respond" and "min_set_size" in hit[0]["why"]
    assert sid not in app.state.node.sessions


# ------------------------------------------------------------------------------------------------------------------------------ (d)
def test_node_audit_chains(dist):
    for b in dist["banks"]:
        app = dist["apps"][b]
        path = app.state.node.audit.path
        assert verify_chain(path) == (True, None)
        psi_calls = [e for e in app.state.traffic if e["path"].startswith("/psi/")]
        entries = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        psi_entries = [e for e in entries if e["action"].startswith("psi_")]
        assert len(psi_entries) == len(psi_calls) > 0
        assert {e["extra"]["call"] for e in psi_entries} <= {"blind", "respond", "finish", "learn"}
        for e in psi_entries:                                               # counts only, never tokens
            assert set(e["extra"]) <= {"call", "session", "peer", "n_in", "n_out", "matches"}
    status, v = asyncio.run(_radar_call(dist["radar"], "GET", "/audit/verify"))
    assert status == 200 and v["ok"] and v["length"] > 0


# ------------------------------------------------------------------------------------------------------------------------------ (e)
def test_compromised_coordinator(dist):
    t = dist["transport"]
    round1 = t.log[:dist["first_round_log"]]
    status, s2 = asyncio.run(_radar_call(dist["radar"], "POST", "/run"))
    assert status == 200 and s2["round_id"] != dist["summary"]["round_id"]
    round2 = t.log[dist["first_round_log"]:]
    e1, e2 = set(_psi_elements(round1)), set(_psi_elements(round2))
    assert e1 and e2 and not e1 & e2, "same token must blind to different elements in different sessions (fresh exponents)"
    # dictionary attack with the full token universe: unblinded H(t) never appears, so hashing candidates does not help
    tokens = pl.read_parquet(f"{WORLD}/tx.parquet", columns=["counterparty_token"])["counterparty_token"].unique().to_list()
    exported = {c["token"] for b in dist["banks"] for c in dist["apps"][b].state.node.view.candidates}
    hashed = {format(hash_to_group(x, PSI_DOMAIN), "0512x") for x in exported | set(tokens[:500])}
    assert not hashed & (e1 | e2)
    corpus = "".join(e.get("request", "") + e.get("response", "") for e in t.log)
    assert not any(x in corpus for x in exported)
    # HONEST known leak: the relay sees both double-blinded sets of a session, so it learns the per-pair intersection SIZE
    # (not which tokens). It equals what the initiator learned; match rows reveal the same count later anyway.
    by_sid: dict[str, dict] = {}
    for e in round1:
        if e["path"] in ("/psi/respond", "/psi/finish") and e["status"] == 200:
            sid = json.loads(e["request"])["session_id"]
            by_sid.setdefault(sid, {})[e["path"]] = json.loads(e["response"])
    assert by_sid
    for sid, m in by_sid.items():
        inferred = len(set(m["/psi/respond"]["double"]) & set(m["/psi/finish"]["back"]))
        initiator = sid.split(":")[1]
        lines = [json.loads(x) for x in dist["apps"][initiator].state.node.audit.path.read_text(encoding="utf-8").splitlines()]
        learned = [x["extra"]["matches"] for x in lines if x["action"] == "psi_finish" and x["extra"]["session"] == sid]
        assert learned == [inferred]


# ------------------------------------------------------------------------------------------------------------------------------ slow
@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("STAJ_SLOW_TESTS") != "1", reason="starts real uvicorn subprocesses on ports 8101-8103/8200; set STAJ_SLOW_TESTS=1")
def test_real_processes_on_ports():
    _ensure_world()
    env = {**os.environ, "PYTHONPATH": ".", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "scripts/run_local_cluster.py", WORLD, "--json"], capture_output=True, text=True, env=env, timeout=1800)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["clusters_disclosed"] >= 1 and out["raw_records_exposed"] == 0 and out["leak_check"] == "clean"
