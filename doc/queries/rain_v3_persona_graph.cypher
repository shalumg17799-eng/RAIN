// =====================================================================================================
// RAIN v0.3 knowledge graph (KAG) - persona queries for Neo4j Browser
// Open http://localhost:17476/browser/ , connect URL bolt://localhost:17689 , user neo4j / password
// Database: neo4j. The v0.3 release is scoped by the property release = 'rain-v3.0.0'.
//
// Why "no Persona nodes" showed up before: the release has 523 nodes, 295 of them Columns. A query like
// MATCH (n {release:'rain-v3.0.0'}) RETURN n LIMIT 300 returns only data-ontology nodes (columns, classes,
// tables) and never reaches the 7 Persona nodes. Query them by label, as below.
// Note: the same database also holds the v0.2 seed graph (11 Persona nodes WITHOUT a release property).
// =====================================================================================================

// @id KAG-1  The seven v0.3 personas (table view)
MATCH (p:Persona {release: 'rain-v3.0.0'})
RETURN p.order AS order, p.name AS name, p.role AS role, p.key AS key,
       size(coalesce(p.suggested_queries, [])) AS suggested_queries
ORDER BY p.order;

// @id KAG-2  Every v0.3 persona with everything it links to (graph view)
MATCH (p:Persona {release: 'rain-v3.0.0'})-[r]->(x)
RETURN p, r, x;

// @id KAG-3  One persona's neighbourhood (swap the key: GregoryHaskins, NaomiCastellanos, RajMalhotra,
//            LaurenPike, TeresaLopez, BrandonKee, LindaGarcia)
MATCH (p:Persona {release: 'rain-v3.0.0', key: 'persona:GregoryHaskins'})-[r]-(x)
RETURN p, r, x;

// @id KAG-4  Priority signals per persona
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:HAS_SIGNAL]->(s:Signal)
RETURN p.name AS persona, s.name AS signal, s.severity AS severity, s.detail AS detail
ORDER BY p.order, s.severity;

// @id KAG-5  The PRD's suggested questions per persona (each one is answered by that persona's UI)
MATCH (p:Persona {release: 'rain-v3.0.0'})
UNWIND coalesce(p.suggested_queries, []) AS question
RETURN p.name AS persona, question
ORDER BY p.order;

// @id KAG-6  Guided conversation steps per persona, in order
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:HAS_STEP]->(s:Step)
RETURN p.name AS persona, s.step AS step, s.user_prompt AS user_prompt,
       s.visualization AS visualization, s.data_sources AS data_sources
ORDER BY p.order, s.step;

// @id KAG-7  What data each persona's workbenches read: Persona -> Workbench -> Class -> Table (planned schema)
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:USES]->(w:Workbench)-[:READS]->(c:Class)-[:MAPS_TO]->(t:Table)
RETURN p.name AS persona, w.name AS workbench,
       collect(DISTINCT c.name) AS classes, collect(DISTINCT t.name) AS tables
ORDER BY persona, workbench;

// @id KAG-8  Same lineage as a graph (one persona; swap the key)
MATCH path = (p:Persona {release: 'rain-v3.0.0', key: 'persona:NaomiCastellanos'})-[:USES]->(:Workbench)
             -[:READS]->(:Class)-[:MAPS_TO]->(:Table)
RETURN path;

// @id KAG-9  The v0.3 release without column detail (228 nodes; personas included)
MATCH (n {release: 'rain-v3.0.0'})
WHERE NOT n:Column
OPTIONAL MATCH (n)-[r]->(m {release: 'rain-v3.0.0'})
WHERE NOT m:Column
RETURN n, r, m;

// @id KAG-10 Contract checkpoint the operator personas view
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:VIEWS]->(c:Checkpoint)
RETURN c.name AS checkpoint, c.actual_pmpm AS actual_pmpm, c.expected_pmpm AS expected_pmpm,
       c.pct_above_expected AS pct_above_expected, c.annualized_gap_usd AS annualized_gap_usd,
       c.days_left AS days_left, collect(p.name) AS viewed_by;
