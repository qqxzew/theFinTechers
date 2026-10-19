"""Collector statistics on the summed vectors (plain totals; the collector never sees a single bank's counts).

WHERE: p0 = sum K / sum P; buckets with banks >= 2 and K >= 3 are tested with binom.sf(K-1, P, p0); BH-FDR over the tested buckets.
Buckets with P >= p_inst or on the allowlist are reported but never expanded; buckets with P <= small_max are marked small.
HOW: see how_windows (space-time permutation baseline, Kulldorff et al. 2005).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import binom


def bh_reject(p: np.ndarray, q: float) -> np.ndarray:
    """Benjamini-Hochberg: boolean mask of rejected hypotheses at FDR level q."""
    m = len(p)
    if m == 0:
        return np.zeros(0, bool)
    order = np.argsort(p)
    thresh = q * (np.arange(1, m + 1) / m)
    ok = p[order] <= thresh
    k = np.max(np.nonzero(ok)[0]) + 1 if ok.any() else 0
    out = np.zeros(m, bool)
    out[order[:k]] = True
    return out


@dataclass
class WhereResult:
    p0: float
    n_tested: int
    flagged: list[dict] = field(default_factory=list)      # expandable buckets: {bucket, P, K, banks, p, small}
    suppressed: list[dict] = field(default_factory=list)   # significant but institutional (P >= p_inst or allowlisted): counted, never expanded


def where_test(P: np.ndarray, K: np.ndarray, n_banks: np.ndarray, *, q: float = 0.01, p_inst: int = 50, small_max: int = 20,
               allowlist_buckets: set[int] | frozenset[int] = frozenset(), min_k: int = 3, min_banks: int = 2) -> WhereResult:
    P = P.astype(np.int64)
    K = K.astype(np.int64)
    tot_p = int(P.sum())
    p0 = float(K.sum()) / tot_p if tot_p else 0.0
    cand = np.nonzero((n_banks >= min_banks) & (K >= min_k) & (P >= K))[0]
    if len(cand) == 0 or p0 <= 0:
        return WhereResult(p0, 0)
    pv = binom.sf(K[cand] - 1, P[cand], p0)
    rej = bh_reject(pv, q)
    res = WhereResult(p0, len(cand))
    for b, p, r in zip(cand, pv, rej, strict=True):
        if not r:
            continue
        row = {"bucket": int(b), "P": int(P[b]), "K": int(K[b]), "banks": int(n_banks[b]), "p": float(p), "small": bool(P[b] <= small_max)}
        (res.suppressed if (P[b] >= p_inst or int(b) in allowlist_buckets) else res.flagged).append(row)
    return res


@dataclass
class HowResult:
    n_windows: int
    n_tested: int
    flagged: list[dict] = field(default_factory=list)


def _window_sum(a: np.ndarray, skim_w: int, days: int) -> np.ndarray:
    """a: (D, S, L, Z). Sum over `skim_w` adjacent skim bins and `days` consecutive days ending at each index (valid positions only)."""
    cs = np.cumsum(np.pad(a, ((1, 0), (0, 0), (0, 0), (0, 0))), axis=0)
    by_day = cs[days:] - cs[:-days] if days <= a.shape[0] else np.zeros((0, *a.shape[1:]))
    cs2 = np.cumsum(np.pad(by_day, ((0, 0), (1, 0), (0, 0), (0, 0))), axis=1)
    return cs2[:, skim_w:] - cs2[:, :-skim_w]


def _window_max(a: np.ndarray, skim_w: int, days: int) -> np.ndarray:
    D, S = a.shape[0], a.shape[1]
    out = None
    for dd in range(days):
        for ss in range(skim_w):
            part = a[dd:D - days + 1 + dd, ss:S - skim_w + 1 + ss]
            out = part if out is None else np.maximum(out, part)
    return out


def how_test(C: np.ndarray, B: np.ndarray, *, last_days: int = 2, q: float = 0.01, min_obs: int = 4, min_banks: int = 2) -> HowResult:
    """Space-time permutation scan (Kulldorff et al. 2005 style) on summed cell counts.

    C: (D, 30, 6, 2) customers with an event per day/cell (sum over banks); B: same shape, number of banks with C > 0 (sum of the indicators).
    mu(cell, day) = C(cell, .) * C(., day) / C(., .) over the whole history plus the current window. Windows: skim width 1 or 3 x one delay bin x
    one dormant value x 1-3 consecutive days; only windows ENDING in the last `last_days` days are scanned (the scan runs every replay step).
    Family for BH-FDR = all enumerated windows of that scan.
    """
    from scipy.stats import poisson
    C = C.astype(np.float64)
    D = C.shape[0]
    tot = C.sum()
    if tot <= 0:
        return HowResult(0, 0)
    mu = C.sum(axis=0, keepdims=True) * C.sum(axis=(1, 2, 3), keepdims=True) / tot
    rows: list[tuple] = []
    n_windows = 0
    for sw in (1, 3):
        for nd in (1, 2, 3):
            obs = _window_sum(C, sw, nd)
            mus = _window_sum(mu, sw, nd)
            bk = _window_max(B, sw, nd)
            last = obs.shape[0]            # window k covers days k .. k+nd-1; end day = k+nd-1
            ks = [k for k in range(last) if k + nd - 1 >= D - last_days]
            if not ks:
                continue
            n_windows += len(ks) * obs[0].size
            sub_o, sub_m, sub_b = obs[ks], mus[ks], bk[ks]
            ok = (sub_o >= min_obs) & (sub_b >= min_banks)
            for idx in zip(*np.nonzero(ok), strict=True):
                k, s, dl, z = (int(x) for x in idx)
                p = float(poisson.sf(sub_o[k, s, dl, z] - 1, max(sub_m[k, s, dl, z], 1e-12)))
                rows.append((p, ks[k], s, sw, dl, z, nd, float(sub_o[k, s, dl, z]), float(sub_m[k, s, dl, z]), int(sub_b[k, s, dl, z])))
    if not rows:
        return HowResult(n_windows, 0)
    pv = np.array([r[0] for r in rows])
    # BH over ALL enumerated windows of the scan: untested windows have p = 1, so the family size is n_windows
    order = np.argsort(pv)
    thresh = q * (np.arange(1, len(pv) + 1) / max(n_windows, len(pv)))
    ok = pv[order] <= thresh
    kmax = int(np.max(np.nonzero(ok)[0])) + 1 if ok.any() else 0
    res = HowResult(n_windows, len(rows))
    for i in order[:kmax]:
        p, d1, s, sw, dl, z, nd, o, m, b = rows[i]
        res.flagged.append({"skim_lo": s + 1, "skim_hi": s + sw, "delay_bin": dl, "dormant": z, "day_lo": d1, "day_hi": d1 + nd - 1,
                            "obs": o, "expected": m, "banks": b, "p": p, "strength": "strong" if p < 1e-9 else "moderate"})
    return res
