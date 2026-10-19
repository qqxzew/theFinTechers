"""Secure aggregation: masked sum == plain sum, a single masked vector is uniform and uncorrelated, a missing bank fails loudly,
the collector module cannot see bank data."""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import chi2

from collector.aggregate import MissingBankError, Round
from node.secagg import BankKey, masked_vector

BANKS = ["B1", "B2", "B3"]
N = 1 << 14


def _setup():
    keys = {b: BankKey(b) for b in BANKS}
    pubs = {b: k.public for b, k in keys.items()}
    return keys, pubs


def _counts(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = np.zeros(N, np.uint32)
    v[rng.integers(0, N, 300)] = rng.integers(1, 6, 300)
    return v


def test_masked_sum_equals_plain_sum():
    keys, pubs = _setup()
    plain = {b: _counts(i) for i, b in enumerate(BANKS)}
    rnd = Round("r1", BANKS)
    for b in BANKS:
        rnd.submit(b, "P", masked_vector(plain[b], keys[b], BANKS, pubs, "r1", "P"))
    assert np.array_equal(rnd.total("P"), sum(plain.values()).astype(np.uint32))


def test_single_masked_vector_is_uniform_and_uncorrelated():
    keys, pubs = _setup()
    plain = _counts(1)
    v = masked_vector(plain, keys["B1"], BANKS, pubs, "r2", "P")
    # chi-square on the top 8 bits over 256 bins
    obs = np.bincount((v >> 24).astype(np.int64), minlength=256)
    exp = len(v) / 256
    stat = ((obs - exp) ** 2 / exp).sum()
    assert chi2.sf(stat, 255) > 0.001
    assert abs(np.corrcoef(v.astype(np.float64), plain.astype(np.float64))[0, 1]) < 0.05
    assert not np.array_equal(v, plain)


def test_missing_bank_fails_loudly():
    keys, pubs = _setup()
    rnd = Round("r3", BANKS)
    for b in BANKS[:2]:
        rnd.submit(b, "P", masked_vector(_counts(1), keys[b], BANKS, pubs, "r3", "P"))
    with pytest.raises(MissingBankError):
        rnd.total("P")


def test_masks_differ_per_round_and_label():
    keys, pubs = _setup()
    a = masked_vector(np.zeros(64, np.uint32), keys["B1"], BANKS, pubs, "r4", "P")
    b = masked_vector(np.zeros(64, np.uint32), keys["B1"], BANKS, pubs, "r5", "P")
    c = masked_vector(np.zeros(64, np.uint32), keys["B1"], BANKS, pubs, "r4", "K")
    assert not np.array_equal(a, b) and not np.array_equal(a, c)


def test_rejects_non_subgroup_public_key():
    keys, _ = _setup()
    with pytest.raises(ValueError):
        keys["B1"].shared_secret(2**2047 + 12345)


def test_collector_module_cannot_import_bank_data():
    banned = {"node", "radar", "redteam", "eval", "ingest", "copilot", "escalation", "export", "api", "audit"}
    for f in Path("collector").glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
            for m in mods:
                assert m.split(".")[0] not in banned, f"{f} imports {m}"
