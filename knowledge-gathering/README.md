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

## Run it

Tests: `pytest tests/` (uses these folders through `dif/config.py` defaults).
