"""Run several task specs in parallel: python orchestrator/run_batch.py t001 t002 ..."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worker import run_task  # noqa: E402

T = Path(__file__).resolve().parent / "tasks"


def one(prefix: str) -> dict:
    f = next(T.glob(f"{prefix}*.json"))
    try:
        return run_task(json.loads(f.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        return {"id": f.stem, "status": "crash", "summary": repr(e), "tokens": 0}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(one, sys.argv[1:]):
            print(json.dumps(r, ensure_ascii=False))
