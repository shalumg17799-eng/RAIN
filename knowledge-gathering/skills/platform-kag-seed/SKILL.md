---
name: platform-kag-seed
version: 1.0.0
description: Seeds the platform KAG from the governed upper ontology (Platform Concept and Relation nodes with SUBCLASS_OF) plus optional skill and agent catalog nodes, writing through neo4j-publish.
dependencies: [neo4j-publish]
validation:
  required_input: []
  required_output: [published, counts, release]
examples:
  - input: {}
  - input: {skills: "<SkillRegistry.list()>", agents: "<AgentRegistry.list()>"}
---

# Platform KAG Seed (plan 4.3)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

## Input
- `upper_ontology` (optional): defaults to `platform/ontology/upper-ontology.v1.json` under `DIF_PLATFORM_DIR`.
- `skills` (optional): `[{name, version, description?}]`; `agents` (optional): `[{name, version, description?, steps?}]`.
  When both are omitted the running platform's registry is used (shared skills and enabled agents; `include_registry: false` turns that off).

## Records
- `["Platform", "Concept"]` nodes (`key concept:<id>`, props `concept_id, name, description, keywords`), `SUBCLASS_OF` to the parent.
- `["Platform", "Relation"]` nodes (`key relation:<id>`) with `HAS_DOMAIN` / `HAS_RANGE` to the concepts.
- `["Platform", "Skill"]` / `["Platform", "Agent"]` nodes (`key skill:<name>@<version>`, props `name, version, description`).
- `["Platform", "Release"]` node (`key release:platform-<version>`) with `CONTAINS` to every concept.

All rows are published with `enterprise_id: platform` and `release: platform-<upper ontology version>` through
`neo4j-publish` (imported from its `scripts/run.py`), so the usual dry-run / unconfigured-URI behaviour applies.

## Output
`{published, release, counts, dry_run, note?, nodes, relationships}`.
