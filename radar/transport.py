"""Transport between the radar coordinator and bank nodes. Every request/response is recorded verbatim (size-capped) so the traffic
that crossed a node boundary can be inspected (GET /wire on the radar, tests/integration/test_distributed.py).

Two implementations of one small interface:
  HttpTransport  - real HTTP (httpx) to node URLs, e.g. http://127.0.0.1:8101 (scripts/run_local_cluster.py, docker compose)
  AsgiTransport  - in-memory: httpx.ASGITransport straight into the node FastAPI apps (tests; no ports opened)
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

WIRE_CAP_BYTES = 64 * 1024 * 1024


class Transport(ABC):
    """request(bank, method, path, body) -> (status, json). Records every exchange in self.log."""

    def __init__(self, cap_bytes: int = WIRE_CAP_BYTES, timeout: float = 600.0) -> None:
        self.log: list[dict] = []
        self.cap_bytes = cap_bytes
        self.used_bytes = 0
        self.total_bytes = 0
        self.timeout = timeout

    @property
    @abstractmethod
    def banks(self) -> list[str]: ...

    @abstractmethod
    def _client(self, bank: str) -> httpx.AsyncClient: ...

    async def request(self, bank: str, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        raw = json.dumps(body, separators=(",", ":")) if body is not None else ""
        async with self._client(bank) as c:
            r = await c.request(method, path, content=raw.encode() if raw else None,
                                headers={"content-type": "application/json"} if raw else None)
        text = r.text
        try:
            data = r.json()
        except ValueError:
            data = {"raw": text}
        size = len(raw) + len(text)
        self.total_bytes += size
        entry = {"seq": len(self.log), "to": bank, "method": method, "path": path, "status": r.status_code,
                 "request_bytes": len(raw), "response_bytes": len(text)}
        if self.used_bytes + size <= self.cap_bytes:
            entry |= {"request": raw, "response": text}
            self.used_bytes += size
        else:
            entry["truncated"] = True
        self.log.append(entry)
        return r.status_code, data


class HttpTransport(Transport):
    def __init__(self, node_urls: dict[str, str], **kw) -> None:
        super().__init__(**kw)
        self.node_urls = dict(node_urls)

    @property
    def banks(self) -> list[str]:
        return sorted(self.node_urls)

    def _client(self, bank: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.node_urls[bank], timeout=self.timeout)


class AsgiTransport(Transport):
    """In-memory transport: no sockets, but the same HTTP/JSON encoding as the real thing (requests go through the node's ASGI stack)."""

    def __init__(self, node_apps: dict[str, Any], **kw) -> None:
        super().__init__(**kw)
        self.node_apps = dict(node_apps)

    @property
    def banks(self) -> list[str]:
        return sorted(self.node_apps)

    def _client(self, bank: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.node_apps[bank]), base_url=f"http://node-{bank.lower()}",
                                 timeout=self.timeout)
