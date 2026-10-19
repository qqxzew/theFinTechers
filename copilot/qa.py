"""QA validation of copilot drafts against the structured case."""

import re

NOT_AVAILABLE_MARKERS = ("not available", "nedostupn", "neni k dispozici", "není k dispozici")

TIPPING_OFF_PATTERNS = (
    r"report(ed)?\s+(you|this|it|to)",
    r"\bFIU\b",
    r"FA[UÚ]",
    r"oznám",
    r"podez[řr]el",
    r"suspicious (transaction|activity) report",
    r"do not tell",
    r"nesd[ěe]l",
    r"\bSTR\b",
    r"\bOPO\b",
)

NUMBER_RE = re.compile(r"\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?%?")


def _case_numbers(node: object) -> list[float]:
    """Recursively collect all numeric values (excluding bools) from the case JSON."""
    found: list[float] = []
    if isinstance(node, bool):
        return found
    if isinstance(node, (int, float)):
        found.append(float(node))
    elif isinstance(node, dict):
        for value in node.values():
            found.extend(_case_numbers(value))
    elif isinstance(node, (list, tuple)):
        for value in node:
            found.extend(_case_numbers(value))
    return found


def _valid_refs(case: dict) -> set[str]:
    """Build the set of reference strings that may legitimately be cited."""
    refs: set[str] = set()
    for entry in case.get("signals", []):
        sid = entry.get("signal_id")
        if isinstance(sid, str):
            refs.add(sid)
    for entry in case.get("exculpatory", []):
        sid = entry.get("signal_id")
        if isinstance(sid, str):
            refs.add(sid)
    refs.update(f"features.{key}" for key in case.get("features", {}))
    refs.update(f"cluster.{key}" for key in case.get("cluster", {}))
    refs.update(f"case.{key}" for key in case)
    refs.update(f"triage_reasons[{i}]" for i in range(len(case.get("triage_reasons", []))))
    return refs


def _number_ok(value: float, is_percent: bool, case_numbers: list[float]) -> bool:
    """Check a number from the text against all numeric values in the case."""
    if is_percent:
        for case_value in case_numbers:
            if 0.0 <= case_value <= 1.0 and abs(value - 100.0 * case_value) <= 1.0:
                return True
            if value == case_value:
                return True
        return False
    if abs(value) < 1000:
        return True
    return any(abs(value - cv) <= 0.005 * abs(cv) for cv in case_numbers)


_SIGNAL_PARTS = {"score", "notes", "evidence", "source", "template", "detector_id"}


def _inside_valid_signal(ref: str, valid_refs: set[str]) -> bool:
    """'<signal_id>.<part>' or '<signal_id>.evidence.<key>' points inside a signal that exists."""
    parts = re.split(r"[.\s]+", ref.strip(), maxsplit=1)    # "D6:R1.notes", "D6:R1 evidence.x" (models vary the separator)
    return len(parts) == 2 and parts[0] in valid_refs and re.split(r"[.\s]+", parts[1])[0] in _SIGNAL_PARTS


def _has_name(name: str, text: str) -> bool:
    """Whole-word, case-insensitive match (a staff name such as 'max' must not fire on 'maximálně')."""
    return re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.IGNORECASE) is not None


def validate_draft(
    draft: dict,
    case: dict,
    analyst_names: list[str],
    customer_facing: bool = False,
) -> list[dict]:
    """Validate a draft against the case; return a list of violation dicts (empty = valid)."""
    violations: list[dict] = []
    valid_refs = _valid_refs(case)
    case_numbers = _case_numbers(case)
    names = [n for n in analyst_names if n]

    free_text = draft.get("free_text", "")
    for name in names:
        if _has_name(name, free_text):
            violations.append(
                {"kind": "analyst_name", "sentence": None, "detail": f"analyst name {name!r} in free_text"}
            )

    for i, sentence in enumerate(draft.get("sentences", [])):
        text = sentence.get("text", "")
        lowered = text.lower()

        if not sentence.get("refs") and not any(m in lowered for m in NOT_AVAILABLE_MARKERS):
            violations.append(
                {"kind": "missing_reference", "sentence": i, "detail": "sentence has no refs"}
            )

        for ref in sentence.get("refs", []):
            if ref not in valid_refs and not _inside_valid_signal(ref, valid_refs):
                violations.append(
                    {"kind": "unknown_reference", "sentence": i, "detail": f"unknown ref {ref!r}"}
                )

        for match in NUMBER_RE.finditer(text):
            token = match.group(0)
            is_percent = token.endswith("%")
            digits = token[:-1] if is_percent else token
            digits = digits.replace(" ", "").replace("\u00a0", "").replace(",", ".")
            if not digits:
                continue
            value = float(digits)
            if not _number_ok(value, is_percent, case_numbers):
                violations.append(
                    {
                        "kind": "number_not_in_case",
                        "sentence": i,
                        "detail": f"number {token!r} not supported by case values",
                    }
                )

        for name in names:
            if _has_name(name, text):
                violations.append(
                    {"kind": "analyst_name", "sentence": i, "detail": f"analyst name {name!r} in text"}
                )

        if customer_facing:
            for pattern in TIPPING_OFF_PATTERNS:
                found = re.search(pattern, text, re.IGNORECASE)
                if found:
                    violations.append(
                        {
                            "kind": "tipping_off",
                            "sentence": i,
                            "detail": f"tipping-off pattern {pattern!r} matched {found.group(0)!r}",
                        }
                    )
                    break

    return violations
