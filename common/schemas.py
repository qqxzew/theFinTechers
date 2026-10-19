"""Frozen shared schemas (canonical tx/client, Signal, Case, PSI messages). Change only via docs/DECISIONS.md."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Direction(StrEnum):
    IN = "in"
    OUT = "out"
    REMIT_OUT = "remit_out"


class Transaction(BaseModel):
    tx_id: str
    bank_id: str
    client_id: str
    ts: datetime  # UTC
    amount_czk: float
    amount_orig: float
    currency: str
    direction: Direction
    own_account: str
    counterparty_token: str
    payer_country: str | None
    payee_country: str | None
    channel_type: str
    source_dataset: str


class Client(BaseModel):
    client_id: str
    bank_id: str
    client_country: str | None
    contract_date: datetime | None
    contract_form: str | None  # "in person" | "distant form"
    pep: bool
    client_type: str | None  # source spelling kept ("enterpreneur")
    expected_volume: float | None
    expected_count: float | None
    q2_volume: float | None
    q2_count: float | None
    q2_max: float | None
    aml_risk: str | None  # low | medium | high
    source_dataset: str
    derived: bool = False


class Signal(BaseModel):
    signal_id: str
    detector_id: str
    version: str
    client_id: str
    score: float = Field(ge=0, le=1)
    evidence: list[str]  # field refs / tx ids
    explanation_template_key: str
    source: str  # citation or "own design"
    exculpatory: bool = False


class Triage(StrEnum):
    FP = "FP"
    REVIEW = "REVIEW"


class Case(BaseModel):
    case_id: str
    bank_id: str
    client_id: str
    signals: list[Signal]
    exculpatory: list[Signal]
    priority: int = Field(ge=0, le=100)
    triage: Triage
    triage_reasons: list[str]  # each references signal ids
    route: str = "mule_review"  # or "victim_protection"
    cluster_id: str | None = None


class PsiMessage(BaseModel):
    session_id: str
    sender: str
    step: str  # "blind" | "double_blind"
    elements: list[str]  # hex-encoded group elements only
