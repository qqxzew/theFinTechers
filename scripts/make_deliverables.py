"""Generate deliverables: FINREG CSV for the CNB alerts and OPO drafts (Markdown + PDF) for the top REVIEW cases.

python scripts/make_deliverables.py   (needs AWS SSO for the narrative model; ~5 min)
Outputs: eval/out/finreg_cnb.csv, eval/out/opo/<case_id>.{md,pdf}, eval/out/audit_cnb.jsonl
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import polars as pl

from api.state import build_state
from audit.log import AuditLog
from copilot.bedrock_client import LLM
from copilot.budgets import Budget
from copilot.case_json import build_case_json
from copilot.model_registry import ModelRegistry, load_models
from copilot.opo_draft import build_opo, draft_section_v, load_settings, to_markdown
from export.finreg_csv import to_finreg_rows, write_finreg_csv
from export.opo_export import opo_to_pdf
from ingest.cnb_clients import load_clients
from ingest.cnb_tx import load_transactions
from ingest.fx import load_fx
from node.pipeline import load_config, run_node

OUT = Path("eval/out")


def finreg_cnb(cfg: dict):
    tx = load_transactions("data/raw/cnb/transactions.csv", load_fx("config/fx.yaml"))
    cl = load_clients("data/raw/cnb/clients.csv")
    r = run_node("CNB", tx, cl, cfg)
    audit_path = OUT / "audit_cnb.jsonl"
    audit_path.unlink(missing_ok=True)
    audit = AuditLog(audit_path)
    cases = {}
    for c in r.cases:
        e = audit.append(actor="node:CNB", action="case_built", why=f"priority={c.priority} triage={c.triage.value}", rule_version="thresholds-1",
                         model_version=None, input_hash=c.case_id)
        cases[c.client_id] = {"triage": c.triage.value, "priority": c.priority, "reasons": c.triage_reasons, "log": e["hash"]}
    df = to_finreg_rows(r.alerts, cases, {})
    write_finreg_csv(df, str(OUT / "finreg_cnb.csv"))
    return r, df


def draft(llm: LLM, case_json: dict, label: str, audit_head: str, role: str) -> str:
    sv = draft_section_v(llm, case_json, Budget(8, 80000, 1.0, 900), role=role)
    opo = build_opo(case_json, sv, load_settings(), audit_head, "2026-10-19")
    d = OUT / "opo"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{label}.md").write_text(to_markdown(opo), encoding="utf-8")
    opo_to_pdf(opo, str(d / f"{label}.pdf"))
    return f"{label}: section V attempts={sv['attempts']} violations={len(sv['violations'])}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_config()
    models = load_models()
    reg = ModelRegistry(models)
    reg.active = dict(models["roles"])
    role = models.get("narrative_role", "agent_primary")
    llm = LLM(reg, AuditLog(OUT / "audit_deliverables.jsonl"))
    r, df = finreg_cnb(cfg)
    print(f"FINREG CSV: {df.height} alerts -> eval/out/finreg_cnb.csv", flush=True)
    jobs = []
    # (a) the three highest-priority REVIEW cases of the CNB data (no mule network exists there: expect weak cases)
    feats = {row["client_id"]: row for row in r.features.to_dicts()}
    top = sorted((c for c in r.cases if c.triage.value == "REVIEW"), key=lambda c: -c.priority)[:3]
    for c in top:
        jobs.append((build_case_json(c, feats[c.client_id], None), f"CNB_{c.case_id}"))
    # (b) the five highest-priority REVIEW cases of the demo red-team world (planted mules, one per bank where possible)
    st = build_state("data/redteam/seed505", audit_path="eval/out/audit_deliverables_world.jsonl")
    seen: dict[str, int] = {}
    for cid, c in sorted(st.cases.items(), key=lambda kv: -kv[1].priority):
        if c.triage.value == "REVIEW" and c.route == "mule_review" and seen.get(c.bank_id, 0) < 2 and len(seen) <= 3:
            seen[c.bank_id] = seen.get(c.bank_id, 0) + 1
            jobs.append((st.case_json(cid), f"DEMO_{cid}"))
        if sum(seen.values()) >= 5:
            break
    head = st.audit.path.read_text(encoding="utf-8").splitlines()[-1]
    import json

    head_hash = json.loads(head)["hash"]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for line in ex.map(lambda j: draft(llm, j[0], j[1], head_hash, role), jobs):
            print(line, flush=True)
    print(pl.DataFrame({"files": sorted(p.name for p in (OUT / "opo").glob("*"))}))


if __name__ == "__main__":
    main()
