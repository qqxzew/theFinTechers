"""Bank-node pipeline (blue team): FINREG rules + detectors + innocence layer -> cases -> radar candidates.

Never imports redteam/ or eval/. Input is ONE bank's canonical tx/clients.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import polars as pl
import yaml

from common.schemas import Case, Signal
from node.cases.builder import build_case
from node.cases.scoring import score_case
from node.detectors import ALL_DETECTORS, d6_same_hand, d8_structuring
from node.features.build import build_features
from node.innocence import (
    e1_mom,
    e2_life,
    e3_source,
    e4_institutional,
    e5_reciprocity,
    e6_pooling,
    e7_cohost,
    e8_earner,
    victim,
)
from node.rules.rule_a import rule_a
from node.rules.rule_b import rule_b
from node.rules.rule_c import rule_c
from node.tokens.export import export_candidates

INNOCENCE = [e1_mom, e2_life, e3_source, e4_institutional, e5_reciprocity, e6_pooling, e7_cohost, e8_earner]
ASOF = datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC)


def load_config(thresholds: str = "config/thresholds.yaml", units: str = "config/units.yaml",
                hr: str = "config/high_risk_jurisdictions.yaml") -> dict:
    th = yaml.safe_load(open(thresholds, encoding="utf-8"))
    th["units"] = yaml.safe_load(open(units, encoding="utf-8"))
    h = yaml.safe_load(open(hr, encoding="utf-8"))
    th["hr_countries"] = set(h["eu"]["countries"]) | set(h["fatf"]["call_for_action"]) | set(h["fatf"]["increased_monitoring"])
    return th


@dataclass
class NodeResult:
    bank_id: str
    features: pl.DataFrame
    cases: list[Case]
    probs: dict[str, float]
    alerts: pl.DataFrame
    candidates: list[dict]
    signals: list[Signal] = field(default_factory=list)
    metas: dict[str, dict] = field(default_factory=dict)
    exculpatory: dict[str, list[Signal]] = field(default_factory=dict)
    degree: dict[str, int] = field(default_factory=dict)
    ref_to_client: dict[str, str] = field(default_factory=dict)
    cfg: dict = field(default_factory=dict)
    n_eligible: int = 0
    feat_by_id: dict[str, dict] = field(default_factory=dict)
    client_meta: dict[str, dict] = field(default_factory=dict)
    ctx: dict = field(default_factory=dict)


def _rule_signals(a: pl.DataFrame, b: pl.DataFrame, c: pl.DataFrame) -> list[Signal]:
    out = []
    for r in a.iter_rows(named=True):
        out.append(Signal(signal_id=f"R-A:{r['client_id']}", detector_id="R-A", version="1", client_id=r["client_id"],
                          score=min(1.0, 0.3 + 0.2 * len(r["reasons"])), evidence=list(r["reasons"]),
                          explanation_template_key="rule_a", source="FINREG rule A"))
    bc = b.group_by("client_id").agg(pl.len().alias("n"), pl.col("reason").first().alias("reason"))
    for r in bc.iter_rows(named=True):
        out.append(Signal(signal_id=f"R-B:{r['client_id']}", detector_id="R-B", version="1", client_id=r["client_id"],
                          score=min(1.0, 0.5 + 0.1 * r["n"]), evidence=[r["reason"], f"n_tx={r['n']}"],
                          explanation_template_key="rule_b", source="FINREG rule B"))
    for r in c.iter_rows(named=True):
        out.append(Signal(signal_id=f"R-C:{r['client_id']}", detector_id="R-C", version="1", client_id=r["client_id"],
                          score=0.8, evidence=["inflow_amount", "outflow_amount"], explanation_template_key="rule_c", source="FINREG rule C"))
    return out


def run_node(bank_id: str, tx: pl.DataFrame, clients: pl.DataFrame, cfg: dict, bank_secret: bytes = b"demo-secret",
             asof: datetime = ASOF, use_innocence: bool = True, detectors_off: tuple[str, ...] = ()) -> NodeResult:
    feat = build_features(tx, clients, cfg["features"], asof, cfg["units"]["expected_unit"])
    rows = feat.to_dicts()
    by_id = {r["client_id"]: r for r in rows}
    ctx = {"cfg": cfg["detectors"], "pileup_thresholds": d8_structuring.find_pileup_thresholds(
        [a for r in rows for a in r["out_amounts"]])}
    # FINREG rules
    ru = {**cfg["rule_a"], "expected_unit": cfg["units"]["expected_unit"], "q2_unit": cfg["units"]["q2_unit"]}
    ra, rb, rc = rule_a(tx, clients, ru), rule_b(tx, clients, cfg["hr_countries"], cfg["rule_b"]), rule_c(tx, cfg["rule_c"])
    alerts = pl.concat([
        ra.select(["client_id", "alert_type"]).with_columns(pl.lit(None, dtype=pl.String).alias("transaction_id")),
        rb.select(["client_id", "alert_type", pl.col("tx_id").alias("transaction_id")]),
        rc.select(["client_id", "alert_type"]).with_columns(pl.lit(None, dtype=pl.String).alias("transaction_id")),
    ])
    sus: dict[str, list[Signal]] = {}
    exc: dict[str, list[Signal]] = {}
    for s in _rule_signals(ra, rb, rc):
        if s.detector_id not in detectors_off:
            sus.setdefault(s.client_id, []).append(s)
    for r in rows:
        for d in ALL_DETECTORS:
            if d.DETECTOR_ID in detectors_off:
                continue
            for s in d.detect(r, ctx):
                sus.setdefault(s.client_id, []).append(s)
        for s in victim.detect(r, ctx):
            sus.setdefault(s.client_id, []).append(s)
    if "D6" not in detectors_off:
        for s in d6_same_hand.detect_group(rows, ctx):
            sus.setdefault(s.client_id, []).append(s)
    if use_innocence:
        for cid in sus:
            for m in INNOCENCE:
                exc.setdefault(cid, []).extend(m.detect(by_id[cid], ctx))
    hr = cfg["hr_countries"]
    cl_by = {r["client_id"]: r for r in clients.to_dicts()}
    cases, probs, metas = [], {}, {}

    def _meta_for(cid: str) -> dict:
        f = by_id[cid]
        return {"aml_risk": f["aml_risk"] or "low", "pep": bool(f["pep"]), "high_risk_country": (cl_by[cid]["client_country"] or "") in hr,
                "days_since_contract": f["days_since_contract"] if f["days_since_contract"] is not None else 9999,
                "contract_form": f["contract_form"], "in_cluster": False, "big_amount": f["big_in_amount"] or f["max_single_in"] or 0.0,
                "cluster_id": None}

    for cid, sigs in sus.items():
        meta = _meta_for(cid)
        metas[cid] = meta
        case = build_case(bank_id, cid, sigs, exc.get(cid, []), meta, cfg["cases"])
        cases.append(case)
        probs[cid] = score_case([s for s in sigs if s.detector_id != "VICTIM"], exc.get(cid, []), cfg["cases"]["weights"])["prob"]
    cand = export_candidates(cases, by_id, probs, bank_secret, cfg["token_export"])
    from node.features.degree import counterparty_degree
    dd = counterparty_degree(tx)
    degree = dict(zip(dd["counterparty_token"].to_list(), dd["degree"].to_list(), strict=True))
    from node.tokens.export import cand_ref
    exported = {c["cand_ref"] for c in cand}
    ref_to_client = {}
    client_meta = {}
    for cid in by_id:
        ref = cand_ref(bank_secret, cid)
        if ref in exported:
            ref_to_client[ref] = cid
            client_meta[cid] = metas.get(cid) or _meta_for(cid)
    n_eligible = sum(1 for f in by_id.values() if f.get("exit_tokens_low"))
    return NodeResult(bank_id, feat, cases, probs, alerts, cand, [s for v in sus.values() for s in v], metas, exc, degree, ref_to_client, cfg, n_eligible, by_id, client_meta, ctx)


def apply_clusters(res: NodeResult, clusters: list[dict]) -> list[Case]:
    """Rebuild the cases of candidates that sit in a DISCLOSED cluster: cluster membership raises priority and blocks auto-closing."""
    member: dict[str, str] = {}
    member_score: dict[str, float] = {}
    for c in clusters:
        if not c["disclosed"]:
            continue
        for bank, ref in c["candidates"]:
            if bank == res.bank_id and ref in res.ref_to_client:
                member[res.ref_to_client[ref]] = c["cluster_id"]
                use_sig = res.cfg.get("radar", {}).get("use_significance", False) and c.get("x_score") is not None
                member_score[res.ref_to_client[ref]] = c["x_score"] if use_sig else c["score"]
    out = []
    sigs_by: dict[str, list[Signal]] = {}
    for s in res.signals:
        sigs_by.setdefault(s.client_id, []).append(s)
    for case in res.cases:
        cid = case.client_id
        if cid in member:
            meta = {**res.metas[cid], "in_cluster": True, "cluster_id": member[cid]}
            xs = Signal(signal_id=f"X:{cid}", detector_id="X", version="1", client_id=cid, score=member_score[cid],
                        evidence=[f"cluster_id={member[cid]}"], explanation_template_key="radar_cluster",
                        source="Stáj radar: blinded cross-bank exit-token match (PSI)")
            out.append(_floor(build_case(res.bank_id, cid, [*sigs_by[cid], xs], res.exculpatory.get(cid, []), meta, res.cfg["cases"]), res, member_score[cid]))
        else:
            out.append(case)
    have = {c.client_id for c in out}
    for cid, cl_id in member.items():
        if cid in have or cid not in res.feat_by_id:
            continue
        exc = [sg for m in INNOCENCE for sg in m.detect(res.feat_by_id[cid], res.ctx)]
        meta = {**res.client_meta[cid], "in_cluster": True, "cluster_id": cl_id}
        xs = Signal(signal_id=f"X:{cid}", detector_id="X", version="1", client_id=cid, score=member_score[cid], evidence=[f"cluster_id={cl_id}"],
                    explanation_template_key="radar_cluster", source="Stáj radar: blinded cross-bank exit-token match (PSI)")
        out.append(_floor(build_case(res.bank_id, cid, [xs], exc, meta, res.cfg["cases"]), res, member_score[cid]))
    return out


def _floor(case: Case, res: NodeResult, x_score: float) -> Case:
    """Pre-registered: with the significance gate ON, members of a disclosed cluster get priority >= 30 + round(20 x x_score)."""
    if not res.cfg.get("radar", {}).get("use_significance", False):
        return case
    floor = res.cfg["cases"]["fp_max_priority"] + round(20 * x_score)
    return case if case.priority >= floor else case.model_copy(update={"priority": min(100, floor)})

