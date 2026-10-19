"""Write data/MANIFEST.json: file, size, SHA-256, row count, columns, download time."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

FILES = ["cnb/transactions.csv", "cnb/clients.csv", "ibm/HI-Small_Trans.csv", "ibm/HI-Small_Patterns.txt"]


def describe(p: Path) -> dict:
    h, rows = hashlib.sha256(), 0
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
            rows += chunk.count(b"\n")
    with p.open(encoding="utf-8-sig") as f:
        first = f.readline().rstrip("\n")
    cols = first.split(";" if ";" in first else ",") if p.suffix == ".csv" else None
    return {"file": p.name, "size": p.stat().st_size, "sha256": h.hexdigest(),
            "rows": rows - 1 if cols else rows, "columns": cols,
            "recorded_at": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat()}


def main(root: str = "data/raw") -> None:
    out = [describe(Path(root) / f) for f in FILES if (Path(root) / f).exists()]
    Path("data/MANIFEST.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps([{k: v for k, v in o.items() if k != "columns"} for o in out], indent=1))


if __name__ == "__main__":
    main()
