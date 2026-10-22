"""Publish a PRD run's REVIEWED ontology into the knowledge graph (KAG).

    python -m insights.prd.publish_kag                      # artifacts/rain-prd-run -> env KAG
    python -m insights.prd.publish_kag --database rain-kag  # a specific Neo4j database
    python -m insights.prd.publish_kag --dry-run            # show what would be written

This is the human-gated last mile of the PRD pipeline: the data-pack agents DESIGN the ontology
(upper-ontology.json + lower-ontology.json) but never touch a live system; an operator publishes
it, and only when the run's own audit is clean — any unmapped concept or invalid edge refuses the
publish (override consciously with --force). Publishing writes exactly the shape the NLQ
retrieval reads (insights/catalog/kag_neo4j.py):

    (:Concept {name, synonyms, definition})-[:MAPS_TO]->(:Entity {table, schema})
    (:Entity)-[:HAS_ATTRIBUTE]->(:Attribute {name, type, position, is_primary_key})
    (:Entity)-[:REFERENCES {from_column, to_column}]->(:Entity)
    plus (:Persona)-[:SERVES]->(:Concept) as Data-Factory hints (never access authority).

Every write is a MERGE keyed on stable identities and stamped with the publishing run id, so
re-publishing a newer run updates in place. Entitlements are enforced at RETRIEVAL time by the
app profile — the graph itself is metadata and carries no rows.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS = ROOT / "artifacts" / "rain-prd-run"


class PublishRefused(ValueError):
    """The run's audit has unresolved flags; a human must look before this ships."""


@dataclass(frozen=True)
class GraphRows:
    """The typed, deduplicated rows a publish writes. Pure data: unit-testable without Neo4j."""

    entities: list[dict] = field(default_factory=list)
    attributes: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    concepts: list[dict] = field(default_factory=list)
    maps_to: list[dict] = field(default_factory=list)
    personas: list[dict] = field(default_factory=list)
    serves: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "entities": len(self.entities),
            "attributes": len(self.attributes),
            "references": len(self.references),
            "concepts": len(self.concepts),
            "maps_to": len(self.maps_to),
            "personas": len(self.personas),
            "serves": len(self.serves),
        }


def assert_audit_clean(audit: dict) -> None:
    unmapped = audit.get("unmapped_concepts") or []
    invalid = audit.get("invalid_edge_references") or []
    if unmapped or invalid:
        raise PublishRefused(
            f"the ontology audit flags {len(unmapped)} unmapped concept(s) and "
            f"{len(invalid)} invalid edge reference(s); review them (ontology-audit.json) "
            "or publish consciously with --force"
        )


def build_graph_rows(upper: dict, lower: dict, *, schema: str = "public") -> GraphRows:
    """Transform the PRD's ontology artifacts into the KAG's retrieval shape."""
    rows = GraphRows()

    lower_nodes = {n["id"]: n for n in lower.get("nodes") or []}
    entity_table = {
        nid: n["name"] for nid, n in lower_nodes.items() if n.get("kind") == "Entity"
    }
    for nid, n in lower_nodes.items():
        if n.get("kind") != "Entity":
            continue
        rows.entities.append({
            "table": n["name"],
            "schema": schema,
            "grain": n.get("grain") or "",
            "source_system": n.get("source_system") or "",
        })

    position: dict[str, int] = {}
    for edge in lower.get("edges") or []:
        if edge.get("type") == "HAS_ATTRIBUTE":
            table = entity_table.get(edge.get("from"))
            attr = lower_nodes.get(edge.get("to"))
            if not table or not attr:
                continue
            position[table] = position.get(table, 0) + 1
            pk = lower_nodes[edge["from"]].get("primary_key")
            rows.attributes.append({
                "table": table,
                "name": attr["name"],
                "type": attr.get("data_type") or "unknown",
                "position": position[table],
                "is_primary_key": bool(pk) and attr["name"] == pk,
            })
        elif edge.get("type") == "REFERENCES":
            left = entity_table.get(edge.get("from"))
            right = entity_table.get(edge.get("to"))
            if not left or not right or not edge.get("from_column") or not edge.get("to_column"):
                continue
            rows.references.append({
                "from_table": left,
                "to_table": right,
                "from_column": edge["from_column"],
                "to_column": edge["to_column"],
            })

    upper_nodes = {n["id"]: n for n in upper.get("nodes") or []}
    for nid, n in upper_nodes.items():
        if n.get("kind") == "Concept":
            rows.concepts.append({
                "id": nid,
                "name": n["name"],
                "definition": n.get("definition") or "",
                "synonyms": list(n.get("synonyms") or []),
            })
        elif n.get("kind") == "Persona":
            rows.personas.append({
                "id": nid,
                "persona_id": n.get("persona_id") or nid,
                "name": n.get("name") or nid,
                "role": n.get("role") or "",
            })

    for edge in upper.get("edges") or []:
        if edge.get("type") == "MAPS_TO":
            concept = upper_nodes.get(edge.get("from"), {})
            table = entity_table.get(edge.get("to"))
            if concept.get("kind") == "Concept" and table:
                rows.maps_to.append({"concept": concept["name"], "table": table})
        elif edge.get("type") == "SERVES":
            persona = upper_nodes.get(edge.get("from"), {})
            concept = upper_nodes.get(edge.get("to"), {})
            if persona.get("kind") == "Persona" and concept.get("kind") == "Concept":
                rows.serves.append({"persona": persona.get("name"), "concept": concept["name"]})
    return rows


def publish(rows: GraphRows, *, uri: str, user: str, password: str, database: str,
            run_id: str) -> None:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            def run(query: str, **params) -> None:
                session.run(query, **params).consume()

            for e in rows.entities:
                run(
                    "MERGE (x:Entity {table: $table}) "
                    "SET x.schema = $schema, x.grain = $grain, x.source_system = $source_system, "
                    "    x.published_from = 'prd', x.prd_run_id = $run_id",
                    **e, run_id=run_id,
                )
            for a in rows.attributes:
                run(
                    "MATCH (e:Entity {table: $table}) "
                    "MERGE (e)-[:HAS_ATTRIBUTE]->(x:Attribute {name: $name, entity: $table}) "
                    "SET x.type = $type, x.position = $position, "
                    "    x.is_primary_key = $is_primary_key, x.published_from = 'prd'",
                    **a,
                )
            for r in rows.references:
                run(
                    "MATCH (a:Entity {table: $from_table}), (b:Entity {table: $to_table}) "
                    "MERGE (a)-[x:REFERENCES {from_column: $from_column, to_column: $to_column}]"
                    "->(b)",
                    **r,
                )
            for c in rows.concepts:
                run(
                    "MERGE (x:Concept {name: $name}) "
                    "SET x.definition = $definition, x.synonyms = $synonyms, "
                    "    x.published_from = 'prd', x.prd_run_id = $run_id",
                    **c, run_id=run_id,
                )
            for m in rows.maps_to:
                run(
                    "MATCH (c:Concept {name: $concept}), (e:Entity {table: $table}) "
                    "MERGE (c)-[:MAPS_TO]->(e)",
                    **m,
                )
            for p in rows.personas:
                run(
                    "MERGE (x:Persona {name: $name}) "
                    "SET x.persona_id = $persona_id, x.role = $role",
                    **p,
                )
            for s in rows.serves:
                run(
                    "MATCH (p:Persona {name: $persona}), (c:Concept {name: $concept}) "
                    "MERGE (p)-[:SERVES]->(c)",
                    **s,
                )
    finally:
        driver.close()


def main(argv=None) -> int:
    from insights.config import environment

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--uri", help="bolt URI (default: NEO4J_URI / INSIGHTS_KAG_URI from env)")
    parser.add_argument("--user", help="default: NEO4J_USER or neo4j")
    parser.add_argument("--password", help="default: NEO4J_PASSWORD from env")
    parser.add_argument("--database", help="default: NEO4J_DATABASE from env, else neo4j")
    parser.add_argument("--force", action="store_true",
                        help="publish even though the audit has unresolved flags")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    upper = json.loads((args.artifacts / "upper-ontology.json").read_text(encoding="utf-8"))
    lower = json.loads((args.artifacts / "lower-ontology.json").read_text(encoding="utf-8"))
    audit = json.loads((args.artifacts / "ontology-audit.json").read_text(encoding="utf-8"))
    report_path = args.artifacts / "run-report.json"
    run_id = ""
    if report_path.is_file():
        run_id = json.loads(report_path.read_text(encoding="utf-8")).get("run_id") or ""

    if not args.force:
        assert_audit_clean(audit)
    else:
        print("WARNING: --force publish despite audit flags", file=sys.stderr)

    rows = build_graph_rows(upper, lower)
    print(f"publishing PRD run {run_id or '?'} ontology:",
          ", ".join(f"{k}={v}" for k, v in rows.counts().items()))
    if args.dry_run:
        print("dry run - nothing written")
        return 0

    env = environment(ROOT / "rain-api" / ".env")
    uri = args.uri or env.get("NEO4J_URI") or env.get("INSIGHTS_KAG_URI") or "bolt://127.0.0.1:7687"
    user = args.user or env.get("NEO4J_USER") or "neo4j"
    password = args.password or env.get("NEO4J_PASSWORD") or ""
    database = args.database or env.get("NEO4J_DATABASE") or "neo4j"
    publish(rows, uri=uri, user=user, password=password, database=database, run_id=run_id)
    print(f"published to {uri} database {database!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
