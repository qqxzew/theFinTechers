from audit.log import AuditLog, verify_chain


def test_append_and_verify(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    e1 = log.append(actor="analyst1", action="triage", why="r", rule_version="1", model_version=None, input_hash="h1")
    e2 = log.append(actor="agent", action="explain", why="r2", rule_version="1", model_version="m", input_hash="h2")
    assert e1["prev_hash"] == "0" * 64
    assert e2["prev_hash"] == e1["hash"]
    assert verify_chain(tmp_path / "a.jsonl") == (True, None)


def test_tamper_detected(tmp_path):
    p = tmp_path / "a.jsonl"
    log = AuditLog(p)
    for i in range(4):
        log.append(actor="x", action="a", why=str(i), rule_version="1", model_version=None, input_hash="h")
    lines = p.read_text().splitlines()
    lines[1] = lines[1].replace('"why": "1"', '"why": "9"')
    p.write_text("\n".join(lines) + "\n")
    ok, bad = verify_chain(p)
    assert ok is False and bad == 1


def test_reopen_continues_chain(tmp_path):
    p = tmp_path / "a.jsonl"
    AuditLog(p).append(actor="x", action="a", why="w", rule_version="1", model_version=None, input_hash="h")
    AuditLog(p).append(actor="x", action="b", why="w", rule_version="1", model_version=None, input_hash="h")
    assert verify_chain(p) == (True, None)
