import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from radar.psi.dh_psi import P, PsiParty, Q, hash_to_group

tok = st.text(alphabet="ABCDEFGH0123456789:", min_size=1, max_size=12)


def run(a_tokens, b_tokens, card=False):
    a, b = PsiParty(a_tokens, "t"), PsiParty(b_tokens, "t")
    m1 = a.blind()
    m2, m3 = b.respond(m1, cardinality_only=card)
    res_a, back = a.finish(m2, m3, cardinality_only=card)
    res_b = None if card else b.learn_from_return(back)
    return res_a, res_b


@settings(max_examples=8, deadline=None)
@given(st.lists(tok, max_size=8), st.lists(tok, max_size=8))
def test_psi_equals_plain_intersection(xs, ys):
    ra, rb = run(xs, ys)
    want = set(xs) & set(ys)
    assert ra == want and rb == want


@settings(max_examples=6, deadline=None)
@given(st.lists(tok, max_size=8), st.lists(tok, max_size=8))
def test_cardinality_mode(xs, ys):
    n, _ = run(xs, ys, card=True)
    assert n == len(set(xs) & set(ys))


def test_hash_lands_in_subgroup_and_domain_separated():
    h1, h2 = hash_to_group("x", "d1"), hash_to_group("x", "d2")
    assert pow(h1, Q, P) == 1 and h1 != h2


def test_blinded_messages_contain_no_plaintext_and_differ_per_session():
    m_a = PsiParty(["secret-token"], "t").blind()
    m_b = PsiParty(["secret-token"], "t").blind()
    assert m_a != m_b and b"secret" not in bytes.fromhex(m_a[0])


def test_rejects_non_subgroup_element():
    b = PsiParty(["a"], "t")
    with pytest.raises(ValueError):
        b.respond([format(11, "0512x")])  # 11 is a quadratic non-residue mod p, i.e. outside the order-q subgroup
