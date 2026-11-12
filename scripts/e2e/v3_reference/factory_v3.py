"""Run the DIF build-time factory on the PRD v0.3 inputs (no gates, no LLM, KAG write deferred).

Runs inside a container with the repo mounted at /app. DIF_DATABASE_URL must point at a local
(non bind-mounted) sqlite file; the artifact store defaults to /app/.data/artifacts.
Writes the kag-builder map output to /app/artifacts/rain-v3-kag-records.json for publishing.
"""
import json
import shutil
import time
from pathlib import Path

from dif.config import ROOT, settings
from dif.runtime.factory import build_runtime

PRD = ROOT / "doc/prd/RAIN_Prototype_Spec_v2_factory_extract.txt"
DDL = ROOT / "doc/prd/RAIN_Prototype_Spec_v2_planned_schemas.sql"
print("db:", settings.database_url, "| artifacts:", settings.artifact_store, "| llm:", settings.llm_provider)

rt = build_runtime("local")
t0 = time.time()
run = rt.start("dif-build-orchestrator", {
    "prd": PRD.read_text(encoding="utf-8"), "schemas": [DDL.read_text(encoding="utf-8")],
    "release": "rain-v3.0.0", "package_version": "3.0.0",
    "rows_per_table": 10, "seed": 7, "auto_approve": True, "overwrite": True,
}, enterprise="rain", by="claude-e2e")
print(f"orchestrator: {run['status']} in {time.time() - t0:.1f}s", run.get("error") or "")

out = run.get("output") or {}
for k in ("scenario", "data_status", "kag_release", "kag_published", "readiness", "package_version", "package_uri"):
    print(f"  {k}: {out.get(k)}")
for k in ("tables", "entities", "ontology_classes", "alignment", "package_files"):
    v = out.get(k)
    print(f"  {k}: {len(v) if isinstance(v, (list, dict)) else v}")
print("  acceptance passed:", (run.get("state") or {}).get("acceptance", {}).get("passed"))
gaps = {k: v for k, v in out.items() if "gap" in k or "unmapped" in k or "missing" in k}
if gaps:
    print("  gaps:", json.dumps(gaps)[:800])

children = rt.store.list_runs(100, parent=run["id"])
for c in sorted(children, key=lambda c: c["created_at"]):
    print(f"  child {c['agent']:34s} {c['status']}")

kag = next(c for c in children if c["agent"] == "kag-builder-agent")
steps = rt.store.get_run(kag["id"])["state"]["steps"]
m = steps["map"]["output"]
pre = steps.get("precheck", {}).get("output", {})
print(f"kag map: {len(m['nodes'])} nodes / {len(m['relationships'])} relationships;"
      f" release={m.get('release')} enterprise={m.get('enterprise_id')}; precheck passed={pre.get('passed')}")
for issue in (pre.get("issues") or [])[:10]:
    print("   precheck issue:", issue)

dst = ROOT / "artifacts"
dst.mkdir(exist_ok=True)
(dst / "rain-v3-kag-records.json").write_text(json.dumps(
    {"release": m["release"], "enterprise_id": m["enterprise_id"],
     "nodes": m["nodes"], "relationships": m["relationships"]}), encoding="utf-8")

pkg = ROOT / ".data/artifacts/packages/rain/3.0.0"
if pkg.is_dir():
    visible = dst / "RAIN_Knowledge_Package_v3.0.0"
    shutil.rmtree(visible, ignore_errors=True)
    shutil.copytree(pkg, visible)
    print("package files:", sorted(p.name for p in visible.iterdir()))
