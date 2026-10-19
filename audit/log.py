"""Append-only hash-chained JSONL audit log."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


def _canonical_hash(entry: dict[str, Any]) -> str:
    """SHA-256 hex of the canonical JSON of an entry without its 'hash' key."""
    payload = {k: v for k, v in entry.items() if k != "hash"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only JSONL log where each entry chains to the previous entry's hash."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._seq = 0
        self._prev_hash = GENESIS_HASH
        if self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                last = json.loads(lines[-1])
                self._seq = int(last["seq"]) + 1
                self._prev_hash = last["hash"]

    def append(
        self,
        actor: str,
        action: str,
        why: str,
        rule_version: str | None,
        model_version: str | None,
        input_hash: str,
        **extra: Any,
    ) -> dict[str, Any]:
        """Append a chained entry and return it, including its hash."""
        entry: dict[str, Any] = {
            "seq": self._seq,
            "ts": datetime.now(UTC).isoformat(),
            "actor": actor,
            "action": action,
            "why": why,
            "rule_version": rule_version,
            "model_version": model_version,
            "input_hash": input_hash,
            "extra": dict(extra),
            "prev_hash": self._prev_hash,
        }
        entry["hash"] = _canonical_hash(entry)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=False) + "\n")
        self._seq += 1
        self._prev_hash = entry["hash"]
        return entry


def verify_chain(path: str | Path) -> tuple[bool, int | None]:
    """Verify the chain; return (True, None) if intact else (False, first bad line index)."""
    text = Path(path).read_text(encoding="utf-8")
    prev_hash = GENESIS_HASH
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("prev_hash") != prev_hash:
            return False, index
        if entry.get("hash") != _canonical_hash(entry):
            return False, index
        prev_hash = entry["hash"]
    return True, None
