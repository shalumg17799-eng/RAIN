"""Seed the docker Neo4j with the RAIN knowledge graph (KAG).

Idempotent one-shot that runs inside the backend image (the repo and the neo4j driver are both there):
    python deploy/scripts/seed_neo4j.py

PRD v0.4 (this branch): the KAG is ONE release-scoped graph (`release` property on every node), published by
scripts/e2e/kag_v4_refresh.py from what the v0.4 app has now (Postgres rain_v4, the query pack, the persona
contracts, the PRD v0.4 seed). So the seed:

- does nothing when any release-scoped node exists (the KAG is already published; re-run the refresh script
  to update it, never this seed);
- otherwise publishes the v0.4 KAG with scripts/e2e/kag_v4_refresh.py, which needs database rain_v4 in
  Postgres (PG_HOST/PG_PORT); when rain_v4 is not loaded yet it prints how to publish later and exits 0;
- never loads the old v1/v2 graph (rain-neo4j-graph/*.cypher) unless NEO4J_SEED_LEGACY=1, and even then only
  into a database with no release and fewer than 5 personas.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
GRAPH_DIR = ROOT / "rain-neo4j-graph"
REFRESH = ROOT / "scripts" / "e2e" / "kag_v4_refresh.py"

# Legacy v1/v2 graph (NEO4J_SEED_LEGACY=1 only): build_graph first (the base ontology), then the persona graph
# and its extensions.
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


def seed_legacy(session) -> None:
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
    counts = session.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC").data()
    print(f"seeded {total} statements; nodes:", ", ".join(f"{r['l']}={r['c']}" for r in counts))


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
        releases = session.run("MATCH (n) WHERE n.release IS NOT NULL RETURN n.release AS r, count(*) AS c ORDER BY r").data()
        if releases:
            print("KAG already published (" + ", ".join(f"{r['r']}: {r['c']} nodes" for r in releases)
                  + ") - nothing to do; update it with scripts/e2e/kag_v4_refresh.py")
            return 0
        personas = session.run("MATCH (p:Persona) RETURN count(p) AS c").single()["c"]
        if os.environ.get("NEO4J_SEED_LEGACY") == "1":
            if personas >= 5:
                print(f"legacy graph already seeded ({personas} personas) - nothing to do")
            else:
                seed_legacy(session)
            return 0
    driver.close()

    if not REFRESH.is_file():
        print(f"{REFRESH} is missing: the v0.4 KAG is not published (the v1/v2 graph is not loaded either)")
        return 0
    print("no KAG release in Neo4j: publishing the v0.4 KAG with scripts/e2e/kag_v4_refresh.py")
    rc = subprocess.call([sys.executable, str(REFRESH), "--no-docs"], cwd=str(ROOT))
    if rc == 0:
        return 0
    if rc == 3:   # kag_v4_refresh.EXIT_CHECKS_FAILED
        print("KAG published; some release checks failed (see the output above)")
        return 0
    print("the v0.4 KAG could not be published yet (is database rain_v4 loaded in Postgres?). After loading it run:\n"
          "  docker compose -p rain4 run --rm neo4j-seed     (or scripts/e2e/kag_v4_refresh.py on the rain4 network)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
