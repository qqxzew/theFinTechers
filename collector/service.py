"""Collector service. POST /rounds/{id}/submit takes ONE masked vector of ONE bank; GET /rounds/{id}/flags returns flagged bucket ids and windows.

The service only ever holds masked uint32 vectors and their sums. It has no mask key, no bank data and no customer identifiers. A round needs
every registered bank: a missing bank gives HTTP 409 (no dropout recovery). Run: COLLECTOR_BANKS=B1,B2,B3 uvicorn collector.service:app --port 8100
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from collector.aggregate import MissingBankError, Round
from collector.stats import how_test, where_test

log = logging.getLogger("collector")
logging.basicConfig(level=logging.INFO, format="[collector] %(message)s")
N_BUCKETS = 1 << 18
HOW_SHAPE = (30, 6, 2)

app = FastAPI(title="Stáj collector", version="1")
BANKS = [b for b in os.environ.get("COLLECTOR_BANKS", "B1,B2,B3").split(",") if b]
ROUNDS: dict[str, Round] = {}
CONFIG: dict[str, Any] = {"p_inst": int(os.environ.get("COLLECTOR_P_INST", "30")), "q": 0.01, "allowlist": set()}


class Submit(BaseModel):
    bank_id: str
    label: str                 # P | K | I (WHERE) or C | B (HOW, one day per round: label "C:<day>" / "B:<day>")
    vector_b64: str            # little-endian uint32, MASKED


class Allowlist(BaseModel):
    buckets: list[int]


@app.post("/config/allowlist")
def set_allowlist(a: Allowlist) -> dict:
    CONFIG["allowlist"] = set(a.buckets)
    log.info("allowlist of %d institutional bucket ids stored (ids only, no account numbers)", len(a.buckets))
    return {"n": len(a.buckets)}


@app.post("/rounds/{round_id}/submit")
def submit(round_id: str, s: Submit) -> dict:
    rnd = ROUNDS.setdefault(round_id, Round(round_id, BANKS))
    raw = base64.b64decode(s.vector_b64)
    vec = np.frombuffer(raw, dtype="<u4")
    try:
        rnd.submit(s.bank_id, s.label, vec)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    log.info("round %s: received MASKED vector %s from %s (%d x uint32, sha256 %s...) - looks uniform, not decodable alone",
             round_id, s.label, s.bank_id, len(vec), hashlib.sha256(raw).hexdigest()[:10])
    return {"received": s.label, "bank": s.bank_id}


@app.get("/rounds/{round_id}/flags")
def flags(round_id: str) -> dict:
    rnd = ROUNDS.get(round_id)
    if rnd is None:
        raise HTTPException(404, "unknown round")
    try:
        P, K, ind = (rnd.total(x).astype(np.int64) for x in ("P", "K", "I"))
    except MissingBankError as e:
        log.warning("round %s FAILED loudly: %s", round_id, e)
        raise HTTPException(409, str(e)) from e
    log.info("round %s: sums of masked vectors computed (plain totals only; no single bank's counts are ever visible)", round_id)
    wr = where_test(P, K, ind, q=CONFIG["q"], p_inst=CONFIG["p_inst"], allowlist_buckets=CONFIG["allowlist"])
    out: dict[str, Any] = {"round": round_id, "where": {"flagged": [{"bucket": f["bucket"], "small": f["small"], "banks": f["banks"], "p": f["p"], "totals": {"P": f["P"], "K": f["K"]}}
                                                                    for f in wr.flagged],
                                                        "n_suppressed_institutional": len(wr.suppressed), "n_tested": wr.n_tested}, "how": {"flagged": []}}
    days = sorted({int(lbl.split(":")[1]) for lbl in rnd._v if lbl.startswith("C:")})
    if days:
        try:
            C = np.stack([rnd.total(f"C:{d}") for d in days]).astype(np.int64).reshape(len(days), *HOW_SHAPE)
            B = np.stack([rnd.total(f"B:{d}") for d in days]).astype(np.int64).reshape(len(days), *HOW_SHAPE)
        except MissingBankError as e:
            raise HTTPException(409, str(e)) from e
        hr = how_test(C, B, last_days=2, q=CONFIG["q"])
        out["how"] = {"n_windows": hr.n_windows, "flagged": [{**w, "day_lo": days[w["day_lo"]], "day_hi": days[w["day_hi"]]} for w in hr.flagged]}
    return out
