import json
import logging
import os
import urllib.request

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from sqlalchemy import text

from dif import mcp_client, telemetry
from dif.auth import admin_user, approver_user, current_user, warn_if_open
from dif.config import settings
from dif.evaluation.framework import evaluate
from dif.runtime.agents import AgentError
from dif.runtime.engine import Runtime
from dif.runtime.factory import build_runtime
from dif.runtime.metrics import QUEUE_DEPTH

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
telemetry.setup()
warn_if_open()

rt: Runtime = build_runtime()
QUEUE_DEPTH.set_function(rt.executor.depth)
if rt.executor.kind == "local":
    rt.recover_orphans()
app = FastAPI(title="DIF Data Intelligence Factory", version="1.3.0",
              description="Agent runtime (durable runs, approval gates, parallel steps), skill registry, build-time "
                          "agents and evaluation. Authenticate with the X-API-Key header (Authorize button).")


class RunRequest(BaseModel):
    input: dict
    dry_run: bool = False
    version: str | None = None
    enterprise: str | None = None   # platform-wide keys may run on behalf of an enterprise


class SkillRequest(BaseModel):
    input: dict


class EvalRequest(BaseModel):
    cases: list[dict] | None = None
    dry_run: bool = True


class DecisionRequest(BaseModel):
    comment: str | None = None
    data: dict | None = None        # approve only: reviewer-supplied data passed on as the gate step output


def _bad(e, code=400):
    return HTTPException(code, str(e))


def _scope(user, requested=None):
    """Enterprise a request acts on: the key's own enterprise, else the requested one (platform keys), else none."""
    if user["enterprise"]:
        if requested and requested != user["enterprise"]:
            raise HTTPException(403, "key is bound to another enterprise")
        return user["enterprise"]
    return requested


# ---- health / observability (open: used by load balancers and Prometheus) --------------------------
@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "skills": len(rt.skills.list()), "agents": len(rt.agents.list()),
            "executor": rt.executor.kind, "auth": bool(settings.api_keys), "skill_errors": rt.skills.errors,
            "artifact_store": settings.artifact_store.split("://")[0]}


@app.get("/health/ready", tags=["ops"])
def ready():
    """Readiness probe: 503 until the database (and Temporal, if used) are reachable."""
    try:
        with rt.store.engine.connect() as c:
            c.execute(text("select 1"))
        if not rt.executor.healthy():
            raise RuntimeError(f"{rt.executor.kind} executor unavailable")
    except Exception as e:
        raise HTTPException(503, f"not ready: {e}")
    return {"status": "ready"}


def _http_ok(url):
    try:
        urllib.request.urlopen(url, timeout=3).read()
        return "ok"
    except Exception as e:
        return f"error: {e}"


@app.get("/health/deps", tags=["ops"])
def health_deps():
    out = {}
    try:
        with rt.store.engine.connect() as c:
            c.execute(text("select 1"))
        out["database"] = "ok"
    except Exception as e:
        out["database"] = f"error: {e}"
    out["executor"] = f"ok ({rt.executor.kind})" if rt.executor.healthy() else f"error ({rt.executor.kind})"
    try:
        rt.artifacts.ls("")
        out["artifact_store"] = f"ok ({settings.artifact_store.split('://')[0]})"
    except Exception as e:
        out["artifact_store"] = f"error: {e}"
    for name, env, path in (("neo4j", "DIF_NEO4J_HTTP", ""), ("qdrant", "DIF_QDRANT_URL", "/healthz"),
                            ("ollama", "DIF_OLLAMA_URL", "/api/tags")):
        url = os.getenv(env)
        out[name] = _http_ok(url.rstrip("/") + path) if url else "not configured"
    return out


@app.get("/metrics", tags=["ops"])
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---- skills ---------------------------------------------------------------------------------------
@app.get("/skills", tags=["skills"])
def skills(user=Depends(current_user)):
    return rt.skills.list(user["enterprise"])


@app.post("/skills/reload", tags=["skills"], dependencies=[Depends(admin_user)])
def reload_skills():
    rt.skills.discover()
    return {"skills": len(rt.skills.list()), "errors": rt.skills.errors}


@app.post("/skills/{name}/execute", tags=["skills"])
def run_skill(name: str, req: SkillRequest, version: str | None = None, user=Depends(current_user)):
    try:
        skill = rt.skills.get(name, version, user["enterprise"])
        if skill.restricted and user["role"] != "admin":
            raise HTTPException(403, f"skill '{name}' is restricted to admin keys")
        return skill.execute(req.input, {"dry_run": True, "enterprise": user["enterprise"], "artifacts": rt.artifacts})
    except HTTPException:
        raise
    except Exception as e:  # skill-level failure (bad input, upstream/MCP error): report, don't 500
        raise _bad(e)


# ---- MCP servers ----------------------------------------------------------------------------------
@app.get("/mcp/servers", tags=["mcp"], dependencies=[Depends(current_user)])
def mcp_servers():
    """Configured MCP servers (credentials are never returned)."""
    return [{"name": n, "transport": c.get("transport", "http"), "url": c.get("url"),
             "allowed_tools": c.get("allowed_tools", mcp_client.DEFAULT_ALLOWED)} for n, c in mcp_client.load_servers().items()]


@app.get("/mcp/servers/{name}/tools", tags=["mcp"], dependencies=[Depends(admin_user)])
def mcp_tools(name: str):
    """Live tools/list from the server, with whether each tool passes the platform allowlist. Use it to discover tool names."""
    try:
        return mcp_client.list_tools(name)
    except mcp_client.McpError as e:
        raise HTTPException(502, str(e))


# ---- agents ---------------------------------------------------------------------------------------
@app.get("/agents", tags=["agents"], dependencies=[Depends(current_user)])
def agents():
    return rt.agents.list()


@app.post("/agents", tags=["agents"], status_code=201)
def register_agent(cfg: dict, user=Depends(admin_user)):
    """Register a new agent (or new version) at runtime: {name, version, description, steps:[...], output, persist, acceptance}."""
    try:
        rt.agents.register(cfg, rt.skills, user["name"], user["enterprise"])
    except AgentError as e:
        raise _bad(e, 422)
    return {"registered": f"{cfg['name']}@{cfg['version']}"}


@app.post("/agents/{name}/versions/{version}/{action}", tags=["agents"])
def toggle_agent(name: str, version: str, action: str, _=Depends(admin_user)):
    if action not in ("enable", "disable"):
        raise HTTPException(404, "action must be enable|disable")
    try:
        rt.agents.set_enabled(name, version, action == "enable")
    except AgentError as e:
        raise _bad(e, 404)
    return {"agent": name, "version": version, "enabled": action == "enable"}


@app.post("/agents/{name}/runs", tags=["runs"], status_code=202)
def start_run(name: str, req: RunRequest, wait: bool = Query(False, description="block until the run finishes or pauses"),
              user=Depends(current_user)):
    try:
        fn = rt.start if wait else rt.submit
        return fn(name, req.input, req.dry_run, user["name"], req.version, _scope(user, req.enterprise))
    except AgentError as e:
        raise _bad(e, 404)


@app.post("/agents/{name}/evaluate", tags=["evaluation"])
def evaluate_agent(name: str, req: EvalRequest, user=Depends(current_user)):
    try:
        return evaluate(rt, name, req.cases or DEFAULT_CASES, req.dry_run, user["enterprise"])
    except AgentError as e:
        raise _bad(e, 404)


# ---- runs -----------------------------------------------------------------------------------------
@app.get("/runs", tags=["runs"])
def list_runs(status: str | None = None, agent: str | None = None, parent: str | None = None, limit: int = 50,
              user=Depends(current_user)):
    return rt.store.list_runs(limit, status, agent, user["enterprise"], parent)


@app.get("/runs/{rid}", tags=["runs"])
def get_run(rid: str, user=Depends(current_user)):
    r = rt.store.get_run(rid, user["enterprise"])
    if not r:
        raise HTTPException(404, "run not found")
    if r["status"] == "awaiting_approval":
        gate = rt.store.pending_gate(rid)
        r["pending_approval"] = {"step": gate[0], **{k: gate[1].get(k) for k in ("title", "payload", "roles", "requested_at", "delegated", "child_run")}} if gate else None
    return r


@app.get("/runs/{rid}/history", tags=["runs"])
def history(rid: str, user=Depends(current_user)):
    if not rt.store.get_run(rid, user["enterprise"]):
        raise HTTPException(404, "run not found")
    return rt.store.history(rid)


@app.get("/runs/{rid}/children", tags=["runs"])
def children(rid: str, user=Depends(current_user)):
    if not rt.store.get_run(rid, user["enterprise"]):
        raise HTTPException(404, "run not found")
    return rt.store.list_runs(200, parent=rid)


@app.post("/runs/{rid}/resume", tags=["runs"])
def resume(rid: str, wait: bool = False, user=Depends(current_user)):
    if not rt.store.get_run(rid, user["enterprise"]):
        raise HTTPException(404, "run not found")
    try:
        return rt.resume(rid, wait)
    except AgentError as e:
        raise _bad(e, 409)


@app.post("/runs/{rid}/cancel", tags=["runs"])
def cancel(rid: str, user=Depends(current_user)):
    if not rt.store.get_run(rid, user["enterprise"]):
        raise HTTPException(404, "run not found")
    try:
        return {"id": rid, "status": rt.cancel(rid)}
    except AgentError as e:
        raise _bad(e, 404)


def _gate_check(rid, user):
    run = rt.store.get_run(rid, user["enterprise"])
    if not run:
        raise HTTPException(404, "run not found")
    if run["status"] != "awaiting_approval":
        raise HTTPException(409, f"run is {run['status']}, not awaiting approval")
    gate = rt.store.pending_gate(rid)
    if gate and user["role"] not in gate[1].get("roles", ["approver", "admin"]):
        raise HTTPException(403, f"this gate requires one of roles {gate[1]['roles']}")


@app.post("/runs/{rid}/approve", tags=["approvals"], status_code=202)
def approve(rid: str, req: DecisionRequest, wait: bool = False, user=Depends(approver_user)):
    """Approve the pending gate: the run continues (re-enqueued, or executed inline with wait=true)."""
    _gate_check(rid, user)
    try:
        return rt.approve(rid, user["name"], req.comment, req.data, wait)
    except AgentError as e:
        raise _bad(e, 409)


@app.post("/runs/{rid}/reject", tags=["approvals"])
def reject(rid: str, req: DecisionRequest, user=Depends(approver_user)):
    """Reject the pending gate: the run ends with status rejected (terminal)."""
    _gate_check(rid, user)
    try:
        return rt.reject(rid, user["name"], req.comment)
    except AgentError as e:
        raise _bad(e, 409)


@app.get("/approvals", tags=["approvals"])
def approvals(user=Depends(current_user)):
    """Runs waiting for a human decision, with the gate payload."""
    out = []
    for r in rt.store.list_runs(200, status="awaiting_approval", enterprise=user["enterprise"]):
        gate = rt.store.pending_gate(r["id"])
        if gate:
            out.append({**r, "step": gate[0], "title": gate[1].get("title"), "roles": gate[1].get("roles"),
                        "requested_at": gate[1].get("requested_at"), "delegated": gate[1].get("delegated", False)})
    return out


# ---- artifacts ------------------------------------------------------------------------------------
@app.get("/artifacts", tags=["artifacts"])
def artifacts(kind: str | None = None, run_id: str | None = None, include_body: bool = True, limit: int = 100,
              user=Depends(current_user)):
    return rt.store.artifacts(kind, user["enterprise"], run_id, include_body, limit)


@app.get("/artifacts/{aid}", tags=["artifacts"])
def get_artifact(aid: int, user=Depends(current_user)):
    a = rt.store.get_artifact(aid, user["enterprise"])
    if not a:
        raise HTTPException(404, "artifact not found")
    return a


@app.get("/artifacts/{aid}/download", tags=["artifacts"])
def download_artifact(aid: int, user=Depends(current_user)):
    a = rt.store.get_artifact(aid, user["enterprise"])
    if not a:
        raise HTTPException(404, "artifact not found")
    return Response(json.dumps(a["body"], indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{a["kind"]}-v{a["version"]}.json"'})


@app.get("/artifacts/{aid}/files", tags=["artifacts"])
def artifact_files(aid: int, user=Depends(current_user)):
    """Files this artifact stored in the object store (landed data, packages), from its `uri`/`files` metadata."""
    a = rt.store.get_artifact(aid, user["enterprise"])
    if not a:
        raise HTTPException(404, "artifact not found")
    body = a.get("body") or {}
    return {"uri": a.get("uri"), "files": body.get("files") or [t.get("uri") for t in body.get("tables", []) if t.get("uri")]}


DEFAULT_CASES = [{
    "name": "ussfcu-compliance-dashboard",
    "input": {"prd": (settings.schema_catalog_dir.parent / "prd.txt").read_text()
              if (settings.schema_catalog_dir.parent / "prd.txt").exists() else "USSFCU Compliance Dashboard PRD",
              "schemas": ["loan_application", "member", "fair_lending_snapshot"]},
    "expect": {"tables": ["loan_application", "member"],
               "columns": {"loan_application": ["id", "product_type", "status"]},
               "lineage": {"loan_application": "core_banking"}},
}]
