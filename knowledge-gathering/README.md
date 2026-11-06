# Knowledge Gathering (DIF build-time factory)

Everything for the knowledge-gathering pipeline lives here, in one place:

    knowledge-gathering/
      agents/     # one YAML per pipeline agent (steps wired skill -> skill)
      skills/     # one folder per skill (SKILL.md + scripts/run.py)

The RAIN insights runtime (NLQ answering, PRD design) is separate: its skills are in `skills/`
and its agent packs in `agents/` at the repo root. Loader paths are configured in
`dif/config.py` (`DIF_SKILLS_DIR`, `DIF_AGENTS_DIR` env vars override the defaults).
Enterprise-specific skill overrides still layer on top from `enterprises/<id>/skills/`.

## Pipeline steps -> agents -> skills

| Step | Agent (`agents/`) | Skills (`skills/`) | Output artifact |
|---|---|---|---|
| 1. Domain Modelling | `domain-modelling-agent` | `domain-model-extractor`, `domain-model-normalizer` | `domain_model` (domain-model.v1.json) |
| 2. Metadata Extraction | `metadata-extraction-agent` | `schema-metadata-extractor`, `metadata-validator` | `extraction` (metadata registry) |
| 3. Metadata Enrichment | `domain-enrichment-agent` | `domain-enricher`, `semantic-mapper` | `domain_catalog` + semantic mappings |
| 4. Lower Ontology | `lower-ontology-agent` | `lower-ontology-builder`, `ontology-validator` | `ontology` (lower-ontology) |
| 5. Upper Ontology | `upper-ontology-alignment-agent` | `upper-ontology-aligner`, `ontology-validator` | `alignment` (upper-ontology mapping) |
| 6. KAG Build & Publish | `kag-builder-agent` | `kag-model-mapper`, `neo4j-validate`, `neo4j-publish` | `kag_release` in Neo4j |
| Data acquisition (MVP-1) | `data-acquisition-agent` | `scenario-router`, `provisional-schema-generator`, `synthetic-data-generator`, `data-landing`, `data-profiler`, `data-readiness-report` | `data_assets` readiness report |
| Validation gate | `validation-agent` | `acceptance-check`, `llm-judge`, `validation-summary` | validation report |
| Reconciliation | `reconciliation-agent` | `reconciler` | reconciled package |
| Packaging | `package-publisher-agent` | `package-assembler`, `package-store` | published knowledge package |
| End-to-end | `dif-build-orchestrator` | `prd-intake`, `source-discovery`, then runs the agents above as children, with human gates | knowledge package manifest |

Supporting skills also here: `ddl-source-reader` and `mcp-call` (read source schemas for
source-discovery / uc3), `platform-kag-seed` (seeds the platform KAG).

## PRD inputs and knowledge releases

Each PRD wave gets two prepared inputs in `doc/prd/` (the raw document stays there as the human
reference; the factory never reads it directly):

| Wave | Source document (`doc/prd/`) | Factory inputs (`doc/prd/`) | Package / release | KAG |
|---|---|---|---|---|
| v0.1 | `RAIN_Platform_PRD_v0.1.txt` (stand-in) | the txt itself + operational DDL | `1.0.1` | not published |
| v0.2 | `RAIN_Platform_PRD_v0.2.docx` | `RAIN_Platform_PRD_v0.2_factory_extract.txt` + `RAIN_Platform_PRD_v0.2_planned_schemas.sql` (+ 19 operational DDLs) | `2.0.0` / `rain-v2.0.0` | published to `rain-complete` (readiness blocked: operational tables unmapped, approved knowingly) |
| v0.3 | `RAIN_Prototype_Spec_v2.docx` (value-based care prototype spec) | `RAIN_Prototype_Spec_v2_factory_extract.txt` + `RAIN_Prototype_Spec_v2_planned_schemas.sql` (planned-only, 38 tables) | `3.0.0` / `rain-v3.0.0` | published to its own `rain-v3` database (readiness partial; only known gap: `no_show_rate`) |

Packages land in `.data/artifacts/packages/rain/<version>/` (gitignored) with a visible copy in
`artifacts/RAIN_Knowledge_Package_v<version>/`. Each wave's KAG is its own database on the local
Neo4j (`bolt://127.0.0.1:7687`): v0.2 lives in **`rain-complete`**, v0.3 in **`rain-v3`**
(mirroring the per-wave Postgres split below). A release is published under
`(enterprise_id: rain, release: rain-v<version>)`, and re-publishing a release means deleting its
nodes first (the publish skill MERGEs and never removes stale nodes). The backend's KAG reads
follow `NEO4J_DATABASE` in `rain-api/.env` (currently `rain-complete`, the v0.2 graph); point a
process at the v0.3 graph with `NEO4J_DATABASE=rain-v3`.

The factory publishes the **data ontology** (Class/Table/Column/DataAsset/System). The rest of
the PRD's knowledge — organizations, counties/sites, the contract checkpoint with its master
metrics, the quality gate and measures, impactability segments, use cases, pages/workbenches
(wired to the classes they read), AI capabilities, personas with their signals, and the guided
conversation steps — is seeded by **`seeds/rain_v3_prd_seed.py`** (run it after the factory
release is in; idempotent MERGE into the same release, nodes carry `provenance: ["prd_seed"]`).
For the v0.3 wave that adds 87 nodes / 270 relationships on top of the factory's 443/530.

### Preparing a factory extract (the no-LLM grammar)

The deterministic extractor mines entities from the extract text, so the distillation must follow
its grammar or the kag precheck refuses on orphan classes:

- Write every planned entity as its snake_case table name (`care_gap`, `impactability_score`);
  single-word tables (`patient`, `claim`) just need a mention. Every table in the DDL should be
  mentioned, or reconciliation reports it unmapped.
- `records` is parsed as a verb: never put text after "X records" except a sentence end or a
  comma (`...uses outreach_task records.` is safe; `...records as the ranked worklist` mints an
  `AsTheRankedWorklist` orphan). Same for lowercase `model(s)`, `shows/show`, `needs`, `stores`,
  `tracks` mid-sentence — even inside hyphenated words (`high-need high-cost` minted `HighCost`).
- A snake token that is a column, not a table (`outreach_rank`), becomes an orphan class — write
  it with spaces ("an outreach rank") so it lands as an attribute instead.
- No multi-word TitleCase in the body (org names, "Choosing Wisely"): TitleCase phrases become
  entities. Phrase use cases as questions; `X belongs to a Y` yields a relationship;
  `X carries a/an Z` yields attributes.
- A deliberately unmodelled entity works as "also needs a `<x>` entity that is not yet modelled"
  if `<x>` carries an upper-ontology keyword (`no_show_rate` → Metric via "rate").

Every planned table in the schemas SQL carries a `-- source: <feed>` comment; that is where the
System/lineage nodes come from.

## Run it

Build (in-process, gates skipped; leave `DIF_NEO4J_URI` unset to keep the KAG write a separate,
reviewed step — precheck/validate still run in-memory):

    from dif.runtime.factory import build_runtime
    rt = build_runtime("local")
    run = rt.start("dif-build-orchestrator", {
        "prd": <factory extract text>, "schemas": [<planned schemas DDL text>],
        "release": "rain-v3.0.0", "package_version": "3.0.0",
        "rows_per_table": 10, "seed": 7, "auto_approve": True, "overwrite": True,
    }, enterprise="rain")

With human gates instead: serve `uvicorn dif.app:app --port 8099` with `DIF_API_KEYS` set and
drive the three approvals over the API. To publish a finished release, take the kag-builder
child run's `map` step output (nodes/relationships) from `dif.db` and run the `neo4j-publish` +
`neo4j-validate` skills with a driver factory pinned to the wave's database (`rain-complete` for
v0.2, `rain-v3` for v0.3 — create it first with `CREATE DATABASE $db IF NOT EXISTS` against the
`system` database; DIF's own session lands in the DBMS default database otherwise).

The frontend serving layer is separate: `deploy/scripts/build_data_api.py --prd <extract>
--ddl <planned schemas>` generates seeded synthetic rows, loads Postgres and writes a FastAPI
router. Each wave serves from its own database (`PG_DB` env selects the load target;
`--db-env/--db-default` bake the router's connection, `--mount`/`--tag` name it):

- v0.2: database `rain`, schema `synthetic` + `public_data` → `rain-api/data_api.py` at `/api/v2/data`
- v0.3: database `rain_v3` (same two schemas; public data loaded with `PG_DB=rain_v3
  deploy/scripts/load_public_data.py .`) → `rain-api/data_api_v3.py` at `/api/v3/data`
  (connection override: `PG_DB_V3`)

Tests: `pytest tests/` (uses these folders through `dif/config.py` defaults).
