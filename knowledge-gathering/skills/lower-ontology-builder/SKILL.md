---
name: lower-ontology-builder
version: 1.0.0
description: Builds an enterprise lower ontology (classes, data/object properties, axioms, coverage) from a domain model, optional semantic mappings and the extracted metadata graph; deterministic with evidence, optional LLM-written descriptions.
dependencies: []
validation:
  required_input: [domain_model]
  required_output: [name, version, namespace, classes, object_properties, data_properties, axioms, coverage, validation]
examples:
  - input: {domain_model: "<domain-model.v1.json>", semantic_mappings: "<semantic-mappings.v1.json>", extraction: "<schema-metadata-extractor output>"}
---

# Lower Ontology Builder (PRD US-012)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

Turns the approved domain model plus technical metadata into an `ontology.v1.json` object. Every class carries its
provenance (`source.entity` / `source.table`) and the evidence texts it was derived from.

## Input
- `domain_model` (required): `domain-model.v1.json` (`entities[{id, name, description, attributes, keys, evidence}]`, `relationships`).
- `semantic_mappings` (optional): `semantic-mappings.v1.json`; entity-level rows (`attribute` null) bind a class to a table,
  column-level rows add data properties for mapped columns.
- `extraction` (optional): output of `schema-metadata-extractor` (`tables`, `columns`, `keys`, `lineage`, `metadata_graph`).
  Tables no entity maps to become classes of their own (`source.table`), FK edges become object properties.
- `glossary` (optional): `[{term, definition}]`; a definition whose term matches a class name becomes its description.
- `namespace` (default `https://dif.radiant.digital/ontology/<enterprise or 'enterprise'>#`), `name` (default `<enterprise>-lower-ontology`).
- `use_llm` (optional, default true): only with `DIF_LLM_PROVIDER` != `none`; writes descriptions for classes that have none.

## Rules (deterministic)
- Class per entity: id = PascalCase(entity id), `source.entity`, evidence = entity evidence texts. Entity -> table binding:
  semantic mapping, else name match (snake_case of id/name, plural-insensitive) against the extraction tables.
- Class per uncovered table: id = PascalCase(table), `source.table`, data properties from its columns.
- Data properties: `<Class>.<camelCase attribute>`; datatype from `attribute.type` / column type, else name heuristics
  (`*_id` -> `xsd:long`, `*_at`/`*date` -> `xsd:dateTime`, amount/price/score/rate -> `xsd:decimal`, `is_`/`has_` -> `xsd:boolean`, else `xsd:string`).
- Object properties: domain-model relationships (camelCase name, cardinality from the relationship type) and FK
  `REFERENCES` edges between tables bound to classes (`*..1`), de-duplicated per (domain, range).
- Axioms: `key` per entity key / table primary key; `subclass_hint` when a class name ends with another class name.
- `coverage`: `{entities_total, entities_covered, tables_total, tables_covered}`.
- `validation`: the result of `ontology-validator` (imported from the sibling skill; a minimal fallback check otherwise).

## Output
`ontology.v1.json`: `name, version ("1.0.0"), namespace, classes, object_properties, data_properties, axioms, coverage, validation`,
plus `llm_error` when the optional description step failed (the deterministic result still stands).
