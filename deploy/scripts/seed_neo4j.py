"""Seed the docker Neo4j with the RAIN knowledge graph from rain-neo4j-graph/*.cypher.

Idempotent one-shot: waits for Neo4j, skips when the graph already holds the personas, else runs
the loader cypher files in dependency order. Runs inside the backend image (the repo and the
neo4j driver are both there):   python deploy/scripts/seed_neo4j.py
"""

import os
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
GRAPH_DIR = ROOT / "rain-neo4j-graph"

# build_graph first (the base ontology), then the persona graph and its extensions.
CYPHER_FILES = [
    "build_graph.cypher",
    "build_persona_graph.cypher",
    "add_facility_mapping.cypher",
    "add_transport_mapping.cypher",
    "add_risk_signal_mappings.cypher",
    "add_david_ontology_extension.cypher",
    "add_cached_questions.cypher",
]


def statements(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    code = "".join(l for l in lines if l.strip() and not l.strip().startswith("//"))
    return [s.strip().rstrip(";").strip() for s in code.split(";\n") if s.strip()]


def main() -> int:
    uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "password"))
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    driver = GraphDatabase.driver(uri, auth=auth)

    deadline = time.monotonic() + 180
    while True:
        try:
            driver.verify_connectivity()
            break
        except Exception as exc:
            if time.monotonic() > deadline:
                print(f"neo4j never became ready: {type(exc).__name__}", file=sys.stderr)
                return 1
            time.sleep(2)

    with driver.session(database=database) as session:
        personas = session.run("MATCH (p:Persona) RETURN count(p) AS c").single()["c"]
        if personas >= 5:
            print(f"graph already seeded ({personas} personas) - nothing to do")
            return 0
        total = 0
        for name in CYPHER_FILES:
            path = GRAPH_DIR / name
            if not path.is_file():
                print(f"skipping missing {name}", file=sys.stderr)
                continue
            ran = 0
            for statement in statements(path):
                session.run(statement).consume()
                ran += 1
            total += ran
            print(f"{name}: {ran} statements")
        counts = session.run(
            "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC"
        ).data()
        print(f"seeded {total} statements; nodes:",
              ", ".join(f"{r['l']}={r['c']}" for r in counts))
    driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
