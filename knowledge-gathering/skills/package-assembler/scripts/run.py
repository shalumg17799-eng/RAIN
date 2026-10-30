import hashlib
import json
import time

import yaml

FILES = (("requirements.json", "requirements", "requirements"), ("domain-model.json", "domain_model", "domain_model"),
         ("ontology/lower-ontology.json", "ontology", "lower_ontology"), ("ontology/upper-ontology-alignment.json", "alignment", "ontology_alignment"),
         ("semantic-mappings.json", "semantic_mappings", "semantic_mappings"), ("domain-catalog.json", "domain_catalog", "domain_catalog"),
         ("data-assets.json", "data_assets", "data_assets"), ("kag-release.json", "kag_release", "kag_release"),
         ("reconciliation.json", "reconciliation", "reconciliation"), ("evaluation-report.json", "evaluation_report", "evaluation_report"))


def _lineage_from_store(store, rid):
    """Agent/skill versions and persisted artifact ids of this run, its ancestors' earlier children and its children."""
    agents, skills, artifacts = {}, {}, {}
    root = rid
    while (r := store.get_run(root)) and r.get("parent_run_id"):
        root = r["parent_run_id"]
    todo = [root]
    while todo:
        r = store.get_run(todo.pop())
        if not r:
            continue
        agents[r["agent"]] = r["agent_version"]
        for e in store.history(r["id"]):
            if e["event"] == "step_started" and (e.get("detail") or {}).get("skill"):
                skills[e["detail"]["skill"]] = e["detail"].get("version")
        for a in store.artifacts(run_id=r["id"], include_body=False):
            artifacts.setdefault(a["kind"], a["id"])
        todo += [c["id"] for c in store.list_runs(200, parent=r["id"])]
    return agents, skills, artifacts


def _next_version(store, ent):
    n = len(store.artifacts("knowledge_package", ent, include_body=False, limit=10000)) if store else 0
    return f"1.0.{n + 1}"


def run(inp, ctx):
    ent = inp.get("enterprise_id") or ctx.get("enterprise")
    version = str(inp.get("package_version") or _next_version(ctx.get("store"), ent))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    docs = {}
    for path, key, _ in FILES:
        if inp.get(key) is not None:
            docs[path] = inp[key]
    dm, req = inp.get("domain_model") or {}, inp.get("requirements") or {}
    docs["business-rules.json"] = inp.get("business_rules") or {"constraints": dm.get("constraints", []), "policies": req.get("policies", [])}
    rec, sm, da = inp.get("reconciliation") or {}, inp.get("semantic_mappings") or {}, inp.get("data_assets") or {}
    docs["unresolved-gaps.json"] = {"reconciliation": rec.get("unresolved", []), "mapping_gaps": sm.get("gaps", []),
                                    "data_gaps": da.get("gaps", []), "assumptions": (dm.get("assumptions", []) + da.get("assumptions", []))}
    docs["quality-report.json"] = {"validation_reports": inp.get("validation_reports") or [],
                                   "kag_validation": (inp.get("kag_release") or {}).get("validation"),
                                   "ontology_validation": (inp.get("ontology") or {}).get("validation"),
                                   "data_profiles": {t["name"]: t.get("profile") for t in da.get("tables", []) if t.get("profile")},
                                   "reconciliation_score": rec.get("score")}
    agents, skills, artifact_ids = {}, {}, {}
    if ctx.get("store") and ctx.get("run_id"):
        agents, skills, artifact_ids = _lineage_from_store(ctx["store"], ctx["run_id"])
    agents.update(inp.get("agent_versions") or {})
    skills.update(inp.get("skill_versions") or {})
    artifact_ids.update(inp.get("artifact_ids") or {})
    docs["provenance.json"] = {"run_id": ctx.get("run_id"), "enterprise_id": ent, "artifact_ids": artifact_ids,
                               "agents": agents, "skills": skills, "created_at": now}
    readiness = rec.get("readiness") or ("ready" if not rec else "partial")
    data_status = da.get("readiness_status") or "schema_only"
    files = []
    for path, doc in docs.items():
        text = json.dumps(doc, indent=2, default=str)
        files.append({"path": path, "kind": next((k for p, _, k in FILES if p == path), path.split(".")[0].replace("-", "_")),
                      "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()), "content": text})
    manifest = {"enterprise_id": ent, "package_version": version, "created_at": now, "uri": None,
                "files": [{k: v for k, v in f.items() if k != "content"} for f in files],
                "versions": {"ontology": (inp.get("ontology") or {}).get("version"),
                             "upper_ontology": (inp.get("alignment") or {}).get("upper_ontology_version"),
                             "kag_snapshot": (inp.get("kag_release") or {}).get("release"), "agents": agents, "skills": skills},
                "artifacts": artifact_ids, "validation": {"reconciliation": rec.get("score"), "readiness": readiness},
                "readiness": readiness, "data_status": data_status}
    mtext = yaml.safe_dump(manifest, sort_keys=False)
    files.append({"path": "manifest.yaml", "kind": "manifest", "sha256": hashlib.sha256(mtext.encode()).hexdigest(),
                  "bytes": len(mtext.encode()), "content": mtext})
    return {"package_version": version, "enterprise_id": ent, "files": files, "manifest": manifest,
            "readiness": readiness, "data_status": data_status}
