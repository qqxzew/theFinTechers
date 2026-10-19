"""Demo state for the API: runs the bank nodes and the radar on a world directory and keeps everything the UI needs in memory.

The API is a thin read layer over deterministic results plus human decisions. Nothing here decides: decisions come only from POST /decision.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
import yaml

from audit.log import AuditLog
from copilot.case_json import build_case_json
from copilot.tools.case_tools import CaseTools
from eval.redteam_eval import load_world, run_banks, to_bank_node
from node.pipeline import apply_clusters, load_config
from radar.guards import Guards
from radar.sessions import run_radar, token_id

EPOCH_KEY = b"epoch-demo"
STAFF = ["ann", "tom", "rob", "zoe", "max", "eva", "jan", "lea"]
RULE_AUTHOR = "rob"


@dataclass
class DemoState:
    world: str
    cfg: dict
    tx: pl.DataFrame
    clients: pl.DataFrame
    results: dict
    cases: dict            # case_id -> Case (after radar)
    feats: dict            # client_id -> feature row
    case_bank: dict        # case_id -> bank_id
    radar: object
    audit: AuditLog
    matrix: dict
    case_jsons: dict = field(default_factory=dict)
    explanations: dict = field(default_factory=dict)
    opo: dict = field(default_factory=dict)
    decisions: dict = field(default_factory=dict)
    proposals: dict = field(default_factory=dict)
    tools: CaseTools | None = None
    metrics_path: str = "eval/out/redteam_seed707.json"
    cnb_path: str = "eval/out/cnb_eval.json"

    def owner_of(self, client_id: str) -> str:
        return STAFF[int(hashlib.sha256(client_id.encode()).hexdigest(), 16) % len(STAFF)]

    def matched_accounts(self, case, cluster: dict) -> list[str]:
        """The accounts behind the drops: this client's own exit accounts whose keyed ids matched other banks' candidates.

        Plaintext is known only to the owning bank (the radar saw keyed ids); resolving the account owner is the bank's own job, outside Stau.
        """
        res = self.results[case.bank_id]
        ref = next((r for r, cid in res.ref_to_client.items() if cid == case.client_id), None)
        toks = {c["token"] for c in res.candidates if c["cand_ref"] == ref}
        return sorted(t for t in toks if token_id(EPOCH_KEY, t) in set(cluster["tokens"]))

    def case_json(self, case_id: str) -> dict:
        if case_id not in self.case_jsons:
            case = self.cases[case_id]
            feat = self.feats[case.client_id]
            cluster = None
            if case.cluster_id:
                for c in self.radar.clusters:
                    if c["cluster_id"] == case.cluster_id:
                        cluster = c["post_match"].get(case.bank_id) | {"cluster_id": c["cluster_id"]}
                        cluster["matched_exit_accounts"] = self.matched_accounts(case, c)
            cj = build_case_json(case, feat, cluster)
            cj["case_id"] = case_id
            self.case_jsons[case_id] = cj
        return self.case_jsons[case_id]


def build_state(world: str = "data/redteam/seed707", audit_path: str = "eval/out/audit_demo.jsonl", fresh: bool = True) -> DemoState:
    cfg = load_config()
    tx, cl, _ = load_world(world, with_labels=False)   # the API process never reads labels
    results = run_banks(tx, cl, cfg)
    if fresh and os.path.exists(audit_path):
        os.remove(audit_path)
    audit = AuditLog(audit_path)
    rc = cfg["radar"]
    radar = run_radar([to_bank_node(r) for r in results.values()], Guards(cfg["radar_guards"]), epoch_key=EPOCH_KEY, audit=audit,
                       min_significance=rc["min_significance"] if rc["use_significance"] else None, significance_cap=rc["significance_cap"])
    cases, feats, case_bank = {}, {}, {}
    for b, r in results.items():
        for c in apply_clusters(r, radar.clusters):
            cases[c.case_id] = c
            case_bank[c.case_id] = b
        for row in r.features.to_dicts():
            feats[row["client_id"]] = row
    matrix = yaml.safe_load(open("config/escalation_matrix.yaml", encoding="utf-8"))
    st = DemoState(world, cfg, tx, cl, results, cases, feats, case_bank, radar, audit, matrix)
    for cid, c in cases.items():
        audit.append(actor="node:" + c.bank_id, action="case_built", why=f"priority={c.priority} triage={c.triage.value} route={c.route}",
                     rule_version="thresholds-1", model_version=None, input_hash=hashlib.sha256(cid.encode()).hexdigest()[:16])
    st.tools = CaseTools({}, rules={})
    return st


def save_json(path: str, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
