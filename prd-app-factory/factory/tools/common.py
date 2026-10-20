"""Tools every agent has: read App Pack files, run read-only SQL, finish."""
from __future__ import annotations

import json

from factory.apppack import now
from factory.tools import RunContext, tool
from factory.tools.db import run_readonly


@tool("read_pack_file",
      "Read a text file from this app's App Pack (e.g. manifest.yaml, data_contract.yaml, metrics.yaml, "
      "reports/conformance.json, handoffs/<agent>.json). Paths are relative to the App Pack root.",
      {"path": {"type": "string"}}, ["path"])
def read_pack_file(ctx: RunContext, path: str):
    target = (ctx.pack.dir / path).resolve()
    if ctx.pack.dir.resolve() not in target.parents and target != ctx.pack.dir.resolve():
        raise ValueError("path must stay inside the App Pack")
    if not target.is_file():
        files = sorted(str(p.relative_to(ctx.pack.dir)) for p in ctx.pack.dir.rglob("*")
                       if p.is_file() and "logs" not in p.parts and "data" not in p.parts)
        return {"error": f"{path} not found", "available": files[:200]}
    text = target.read_text(encoding="utf-8", errors="replace")
    return text if len(text) < 120_000 else text[:120_000] + "\n...[truncated]"


@tool("run_sql",
      "Run ONE read-only SELECT (or WITH ... SELECT) against this app's staging schema. Table names are "
      "unqualified (search_path is the app schema). Returns columns and up to 50 rows. Writes are refused.",
      {"sql": {"type": "string"}}, ["sql"])
def run_sql(ctx: RunContext, sql: str):
    columns, rows = run_readonly(ctx.pack.app_id, sql, limit=50)
    return {"columns": columns, "rows": rows, "row_count_shown": len(rows)}


@tool("finish",
      "Call exactly once when your stage is complete (or blocked). This ends your run and hands over to the "
      "coordinator. Be specific: what you produced, what you checked, what a reviewer should look at.",
      {"status": {"type": "string", "enum": ["ok", "blocked"]},
       "summary": {"type": "string"},
       "outputs": {"type": "array", "items": {"type": "string"}, "description": "App Pack paths you wrote"},
       "checks": {"type": "array", "items": {"type": "string"}, "description": "What you verified and the result"},
       "open_questions": {"type": "array", "items": {"type": "string"}}},
      ["status", "summary"])
def finish(ctx: RunContext, status: str, summary: str, outputs=None, checks=None, open_questions=None):
    ctx.finished = {"agent": ctx.agent, "mode": ctx.mode, "status": status, "summary": summary,
                    "outputs": outputs or [], "checks": checks or [], "open_questions": open_questions or [],
                    "finished_at": now()}
    name = f"handoffs/{ctx.agent}{'-' + ctx.mode if ctx.mode else ''}.json"
    ctx.pack.write_json(name, ctx.finished)
    return json.dumps({"recorded": name})
