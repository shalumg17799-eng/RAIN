"""Agent 5 (QA & release) tools.

verify mode : conformance verdict, security checks, smoke test, findings.
release mode: deployment kit (Dockerfile, Bicep, script), Azure deploy (only
              after gate C is approved), release notes."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import yaml
from psycopg import sql as psql

from factory.apppack import now
from factory.conformance import evaluate, markdown
from factory.config import ROOT, schema_for
from factory.tools import RunContext, tool
from factory.tools.db import connect
from factory.tools.knowledge import role_id

TEMPLATES = ROOT / "factory" / "deploy_templates"


@tool("run_conformance", "Compute the PRD conformance verdict: every KPI, signal headline and signal "
      "sub-figure in the manifest against the metric layer. Writes reports/conformance.{json,md}. Returns the "
      "totals and every figure that is not a live match.", {})
def run_conformance(ctx: RunContext):
    # Recompute every metric now, so the verdict reflects the data as loaded, not cached values.
    from factory.apppack import Metrics
    from factory.tools.db import scalar
    metrics = ctx.pack.metrics()
    fresh = []
    for m in metrics.metrics:
        if m.sql:
            try:
                m = m.model_copy(update={"value": scalar(ctx.pack.app_id, m.sql), "computed_at": now()})
            except Exception as exc:
                m = m.model_copy(update={"value": None, "note": f"ERROR: {str(exc).splitlines()[0][:200]}"})
        fresh.append(m)
    ctx.pack.save_metrics(Metrics(metrics=fresh))
    report = evaluate(ctx.pack)
    ctx.pack.write_json("reports/conformance.json", report)
    ctx.pack.path("reports", "conformance.md").write_text(markdown(report, ctx.pack.manifest().app.name), encoding="utf-8")
    problems = [{k: r[k] for k in ("id", "kind", "label", "prd", "served", "status", "sql", "note")}
                for r in report["rows"] if r["status"] in ("mismatch", "missing", "static")]
    return {k: report[k] for k in ("total_checkable", "matched", "static", "rate", "rate_with_static", "by_kind")} | \
        {"not_live_matches": problems}


@tool("run_security_checks", "Check the governed AI layer against the database itself, per persona role: "
      "tables the role was not granted are refused, no write privilege exists, and row-level filters return "
      "nothing when the persona's scope attributes are absent. Writes reports/security.json.", {})
def run_security_checks(ctx: RunContext):
    app_id, schema = ctx.pack.app_id, schema_for(ctx.pack.app_id)
    profile = yaml.safe_load(ctx.pack.path("insights", app_id, "app.yaml").read_text(encoding="utf-8"))
    keys = yaml.safe_load(ctx.pack.path("insights", "keys.local.yaml").read_text(encoding="utf-8"))["keys"]
    with connect() as conn:
        all_tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (schema,)).fetchall()]
    results, failures = {}, 0
    for role, spec in profile["roles"].items():
        pg_role = f"insights_{role}"
        granted = set(spec["tables"])
        attrs = next((k.get("attributes", {}) for k in keys if role in k["roles"]), {})
        checks = []
        # autocommit: each `with conn.transaction()` is a real transaction, so SET LOCAL ROLE ends with it
        # (inside an outer transaction a savepoint would leave the role in force for later checks).
        with connect(autocommit=True) as conn:
            for table in all_tables:
                priv = conn.execute("SELECT has_table_privilege(%s, %s, 'INSERT') OR "
                                    "has_table_privilege(%s, %s, 'UPDATE') OR has_table_privilege(%s, %s, 'DELETE')",
                                    (pg_role, f"{schema}.{table}") * 3).fetchone()[0]
                checks.append({"check": f"no write on {table}", "passed": not priv})
                if table not in granted:
                    try:
                        with conn.transaction():
                            conn.execute(psql.SQL("SET LOCAL ROLE {}").format(psql.Identifier(pg_role)))
                            conn.execute(psql.SQL("SELECT 1 FROM {} LIMIT 1").format(psql.Identifier(schema, table)))
                        checks.append({"check": f"{table} refused (not granted)", "passed": False})
                    except Exception:
                        checks.append({"check": f"{table} refused (not granted)", "passed": True})
            for table, tspec in spec["tables"].items():
                if not tspec.get("row_filter"):
                    continue
                counts = {}
                for label, with_attrs in (("with_scope", True), ("without_scope", False)):
                    with conn.transaction():
                        conn.execute(psql.SQL("SET LOCAL ROLE {}").format(psql.Identifier(pg_role)))
                        if with_attrs:
                            for k, v in attrs.items():
                                conn.execute("SELECT set_config(%s, %s, true)", (f"insights.{k}", v))
                        counts[label] = conn.execute(psql.SQL("SELECT COUNT(*) FROM {}").format(
                            psql.Identifier(schema, table))).fetchone()[0]
                total = conn.execute(psql.SQL("SELECT COUNT(*) FROM {}").format(psql.Identifier(schema, table))).fetchone()[0]
                checks.append({"check": f"row filter on {table}", "passed": counts["without_scope"] == 0,
                               "rows_total": total, **counts})
        failures += sum(1 for c in checks if not c["passed"])
        results[role] = checks
    report = {"checked_at": now(), "failures": failures, "roles": results}
    ctx.pack.write_json("reports/security.json", report)
    summary = {role: f"{sum(c['passed'] for c in cs)}/{len(cs)} passed" for role, cs in results.items()}
    return {"failures": failures, "summary": summary,
            "failed": [f"{r}: {c['check']}" for r, cs in results.items() for c in cs if not c["passed"]][:30],
            "row_filters": {r: [c for c in cs if c["check"].startswith("row filter")] for r, cs in results.items()}}


@tool("smoke_test_ask", "Ask the running app one question per persona through the governed AI layer (real "
      "model calls). Use a question from that persona's suggested list whose answer is a PRD figure. Returns "
      "status, narrative and SQL per question; writes reports/smoke.json.",
      {"questions": {"type": "object", "description": "{persona_id: question}"}}, ["questions"])
def smoke_test_ask(ctx: RunContext, questions: dict):
    from fastapi.testclient import TestClient
    from factory.runtime_app.server import create_app
    client = TestClient(create_app(ctx.pack.app_id, enable_ask=True))
    out = {}
    for persona, q in questions.items():
        r = client.post("/api/ask", json={"persona": persona, "question": q})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": r.text}
        out[persona] = {"question": q, "http": r.status_code, "status": body.get("status"),
                        "narrative": body.get("narrative") or body.get("reason") or body.get("detail"),
                        "rows": (body.get("data") or {}).get("rows", [])[:3], "sql": body.get("sql")}
    ctx.pack.write_json("reports/smoke.json", out)
    return out


@tool("record_findings",
      "Classify every figure that is not a live match, so the coordinator can route the work back: "
      "cause = data (the loaded data cannot produce the PRD figure: agent 2 recalibrates), metric (the SQL "
      "definition is wrong: agent 3 fixes it), prd (the PRD is ambiguous or contradicts itself: human decides), "
      "static_ok (a fixed PRD value with no data source, acceptable as static). Give evidence for each.",
      {"findings": {"type": "array", "items": {"type": "object", "properties": {
          "id": {"type": "string"}, "cause": {"type": "string", "enum": ["data", "metric", "prd", "static_ok"]},
          "evidence": {"type": "string"}, "suggested_fix": {"type": "string"}},
          "required": ["id", "cause", "evidence"]}}},
      ["findings"])
def record_findings(ctx: RunContext, findings: list[dict]):
    ctx.pack.write_json("reports/findings.json", {"recorded_at": now(), "findings": findings})
    by = {}
    for f in findings:
        by[f["cause"]] = by.get(f["cause"], 0) + 1
    return {"recorded": len(findings), "by_cause": by}


@tool("prepare_deployment", "Write the Azure deployment kit for this app into deploy/: Dockerfile, "
      ".dockerignore, Bicep template (Container Apps environment, runtime app, provisioning job, PostgreSQL "
      "Flexible Server, Log Analytics), parameters file and deploy script.", {})
def prepare_deployment(ctx: RunContext):
    app_id = ctx.pack.app_id
    out = ctx.pack.path("deploy")
    written = []
    for src in TEMPLATES.iterdir():
        text = src.read_text(encoding="utf-8").replace("__APP_ID__", app_id).replace("__APP_DASH__", app_id.replace("_", "-"))
        (out / src.name).write_text(text, encoding="utf-8")
        written.append(f"deploy/{src.name}")
    access = ctx.pack.path("access.yaml")
    if not access.is_file():
        personas = [p.id for p in ctx.pack.manifest().personas]
        lines = ["# Entra ID group (or app role) object ids allowed to use each persona view.",
                 "# Used when the app is deployed with sign-in (FACTORY_AUTH=entra). Empty = nobody."]
        lines += [f"{p}: []" for p in personas]
        access.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append("access.yaml")
    return {"written": written, "az_cli_available": shutil.which("az") is not None}


@tool("deploy_to_azure", "Deploy to Azure with deploy/deploy.sh (or deploy.ps1 on Windows). Only runs after gate C is approved and when "
      "the Azure CLI is installed and signed in, with AZURE_SUBSCRIPTION_ID, AZURE_LOCATION and "
      "AZURE_RESOURCE_GROUP set. Otherwise returns why it was skipped.", {})
def deploy_to_azure(ctx: RunContext):
    if "C" not in ctx.approved_gates:
        return {"skipped": "gate C (conformance review) has not been approved"}
    if shutil.which("az") is None:
        return {"skipped": "Azure CLI (az) is not installed on this machine"}
    missing = [v for v in ("AZURE_SUBSCRIPTION_ID", "AZURE_LOCATION", "AZURE_RESOURCE_GROUP", "AZURE_ACR_NAME",
                           "PG_ADMIN_PASSWORD", "ANTHROPIC_API_KEY") if not os.environ.get(v)]
    if missing:
        return {"skipped": f"set {', '.join(missing)}"}
    if shutil.which("bash") and os.name != "nt":
        cmd = ["bash", str(ctx.pack.path("deploy", "deploy.sh"))]
    else:
        cmd = ["pwsh" if shutil.which("pwsh") else "powershell", "-NoProfile", "-File", str(ctx.pack.path("deploy", "deploy.ps1"))]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
    ctx.pack.path("reports", "deploy.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return {"exit_code": proc.returncode, "tail": (proc.stdout + proc.stderr)[-3000:]}


@tool("write_release_notes", "Write reports/release.md: what was built, conformance and security results, "
      "anything static or unresolved, how to run it locally, and the deployment status.",
      {"markdown": {"type": "string"}}, ["markdown"])
def write_release_notes(ctx: RunContext, markdown: str):
    ctx.pack.path("reports", "release.md").write_text(markdown, encoding="utf-8")
    return {"written": "reports/release.md"}
