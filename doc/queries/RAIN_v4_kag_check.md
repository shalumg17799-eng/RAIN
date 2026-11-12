# RAIN v0.4 knowledge graph (KAG): release check

Release **`rain-v4.1.0`** in Neo4j database `neo4j` of the compose project `rain4` (http://localhost:17477/browser/, bolt://localhost:17690). Written by `scripts/e2e/kag_v4_refresh.py` on 2026-11-10T16:30:36+00:00 (git unknown (set RAIN_GIT_COMMIT)); re-run that script to rebuild the release and this file.

**21 of 21 checks pass**.

## What the release holds

2,456 nodes and 3,437 relationships, all with `release = 'rain-v4.1.0'`, built from:

- PRD seed: knowledge-gathering/seeds/rain_v4_prd_seed.py (sha 940de2559fcb)
- ontology: artifacts/rain-v4-kag-records.json (present) + platform/ontology/upper-ontology.v1.json
- postgres: rain_v4 synthetic, public_data, ui_v4: 84 tables, 65 foreign keys (pg_catalog, exact counts)
- planned DDL: doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql: 53 planned tables
- computed context: rain-api ui_data_v4.load_sections (computed now); templates from ui_v4.dataset (templates)
- query pack: doc/queries/rain_v4_persona_queries.sql: 70 queries; backend PERSONA_IDS 7
- flows: rain-api/flow_v4.py: 9 endpoints
- frontend: WORKBENCHES 11, switcher personas 7
- public manifest: .data/public/MANIFEST.md (present)

Graph model (main paths):

- `(:Persona)-[:USES {access, scope}]->(:Workbench)-[:READS]->(:Class)-[:MAPS_TO]->(:Table)`
- `(:Persona)-[:ASKS]->(:Query)-[:READS]->(:Table)-[:HAS_COLUMN]->(:Column)-[:REFERENCES]->(:Column)`
- `(:Persona)-[:SEES]->(:MetricGroup|Dataset)`, `(:Dataset)-[:DERIVED_FROM]->(:MetricGroup)-[:COMPUTED_FROM]->(:Table)`
- `(:Workbench|Page)-[:SHOWS]->(:MetricGroup)`, `(:Workbench|Page)-[:TRIGGERS]->(:Flow)-[:WRITES|READS]->(:Table)`
- `(:DataSource)-[:LOADS|FEEDS]->(:Table)-[:FED_BY]->(:System)-[:PROVIDED_BY]->(:DataSource)`, `(:Table)-[:DERIVED_FROM]->(:Table)` (synthetic reference tables built from public_data), `(:Table)-[:IN_SCHEMA]->(:Schema)`
- PRD v0.4 seed: `Organization, County, Site, Contract, Checkpoint, QualityGate, Measure, Metric, Segment, UseCase, Page, Capability, Signal, Step, SuccessMetric` with the persona edges `WORKS_FOR, PARTICIPATES_IN, LANDS_ON, VIEWS, HAS_SIGNAL, OWNS_METRIC, REPORTS_TO`

## What was deleted

Every run that deleted something is logged on the release node (`MATCH (r:Release) RETURN r.cleanup_log`).

- **2026-11-10 (first run)** (run `b1c8b8aae47d`):
  - unreleased v1/v2 seed graph and Platform upper-ontology nodes: 278 nodes, 581 relationships (CachedQuestion 40, CascadeBranch 5, ClosureEvent 1, Concept 15, Concept:Platform 9, Constant 1, CountyRegion 3, CoverageGap 2, KPI 71, Persona 11, Signal 33, SourceField 49, SourceSystem 38)
  - superseded releases: `rain-v4.0.0` 744 nodes, 1094 relationships
  - stale content of `rain-v4.1.0` from an earlier run: 0 nodes, 0 relationships
- **2026-11-10T16:29:43+00:00** (run `1bcfdd6e5185`):
  - unreleased v1/v2 seed graph and Platform upper-ontology nodes: 0 nodes, 0 relationships
  - superseded releases: none, 0 relationships
  - stale content of `rain-v4.1.0` from an earlier run: 147 nodes, 511 relationships

This run: before 2,456 nodes / 3,429 relationships (rain-v4.1.0 2456); after 2,456 / 3,437 (rain-v4.1.0 2456).

## Checks

### K01 PASS: One release in the database, and it is the current one

```cypher
MATCH (n) RETURN coalesce(n.release, '(none)') AS release, count(*) AS nodes ORDER BY release
```

| release | nodes |
|---|---|
| rain-v4.1.0 | 2456 |

### K02 PASS: No node without a release (the v1/v2 seed graph is gone)

```cypher
MATCH (n) WHERE n.release IS NULL RETURN labels(n) AS labels, count(*) AS nodes
```

_no rows_

### K03 PASS: No relationship outside the release

```cypher
MATCH (a)-[r]->(b) WHERE r.release IS NULL OR a.release <> r.release OR b.release <> r.release RETURN type(r) AS type, count(*) AS n
```

_no rows_

### K04 PASS: No legacy label left (v1/v2 seed graph, Platform nodes, factory DataAssets)

```cypher
MATCH (n) WHERE any(l IN labels(n) WHERE l IN ['KPI','SourceField','CachedQuestion','SourceSystem','CascadeBranch','CountyRegion','CoverageGap','Constant','ClosureEvent','Platform','DataAsset']) RETURN labels(n) AS labels, count(*) AS n
```

_no rows_

### K05 PASS: Exactly 7 personas, each with a backend id and a UI persona id

```cypher
MATCH (p:Persona {release: 'rain-v4.1.0'}) RETURN count(p) AS personas, count(p.persona_id) AS with_kag_id, count(p.ui_persona_id) AS with_ui_id
```

| personas | with_kag_id | with_ui_id |
|---|---|---|
| 7 | 7 | 7 |

### K06 PASS: Only the seven personas: every Persona is a PRD v0.4 persona of v0.3 origin, and no RetiredPersona node

```cypher
MATCH (p) WHERE (p:Persona AND (p.release <> 'rain-v4.1.0' OR p.prd_origin <> 'v0.3' OR p.prd_version <> 'v0.4')) OR p:RetiredPersona RETURN labels(p) AS labels, p.name AS persona, p.release AS release
```

_no rows_

### K07 info: The persona roster with UI status, workbench access and pack queries

```cypher
MATCH (p:Persona {release: 'rain-v4.1.0'}) RETURN p.order AS order, p.name AS persona, p.persona_id AS kag_id, p.ui_persona_id AS ui_id, p.ui_status AS ui_status, COUNT { (p)-[:USES]->(:Workbench) } AS workbenches, COUNT { (p)-[:ASKS]->(:Query) } AS queries ORDER BY order
```

| order | persona | kag_id | ui_id | ui_status | workbenches | queries |
|---|---|---|---|---|---|---|
| 1 | Gregory Haskins, MBA | rain_ceo | rain_ceo | switcher | 4 | 10 |
| 2 | Dr. Naomi Castellanos | rain_cmo | rain_cmo | switcher | 5 | 10 |
| 3 | Raj Malhotra | rain_cio | rain_cio | switcher | 2 | 10 |
| 4 | Dr. Lauren Pike | rain_state | rain_state | switcher | 3 | 10 |
| 5 | Teresa Lopez, CHW | rain_chw | rain_chw | switcher | 2 | 10 |
| 6 | Brandon Kee | rain_access | rain_access | switcher | 2 | 10 |
| 7 | Linda Garcia | patient_linda_garcia | rain_linda | switcher | 1 | 10 |

### K08 PASS: Every persona has pack queries

```cypher
MATCH (p:Persona {release: 'rain-v4.1.0'}) WHERE NOT (p)-[:ASKS]->(:Query) RETURN p.name AS persona, p.persona_id AS kag_id, p.backend_persona_id AS backend_id
```

_no rows_

### K09 PASS: Every persona has workbenches (patients: the patient view page instead)

```cypher
MATCH (p:Persona {release: 'rain-v4.1.0'}) WHERE NOT (p)-[:USES]->(:Workbench) AND NOT (p.role = 'Patient' AND (p)-[:LANDS_ON]->(:Page {key: 'page:PatientView'})) RETURN p.name AS persona, p.ui_status AS ui_status, p.has_ui_contract AS has_ui_contract
```

_no rows_

### K10 PASS: Every pack query is in the graph (70 in doc/queries/rain_v4_persona_queries.sql)

```cypher
MATCH (q:Query {release: 'rain-v4.1.0'}) RETURN count(q) AS queries
```

| queries |
|---|
| 70 |

### K11 PASS: Every query reads at least one existing Table node and names no missing table

```cypher
MATCH (q:Query {release: 'rain-v4.1.0'}) WHERE NOT (q)-[:READS]->(:Table) OR size(q.missing_tables) > 0 RETURN q.query_id AS query, q.tables AS tables, q.missing_tables AS missing
```

_no rows_

### K12 PASS: Every query belongs to a persona

```cypher
MATCH (q:Query {release: 'rain-v4.1.0'}) WHERE NOT (:Persona)-[:ASKS]->(q) RETURN q.query_id AS query, q.persona_id AS persona
```

_no rows_

### K13 info: Tables per schema with rows and columns

```cypher
MATCH (t:Table {release: 'rain-v4.1.0'}) RETURN t.schema AS schema, count(t) AS tables, sum(t.row_count) AS rows, sum(t.column_count) AS columns ORDER BY schema
```

| schema | tables | rows | columns |
|---|---|---|---|
| public_data | 24 | 83263 | 1505 |
| synthetic | 59 | 689446 | 468 |
| ui_v4 | 1 | 15 | 5 |

### K14 PASS: Every column belongs to exactly one table; every foreign key points at a column of a table

```cypher
MATCH (c:Column {release: 'rain-v4.1.0'}) WHERE COUNT { (:Table)-[:HAS_COLUMN]->(c) } <> 1 OR EXISTS { MATCH (c)-[:REFERENCES]->(d:Column) WHERE NOT (:Table)-[:HAS_COLUMN]->(d) } RETURN c.key AS column
```

_no rows_

### K15 PASS: Every synthetic table has a source feed; every public_data table has a data source

```cypher
MATCH (t:Table {release: 'rain-v4.1.0'}) WHERE (t.schema = 'synthetic' AND NOT (t)-[:FED_BY]->(:System)) OR (t.schema = 'public_data' AND NOT (:DataSource)-[:LOADS]->(t)) RETURN t.qualified_name AS table
```

_no rows_

### K16 PASS: Every class maps to a table

```cypher
MATCH (c:Class {release: 'rain-v4.1.0'}) WHERE NOT (c)-[:MAPS_TO]->(:Table) RETURN c.name AS class
```

_no rows_

### K17 PASS: Every UI workbench is in the graph and used by at least one persona

```cypher
MATCH (w:Workbench {release: 'rain-v4.1.0'}) WHERE w.in_ui AND NOT (:Persona)-[:USES]->(w) RETURN w.name AS workbench
```

_no rows_

### K18 PASS: Every computed metric group reads tables (directly or through the records it is built from)

```cypher
MATCH (m:MetricGroup {release: 'rain-v4.1.0'}) WHERE m.kind <> 'config' AND NOT (m)-[:COMPUTED_FROM]->(:Table) AND NOT (m)-[:DERIVED_FROM]->(:MetricGroup) RETURN m.name AS group, m.kind AS kind
```

_no rows_

### K19 PASS: Every dataset is derived from at least one metric group

```cypher
MATCH (d:Dataset {release: 'rain-v4.1.0'}) WHERE NOT (d)-[:DERIVED_FROM]->(:MetricGroup) RETURN d.name AS dataset
```

_no rows_

### K20 PASS: Every write-back flow (POST) writes at least one table

```cypher
MATCH (f:Flow {release: 'rain-v4.1.0'}) WHERE f.method = 'POST' AND NOT (f)-[:WRITES]->(:Table) RETURN f.name AS flow
```

_no rows_

### K21 PASS: Every data source has a load status; blocked ones say why

```cypher
MATCH (s:DataSource {release: 'rain-v4.1.0'}) WHERE s.load_status IS NULL OR (s.load_status = 'blocked' AND s.blocked_reason IS NULL) OR s.load_status = 'missing' RETURN s.name AS source, s.load_status AS status
```

_no rows_

### K22 info: Data sources by load status

```cypher
MATCH (s:DataSource {release: 'rain-v4.1.0'}) RETURN s.load_status AS status, count(*) AS sources, collect(s.name) AS names ORDER BY status
```

| status | sources | names |
|---|---|---|
| blocked | 5 | FCC National Broadband Map, CMS Medicare Geographic Variation, VSAC value sets (eCQM value-set expansions), CMS Provider of Services file (official CMS download), HRSA FORHP data files (eligible ZIP codes, county and tract workbook) |
| computed | 5 | Low-value care measure library, HIE ADT feed (synthetic), RAIN cost model, RAIN impactability score, eCQM engine |
| generated | 7 | Synthea (MITRE), Synthetic MCO eligibility and attribution, Synthetic claims (Synthea output, adjusted to Nevada Medicaid patterns), Synthetic EHR (FHIR R4 US Core), Synthetic remote BP readings, Synthetic schedules, eligibility responses and SMS logs, Contract benchmark |
| loaded | 16 | CDC PLACES (2025 release), CDC/ATSDR Social Vulnerability Index (2022), HRSA Health Professional Shortage Areas, County Health Rankings (archived 2025 + March 2026), USDA Rural-Urban Continuum Codes (2023), HRSA FORHP rural areas, Census ZCTA relationship and gazetteer files, Census cartographic boundary files (2024), Census ACS 5-year (2020 to 2024), HRSA health center sites, CMS Hospital General Information and quality, CMS Provider of Services file, NPPES NPI Registry, HRSA Uniform Data System (UDS), CMS eCQMs (CMS165, CMS122, CMS125, CMS130, CMS2), OpenStreetMap road network (via Geofabrik) |

### K23 info: Nodes by label

```cypher
MATCH (n {release: 'rain-v4.1.0'}) RETURN labels(n)[1] AS label, count(*) AS nodes ORDER BY nodes DESC
```

| label | nodes |
|---|---|
| Column | 1978 |
| Table | 84 |
| Query | 70 |
| Class | 59 |
| MetricGroup | 40 |
| DataSource | 33 |
| System | 30 |
| Dataset | 29 |
| Enterprise | 28 |
| SuccessMetric | 17 |
| Step | 16 |
| Workbench | 11 |
| Metric | 10 |
| Flow | 9 |
| County | 6 |
| Capability | 6 |
| Measure | 5 |
| Property | 5 |
| Organization | 4 |
| Segment | 3 |
| Schema | 3 |
| Site | 2 |
| UseCase | 2 |
| Page | 2 |
| Contract | 1 |
| Checkpoint | 1 |
| QualityGate | 1 |
| Release | 1 |

### K24 info: Relationships by type

```cypher
MATCH ({release: 'rain-v4.1.0'})-[r]->() RETURN type(r) AS type, count(*) AS relationships ORDER BY relationships DESC
```

| type | relationships |
|---|---|
| HAS_COLUMN | 1978 |
| COMPUTED_FROM | 206 |
| READS | 192 |
| IN_SCHEMA | 84 |
| ALIGNS_TO | 81 |
| SEES | 71 |
| ASKS | 70 |
| DERIVED_FROM | 69 |
| SHOWS | 67 |
| RELATES_TO | 66 |
| REFERENCES | 65 |
| MAPS_TO | 59 |
| FED_BY | 59 |
| FEEDS | 33 |
| LISTS | 30 |
| CATALOGS | 29 |
| PROVIDED_BY | 25 |
| WRITES | 25 |
| LOADS | 24 |
| USES | 19 |
| OWNS_METRIC | 16 |
| HAS_STEP | 16 |
| TAGGED_WITH | 16 |
| SERVES | 13 |
| HAS_SIGNAL | 12 |
| REFERS_TO | 12 |
| REPORTS | 10 |
| TRIGGERS | 8 |
| LANDS_ON | 7 |
| PARTICIPATES_IN | 7 |
| SERVES_COUNTY | 6 |
| OVERSEES | 6 |
| SUPPORTS | 6 |
| VIEWS | 6 |
| WORKS_FOR | 6 |
| HAS_MEASURE | 5 |
| INSTANCE_OF | 5 |
| HAS_PROPERTY | 5 |
| LAUNCHES | 4 |
| SEGMENTED_BY | 3 |

_12 more rows_

### K25 PASS: Every Table node exists in Postgres rain_v4, and every table of the three schemas has a Table node

```cypher
MATCH (t:Table {release: 'rain-v4.1.0'}) RETURN t.qualified_name  // compared with pg_class
```

| table_nodes | postgres_tables | not_in_postgres | not_in_kag |
|---|---|---|---|
| 84 | 84 |  |  |

### K26 PASS: Row counts on the Table nodes match Postgres at validation time (write-back flows may move them)

```cypher
MATCH (t:Table {release: 'rain-v4.1.0'}) RETURN t.qualified_name, t.row_count  // compared with count(*)
```

| tables_compared | different |
|---|---|
| 84 | {} |

