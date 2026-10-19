"""FINREG regulatory export rows and CSV writing."""

from pathlib import Path

import polars as pl

FINREG_COLUMNS = [
    "alert_id",
    "alert_type",
    "client_id",
    "transaction_id",
    "triage",
    "priority",
    "executive_role",
    "executive_person",
    "approver",
    "reason",
    "log",
]

_SCHEMA = {
    "alert_id": pl.String,
    "alert_type": pl.String,
    "client_id": pl.String,
    "transaction_id": pl.String,
    "triage": pl.String,
    "priority": pl.Int64,
    "executive_role": pl.String,
    "executive_person": pl.String,
    "approver": pl.String,
    "reason": pl.String,
    "log": pl.String,
}


def to_finreg_rows(alerts: pl.DataFrame, cases: dict, decisions: dict) -> pl.DataFrame:
    """Flatten alerts joined with case triage and executive decisions into FINREG rows."""
    rows = []
    for alert in alerts.iter_rows(named=True):
        alert_type = alert["alert_type"]
        client_id = alert["client_id"]
        transaction_id = alert["transaction_id"]
        alert_id = f"{alert_type}-{transaction_id}" if transaction_id is not None else f"{alert_type}-{client_id}"
        case = cases.get(client_id)
        if case is None:
            triage, priority, reason, log = "REVIEW", 0, "no case", ""
        else:
            triage = case["triage"]
            priority = int(case["priority"])
            reason = " | ".join(case["reasons"])
            log = case["log"]
        decision = decisions.get(client_id) or {}
        rows.append(
            {
                "alert_id": alert_id,
                "alert_type": alert_type,
                "client_id": client_id,
                "transaction_id": transaction_id,
                "triage": triage,
                "priority": priority,
                "executive_role": decision.get("executive_role", ""),
                "executive_person": decision.get("executive_person", ""),
                "approver": decision.get("approver", ""),
                "reason": reason,
                "log": log,
            }
        )
    return pl.DataFrame(rows, schema=_SCHEMA).select(FINREG_COLUMNS)


def write_finreg_csv(df: pl.DataFrame, path: str | Path) -> None:
    """Write FINREG rows as utf-8 CSV with ';' separator."""
    df.write_csv(path, separator=";")
