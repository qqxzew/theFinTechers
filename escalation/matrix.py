"""Escalation routing matrix: first matching rule wins."""

from pathlib import Path
from typing import Any

import yaml


def load_matrix(path: str | Path) -> dict[str, Any]:
    """Load a routing matrix from a YAML file."""
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)
        return data


def _matches(when: dict[str, Any], meta: dict[str, Any]) -> bool:
    """Check that all conditions in a rule's 'when' clause hold."""
    if "pep" in when and bool(meta.get("pep")) != bool(when["pep"]):
        return False
    if "cluster" in when and bool(meta.get("cluster")) != bool(when["cluster"]):
        return False
    if "priority_min" in when and not (meta.get("priority", 0) >= when["priority_min"]):
        return False
    if "alert_type" in when and meta.get("alert_type") != when["alert_type"]:
        return False
    return True


def route(meta: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    """Route an alert by the first matching rule; raise ValueError if none match."""
    for i, rule in enumerate(matrix["rules"]):
        if _matches(rule.get("when", {}), meta):
            return {
                "role": rule["role"],
                "rule_index": i,
                "matrix_is_placeholder": bool(matrix.get("placeholder", False)),
            }
    raise ValueError(f"no routing rule matched meta: {meta!r}")
