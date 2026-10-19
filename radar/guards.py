"""Submission guards for radar sessions."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Decision:
    """Outcome of a guard check."""

    allowed: bool
    reason: str


class Guards:
    """Validates submissions against configured limits."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self._accepted: dict[str, list[datetime]] = {}

    def check(self, bank_id: str, submission: list[dict], now: datetime) -> Decision:
        """Check a submission; first failing check returns its reason."""
        n = len(submission)
        if n < self.cfg["min_set_size"]:
            return Decision(False, f"min_set_size: {n} below {self.cfg['min_set_size']}")
        if n > self.cfg["max_tokens"]:
            return Decision(False, f"max_tokens: {n} above {self.cfg['max_tokens']}")
        unscored = sum(1 for item in submission if item["score"] is None) / n
        if unscored > self.cfg["max_unscored_share"]:
            return Decision(False, f"unscored: share {unscored:.3f} above {self.cfg['max_unscored_share']}")
        cutoff = now - timedelta(hours=1)
        recent = [t for t in self._accepted.get(bank_id, []) if t > cutoff]
        self._accepted[bank_id] = recent
        if len(recent) >= self.cfg["max_sessions_per_hour"]:
            return Decision(False, f"rate: {len(recent)} accepted sessions in past hour")
        recent.append(now)
        return Decision(True, "ok")
