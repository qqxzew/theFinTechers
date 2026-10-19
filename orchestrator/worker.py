"""Sandboxed single-task worker on Amazon Bedrock (Converse + tool use).

Usage: python orchestrator/worker.py orchestrator/tasks/<task>.json

A task is a small JSON spec:
  id, goal, read (extra files to preload), write (glob list the worker may write),
  accept (list of commands that must exit 0), max_steps, retries.
The orchestrator (not the worker) decides whether the result is accepted.
"""
from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "orchestrator" / "runs"
MODEL_ID = os.environ.get("WORKER_MODEL", "global.moonshotai.kimi-k3")
PROFILE = os.environ.get("AWS_PROFILE_WORKER", "hackathon")
REGION = os.environ.get("AWS_REGION_WORKER", "eu-central-1")
DENY_READ = (".git/", ".venv/", ".env", "orchestrator/runs/", "data/raw/")
FORBIDDEN_CHARS = set(";|&><`$\n")
ALLOWED_MODULES = {"pytest", "ruff", "mypy"}

SYSTEM = """You are a junior engineer doing ONE small, precisely specified task in the Stáj repo.
Rules:
- Do exactly what the task says. No extra features, no refactors, no renaming.
- Read the listed files first (use read_file). Never guess an interface: match it exactly.
- You can only write to the allowed paths given in the task. Other writes are rejected.
- Write the code, then run the acceptance commands with run_cmd and fix failures.
- Python 3.12 style, type hints, short docstrings, no comments that restate code.
- When the acceptance commands pass, call finish with a 1-3 sentence summary.
- If the task is impossible or the spec is contradictory, call finish with status "blocked" and say why. Do not invent.
"""

TOOLS = {
    "tools": [
        {"toolSpec": {"name": "read_file", "description": "Read a text file (repo-relative path).",
                      "inputSchema": {"json": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}},
        {"toolSpec": {"name": "list_dir", "description": "List a directory (repo-relative).",
                      "inputSchema": {"json": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}},
        {"toolSpec": {"name": "write_file", "description": "Create/overwrite a file in an allowed path. Full content.",
                      "inputSchema": {"json": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}}},
        {"toolSpec": {"name": "run_cmd", "description": "Run `python <file>` or `python -m pytest|ruff|mypy ...` from repo root. No shell operators.",
                      "inputSchema": {"json": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}}},
        {"toolSpec": {"name": "finish", "description": "End the task.",
                      "inputSchema": {"json": {"type": "object", "properties": {"status": {"type": "string", "enum": ["done", "blocked"]}, "summary": {"type": "string"}}, "required": ["status", "summary"]}}}},
    ]
}


def _safe(rel: str) -> Path | None:
    p = (ROOT / rel).resolve()
    try:
        r = p.relative_to(ROOT).as_posix()
    except ValueError:
        return None
    return p if not any((r + "/").startswith(d) or r == d.rstrip("/") for d in DENY_READ) else None


class Sandbox:
    def __init__(self, write_globs: list[str]) -> None:
        self.write_globs = write_globs

    def read_file(self, path: str) -> str:
        p = _safe(path)
        if p is None or not p.is_file():
            return f"ERROR: cannot read {path}"
        t = p.read_text(encoding="utf-8", errors="replace")
        return t if len(t) <= 24000 else t[:24000] + "\n...[truncated]"

    def list_dir(self, path: str) -> str:
        p = _safe(path)
        if p is None or not p.is_dir():
            return f"ERROR: cannot list {path}"
        return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir()))

    def write_file(self, path: str, content: str) -> str:
        p = _safe(path)
        rel = Path(path).as_posix()
        if p is None or ".." in rel.split("/") or not any(fnmatch.fnmatch(rel, g) for g in self.write_globs):
            return f"ERROR: write to {path} not allowed. Allowed: {self.write_globs}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
        return f"ok: wrote {len(content)} chars to {rel}"

    def run_cmd(self, cmd: str, timeout: int = 180) -> tuple[int, str]:
        if FORBIDDEN_CHARS & set(cmd):
            return 2, "ERROR: shell operators not allowed"
        try:
            argv = shlex.split(cmd)
        except ValueError as e:
            return 2, f"ERROR: {e}"
        if not argv or argv[0] != "python":
            return 2, "ERROR: only `python ...` commands allowed"
        ok = (len(argv) >= 3 and argv[1] == "-m" and argv[2] in ALLOWED_MODULES) or (
            len(argv) >= 2 and not argv[1].startswith("-") and _safe(argv[1]) is not None)
        if not ok:
            return 2, "ERROR: allowed: python <repo file> | python -m pytest|ruff|mypy"
        env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_") and k != "PYTHONPATH"}
        env["PYTHONPATH"] = str(ROOT)
        argv[0] = sys.executable
        try:
            r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, "ERROR: timeout"
        out = (r.stdout + r.stderr)
        return r.returncode, out[-6000:]


def _client():
    cfg = Config(read_timeout=300, retries={"max_attempts": 2})
    return boto3.Session(profile_name=PROFILE, region_name=REGION).client("bedrock-runtime", config=cfg)


def _converse(client, messages, system):
    for attempt in range(6):
        try:
            return client.converse(modelId=MODEL_ID, messages=messages, system=[{"text": system}],
                                   toolConfig=TOOLS, inferenceConfig={"maxTokens": 8000})
        except ClientError as e:
            if e.response["Error"]["Code"] in ("ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException", "InternalServerException"):
                time.sleep(2 ** attempt * 2)
                continue
            raise
    raise RuntimeError("bedrock retries exhausted")


def run_task(task: dict) -> dict:
    sb = Sandbox(task["write"])
    client = _client()
    RUNS.mkdir(parents=True, exist_ok=True)
    log = (RUNS / f"{task['id']}.jsonl").open("w", encoding="utf-8")
    preload = "\n\n".join(f"=== {f} ===\n{sb.read_file(f)}" for f in task.get("read", []))
    user = (f"TASK {task['id']}\n{task['goal']}\n\nYou may write only: {task['write']}\n"
            f"Acceptance commands (must all exit 0): {task['accept']}\n\nPRELOADED FILES:\n{preload}")
    messages = [{"role": "user", "content": [{"text": user}]}]
    tokens = 0
    retries_left = task.get("retries", 2)
    status, summary = "step_limit", ""
    for step in range(task.get("max_steps", 20)):
        resp = _converse(client, messages, SYSTEM)
        tokens += resp["usage"]["totalTokens"]
        content = [b for b in resp["output"]["message"]["content"] if "reasoningContent" not in b]
        messages.append({"role": "assistant", "content": content})
        uses = [b["toolUse"] for b in content if "toolUse" in b]
        log.write(json.dumps({"step": step, "stop": resp["stopReason"], "tools": [u["name"] for u in uses]}) + "\n")
        if not uses:
            messages.append({"role": "user", "content": [{"text": "Use a tool. Call finish when done."}]})
            continue
        results, finished = [], False
        for u in uses:
            n, a = u["name"], u["input"]
            if n == "read_file":
                out = sb.read_file(a.get("path", ""))
            elif n == "list_dir":
                out = sb.list_dir(a.get("path", ""))
            elif n == "write_file":
                out = sb.write_file(a.get("path", ""), a.get("content", ""))
            elif n == "run_cmd":
                code, txt = sb.run_cmd(a.get("cmd", ""))
                out = f"exit={code}\n{txt}"
            elif n == "finish":
                status, summary, finished = a.get("status", "done"), a.get("summary", ""), True
                out = "bye"
            else:
                out = "ERROR: unknown tool"
            results.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"text": out}]}})
        messages.append({"role": "user", "content": results})
        if finished:
            if status == "blocked":
                break
            fails = []
            for c in task["accept"]:
                code, txt = sb.run_cmd(c)
                if code != 0:
                    fails.append(f"$ {c}\nexit={code}\n{txt}")
            if not fails:
                status = "accepted"
                break
            if retries_left <= 0:
                status = "rejected"
                break
            retries_left -= 1
            messages.append({"role": "user", "content": [{"text": "Acceptance FAILED. Fix and call finish again.\n" + "\n".join(fails)}]})
            status = "retry"
    if status in ("step_limit", "retry"):
        if all(sb.run_cmd(c)[0] == 0 for c in task["accept"]):
            status = "accepted_after_limit"
    log.write(json.dumps({"final": status, "summary": summary, "tokens": tokens}) + "\n")
    log.close()
    return {"id": task["id"], "status": status, "summary": summary, "tokens": tokens}


if __name__ == "__main__":
    t = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(run_task(t), ensure_ascii=False))
