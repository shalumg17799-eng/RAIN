from dif.config import settings

SCOPE = "{enterprise_id: $enterprise_id, release: $release}"
QUERIES = [
    ("release_present", "error", f"MATCH (n:Enterprise {SCOPE}) RETURN count(n) AS c", "release has no Enterprise nodes", True),
    ("orphan_nodes", "error", f"MATCH (n:Enterprise {SCOPE}) WHERE NOT (n)--() RETURN count(n) AS c", "orphan Enterprise node(s)", False),
    ("classes_aligned", "warning", f"MATCH (n:Enterprise:Class {SCOPE}) WHERE NOT (n)-[:ALIGNS_TO]->() RETURN count(n) AS c",
     "Class node(s) without ALIGNS_TO", False),
    ("tables_mapped", "warning", f"MATCH (n:Enterprise:Table {SCOPE}) WHERE NOT ()-[:MAPS_TO]->(n) RETURN count(n) AS c",
     "Table node(s) without MAPS_TO", False),
    ("provenance_present", "error", f"MATCH (n:Enterprise {SCOPE}) WHERE n.provenance IS NULL OR size(n.provenance) = 0 RETURN count(n) AS c",
     "Enterprise node(s) without provenance", False),
]


def _default_driver_factory(uri, user, password):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(uri, auth=(user, password))


_driver_factory = _default_driver_factory


def _report(findings):
    """findings: [(name, severity, count, message, subjects)] -> output."""
    issues, checks = [], []
    for name, severity, count, message, subjects in findings:
        ok = count == 0
        checks.append({"name": name, "passed": ok or severity != "error", "detail": "ok" if ok else f"{count} {message}"})
        if not ok:
            issues.append({"severity": severity, "message": f"{count} {message}", "count": count, "subjects": subjects[:20]})
    return {"passed": all(c["passed"] for c in checks), "issues": issues, "checks": checks}


def validate_records(nodes, relationships, enterprise, release):
    ent = {n["key"]: n for n in nodes if "Enterprise" in (n.get("labels") or [])
           and (n.get("props") or {}).get("enterprise_id", enterprise) == enterprise and (n.get("props") or {}).get("release", release) == release}
    touched = {r["from"] for r in relationships} | {r["to"] for r in relationships}
    aligned = {r["from"] for r in relationships if r["type"] == "ALIGNS_TO"}
    mapped = {r["to"] for r in relationships if r["type"] == "MAPS_TO"}
    orphans = sorted(k for k in ent if k not in touched)
    unaligned = sorted(k for k, n in ent.items() if "Class" in n["labels"] and k not in aligned)
    unmapped = sorted(k for k, n in ent.items() if "Table" in n["labels"] and k not in mapped)
    no_prov = sorted(k for k, n in ent.items() if not (n.get("props") or {}).get("provenance"))
    return _report([("release_present", "error", 0 if ent else 1, "release has no Enterprise nodes", []),
                    ("orphan_nodes", "error", len(orphans), "orphan Enterprise node(s)", orphans),
                    ("classes_aligned", "warning", len(unaligned), "Class node(s) without ALIGNS_TO", unaligned),
                    ("tables_mapped", "warning", len(unmapped), "Table node(s) without MAPS_TO", unmapped),
                    ("provenance_present", "error", len(no_prov), "Enterprise node(s) without provenance", no_prov)])


def validate_graph(enterprise, release):
    driver = _driver_factory(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    findings = []
    try:
        with driver.session() as session:
            for name, severity, cypher, message, invert in QUERIES:
                rec = session.run(cypher, enterprise_id=enterprise, release=release).single()
                c = int(rec["c"] if rec is not None else 0)
                findings.append((name, severity, (0 if c else 1) if invert else c, message, []))
    finally:
        if hasattr(driver, "close"):
            driver.close()
    return _report(findings)


def run(inp, ctx):
    ctx = ctx or {}
    release = str(inp["release"])
    enterprise = inp.get("enterprise") or ctx.get("enterprise") or "default"
    if settings.neo4j_uri and not ctx.get("dry_run") and not inp.get("in_memory"):
        return {**validate_graph(enterprise, release), "mode": "graph", "release": release}
    nodes, rels = inp.get("nodes"), inp.get("relationships")
    if not isinstance(nodes, list) or not isinstance(rels, list):
        return {"passed": False, "mode": "memory", "release": release,
                "issues": [{"severity": "error", "count": 1, "message": "no Neo4j driver configured and no in-memory records to validate"}],
                "checks": [{"name": "records_available", "passed": False, "detail": "pass nodes/relationships or set DIF_NEO4J_URI"}]}
    return {**validate_records(nodes, rels, enterprise, release), "mode": "memory", "release": release}
