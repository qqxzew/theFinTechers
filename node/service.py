"""One bank node as its own HTTP service (distributed mode). Run: python -m node.service --bank B1 --world data/redteam/seed101 --port 8101

The node loads ONLY its own bank's rows (lazy parquet scan filtered on bank_id; labels.parquet is never opened), runs the bank pipeline,
and keeps its NodeResult, its bank secret, its epoch key and every per-session PSI exponent in process memory. Tokens leave the node
only inside PSI (as blinded group elements) and, after a match, as keyed token ids (HMAC under the epoch key that the banks share out of
band via STAJ_EPOCH_KEY; the coordinator never holds it).

Endpoints the radar calls (cross-boundary): /health, /submission, /psi/blind, /psi/respond, /psi/finish, /psi/learn,
/session/{round_id}/match-rows, /clusters. Bank-internal endpoints (the bank's own analyst UI; the radar never calls them, a real
deployment binds them to the bank's internal network): /cases, /cases/{case_id}, /audit, /audit/verify.

Every PSI call is written to the node's OWN hash-chained audit log (actor, action, session, peer, counts; never tokens).
Security model: semi-honest (see docs/DISTRIBUTED.md). Never imports eval/ or redteam/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from audit.log import AuditLog, verify_chain
from common.schemas import Case
from copilot.case_json import build_case_json
from node.pipeline import NodeResult, apply_clusters, load_config, run_node
from radar.guards import Guards
from radar.psi.dh_psi import HEX_LEN, PsiParty
from radar.sessions import _bucket, token_id

PSI_DOMAIN = "staj-psi-v1"
SESSION_RE = re.compile(r"^(?P<round>[A-Za-z0-9_-]{1,64}):(?P<a>[A-Za-z0-9_-]{1,32}):(?P<b>[A-Za-z0-9_-]{1,32})$")
HEX_RE = re.compile(rf"^[0-9a-f]{{{HEX_LEN}}}$")
TRAFFIC_CAP_BYTES = 64 * 1024 * 1024


# ---------------------------------------------------------------------------------------------------------------------------- data
def load_bank_slice(world_dir: str, bank_id: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Only this bank's rows of tx/clients. labels.parquet (hidden ground truth) is never opened by a node."""
    tx = pl.scan_parquet(f"{world_dir}/tx.parquet").filter(pl.col("bank_id") == bank_id).collect()
    cl = (pl.scan_parquet(f"{world_dir}/clients.parquet").filter(pl.col("bank_id") == bank_id)
          .with_columns(pl.col("contract_date").dt.replace_time_zone(None)).collect())
    if cl.height == 0:
        raise ValueError(f"no clients for bank {bank_id} in {world_dir}")
    return tx, cl


@dataclass
class BankView:
    """What the node is willing to put into PSI and post-match rows. Same construction as eval.redteam_eval.to_bank_node (copied here
    because node/ must not import eval/)."""
    candidates: list[dict]
    rarity: dict[str, float]
    stats: dict[str, dict]

    @classmethod
    def of(cls, r: NodeResult) -> BankView:
        feat = {row["client_id"]: row for row in r.features.select(["client_id", "lag_median_h", "retention_median"]).to_dicts()}
        stats = {ref: {k: feat[cid][k] for k in ("lag_median_h", "retention_median")} for ref, cid in r.ref_to_client.items()}
        rarity = {c["token"]: 1.0 / max(1, r.degree.get(c["token"], 1)) for c in r.candidates}
        return cls(r.candidates, rarity, stats)

    def submission(self) -> list[dict]:
        best: dict[str, float] = {}
        for c in self.candidates:
            best[c["token"]] = max(best.get(c["token"], 0.0), c["score"])
        return [{"token": t, "score": s} for t, s in best.items()]

    def refs_for(self, token: str) -> list[str]:
        return sorted({c["cand_ref"] for c in self.candidates if c["token"] == token})


@dataclass
class PsiSession:
    party: PsiParty | None
    role: str          # "initiator" | "responder"
    peer: str
    round_id: str
    state: str         # blinded | responded | done


@dataclass
class NodeState:
    bank_id: str
    result: NodeResult
    view: BankView
    tx: pl.DataFrame
    feats: dict[str, dict]
    audit: AuditLog
    epoch_key: bytes
    guards: Guards
    cases: dict[str, Case] = field(default_factory=dict)
    sessions: dict[str, PsiSession] = field(default_factory=dict)
    matched: dict[str, set[str]] = field(default_factory=dict)       # round_id -> own tokens learned in PSI
    cluster_info: dict[str, dict] = field(default_factory=dict)      # cluster_id -> minimal post-match info
    lock: threading.Lock = field(default_factory=threading.Lock)

    def log(self, action: str, why: str, **extra) -> None:
        self.audit.append(actor=f"node:{self.bank_id}", action=action, why=why, rule_version="psi-1", model_version=None,
                          input_hash=hashlib.sha256(json.dumps(extra, sort_keys=True, default=str).encode()).hexdigest()[:16], **extra)


# ---------------------------------------------------------------------------------------------------------------------------- bodies
class BlindBody(BaseModel):
    session_id: str
    peer: str


class RespondBody(BaseModel):
    session_id: str
    peer: str
    incoming: list[str]


class FinishBody(BaseModel):
    session_id: str
    double: list[str]
    blind: list[str]


class LearnBody(BaseModel):
    session_id: str
    returned: list[str]


class ClustersBody(BaseModel):
    round_id: str
    clusters: list[dict]


# ---------------------------------------------------------------------------------------------------------------------------- traffic
class TrafficRecorder:
    """Pure ASGI middleware: records every request/response body this node exchanged, verbatim (size-capped). Used by the
    integration test to inspect what crossed the node boundary from the node's side."""

    def __init__(self, app, sink: list[dict], cap: int = TRAFFIC_CAP_BYTES) -> None:
        self.app, self.sink, self.cap, self.used = app, sink, cap, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        req_chunks: list[bytes] = []
        resp_chunks: list[bytes] = []
        status = {"code": 0}

        async def recv():
            msg = await receive()
            if msg["type"] == "http.request":
                req_chunks.append(msg.get("body", b""))
            return msg

        async def snd(msg):
            if msg["type"] == "http.response.start":
                status["code"] = msg["status"]
            elif msg["type"] == "http.response.body":
                resp_chunks.append(msg.get("body", b""))
            await send(msg)

        await self.app(scope, recv, snd)
        req, resp = b"".join(req_chunks), b"".join(resp_chunks)
        entry = {"method": scope["method"], "path": scope["path"], "status": status["code"], "request_bytes": len(req), "response_bytes": len(resp)}
        if self.used + len(req) + len(resp) <= self.cap:
            entry |= {"request": req.decode("utf-8", "replace"), "response": resp.decode("utf-8", "replace")}
            self.used += len(req) + len(resp)
        else:
            entry["truncated"] = True
        self.sink.append(entry)


# ---------------------------------------------------------------------------------------------------------------------------- app
def _hex_ok(elems: list[str]) -> bool:
    return all(HEX_RE.match(e) for e in elems)


def build_node_state(bank_id: str, world_dir: str, secret: bytes | str, epoch_key: bytes | str | None = None,
                     audit_path: str | None = None, cfg: dict | None = None) -> NodeState:
    cfg = cfg or load_config()
    secret_b = secret.encode() if isinstance(secret, str) else secret
    ek = epoch_key if epoch_key is not None else os.environ.get("STAJ_EPOCH_KEY")
    if not ek:
        raise RuntimeError("epoch key missing: banks share it out of band via STAJ_EPOCH_KEY (the coordinator never holds it)")
    ek_b = ek.encode() if isinstance(ek, str) else ek
    tx, cl = load_bank_slice(world_dir, bank_id)
    res = run_node(bank_id, tx, cl, cfg, bank_secret=secret_b)
    audit_path = audit_path or os.environ.get("STAJ_NODE_AUDIT") or f"eval/out/audit_node_{bank_id}.jsonl"
    Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
    st = NodeState(bank_id, res, BankView.of(res), tx, {r["client_id"]: r for r in res.features.to_dicts()}, AuditLog(audit_path),
                   ek_b, Guards(cfg["radar_guards"]))
    st.cases = {c.case_id: c for c in res.cases}
    st.log("node_started", f"{len(res.cases)} cases, {len(st.view.submission())} exportable tokens", n_tx=tx.height, n_clients=cl.height)
    return st


def create_node_app(bank_id: str, world_dir: str, secret: bytes | str, epoch_key: bytes | str | None = None,
                    audit_path: str | None = None, cfg: dict | None = None) -> FastAPI:
    st = build_node_state(bank_id, world_dir, secret, epoch_key, audit_path, cfg)
    app = FastAPI(title=f"Stáj bank node {bank_id}", version="1")
    traffic: list[dict] = []
    app.state.node = st
    app.state.traffic = traffic
    app.add_middleware(TrafficRecorder, sink=traffic)

    def refuse(action: str, session_id: str, peer: str, reason: str, code: int = 403):
        st.log("psi_refused", reason, call=action, session=session_id[:200], peer=peer[:40])
        raise HTTPException(code, f"refused: {reason}")

    def parse_session(action: str, session_id: str, peer: str) -> tuple[str, str]:
        m = SESSION_RE.match(session_id)
        if not m or st.bank_id not in (m["a"], m["b"]) or m["a"] == m["b"]:
            refuse(action, session_id, peer, "malformed session id or this node is not a party", 400)
        other = m["b"] if m["a"] == st.bank_id else m["a"]
        if peer != other:
            refuse(action, session_id, peer, "peer does not match session id", 400)
        return m["round"], other

    @app.get("/health")
    def health():
        return {"ok": True, "bank_id": st.bank_id, "role": "bank-node"}

    @app.get("/submission")
    def submission():
        """Guard-checkable summary only: counts and scored share. Tokens in clear never leave the node."""
        sub = st.view.submission()
        unscored = sum(1 for s in sub if s["score"] is None)
        return {"bank_id": st.bank_id, "token_count": len(sub), "unscored_count": unscored,
                "scored_share": round(1 - unscored / len(sub), 4) if sub else 0.0}

    @app.post("/psi/blind")
    def psi_blind(body: BlindBody):
        round_id, peer = parse_session("blind", body.session_id, body.peer)
        m = SESSION_RE.match(body.session_id)
        with st.lock:
            if body.session_id in st.sessions:
                refuse("blind", body.session_id, peer, "replay: session id already used", 409)
            if m["a"] != st.bank_id:
                refuse("blind", body.session_id, peer, "this node is not the initiator of the session", 400)
            sub = st.view.submission()
            d = st.guards.check(peer, sub, datetime.now(UTC))
            if not d.allowed:
                refuse("blind", body.session_id, peer, d.reason)
            party = PsiParty([s["token"] for s in sub], PSI_DOMAIN)       # fresh exponent for this session
            out = party.blind()
            st.sessions[body.session_id] = PsiSession(party, "initiator", peer, round_id, "blinded")
            st.log("psi_blind", f"sent {len(out)} blinded elements to {peer}", call="blind", session=body.session_id, peer=peer, n_out=len(out))
        return {"blind": out}

    @app.post("/psi/respond")
    def psi_respond(body: RespondBody):
        round_id, peer = parse_session("respond", body.session_id, body.peer)
        m = SESSION_RE.match(body.session_id)
        with st.lock:
            if body.session_id in st.sessions:
                refuse("respond", body.session_id, peer, "replay: session id already used", 409)
            if m["b"] != st.bank_id:
                refuse("respond", body.session_id, peer, "this node is not the responder of the session", 400)
            if not _hex_ok(body.incoming):
                refuse("respond", body.session_id, peer, f"incoming: not {HEX_LEN}-hex-char group elements", 400)
            # The responder cannot see the peer's scores; it applies the size / rate guards to the incoming set (singleton probes).
            d = st.guards.check(peer, [{"score": 1.0}] * len(body.incoming), datetime.now(UTC))
            if not d.allowed:
                refuse("respond", body.session_id, peer, d.reason)
            party = PsiParty([s["token"] for s in st.view.submission()], PSI_DOMAIN)
            try:
                double, blind = party.respond(body.incoming)
            except ValueError as e:
                refuse("respond", body.session_id, peer, f"invalid element: {e}", 400)
            st.sessions[body.session_id] = PsiSession(party, "responder", peer, round_id, "responded")
            st.log("psi_respond", f"double-blinded {len(double)}, sent {len(blind)} blinded to {peer}", call="respond",
                   session=body.session_id, peer=peer, n_in=len(body.incoming), n_out=len(double) + len(blind))
        return {"double": double, "blind": blind}

    @app.post("/psi/finish")
    def psi_finish(body: FinishBody):
        with st.lock:
            s = st.sessions.get(body.session_id)
            if s is None or s.role != "initiator" or s.state != "blinded":
                refuse("finish", body.session_id, s.peer if s else "?", "no open initiator session", 409)
            if not _hex_ok(body.double + body.blind):
                refuse("finish", body.session_id, s.peer, f"not {HEX_LEN}-hex-char group elements", 400)
            try:
                hits, back = s.party.finish(body.double, body.blind)
            except ValueError as e:
                refuse("finish", body.session_id, s.peer, f"invalid element: {e}", 400)
            st.matched.setdefault(s.round_id, set()).update(hits)
            s.party, s.state = None, "done"                              # exponent forgotten
            st.log("psi_finish", f"learned {len(hits)} matches with {s.peer}", call="finish", session=body.session_id, peer=s.peer,
                   n_in=len(body.double) + len(body.blind), n_out=len(back), matches=len(hits))
        return {"back": back}

    @app.post("/psi/learn")
    def psi_learn(body: LearnBody):
        with st.lock:
            s = st.sessions.get(body.session_id)
            if s is None or s.role != "responder" or s.state != "responded":
                refuse("learn", body.session_id, s.peer if s else "?", "no open responder session", 409)
            if not _hex_ok(body.returned):
                refuse("learn", body.session_id, s.peer, f"not {HEX_LEN}-hex-char group elements", 400)
            try:
                hits = s.party.learn_from_return(body.returned)
            except (ValueError, IndexError) as e:
                refuse("learn", body.session_id, s.peer, f"invalid return: {e}", 400)
            st.matched.setdefault(s.round_id, set()).update(hits)
            s.party, s.state = None, "done"
            st.log("psi_learn", f"learned {len(hits)} matches with {s.peer}", call="learn", session=body.session_id, peer=s.peer,
                   n_in=len(body.returned), matches=len(hits))
        return {"ok": True}

    @app.get("/session/{round_id}/match-rows")
    def match_rows(round_id: str):
        """Minimal post-match rows exactly as radar.sessions.run_radar builds them: keyed token id, bank, cand_ref, rarity, plus
        coarse lag (1 h) / retention (2 pp) buckets per matched candidate."""
        rows, stats, seen = [], [], set()
        for t in sorted(st.matched.get(round_id, set())):
            for ref in st.view.refs_for(t):
                rows.append({"token_id": token_id(st.epoch_key, t), "bank_id": st.bank_id, "cand_ref": ref, "rarity": st.view.rarity.get(t, 0.5)})
                if ref not in seen:
                    seen.add(ref)
                    s = st.view.stats.get(ref, {})
                    stats.append({"cand_ref": ref, "lag_bucket_h": _bucket(s.get("lag_median_h"), 1.0),
                                  "retention_bucket": _bucket(s.get("retention_median"), 0.02)})
        st.log("match_rows_released", f"{len(rows)} rows for round {round_id}", round=round_id, n_rows=len(rows))
        return {"bank_id": st.bank_id, "round_id": round_id, "rows": rows, "stats": stats}

    @app.post("/clusters")
    def clusters(body: ClustersBody):
        """Minimal post-match exchange (master prompt 6.4): only disclosed clusters this bank is part of, with only its own refs."""
        own = [c for c in body.clusters if c.get("disclosed")]
        with st.lock:
            new_cases = apply_clusters(st.result, own)
            st.cases = {c.case_id: c for c in new_cases}
            for c in own:
                st.cluster_info[c["cluster_id"]] = dict(c.get("post_match") or {}) | {"cluster_id": c["cluster_id"]}
            n_in = sum(1 for c in new_cases if c.cluster_id)
            st.log("clusters_applied", f"{len(own)} disclosed clusters, {n_in} own cases in a cluster", round=body.round_id,
                   n_clusters=len(own), n_cases_in_cluster=n_in)
        return {"ok": True, "n_cases_in_cluster": n_in}

    # ---- bank-internal (analyst UI of this bank only)
    @app.get("/cases")
    def cases():
        items = []
        for cid, c in st.cases.items():
            items.append({"case_id": cid, "bank_id": c.bank_id, "client_ref": case_json(cid)["client_ref"], "priority": c.priority,
                          "triage": c.triage.value, "route": c.route, "cluster_id": c.cluster_id})
        items.sort(key=lambda x: -x["priority"])
        return {"bank_id": st.bank_id, "total": len(items), "items": items}

    def case_json(case_id: str) -> dict:
        c = st.cases[case_id]
        cj = build_case_json(c, st.feats[c.client_id], st.cluster_info.get(c.cluster_id) if c.cluster_id else None)
        cj["case_id"] = case_id
        return cj

    @app.get("/cases/{case_id}")
    def case(case_id: str):
        if case_id not in st.cases:
            raise HTTPException(404, "unknown case")
        c = st.cases[case_id]
        cj = case_json(case_id)
        t = st.tx.filter(pl.col("client_id") == c.client_id).sort("ts")
        tl = [{"ts": r["ts"].isoformat(), "direction": r["direction"], "amount_czk": r["amount_czk"], "counterparty": r["counterparty_token"]}
              for r in t.tail(60).to_dicts()]
        return {**cj, "timeline": tl, "radar_cluster": st.cluster_info.get(c.cluster_id) if c.cluster_id else None}

    @app.get("/audit")
    def audit(offset: int = 0, limit: int = 200):
        lines = st.audit.path.read_text(encoding="utf-8").splitlines()
        return {"total": len(lines), "entries": [json.loads(x) for x in lines[offset:offset + min(limit, 1000)]]}

    @app.get("/audit/verify")
    def audit_verify():
        ok, bad = verify_chain(st.audit.path)
        return {"ok": ok, "bad_index": bad, "length": len(st.audit.path.read_text(encoding="utf-8").splitlines())}

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one Stáj bank node as an HTTP service")
    ap.add_argument("--bank", default=os.environ.get("STAJ_BANK_ID", "B1"))
    ap.add_argument("--world", default=os.environ.get("STAJ_WORLD", "data/redteam/seed101"))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8101")))
    a = ap.parse_args()
    import uvicorn

    secret = os.environ.get("STAJ_BANK_SECRET") or f"secret-{a.bank}"   # demo default = the in-process eval's secret
    uvicorn.run(create_node_app(a.bank, a.world, secret), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
