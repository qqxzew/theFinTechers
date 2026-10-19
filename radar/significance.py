"""How improbable is a cross-bank token match under RANDOM overlap?

Null model: at every bank the exported candidates are a random subset (n of the N eligible clients) of that bank's clients. A token that K
of the bank's clients touch then has a hypergeometric number of candidates; popular tokens (large K) are discounted by construction
(an IDF-like effect). Per-bank tail probabilities are combined with Fisher's method and Bonferroni-corrected by the number of tests.
The only extra numbers a bank discloses for a MATCHED token are aggregate counts (local degree, eligible pool, exported candidates).
"""
from __future__ import annotations

import math

from scipy.stats import chi2, hypergeom

P_FLOOR = 1e-300


def bank_tail(x: int, n_eligible: int, deg: int, n_cands: int) -> float:
    """P(X >= x) when n_cands candidates are drawn at random from n_eligible clients, deg of which touch the token."""
    big_k = max(deg, x)
    big_n = max(n_eligible, big_k, n_cands)
    return max(float(hypergeom.sf(x - 1, big_n, big_k, min(n_cands, big_n))), P_FLOOR)


def token_p(entries: list[tuple[int, int, int, int]]) -> float:
    """entries: one (x, n_eligible, deg, n_cands) per bank that matched the token. Fisher-combined p-value."""
    ps = [bank_tail(*e) for e in entries]
    stat = -2.0 * sum(math.log(p) for p in ps)
    return max(float(chi2.sf(stat, 2 * len(ps))), P_FLOOR)


def adjusted_minus_log10(p: float, n_tests: int) -> float:
    """-log10 of the Bonferroni-adjusted p-value (>= 0)."""
    return max(0.0, -math.log10(min(1.0, p * max(1, n_tests))))
