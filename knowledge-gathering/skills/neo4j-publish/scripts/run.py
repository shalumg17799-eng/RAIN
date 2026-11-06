import re
from collections import Counter

from dif.config import settings

LABEL = re.compile(r"^[A-Za-z]+$")
REL_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _default_driver_factory(uri, user, password):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(uri, auth=(user, password))


_driver_factory = _default_driver_factory  # tests inject a fake: callable(uri, user, password) -> driver with .session()


def _labels(labels):
    labels = [str(l) for l in (labels or [])]
    bad = [l for l in labels if not LABEL.match(l)]
    if bad or not labels:
        raise ValueError(f"invalid node labels {labels}: letters only, at least one")
    return ":".join(labels)


def counts(nodes, relationships):
    return {"nodes": len(nodes), "relationships": len(relationships),
            "by_label": dict(sorted(Counter(":".join(str(l) for l in n.get("labels") or []) for n in nodes).items())),
            "by_type": dict(sorted(Counter(r.get("type") for r in relationships).items()))}


def node_statements(nodes, enterprise, release):
    """[(cypher, rows)] grouped by label set; Enterprise nodes merge on (key, enterprise_id, release), Platform on key."""
    groups = {}
    for n in nodes:
        props = dict(n.get("props") or {})
        eid, rel = props.get("enterprise_id") or enterprise, props.get("release") or release
        key = _labels(n["labels"])
        if "Enterprise" in n["labels"]:
            props.update(enterprise_id=eid, release=rel)
            groups.setdefault((key, True), []).append({"key": n["key"], "enterprise_id": eid, "release": rel, "props": props})
        else:
            groups.setdefault((key, False), []).append({"key": n["key"], "props": props})
    out = []
    for (labels, scoped), rows in groups.items():
        merge = "{key: r.key, enterprise_id: r.enterprise_id, release: r.release}" if scoped else "{key: r.key}"
        out.append((f"UNWIND $rows AS r MERGE (n:{labels} {merge}) SET n += r.props", rows))
    return out


def relationship_statements(relationships, enterprise, release):
    groups = {}
    for r in relationships:
        t = str(r["type"])
        if not REL_TYPE.match(t):
            raise ValueError(f"invalid relationship type '{t}'")
        groups.setdefault(t, []).append({"from": r["from"], "to": r["to"], "props": dict(r.get("props") or {}),
                                         "enterprise_id": enterprise, "release": release})
    return [(f"UNWIND $rows AS r "
             f"MATCH (a {{key: r.from}}) WHERE a:Platform OR (a.enterprise_id = r.enterprise_id AND a.release = r.release) "
             f"MATCH (b {{key: r.to}}) WHERE b:Platform OR (b.enterprise_id = r.enterprise_id AND b.release = r.release) "
             f"MERGE (a)-[rel:{t}]->(b) SET rel += r.props", rows) for t, rows in groups.items()]


def _batches(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def run(inp, ctx):
    nodes, rels, release = inp["nodes"], inp["relationships"], str(inp["release"])
    if not isinstance(nodes, list) or not isinstance(rels, list):
        raise ValueError("nodes and relationships must be lists of records")
    ctx = ctx or {}
    enterprise = inp.get("enterprise") or ctx.get("enterprise") or "default"
    batch = max(1, int(inp.get("batch_size", 500)))
    statements = node_statements(nodes, enterprise, release) + relationship_statements(rels, enterprise, release)  # validates labels/types
    out = {"published": False, "release": release, "enterprise_id": enterprise, "counts": counts(nodes, rels), "dry_run": bool(ctx.get("dry_run"))}
    if ctx.get("dry_run"):
        return {**out, "note": "dry run: nothing written to Neo4j"}
    if not settings.neo4j_uri:
        return {**out, "note": "DIF_NEO4J_URI not configured: records computed but not written"}

    driver = _driver_factory(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        with driver.session() as session:
            for cypher, rows in statements:
                for rows_batch in _batches(rows, batch):
                    session.run(cypher, rows=rows_batch)
    finally:
        if hasattr(driver, "close"):
            driver.close()
    return {**out, "published": True, "statements": len(statements)}
