"""Radar coordinator: orchestrates pairwise PSI sessions between bank nodes and clusters the matches.

The coordinator sees only: blinded group elements (hex), keyed token ids, bank-local pseudonymous candidate refs, rarity values and
coarse lag/retention buckets. It never sees customer ids, transactions or plaintext tokens. Every wire message is recorded in `wire`
so an integration test can assert that no plaintext token or client id ever crossed a node boundary.

Security model: semi-honest parties (see ARCHITECTURE.md threat model). PSI minimises disclosure; it is not a legal basis for sharing.
"""
from __future__ import annotations

import hashlib
import hmac
import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime

from audit.log import AuditLog
from radar.clustering import build_clusters
from radar.guards import Guards
from radar.psi.dh_psi import PsiParty


@dataclass
class BankNode:
    """What a bank exposes to the radar. Built from the bank's own NodeResult; holds no raw transactions."""
    bank_id: str
    candidates: list[dict]          # [{'token','cand_ref','score'}]
    rarity: dict[str, float]        # token -> 1/bank_degree
    stats: dict[str, dict]          # cand_ref -> {'lag_median_h','retention_median'} (coarsened before sending)

    def submission(self) -> list[dict]:
        best: dict[str, float] = {}
        for c in self.candidates:
            best[c["token"]] = max(best.get(c["token"], 0.0), c["score"])
        return [{"token": t, "score": s} for t, s in best.items()]

    def refs_for(self, token: str) -> list[str]:
        return sorted({c["cand_ref"] for c in self.candidates if c["token"] == token})


@dataclass
class RadarResult:
    clusters: list[dict]
    refused: dict[str, str]
    exposure: dict
    wire: list[dict] = field(default_factory=list)


def token_id(epoch_key: bytes, token: str) -> str:
    return hmac.new(epoch_key, token.encode(), hashlib.sha256).hexdigest()[:16]


def _bucket(v: float | None, step: float) -> float | None:
    return None if v is None else round(round(v / step) * step, 4)


def run_radar(nodes: list[BankNode], guards: Guards, epoch_key: bytes, audit: AuditLog | None = None,
              now: datetime | None = None, cardinality_only: bool = False) -> RadarResult:
    now = now or datetime.now(UTC)
    wire: list[dict] = []
    refused: dict[str, str] = {}
    live: list[BankNode] = []
    for n in nodes:
        d = guards.check(n.bank_id, n.submission(), now)
        if not d.allowed:
            refused[n.bank_id] = d.reason
            if audit:
                audit.append(actor="radar", action="submission_refused", why=d.reason, rule_version="guards-1", model_version=None,
                             input_hash=hashlib.sha256(n.bank_id.encode()).hexdigest()[:16], bank=n.bank_id)
        else:
            live.append(n)
    matched: dict[str, set[str]] = {n.bank_id: set() for n in live}
    elements = 0
    nbytes = 0
    for a, b in itertools.combinations(live, 2):
        ta = [x["token"] for x in a.submission()]
        tb = [x["token"] for x in b.submission()]
        pa, pb = PsiParty(ta, "staj-psi-v1"), PsiParty(tb, "staj-psi-v1")
        m1 = pa.blind()
        m2, m3 = pb.respond(m1, cardinality_only=cardinality_only)
        res_a, back = pa.finish(m2, m3, cardinality_only=cardinality_only)
        for name, step, msg in (("A->B blind", a.bank_id, m1), ("B->A double", b.bank_id, m2), ("B->A blind", b.bank_id, m3), ("A->B back", a.bank_id, back)):
            wire.append({"session": f"{a.bank_id}:{b.bank_id}", "msg": name, "from": step, "n": len(msg), "sample": msg[:2]})
            elements += len(msg)
            nbytes += sum(len(e) for e in msg) // 2
        if cardinality_only:
            if audit:
                audit.append(actor="radar", action="psi_cardinality", why=f"{a.bank_id}-{b.bank_id}: {res_a}", rule_version="psi-1",
                             model_version=None, input_hash="-", pair=f"{a.bank_id}:{b.bank_id}")
            continue
        res_b = pb.learn_from_return(back)
        matched[a.bank_id] |= set(res_a)
        matched[b.bank_id] |= set(res_b)
        if audit:
            for who, tokens in ((a.bank_id, res_a), (b.bank_id, res_b)):
                audit.append(actor=f"radar:{who}", action="psi_session", why=f"pair {a.bank_id}-{b.bank_id}: {len(tokens)} matches",
                             rule_version="psi-1", model_version=None, input_hash="-", pair=f"{a.bank_id}:{b.bank_id}", matches=len(tokens))
    rows: list[dict] = []
    lagret: dict[tuple[str, str], tuple] = {}
    for n in live:
        for t in matched[n.bank_id]:
            for ref in n.refs_for(t):
                rows.append({"token_id": token_id(epoch_key, t), "bank_id": n.bank_id, "cand_ref": ref, "rarity": n.rarity.get(t, 0.5)})
                s = n.stats.get(ref, {})
                lagret[(n.bank_id, ref)] = (_bucket(s.get("lag_median_h"), 1.0), _bucket(s.get("retention_median"), 0.02))
    wire.append({"session": "coordinator", "msg": "match rows", "from": "banks", "n": len(rows), "sample": [{k: v for k, v in r.items()} for r in rows[:2]]})
    clusters = build_clusters(rows)
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
        if audit and c["disclosed"]:
            audit.append(actor="radar", action="cluster_disclosed", why=f"{c['cluster_id']}: banks={len(c['banks'])} cand={len(c['candidates'])}",
                         rule_version="cluster-1", model_version=None, input_hash=c["cluster_id"], score=c["score"])
    clusters.sort(key=lambda c: -c["score"])
    exposure = {"mode": "staj_psi", "raw_records_exposed": 0, "blinded_elements": elements, "bytes_exchanged": nbytes,
                "match_rows_to_coordinator": len(rows)}
    return RadarResult(clusters=clusters, refused=refused, exposure=exposure, wire=wire)
