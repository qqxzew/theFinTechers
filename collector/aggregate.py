"""Collector side of the secure aggregation: it receives masked uint32 vectors and sums them. It has no key and no bank data."""
from __future__ import annotations

import numpy as np


class MissingBankError(RuntimeError):
    """A round needs every registered bank; there is deliberately no dropout recovery."""


class Round:
    def __init__(self, round_id: str, banks: list[str]) -> None:
        self.round_id = round_id
        self.banks = sorted(banks)
        self._v: dict[str, dict[str, np.ndarray]] = {}
        self.bytes_in: dict[str, int] = {b: 0 for b in self.banks}

    def submit(self, bank_id: str, label: str, vec: np.ndarray) -> None:
        if bank_id not in self.banks:
            raise PermissionError(f"unknown bank {bank_id}")
        v = np.asarray(vec, dtype=np.uint32)
        self._v.setdefault(label, {})[bank_id] = v
        self.bytes_in[bank_id] += v.nbytes

    def total(self, label: str) -> np.ndarray:
        got = self._v.get(label, {})
        missing = [b for b in self.banks if b not in got]
        if missing:
            raise MissingBankError(f"round {self.round_id}, vector {label}: missing {missing}")
        out = np.zeros_like(next(iter(got.values())))
        for v in got.values():
            out = out + v            # wraps mod 2^32; masks cancel
        return out
