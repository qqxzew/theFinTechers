import json

from hypothesis import given, settings
from hypothesis import strategies as st

from audit.log import AuditLog, verify_chain

text = st.text(alphabet="abcdefgh 0123456789", min_size=1, max_size=12)


@settings(max_examples=40, deadline=None)
@given(st.lists(text, min_size=1, max_size=12))
def test_any_sequence_verifies_and_reopen_continues(tmp_path_factory, whys):
    p = tmp_path_factory.mktemp("c") / "a.jsonl"
    for i, w in enumerate(whys):
        AuditLog(p).append(actor="x", action="a", why=w, rule_version="1", model_version=None, input_hash=str(i))   # reopen every time
    assert verify_chain(p) == (True, None)


@settings(max_examples=40, deadline=None)
@given(st.lists(text, min_size=2, max_size=10), st.data())
def test_any_single_edit_is_detected_at_or_before_the_edit(tmp_path_factory, whys, data):
    p = tmp_path_factory.mktemp("t") / "a.jsonl"
    log = AuditLog(p)
    for i, w in enumerate(whys):
        log.append(actor="x", action="a", why=w, rule_version="1", model_version=None, input_hash=str(i))
    lines = p.read_text(encoding="utf-8").splitlines()
    i = data.draw(st.integers(0, len(lines) - 1))
    e = json.loads(lines[i])
    e["why"] = e["why"] + "!"
    lines[i] = json.dumps(e)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, bad = verify_chain(p)
    assert ok is False and bad == i


@settings(max_examples=25, deadline=None)
@given(st.lists(text, min_size=3, max_size=10), st.data())
def test_deleting_an_entry_is_detected(tmp_path_factory, whys, data):
    p = tmp_path_factory.mktemp("d") / "a.jsonl"
    log = AuditLog(p)
    for i, w in enumerate(whys):
        log.append(actor="x", action="a", why=w, rule_version="1", model_version=None, input_hash=str(i))
    lines = p.read_text(encoding="utf-8").splitlines()
    i = data.draw(st.integers(0, len(lines) - 2))     # deleting the LAST line is undetectable without an external head pointer (noted in ARCHITECTURE.md)
    del lines[i]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, _ = verify_chain(p)
    assert ok is False
