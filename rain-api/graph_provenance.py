"""
Queries the persona graph (loaded by generate_persona_graph.py) live, on
every request, to attach real provenance to signals/KPIs -- which real
table backs this specific number, according to the graph itself, not
according to my memory of which ones I tested during migration.

This is the piece that actually makes today's Neo4j load DO something in
the running app, instead of sitting there as a disconnected record only
useful for manual Cypher queries.

If a signal/KPI has no COMPUTED_FROM edge in the graph, `source_system`
is simply omitted -- that's the graph honestly reporting "not proven
live," the same distinction the graph itself was built to carry.

Graceful failure: if Neo4j is unreachable, every lookup returns None and
the caller proceeds without provenance fields -- never breaks the request,
same defensive pattern used everywhere else in this project.
"""

from neo4j_fallback import get_driver, NEO4J_URI, NEO4J_DATABASE
from neo4j import exceptions as neo4j_exceptions


def get_signal_provenance(signal_id: str):
    """Returns the real SourceSystem name backing this signal, or None if
    the graph has no COMPUTED_FROM edge for it (i.e., genuinely static)."""
    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                "MATCH (s:Signal {id: $id})-[:COMPUTED_FROM]->(sys:SourceSystem) RETURN sys.name AS name",
                id=signal_id,
            )
            record = result.single()
            return record["name"] if record else None
    except neo4j_exceptions.ServiceUnavailable:
        return None
    except Exception:
        return None


def get_kpi_provenance(persona: str, kpi_id: str):
    """Same lookup for a KPI -- graph id format is '{persona}_{kpi_id}',
    matching exactly how generate_persona_graph.py loaded it."""
    graph_id = f"{persona}_{kpi_id}"
    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                "MATCH (k:KPI {id: $id})-[:COMPUTED_FROM]->(sys:SourceSystem) RETURN sys.name AS name",
                id=graph_id,
            )
            record = result.single()
            return record["name"] if record else None
    except neo4j_exceptions.ServiceUnavailable:
        return None
    except Exception:
        return None


def get_cascade_branch_provenance(branch_id: str):
    """Live lookup of a cascade branch's REPRESENTS (concept) and AFFECTS
    (persona) edges -- proves the cascade page actually reads the graph,
    not just static Python matching the same content by coincidence."""
    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (b:CascadeBranch {id: $id})
                OPTIONAL MATCH (b)-[:REPRESENTS]->(c:Concept)
                OPTIONAL MATCH (b)-[:AFFECTS]->(p:Persona)
                RETURN c.name AS concept, p.name AS persona
            """, id=branch_id)
            record = result.single()
            if not record:
                return None
            return {"concept": record["concept"], "affects_persona": record["persona"]}
    except neo4j_exceptions.ServiceUnavailable:
        return None
    except Exception:
        return None


def get_county_region_provenance(county_name: str):
    """Live lookup of a county region's REPRESENTS (concept) and AFFECTS
    (real SourceSystem) edges."""
    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (r:CountyRegion {name: $name})
                OPTIONAL MATCH (r)-[:REPRESENTS]->(c:Concept)
                OPTIONAL MATCH (r)-[:AFFECTS]->(sys:SourceSystem)
                RETURN c.name AS concept, sys.name AS system
            """, name=county_name)
            record = result.single()
            if not record:
                return None
            return {"concept": record["concept"], "real_data_table": record["system"]}
    except neo4j_exceptions.ServiceUnavailable:
        return None
    except Exception:
        return None


def get_data_source_field_count(source_name: str):
    """How many real ontology field mappings this source backs, per the
    original upper-ontology graph (MAPS_TO edges) -- a genuine live fact
    about the graph's own coverage, not a stored number."""
    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (:Concept)-[:MAPS_TO]->(f:SourceField)-[:BELONGS_TO]->(sys:SourceSystem {name: $name})
                RETURN count(f) AS field_count
            """, name=source_name)
            record = result.single()
            return record["field_count"] if record else 0
    except neo4j_exceptions.ServiceUnavailable:
        return None
    except Exception:
        return None
