"""Radar coordinator as its own HTTP service (distributed mode).
Run: python -m radar.service --nodes B1=http://127.0.0.1:8101,B2=http://127.0.0.1:8102,B3=http://127.0.0.1:8103 --port 8200

The coordinator orchestrates pairwise DH-PSI sessions between bank nodes over HTTP. It RELAYS blinded hex group elements between the
two nodes of a session; it never holds a PSI exponent, a plaintext token, the epoch key or a client id. It applies radar.guards.Guards
to the nodes' submission summaries (counts and scored share only), collects the minimal post-match rows, runs
radar.clustering.build_clusters plus the post-match lag/retention concentration step of radar.sessions.run_radar (replicated in
`post_match`, because run_radar does not expose it as a function), and pushes back to each node only the minimal exchange of master
prompt 6.4 for disclosed clusters it is part of.

Endpoints: GET /health, POST /run (one full round), GET /clusters, GET /wire (every relayed request/response, verbatim, size-capped),
GET /audit, GET /audit/verify. Security model: semi-honest (docs/DISTRIBUTED.md). Never imports eval/ or redteam/.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException

from audit.log import AuditLog, verify_chain
from radar.clustering import build_clusters
from radar.guards import Guards
from radar.psi.dh_psi import HEX_LEN
from radar.transport import HttpTransport, Transport

HEX_RE = re.compile(rf"^[0-9a-f]{{{HEX_LEN}}}$")


def load_radar_cfg(path: str = "config/thresholds.yaml") -> dict:
    return {"radar_guards": yaml.safe_load(open(path, encoding="utf-8"))["radar_guards"]}


def post_match(clusters: list[dict], lagret: dict[tuple[str, str], tuple]) -> list[dict]:
    """Same-hand-global concentration + per-bank minimal exchange. Replicates the loop after build_clusters in radar.sessions.run_radar."""
    for c in clusters:
        stats = [lagret[k] for k in c["candidates"] if k in lagret and lagret[k][0] is not None and lagret[k][1] is not None]
        c["post_match"] = {}
        if len(stats) >= 3:
            lags = sorted(s[0] for s in stats)
            rets = sorted(s[1] for s in stats)
            ml, mr = lags[len(lags) // 2], rets[len(rets) // 2]
            conc = sum(1 for s in stats if abs(s[0] - ml) <= 1.0 and abs(s[1] - mr) <= 0.02) / len(stats)
            c["same_hand_global"] = bool(conc >= 0.7 and mr >= 0.01)
            c["lag_ret_concentration"] = round(conc, 2)
            if c["same_hand_global"]:
                c["score"] = round(min(1.0, c["score"] + 0.15), 4)
        else:
            c["same_hand_global"] = False
            c["lag_ret_concentration"] = None
        for bank in c["banks"]:
            own = [x for x in c["candidates"] if x[0] == bank]
            c["post_match"][bank] = {"cluster_id": c["cluster_id"], "n_other_banks": len(c["banks"]) - 1,
                                     "n_other_candidates": len(c["candidates"]) - len(own), "matched_tokens": c["tokens"],
                                     "lag_ret_concentration": c["lag_ret_concentration"]}
    clusters.sort(key=lambda c: -c["score"])
    return clusters


def node_view(clusters: list[dict], bank: str) -> list[dict]:
    """What one bank receives: disclosed clusters it is part of, its OWN candidate refs only, and the 6.4 post-match summary."""
    return [{"cluster_id": c["cluster_id"], "disclosed": True, "score": c["score"], "same_hand_global": c["same_hand_global"],
             "candidates": [list(x) for x in c["candidates"] if x[0] == bank], "post_match": c["post_match"][bank]}
            for c in clusters if c["disclosed"] and bank in c["banks"]]


class Coordinator:
    def __init__(self, transport: Transport, cfg: dict, audit: AuditLog) -> None:
        self.t = transport
        self.guards = Guards(cfg["radar_guards"])
        self.audit = audit
        self.clusters: list[dict] = []
        self.rounds: list[dict] = []
        self._lock = asyncio.Lock()

    def _log(self, action: str, why: str, **extra) -> None:
        self.audit.append(actor="radar", action=action, why=why, rule_version="psi-1", model_version=None,
                          input_hash=hashlib.sha256(why.encode()).hexdigest()[:16], **extra)

    async def _call(self, bank: str, method: str, path: str, body=None) -> tuple[int, dict]:
        return await self.t.request(bank, method, path, body)

    async def run_round(self, now: datetime | None = None) -> dict:
        async with self._lock:
            return await self._run(now or datetime.now(UTC))

    async def _run(self, now: datetime) -> dict:
        round_id = secrets.token_hex(6)
        refused: dict[str, str] = {}
        live: list[str] = []
        for b in self.t.banks:
            s, sub = await self._call(b, "GET", "/submission")
            if s != 200:
                refused[b] = f"unreachable: HTTP {s}"
                continue
            n, k = int(sub["token_count"]), int(sub["unscored_count"])
            d = self.guards.check(b, [{"score": 1.0}] * (n - k) + [{"score": None}] * k, now)
            if d.allowed:
                live.append(b)
            else:
                refused[b] = d.reason
                self._log("submission_refused", d.reason, bank=b, round=round_id)
        sessions, elements, nbytes = [], 0, 0
        for a, b in itertools.combinations(live, 2):
            sid = f"{round_id}:{a}:{b}"
            info = {"session": sid, "initiator": a, "responder": b, "ok": False}
            sessions.append(info)
            s, r1 = await self._call(a, "POST", "/psi/blind", {"session_id": sid, "peer": b})
            if s != 200 or not self._valid(r1.get("blind")):
                info["refused"] = f"{a} blind: HTTP {s}: {r1.get('detail', '')}"
                self._log("psi_session_failed", info["refused"], session=sid)
                continue
            s, r2 = await self._call(b, "POST", "/psi/respond", {"session_id": sid, "peer": a, "incoming": r1["blind"]})
            if s != 200 or not (self._valid(r2.get("double")) and self._valid(r2.get("blind"))):
                info["refused"] = f"{b} respond: HTTP {s}: {r2.get('detail', '')}"
                self._log("psi_session_failed", info["refused"], session=sid)
                continue
            s, r3 = await self._call(a, "POST", "/psi/finish", {"session_id": sid, "double": r2["double"], "blind": r2["blind"]})
            if s != 200 or not self._valid(r3.get("back")):
                info["refused"] = f"{a} finish: HTTP {s}: {r3.get('detail', '')}"
                self._log("psi_session_failed", info["refused"], session=sid)
                continue
            s, _ = await self._call(b, "POST", "/psi/learn", {"session_id": sid, "returned": r3["back"]})
            info["ok"] = s == 200
            msgs = (r1["blind"], r2["double"], r2["blind"], r3["back"])
            info["elements"] = sum(len(m) for m in msgs)
            elements += info["elements"]
            nbytes += sum(len(e) for m in msgs for e in m) // 2
            self._log("psi_session_relayed", f"{a}->{b}: {info['elements']} blinded elements relayed", session=sid, ok=info["ok"])
        rows: list[dict] = []
        lagret: dict[tuple[str, str], tuple] = {}
        for b in live:
            s, mr = await self._call(b, "GET", f"/session/{round_id}/match-rows")
            if s != 200:
                continue
            for r in mr["rows"]:
                if r["bank_id"] == b:                      # a node can only speak for itself
                    rows.append({k: r[k] for k in ("token_id", "bank_id", "cand_ref", "rarity")})
            for x in mr["stats"]:
                lagret[(b, x["cand_ref"])] = (x["lag_bucket_h"], x["retention_bucket"])
        clusters = post_match(build_clusters(rows), lagret)
        for c in clusters:
            if c["disclosed"]:
                self._log("cluster_disclosed", f"{c['cluster_id']}: banks={len(c['banks'])} cand={len(c['candidates'])}",
                          cluster=c["cluster_id"], score=c["score"], round=round_id)
        pushed = {}
        for b in live:
            s, resp = await self._call(b, "POST", "/clusters", {"round_id": round_id, "clusters": node_view(clusters, b)})
            pushed[b] = resp.get("n_cases_in_cluster") if s == 200 else f"HTTP {s}"
        self.clusters = clusters
        exposure = {"mode": "staj_psi_distributed", "raw_records_exposed": 0, "blinded_elements": elements, "bytes_exchanged": nbytes,
                    "match_rows_to_coordinator": len(rows), "http_messages": len(self.t.log), "http_bytes_total": self.t.total_bytes}
        summary = {"round_id": round_id, "live": live, "refused": refused, "sessions": sessions, "exposure": exposure,
                   "clusters_disclosed": sum(1 for c in clusters if c["disclosed"]), "n_clusters": len(clusters),
                   "cases_in_cluster_per_bank": pushed}
        self.rounds.append(summary)
        self._log("round_done", f"round {round_id}: {summary['clusters_disclosed']} disclosed clusters", round=round_id)
        return summary

    @staticmethod
    def _valid(elems) -> bool:
        """The relay only checks shape (hex of the group's length); subgroup membership is checked by the receiving node."""
        return isinstance(elems, list) and all(isinstance(e, str) and HEX_RE.match(e) for e in elems)


def create_radar_app(node_urls: dict[str, str] | None = None, cfg: dict | None = None, *, transport: Transport | None = None,
                     audit_path: str | None = None) -> FastAPI:
    if transport is None:
        if not node_urls:
            raise ValueError("need node_urls or a transport")
        transport = HttpTransport(node_urls)
    cfg = cfg or load_radar_cfg()
    audit_path = audit_path or os.environ.get("STAJ_RADAR_AUDIT") or "eval/out/audit_radar.jsonl"
    Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
    coord = Coordinator(transport, cfg, AuditLog(audit_path))
    app = FastAPI(title="Stáj radar coordinator", version="1")
    app.state.coordinator = coord

    @app.get("/health")
    def health():
        return {"ok": True, "role": "radar-coordinator", "banks": transport.banks}

    @app.post("/run")
    async def run():
        return await coord.run_round()

    @app.get("/clusters")
    def clusters(disclosed_only: bool = False):
        cl = [c for c in coord.clusters if c["disclosed"] or not disclosed_only]
        return {"rounds": len(coord.rounds), "clusters": cl}

    @app.get("/wire")
    def wire(summary: bool = False, offset: int = 0, limit: int = 1000):
        log = transport.log
        by_path: dict[str, dict] = {}
        for e in log:
            key = re.sub(r"/session/[^/]+/", "/session/{round}/", e["path"])
            p = by_path.setdefault(key, {"messages": 0, "bytes": 0})
            p["messages"] += 1
            p["bytes"] += e["request_bytes"] + e["response_bytes"]
        head = {"messages": len(log), "bytes_total": transport.total_bytes, "bytes_recorded": transport.used_bytes,
                "cap_bytes": transport.cap_bytes, "truncated": any(e.get("truncated") for e in log), "by_path": by_path}
        if summary:
            return head
        return head | {"entries": log[offset:offset + min(limit, 5000)]}

    @app.get("/audit")
    def audit(offset: int = 0, limit: int = 200):
        import json
        lines = Path(audit_path).read_text(encoding="utf-8").splitlines() if Path(audit_path).exists() else []
        return {"total": len(lines), "entries": [json.loads(x) for x in lines[offset:offset + min(limit, 1000)]]}

    @app.get("/audit/verify")
    def audit_verify():
        if not Path(audit_path).exists():
            return {"ok": True, "bad_index": None, "length": 0}
        ok, bad = verify_chain(audit_path)
        return {"ok": ok, "bad_index": bad, "length": len(Path(audit_path).read_text(encoding="utf-8").splitlines())}

    @app.get("/rounds")
    def rounds():
        if not coord.rounds:
            raise HTTPException(404, "no round run yet (POST /run)")
        return {"rounds": coord.rounds}

    return app


def parse_nodes(spec: str) -> dict[str, str]:
    out = {}
    for part in spec.split(","):
        if part.strip():
            bank, _, url = part.strip().partition("=")
            out[bank] = url
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the Stáj radar coordinator as an HTTP service")
    ap.add_argument("--nodes", default=os.environ.get("STAJ_NODE_URLS", "B1=http://127.0.0.1:8101,B2=http://127.0.0.1:8102,B3=http://127.0.0.1:8103"))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8200")))
    a = ap.parse_args()
    import uvicorn

    uvicorn.run(create_radar_app(parse_nodes(a.nodes)), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
