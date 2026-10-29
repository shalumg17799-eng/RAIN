---
name: kag-model-mapper
version: 1.0.0
description: Maps a lower ontology, its upper-ontology alignment, the extracted metadata graph, semantic mappings and data assets to Neo4j node and relationship records (Enterprise and Platform labels) with provenance, ready for neo4j-publish.
dependencies: []
validation:
  required_input: [ontology, alignment]
  required_output: [release, nodes, relationships, counts, provenance]
examples:
  - input: {ontology: "<ontology.v1.json>", alignment: "<alignment.v1.json>", extraction: "<schema-metadata-extractor output>", release: "rel-2026-10"}
---

# KAG Model Mapper (PRD US-014)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

Deterministic: no LLM. Produces plain records; `neo4j-publish` writes them, `neo4j-validate` checks them.

## Input
- `ontology` (required), `alignment` (required).
- `extraction` (optional): `schema-metadata-extractor` output; its `metadata_graph` nodes/edges become Table, Column and
  System nodes with `HAS_COLUMN`, `REFERENCES`, `DERIVED_FROM`.
- `semantic_mappings` (optional): entity-level rows become `MAPS_TO` (class -> table) with `confidence`/`method`;
  without them `MAPS_TO` comes from `class.source.table` (method `source`, confidence 1.0).
- `data_assets` (optional): `data-assets.v1.json`; assets whose table is in the graph become DataAsset nodes with `BACKED_BY` (table -> asset); assets without a table node are not created (they would be orphans) and are listed in the output as `skipped_assets`.
- `release` (default `rel-<run_id>`), `enterprise` (default ctx enterprise, else `default`),
  `artifact_versions` (optional `{artifact_kind: version}` for the provenance list).

## Records
- nodes `[{key, labels, props}]`. Keys: `class:<id>`, `property:<class>.<name>`, `table:<t>`, `column:<t>.<c>`,
  `system:<s>`, `asset:<name>`, `concept:<id>`. Enterprise nodes carry labels `["Enterprise", <Kind>]` and props
  `enterprise_id`, `release`, `provenance` (list of artifact kinds, e.g. `lower_ontology`). Referenced upper concepts are
  `["Platform", "Concept"]` nodes (key only, no release).
- relationships `[{type, from, to, props}]`: `SUBCLASS_OF`, `HAS_PROPERTY`, `RELATES_TO`, `ALIGNS_TO` (`relation`, `confidence`),
  `MAPS_TO` (`confidence`, `method`), `HAS_COLUMN`, `REFERENCES`, `DERIVED_FROM`, `BACKED_BY`.

## Output
`{release, enterprise_id, nodes, relationships, counts{nodes, relationships, by_label, by_type}, provenance[{artifact_kind, artifact_version}]}`.
