"""PSI benchmark: python -m radar.psi.bench  -> eval/out/psi_bench.json (messages, bytes and wall time for 1k / 10k / 100k tokens per bank)."""
from __future__ import annotations

import json
import sys
import time

from radar.psi.dh_psi import PsiParty


def run(n: int, overlap: float = 0.1) -> dict:
    common = int(n * overlap)
    a = [f"A{i}" for i in range(n - common)] + [f"C{i}" for i in range(common)]
    b = [f"B{i}" for i in range(n - common)] + [f"C{i}" for i in range(common)]
    t0 = time.perf_counter()
    pa, pb = PsiParty(a, "bench"), PsiParty(b, "bench")
    m1 = pa.blind()
    m2, m3 = pb.respond(m1)
    got, back = pa.finish(m2, m3)
    learned = pb.learn_from_return(back)
    dt = time.perf_counter() - t0
    assert got == set(learned) == {f"C{i}" for i in range(common)}
    msgs = [m1, m2, m3, back]
    return {"tokens_per_bank": n, "seconds": round(dt, 2), "messages": len(msgs), "elements": sum(len(m) for m in msgs),
            "bytes": sum(len(e) for m in msgs for e in m) // 2, "matches": len(got), "cpu_count": __import__("os").cpu_count()}


if __name__ == "__main__":
    sizes = [int(x) for x in sys.argv[1:]] or [1000, 10000, 100000]
    res = []
    for n in sizes:
        res.append(run(n))
        print(res[-1], flush=True)
        json.dump({"synthetic": True, "runs": res}, open("eval/out/psi_bench.json", "w"), indent=1)
    json.dump({"synthetic": True, "note": "one machine, Python pow() with 256-bit exponents on the 2048-bit RFC 3526 group, process pool", "runs": res},
              open("eval/out/psi_bench.json", "w"), indent=1)
