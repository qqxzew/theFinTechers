"""Conflict-of-interest checks for decisions and approvals."""

from typing import Any


def check_decision(decider: str, case: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    """Return self-review violations for a decider on a case, in fixed order."""
    violations: list[str] = []
    if decider == case["relationship_owner"]:
        violations.append("decider_is_relationship_owner")
    if decider in case["rule_authors"]:
        violations.append("decider_is_rule_author")
    if decider == case["first_triager"]:
        violations.append("decider_is_first_triager")
    return violations


def validate_approval(
    decider: str,
    approver: str | None,
    executor: str,
    priority: int,
    cfg: dict[str, Any],
) -> list[str]:
    """Return four-eyes and approver/executor violations, in fixed order."""
    violations: list[str] = []
    if priority >= cfg["four_eyes_min_priority"] and (approver is None or approver == decider):
        violations.append("four_eyes_required")
    if approver is not None and approver == executor:
        violations.append("approver_is_executor")
    return violations
