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
import os
import secrets
from concurrent.futures import ProcessPoolExecutor

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
EXP_BITS = 256        # secret exponent size: NIST SP 800-56A / RFC 3526 allow short exponents for the 2048-bit group (>= 224 bits for 112-bit security)
PARALLEL_MIN = 2000   # below this many elements the process pool costs more than it saves
_POOL: ProcessPoolExecutor | None = None


def _jacobi(a: int, n: int) -> int:
    """Jacobi symbol (a|n) for odd n > 0. For the safe prime P, (x|P) = 1 exactly when x lies in the prime-order subgroup."""
    a %= n
    result = 1
    while a:
        while a % 2 == 0:
            a //= 2
            if n % 8 in (3, 5):
                result = -result
        a, n = n, a
        if a % 4 == 3 and n % 4 == 3:
            result = -result
        a %= n
    return result if n == 1 else 0


def _pow_chunk(args: tuple[list[int], int]) -> list[int]:
    bases, k = args
    return [pow(b, k, P) for b in bases]


def _check_pow_chunk(args: tuple[list[str], int]) -> list[int]:
    """Decode hex group elements, REJECT any outside the prime-order subgroup (Jacobi symbol), and raise them to k."""
    hexes, k = args
    out = []
    for h in hexes:
        x = int(h, 16)
        if not 1 < x < P - 1 or _jacobi(x, P) != 1:
            raise ValueError("element not in the prime-order subgroup")
        out.append(pow(x, k, P))
    return out


def check_and_modexp_many(hexes: list[str], k: int) -> list[int]:
    """Validate-and-exponentiate untrusted elements (the only place a peer's element meets our secret exponent), parallel for big batches."""
    global _POOL
    workers = os.cpu_count() or 1
    if len(hexes) < PARALLEL_MIN or workers < 2:
        return _check_pow_chunk((hexes, k))
    if _POOL is None:
        _POOL = ProcessPoolExecutor(max_workers=workers)
    size = -(-len(hexes) // workers)
    return [v for part in _POOL.map(_check_pow_chunk, [(hexes[i:i + size], k) for i in range(0, len(hexes), size)]) for v in part]


def _plain(s: str) -> int:
    """Decode an element used for EQUALITY comparison only (it never meets our secret exponent), so no subgroup test is needed."""
    x = int(s, 16)
    if not 1 < x < P - 1:
        raise ValueError("element out of range")
    return x


def modexp_many(bases: list[int], k: int) -> list[int]:
    """[b^k mod P for b in bases], spread over CPU cores for large batches (same results as the serial loop)."""
    global _POOL
    workers = os.cpu_count() or 1
    if len(bases) < PARALLEL_MIN or workers < 2:
        return [pow(b, k, P) for b in bases]
    if _POOL is None:
        _POOL = ProcessPoolExecutor(max_workers=workers)
    size = -(-len(bases) // workers)
    chunks = [(bases[i:i + size], k) for i in range(0, len(bases), size)]
    return [v for part in _POOL.map(_pow_chunk, chunks) for v in part]


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
    if not 1 < x < P - 1 or _jacobi(x, P) != 1:
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
        self._k = secrets.randbits(EXP_BITS) | (1 << (EXP_BITS - 1))   # fresh per session
        self._rng = secrets.SystemRandom()
        self._perm: list[int] = []
        self._peer_double: set[int] = set()

    def blind(self) -> list[str]:
        """Round 1: shuffled H(x)^k for own tokens. The permutation is kept locally."""
        vals = modexp_many([hash_to_group(t, self.domain) for t in self.tokens], self._k)
        out, self._perm = _shuffled(vals, self._rng)
        return [_enc(v) for v in out]

    def respond(self, incoming: list[str], cardinality_only: bool = False) -> tuple[list[str], list[str]]:
        """Responder: raise the initiator's elements to k (same order, or shuffled for cardinality-only) and send own blinded set."""
        double = check_and_modexp_many(incoming, self._k)
        self._peer_double = set(double)
        if cardinality_only:
            self._rng.shuffle(double)
        return [_enc(v) for v in double], self.blind()

    def finish(self, double_blinded_mine: list[str], other_blinded: list[str], cardinality_only: bool = False) -> tuple[set[str] | int, list[str]]:
        """Initiator: intersect. Returns (tokens | cardinality, own double-blinding of the responder's set in received order)."""
        theirs_double = check_and_modexp_many(other_blinded, self._k)
        lookup = set(theirs_double)
        mine = [_plain(e) for e in double_blinded_mine]
        back = [_enc(v) for v in theirs_double]
        if cardinality_only:
            return sum(1 for v in mine if v in lookup), back
        # self._perm[j] = original token index of the j-th sent element
        hits = {self.tokens[self._perm[j]] for j, v in enumerate(mine) if v in lookup}
        return hits, back

    def learn_from_return(self, returned: list[str]) -> set[str]:
        """Responder: given the initiator's double-blinding of the responder's own set (in the order sent by blind()), learn the intersection."""
        mine = {v for v in self._peer_double}
        return {self.tokens[self._perm[j]] for j, e in enumerate(returned) if _plain(e) in mine}
