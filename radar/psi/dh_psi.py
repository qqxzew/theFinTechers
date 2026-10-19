"""Semi-honest Diffie-Hellman private set intersection over the RFC 3526 2048-bit MODP group (group 14).

H(x) = SHA-256-expanded hash of (domain, x) reduced mod p, then squared -> lands in the prime-order subgroup (order q=(p-1)/2).
Flow (A initiator, B responder):
  A: m1 = shuffle(H(x)^a)                                  -> B
  B: m2 = [ (e)^b for e in m1 ] (same order, or shuffled in cardinality mode),  m3 = shuffle(H(y)^b)  -> A
  A: intersection = { x_i : m2[i] in { e^a for e in m3 } }
  A then returns { e^a for e in m3 } in m3's order so B can learn the intersection as well (optional).
Security model: semi-honest. A malicious party can submit arbitrary tokens (probing) or a non-subgroup element; non-subgroup elements are
rejected, probing is handled by radar guards (rate limits, candidate-set admission), not by this module. PSI minimises disclosure; it is not a
legal basis for sharing.
"""
from __future__ import annotations

import hashlib
import secrets

P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)
Q = (P - 1) // 2
HEX_LEN = 512  # 2048 bits


def hash_to_group(token: str, domain: str) -> int:
    """Domain-separated hash of a token into the order-q subgroup."""
    seed = domain.encode() + b"\x00" + token.encode()
    stream = b"".join(hashlib.sha256(i.to_bytes(4, "big") + seed).digest() for i in range(10))
    h = int.from_bytes(stream, "big") % P
    if h in (0, 1, P - 1):  # astronomically unlikely; keep the invariant explicit
        raise ValueError("degenerate hash value")
    return pow(h, 2, P)


def _enc(x: int) -> str:
    return x.to_bytes(HEX_LEN // 2, "big").hex()


def _dec(s: str) -> int:
    x = int(s, 16)
    if not 1 < x < P - 1 or pow(x, Q, P) != 1:
        raise ValueError("element not in the prime-order subgroup")
    return x


def _shuffled(items: list, rng: secrets.SystemRandom) -> tuple[list, list[int]]:
    perm = list(range(len(items)))
    rng.shuffle(perm)
    return [items[i] for i in perm], perm


class PsiParty:
    """One side of one PSI session. A fresh secret exponent is drawn per instance (= per session)."""

    def __init__(self, tokens: list[str], domain: str) -> None:
        self.tokens = list(dict.fromkeys(tokens))
        self.domain = domain
        self._k = secrets.randbelow(Q - 2) + 2
        self._rng = secrets.SystemRandom()
        self._perm: list[int] = []
        self._peer_double: set[int] = set()

    def blind(self) -> list[str]:
        """Round 1: shuffled H(x)^k for own tokens. The permutation is kept locally."""
        vals = [pow(hash_to_group(t, self.domain), self._k, P) for t in self.tokens]
        out, self._perm = _shuffled(vals, self._rng)
        return [_enc(v) for v in out]

    def respond(self, incoming: list[str], cardinality_only: bool = False) -> tuple[list[str], list[str]]:
        """Responder: raise the initiator's elements to k (same order, or shuffled for cardinality-only) and send own blinded set."""
        double = [pow(_dec(e), self._k, P) for e in incoming]
        self._peer_double = set(double)
        if cardinality_only:
            self._rng.shuffle(double)
        return [_enc(v) for v in double], self.blind()

    def finish(self, double_blinded_mine: list[str], other_blinded: list[str], cardinality_only: bool = False) -> tuple[set[str] | int, list[str]]:
        """Initiator: intersect. Returns (tokens | cardinality, own double-blinding of the responder's set in received order)."""
        theirs_double = [pow(_dec(e), self._k, P) for e in other_blinded]
        lookup = set(theirs_double)
        mine = [_dec(e) for e in double_blinded_mine]
        back = [_enc(v) for v in theirs_double]
        if cardinality_only:
            return sum(1 for v in mine if v in lookup), back
        # self._perm[j] = original token index of the j-th sent element
        hits = {self.tokens[self._perm[j]] for j, v in enumerate(mine) if v in lookup}
        return hits, back

    def learn_from_return(self, returned: list[str]) -> set[str]:
        """Responder: given the initiator's double-blinding of the responder's own set (in the order sent by blind()), learn the intersection."""
        mine = {v for v in self._peer_double}
        return {self.tokens[self._perm[j]] for j, e in enumerate(returned) if _dec(e) in mine}
