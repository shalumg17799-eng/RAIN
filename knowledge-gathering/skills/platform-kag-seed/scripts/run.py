import importlib.util
import json
from pathlib import Path

from dif.config import settings

PUBLISH = Path(__file__).resolve().parents[2] / "neo4j-publish" / "scripts" / "run.py"
ENTERPRISE = "platform"


def _publish():
    spec = importlib.util.spec_from_file_location("skill_neo4j_publish_embedded", PUBLISH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run


def load_upper_ontology(spec=None):
    if isinstance(spec, dict) and spec.get("concepts"):
        return spec
    return json.loads((settings.platform_dir / "ontology" / "upper-ontology.v1.json").read_text())


def records(upper, skills=None, agents=None):
    release = f"platform-{upper.get('version', '1.0.0')}"
    nodes, rels = [], []
    ids = {c["id"] for c in upper.get("concepts", [])}
    for c in upper.get("concepts", []):
        nodes.append({"key": f"concept:{c['id']}", "labels": ["Platform", "Concept"],
                      "props": {"concept_id": c["id"], "name": c.get("name", c["id"]), "description": c.get("description"),
                                "keywords": list(c.get("keywords") or []), "release": release}})
        if c.get("parent") in ids:
            rels.append({"type": "SUBCLASS_OF", "from": f"concept:{c['id']}", "to": f"concept:{c['parent']}", "props": {}})
    for r in upper.get("relations", []):
        nodes.append({"key": f"relation:{r['id']}", "labels": ["Platform", "Relation"],
                      "props": {"relation_id": r["id"], "name": r.get("name", r["id"]), "release": release}})
        for end, t in (("domain", "HAS_DOMAIN"), ("range", "HAS_RANGE")):
            if r.get(end) in ids:
                rels.append({"type": t, "from": f"relation:{r['id']}", "to": f"concept:{r[end]}", "props": {}})
    for kind, label, items in (("skill", "Skill", skills or []), ("agent", "Agent", agents or [])):
        for s in items:
            nodes.append({"key": f"{kind}:{s['name']}@{s.get('version', '')}", "labels": ["Platform", label],
                          "props": {"name": s["name"], "version": str(s.get("version", "")), "description": s.get("description"),
                                    "steps": [str(x) for x in s.get("steps") or []], "release": release}})
    nodes.append({"key": f"release:{release}", "labels": ["Platform", "Release"],
                  "props": {"name": release, "upper_ontology": upper.get("name"), "version": str(upper.get("version", "1.0.0"))}})
    rels += [{"type": "CONTAINS", "from": f"release:{release}", "to": f"concept:{c['id']}", "props": {}} for c in upper.get("concepts", [])]
    return release, nodes, rels


def registry_items(ctx):
    """Shared skills and enabled agents of the running platform (enterprise overrides are tenant data, not platform)."""
    reg = (ctx or {}).get("registry") or {}
    skills = [s for s in reg["skills"].list() if not s.get("enterprise")] if reg.get("skills") else []
    agents = [a for a in reg["agents"].list() if a.get("enabled", True)] if reg.get("agents") else []
    return skills, agents


def run(inp, ctx):
    upper = load_upper_ontology(inp.get("upper_ontology"))
    skills, agents = inp.get("skills"), inp.get("agents")
    if skills is None and agents is None and inp.get("include_registry") is not False:   # agents pass null for omitted inputs
        skills, agents = registry_items(ctx)
    release, nodes, rels = records(upper, skills, agents)
    out = _publish()({"nodes": nodes, "relationships": rels, "release": release, "enterprise": ENTERPRISE,
                      "batch_size": inp.get("batch_size") or 500}, ctx)
    return {**out, "release": release, "nodes": nodes, "relationships": rels}
