"""Same seed -> same world -> same report (PSI exponents are random per session, but the matched sets and clusters are not)."""
import hashlib
import json

import polars as pl

from eval.redteam_eval import evaluate
from redteam.generate import generate


def _digest(path):
    return hashlib.sha256(pl.read_parquet(f"{path}/tx.parquet").write_csv().encode()).hexdigest()


def test_world_and_report_are_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate(909, str(a), n_per_bank=150)
    generate(909, str(b), n_per_bank=150)
    assert _digest(a) == _digest(b)
    ra, rb = evaluate(str(a)), evaluate(str(b))

    def key(r):
        return json.dumps({"modes": {m: v["overall"] for m, v in r["modes"].items()}, "breakdown": r["breakdown_staj_psi"],
                           "clusters": sorted(c["cluster_id"] for c in r["clusters"])}, sort_keys=True, default=str)

    assert key(ra) == key(rb)
    assert ra["world"] != "" and ra["synthetic"] is True
