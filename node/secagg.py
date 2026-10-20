"""Bank side of the collector's secure aggregation (pairwise masks, Bonawitz-style without dropout recovery).

seed_ij = SHA-256(DH shared secret of banks i and j on the RFC 3526 group-14 || round_id || vector_label)
mask_ij = SHAKE-256(seed_ij) expanded to uint32[n]
bank i sends v_i = counts + sum_{j>i} mask_ij - sum_{j<i} mask_ji   (mod 2^32)
The collector adds all v_i and gets the plain totals; a single v_i is uniform. A round needs ALL banks (no dropout recovery): a missing bank
makes the round fail loudly in collector.aggregate. Semi-honest model; if the collector colludes with all other banks, the secrecy of one bank is lost.
"""
from __future__ import annotations

import hashlib
import secrets

import numpy as np

from radar.psi.dh_psi import P, Q

G = 2
EXP_BITS = 256


class BankKey:
    """A bank's DH key pair for mask agreement. The public part goes to the other banks, never to the collector."""

    def __init__(self, bank_id: str, secret: int | None = None) -> None:
        self.bank_id = bank_id
        self._x = secret if secret is not None else (secrets.randbits(EXP_BITS) % (Q - 2)) + 2
        self.public = pow(G, self._x, P)

    def shared_secret(self, other_public: int) -> bytes:
        if not 1 < other_public < P - 1 or pow(other_public, Q, P) != 1:
            raise ValueError("peer public key is not in the prime-order subgroup")
        return pow(other_public, self._x, P).to_bytes(256, "big")


def pair_mask(shared: bytes, round_id: str, label: str, n: int) -> np.ndarray:
    seed = hashlib.sha256(shared + round_id.encode() + b"|" + label.encode()).digest()
    return np.frombuffer(hashlib.shake_256(seed).digest(4 * n), dtype="<u4").astype(np.uint32)


def masked_vector(counts: np.ndarray, me: BankKey, bank_order: list[str], publics: dict[str, int], round_id: str, label: str) -> np.ndarray:
    """counts: uint32[n]. bank_order fixes i<j (sorted bank ids); publics: bank_id -> DH public key of every OTHER bank."""
    n = len(counts)
    out = counts.astype(np.uint32).copy()
    i = bank_order.index(me.bank_id)
    for j, other in enumerate(bank_order):
        if other == me.bank_id:
            continue
        m = pair_mask(me.shared_secret(publics[other]), round_id, label, n)
        out = out + m if j > i else out - m          # uint32 arithmetic wraps mod 2^32
    return out.astype(np.uint32)
