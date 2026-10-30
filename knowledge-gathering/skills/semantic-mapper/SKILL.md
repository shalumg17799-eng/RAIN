---
name: semantic-mapper
version: 1.0.0
description: Maps domain-model entities and attributes to extracted tables and columns by name similarity (with FK and lineage evidence), reports per-mapping confidence and the gaps; optional LLM refinement for unmapped entities.
dependencies: []
validation:
  required_input: [extraction]
  required_output: [mappings, gaps, confidence]
examples:
  - input: {domain_model: "<domain-model.v1 artifact>", extraction: "<output of schema-metadata-extractor>"}
---

# Semantic Mapper (plan 5.4)

Second step of `domain-enrichment-agent`: *which table implements which entity, and which column which attribute?*

## Input
- `extraction` (required): `tables[]`, `columns{table: [col]}`, optional `keys{table: {primary, foreign{col: "table.col"}}}`,
  optional `lineage{table: system}` (output of `schema-metadata-extractor`).
- `domain_model` (optional): `entities[{id|name, attributes[{name}], evidence[]}]`, `relationships[]`. When absent the
  skill still returns a valid result: no mappings, every table an `unmapped_table` gap, confidence 0. This keeps the
  agent output contract-valid for callers that only have an extraction.
- `prd`, `taxonomy` (optional, reserved), `use_llm` (optional, default true), `min_confidence` (optional, default 0.5).

## Method (deterministic)
- Names are tokenised (snake/camel/space), singularised, mapped through a small synonym list (`customer -> member`,
  `request -> application`, ...) and stripped of table prefixes (`tbl_`, `dim_`, `fact_`, `stg_`).
- Entity -> table: Jaccard token similarity (`method: name`); identical token sets score 1.0, a token subset at least 0.5.
  When names disagree but at least two attributes match columns, the attribute overlap is used (`method: attribute`).
- Greedy one-to-one assignment by confidence; FK edges consistent with a modelled relationship add +0.1, a lineage system
  mentioned in the entity's evidence +0.05 (capped at 1.0). Both are listed in `evidence`.
- Attribute -> column for every mapped entity (`attribute`/`column` set on the mapping record).
- Gaps: `unmapped_entity`, `unmapped_table`, `unmapped_attribute` (`name` = `entity.attribute`).
- Overall `confidence` = mean entity-level confidence over all entities (unmapped entities count 0).

## LLM refinement (optional)
Unmapped entities are offered to the model with the table list; answers naming a real, still-unassigned table become
`method: llm` mappings with confidence 0.5. On failure `llm_error` is set and the baseline stands.

## Output
`mappings[]`, `gaps[]`, `confidence`, `llm_error?` - valid against `contracts/semantic-mappings.v1.json`.
