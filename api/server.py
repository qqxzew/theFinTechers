"""FastAPI backend for the Stáj UI. Run: python -m api.server  (builds the demo state, then serves on :8000)."""
from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime

import polars as pl
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from api.state import RULE_AUTHOR, STAFF, DemoState, build_state
from audit.log import verify_chain
from copilot.bedrock_client import LLM
from copilot.budgets import Budget
from copilot.explain import explain_case
from copilot.model_registry import ModelRegistry, load_models
from copilot.opo_draft import build_opo, draft_section_v, load_settings, to_markdown
from copilot.rule_qa import answer_question
from escalation.conflicts import check_decision, validate_approval
from escalation.matrix import route

ROLE_RANK = {"analyst_l1": 0, "analyst_l2": 1, "aml_officer": 2, "mlro": 3}


class DecisionBody(BaseModel):
    action: str
    decider: str
    role: str
    reason: str = ""
    approver: str | None = None


class AskBody(BaseModel):
    question: str


class SectionV(BaseModel):
    sentences: list[dict]


def create_app(st: DemoState) -> FastAPI:
    app = FastAPI(title="Stáj API", version="1")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    models_cfg = load_models()
    holder: dict = {}

    def llm() -> LLM:
        if "llm" not in holder:
            reg = ModelRegistry(models_cfg)
            reg.active = dict(models_cfg["roles"])      # optimistic until the background verification finishes
            holder["reg"], holder["llm"] = reg, LLM(reg, st.audit)
            threading.Thread(target=lambda: reg.verify(st.audit), daemon=True).start()
        return holder["llm"]

    narrative_role = models_cfg.get("narrative_role", "agent_primary")

    def meta_of(case_id: str) -> dict:
        c = st.cases[case_id]
        f = st.feats[c.client_id]
        return {"priority": c.priority, "pep": bool(f.get("pep")), "cluster": c.cluster_id is not None, "alert_type": "case"}

    def esc(case_id: str) -> dict:
        r = route(meta_of(case_id), st.matrix)
        return {"role": r["role"], "rule_index": r["rule_index"], "matrix_is_placeholder": r["matrix_is_placeholder"]}

    def get_case(case_id: str):
        if case_id not in st.cases:
            raise HTTPException(404, "unknown case")
        return st.cases[case_id]

    def rules_of(case) -> list[str]:
        return sorted({s.detector_id for s in case.signals if s.detector_id != "VICTIM"} | ({"X"} if case.cluster_id else set()))

    def status_of(case_id: str) -> str:
        d = st.decisions.get(case_id)
        return "open" if not d else ("confirmed" if d["action"] == "confirm" else "overridden")

    @app.get("/api/meta")
    def meta():
        ok, bad = verify_chain(st.audit.path)
        active = holder["reg"].active if "reg" in holder else {}
        return {"data_label": "SYNTHETIC DATA - red-team world (CNB-derived background + planted schemes)", "fx_placeholder": True,
                "matrix_placeholder": bool(st.matrix.get("placeholder")),
                "models": {**models_cfg["roles"], "active": active or models_cfg["roles"]},
                "chain": {"ok": ok, "length": _len(st), "head": _head(st)}, "roles": st.matrix["roles"],
                "four_eyes_min_priority": st.matrix["four_eyes_min_priority"], "staff": STAFF, "bad_index": bad}

    @app.get("/api/queue")
    def queue(rule: str = "", min_priority: int = 0, max_priority: int = 100, triage: str = "", cluster: str = "", bank: str = "", route: str = "",
              offset: int = 0, limit: int = Query(500, le=2000)):
        items = []
        for cid, c in st.cases.items():
            rules = rules_of(c)
            if rule and rule not in rules:
                continue
            if not (min_priority <= c.priority <= max_priority):
                continue
            if triage and c.triage.value != triage:
                continue
            if cluster and c.cluster_id != cluster:
                continue
            if bank and c.bank_id != bank:
                continue
            if route and c.route != route:
                continue
            items.append({"case_id": cid, "bank_id": c.bank_id, "client_ref": st.case_json(cid)["client_ref"], "priority": c.priority,
                          "triage": c.triage.value, "route": c.route, "rules": rules, "cluster_id": c.cluster_id,
                          "escalation_role": esc(cid)["role"], "decision_status": status_of(cid)})
        items.sort(key=lambda x: -x["priority"])
        allc = list(st.cases.values())
        counts = {"alerts_before_triage": sum(len(r.alerts) for r in st.results.values()), "cases": len(allc),
                  "review": sum(1 for c in allc if c.triage.value == "REVIEW"),
                  "fp_auto_closed": sum(1 for c in allc if c.triage.value == "FP"),
                  "victim_protection": sum(1 for c in allc if c.route == "victim_protection")}
        return {"counts": counts, "items": items[offset:offset + limit], "total_matching": len(items), "offset": offset, "limit": limit}

    @app.get("/api/cases/{case_id}")
    def case(case_id: str):
        c = get_case(case_id)
        cj = st.case_json(case_id)
        t = st.tx.filter(pl.col("client_id") == c.client_id).sort("ts")
        tl = [{"ts": r["ts"].isoformat(), "direction": r["direction"], "amount_czk": r["amount_czk"], "counterparty": r["counterparty_token"]}
              for r in t.tail(60).to_dicts()]
        deg = st.results[c.bank_id].degree
        agg: dict = {}
        for r in t.to_dicts():
            k = (r["counterparty_token"], "out" if r["direction"] != "in" else "in")
            agg[k] = agg.get(k, 0.0) + r["amount_czk"]
        top = sorted(agg.items(), key=lambda kv: -kv[1])[:12]
        nodes = [{"id": cj["client_ref"], "label": cj["client_ref"], "kind": "client"}]
        edges = []
        for (tok, d), amt in top:
            nodes.append({"id": tok, "label": tok, "kind": "counterparty_popular" if deg.get(tok, 1) >= st.cfg["features"]["popular_min"] else "counterparty_rare"})
            edges.append({"source": cj["client_ref"] if d == "out" else tok, "target": tok if d == "out" else cj["client_ref"], "amount_czk": amt, "direction": d})
        nodes = list({n["id"]: n for n in nodes}.values())
        return {**cj, "timeline": tl, "local_graph": {"nodes": nodes, "edges": edges}, "explanation": st.explanations.get(case_id, {}).get("explanation"),
                "explanation_violations": st.explanations.get(case_id, {}).get("violations", []), "escalation": esc(case_id),
                "proposals": st.proposals.get(case_id, []), "decision": st.decisions.get(case_id)}

    @app.post("/api/cases/{case_id}/explain")
    def explain(case_id: str):
        get_case(case_id)
        cj = st.case_json(case_id)
        res = explain_case(llm(), cj, Budget(8, 80000, 1.0, 600), role=narrative_role)
        st.explanations[case_id] = res
        st.proposals.setdefault(case_id, []).append({"triage": st.cases[case_id].triage.value, "reason": "; ".join(st.cases[case_id].triage_reasons[:2]),
                                                      "agent": "narrative", "ts": datetime.now(UTC).isoformat()})
        return {**(res["explanation"] or {}), "violations": res["violations"], "model_id": res["model_id"], "cached": res.get("cached", False)}

    @app.post("/api/cases/{case_id}/ask")
    def ask(case_id: str, body: AskBody):
        """Ruleset navigation Q&A: grounded in the case JSON, rule definitions and the configured thresholds."""
        get_case(case_id)
        cj = st.case_json(case_id)
        used = {s["detector_id"] for s in [*cj["signals"], *cj["exculpatory"]]}
        params = {"rule_a": st.cfg["rule_a"], "rule_b": st.cfg["rule_b"], "rule_c": st.cfg["rule_c"],
                  **{d: v for d, v in st.cfg["detectors"].items() if d in used}}
        res = answer_question(llm(), cj, body.question, params, Budget(6, 60000, 1.0, 300), role=narrative_role)
        st.audit.append(actor="human:analyst", action="rule_question", why=body.question[:200], rule_version="copilot-1", model_version=res["model_id"],
                        input_hash=case_id)
        return res

    @app.post("/api/cases/{case_id}/decision")
    def decision(case_id: str, body: DecisionBody):
        c = get_case(case_id)
        viol: list[str] = []
        if body.action not in ("confirm", "override"):
            viol.append("unknown_action")
        if body.action == "override" and len(body.reason.strip()) < 10:
            viol.append("override_requires_written_reason")
        if body.role not in ROLE_RANK:
            viol.append("unknown_role")
        elif ROLE_RANK[body.role] < ROLE_RANK[esc(case_id)["role"]]:
            viol.append("role_below_escalation_target")
        first_triager = (st.decisions.get(case_id) or {}).get("first_triager")
        case_ctx = {"client_id": c.client_id, "relationship_owner": st.owner_of(c.client_id), "rule_authors": [RULE_AUTHOR],
                    "first_triager": first_triager, "priority": c.priority}
        cfgg = {"four_eyes_min_priority": st.matrix["four_eyes_min_priority"]}
        viol += check_decision(body.decider, case_ctx, cfgg)
        viol += validate_approval(body.decider, body.approver, body.decider, c.priority, cfgg) if c.priority >= cfgg["four_eyes_min_priority"] else []
        viol = [v for v in dict.fromkeys(viol) if v != "approver_is_executor" or body.approver == body.decider]
        if viol:
            st.audit.append(actor=f"human:{body.decider}", action="decision_rejected", why=",".join(viol), rule_version="governance-1",
                            model_version=None, input_hash=case_id)
            return {"ok": False, "violations": viol}
        d = {"action": body.action, "decider": body.decider, "role": body.role, "reason": body.reason, "approver": body.approver,
             "ts": datetime.now(UTC).isoformat(), "first_triager": first_triager or body.decider}
        st.decisions[case_id] = d
        st.audit.append(actor=f"human:{body.decider}", action=f"decision:{body.action}", why=body.reason or "confirmed proposal",
                        rule_version="governance-1", model_version=None, input_hash=case_id, role=body.role, approver=body.approver,
                        proposal_triage=c.triage.value)
        return {"ok": True, "violations": [], "decision": d}

    @app.get("/api/opo/{case_id}")
    def opo_get(case_id: str):
        get_case(case_id)
        if case_id not in st.opo:
            cj = st.case_json(case_id)
            sv = draft_section_v(llm(), cj, Budget(8, 80000, 1.0, 600), role=narrative_role)
            st.opo[case_id] = {"v": sv}
        sv = st.opo[case_id]["v"]
        return _opo_payload(st, case_id, sv)

    @app.put("/api/opo/{case_id}/section-v")
    def opo_put(case_id: str, body: SectionV):
        get_case(case_id)
        sv = {"sentences": body.sentences, "violations": []}
        from copilot.qa import validate_draft
        sv["violations"] = validate_draft({"sentences": body.sentences}, st.case_json(case_id), analyst_names=list(STAFF))
        st.opo[case_id] = {"v": sv}
        st.audit.append(actor="human:editor", action="opo_section_v_edited", why=f"{len(body.sentences)} sentences", rule_version="opo-1",
                        model_version=None, input_hash=case_id)
        return _opo_payload(st, case_id, sv)

    @app.get("/api/opo/{case_id}/export.md", response_class=PlainTextResponse)
    def opo_md(case_id: str):
        return to_markdown(opo_get(case_id))

    @app.get("/api/radar")
    def radar():
        banks = []
        for b, r in st.results.items():
            cands = r.candidates
            toks = sorted({c["token"] for c in cands})[:14]
            refs = sorted({c["cand_ref"] for c in cands})[:14]
            nodes = [{"id": f"{b}:{x}", "label": x, "kind": "candidate"} for x in refs] + [{"id": f"t:{t}", "label": t, "kind": "token"} for t in toks]
            edges = [{"source": f"{b}:{c['cand_ref']}", "target": f"t:{c['token']}"} for c in cands if c["cand_ref"] in refs and c["token"] in toks]
            banks.append({"bank_id": b, "n_cases": len(r.cases), "n_review": sum(1 for c in st.cases.values() if c.bank_id == b and c.triage.value == "REVIEW"),
                          "n_candidates_exported": len(refs), "local_graph": {"nodes": nodes, "edges": edges}})
        cl = [{"cluster_id": c["cluster_id"], "banks": c["banks"], "n_candidates": len(c["candidates"]), "tokens": len(c["tokens"]), "score": c["score"],
               "disclosed": c["disclosed"], "same_hand_global": c.get("same_hand_global", False), "lag_ret_concentration": c.get("lag_ret_concentration")}
              for c in st.radar.clusters]
        nodes, edges = [], []
        for c in st.radar.clusters:
            if not c["disclosed"]:
                continue
            cid = c["cluster_id"]
            nodes.append({"id": cid, "label": f"cluster {cid}", "kind": "token"})
            for bank, ref in c["candidates"]:
                nodes.append({"id": f"{bank}:{ref}", "label": ref, "kind": "candidate", "bank": bank})
                edges.append({"source": f"{bank}:{ref}", "target": cid})
        nodes = list({n["id"]: n for n in nodes}.values())
        m = _metrics_raw(st)
        exposure = {k: v["exposure"] for k, v in (m or {}).get("modes", {}).items()} if m else {}
        return {"banks": banks, "clusters": cl, "cluster_graph": {"nodes": nodes, "edges": edges[:400]}, "wire": st.radar.wire,
                "exposure": exposure or {"staj_psi": st.radar.exposure}, "refused": st.radar.refused,
                "disclosure_rule": "A cluster is disclosed only if it spans >= 2 banks and >= 3 candidates. PSI minimises what is shared; it is not a legal basis."}

    @app.get("/api/metrics")
    def metrics():
        m = _metrics_raw(st)
        if not m:
            raise HTTPException(404, "run eval first (python -m eval.run_all)")
        cnb = json.load(open(st.cnb_path, encoding="utf-8")) if os.path.exists(st.cnb_path) else None
        if cnb:
            cnb["sample_sheet_url"] = "/api/files/cnb_sample_30.csv"
        return {"dataset": m["world"], "seed": int(m["world"].rstrip("/").split("seed")[-1]) if "seed" in m["world"] else 0, "synthetic": True,
                "modes": m["modes"], "breakdown": _prefixed(m["breakdown_staj_psi"]), "ablations": {"full": m["modes"]["staj_psi"]["overall"], **m["ablations"]},
                "failures": m["failures_staj_psi"], "cnb": cnb, "operating_point": m["operating_point"], **_report_extras()}

    @app.get("/api/audit")
    def audit(offset: int = 0, limit: int = Query(100, le=500)):
        lines = open(st.audit.path, encoding="utf-8").read().splitlines()
        ents = [json.loads(x) for x in lines[offset:offset + limit]]
        return {"total": len(lines), "entries": ents}

    @app.get("/api/audit/verify")
    def audit_verify():
        ok, bad = verify_chain(st.audit.path)
        return {"ok": ok, "bad_index": bad, "length": _len(st), "head": _head(st)}

    @app.get("/api/files/{name}", response_class=PlainTextResponse)
    def files(name: str):
        allowed = {"cnb_sample_30.csv": "eval/out/cnb_sample_30.csv", "finreg_cnb.csv": "eval/out/finreg_cnb.csv", "report.md": "eval/report.md"}
        if name not in allowed or not os.path.exists(allowed[name]):
            raise HTTPException(404, "not available")
        return open(allowed[name], encoding="utf-8").read()

    @app.get("/api/honesty")
    def honesty():
        return json.load(open("docs/honesty.json", encoding="utf-8")) if os.path.exists("docs/honesty.json") else {
            "sources": [], "planted": [], "limitations": [], "legal_note": "", "not_found_in_public_sources": []}

    return app


def _report_extras() -> dict:
    """Held-out aggregates from eval/report.json (generated by eval/run_all.py), when present."""
    if not os.path.exists("eval/report.json"):
        return {}
    r = json.load(open("eval/report.json", encoding="utf-8"))
    return {k: r[k] for k in ("headline_held_out_mean", "threshold_curve_held_out_mean", "ring_size_sweep", "held_out_seeds", "dev_seeds") if k in r}


def _prefixed(b: dict) -> dict:
    """UI convention: scheme:* (planted mule schemes), persona:* (honest look-alikes), victim:*, other:* (background)."""
    out = {}
    for k, v in b.items():
        label, _, name = k.partition("/")
        pre = {"mule": "scheme", "honest": "persona", "victim": "victim"}.get(label, "other")
        out[f"{pre}:{name}"] = v
    return out


def _len(st: DemoState) -> int:
    return sum(1 for _ in open(st.audit.path, encoding="utf-8"))


def _head(st: DemoState) -> str:
    last = ""
    for last in open(st.audit.path, encoding="utf-8"):
        pass
    return json.loads(last)["hash"] if last else ""


def _metrics_raw(st: DemoState):
    return json.load(open(st.metrics_path, encoding="utf-8")) if os.path.exists(st.metrics_path) else None


def _opo_payload(st: DemoState, case_id: str, sv: dict) -> dict:
    opo = build_opo(st.case_json(case_id), sv, load_settings(), _head(st), datetime.now(UTC).date().isoformat())
    return opo


if __name__ == "__main__":
    import uvicorn

    world = os.environ.get("STAJ_WORLD", "data/redteam/seed505")
    uvicorn.run(create_app(build_state(world)), host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
