"""
Loads build_graph.cypher into a REAL, running Neo4j instance.

This is real, working code using the official neo4j Python driver
(pip install neo4j) -- point it at any Neo4j instance and it will load the
knowledge graph for real: Neo4j Desktop, Neo4j Aura, Docker, or the local
instance from the AADR KAG demo (bolt://localhost:7687).

Usage:
    python3 load_to_neo4j.py --uri bolt://localhost:7687 --user neo4j --password <your-password>

If no arguments are given, defaults match the AADR local setup
(D:\\kag\\kag-demo): bolt://localhost:7687, user "neo4j", password "12345678"
-- change these if your instance differs.
"""

import argparse
from neo4j import GraphDatabase

def load_cypher_statements(path):
    with open(path) as f:
        lines = f.readlines()
    # Strip comment-only and blank lines BEFORE splitting into statements.
    # (Splitting first and filtering chunks that "start with //" is wrong --
    # a comment sitting between two statements has no semicolon before it,
    # so it gets glued onto the NEXT statement into one chunk, and that
    # whole chunk -- including the real statement -- gets silently dropped.)
    code_only = "".join(ln for ln in lines if ln.strip() and not ln.strip().startswith("//"))
    statements = [s.strip().rstrip(";").strip() for s in code_only.split(";\n") if s.strip()]
    return statements

def main():
    parser = argparse.ArgumentParser(description="Load the upper-ontology knowledge graph into Neo4j")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="12345678",
                         help="Defaults to the AADR local demo password -- override for any other instance")
    parser.add_argument("--cypher-file", default="build_graph.cypher")
    args = parser.parse_args()

    statements = load_cypher_statements(args.cypher_file)
    print(f"Loaded {len(statements)} statements from {args.cypher_file}")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        driver.verify_connectivity()
        print(f"Connected to {args.uri}")
    except Exception as e:
        print(f"Could not connect to {args.uri}: {e}")
        print("Check that Neo4j is running and the URI/credentials are correct.")
        driver.close()
        return

    with driver.session() as session:
        for i, stmt in enumerate(statements, 1):
            try:
                session.run(stmt)
            except Exception as e:
                print(f"Statement {i} failed: {e}\n  {stmt[:120]}...")
        print(f"Executed {len(statements)} statements.")

    # Quick sanity check -- count what actually landed
    with driver.session() as session:
        counts = session.run("""
            MATCH (c:Concept) WITH count(c) AS concepts
            MATCH (s:SourceSystem) WITH concepts, count(s) AS systems
            MATCH (f:SourceField) WITH concepts, systems, count(f) AS fields
            MATCH ()-[r:MAPS_TO]->() 
            RETURN concepts, systems, fields, count(r) AS mappings
        """).single()
        print(f"\nLoaded: {counts['concepts']} concepts, {counts['systems']} source systems, "
              f"{counts['fields']} fields, {counts['mappings']} MAPS_TO edges")

    driver.close()

if __name__ == "__main__":
    main()