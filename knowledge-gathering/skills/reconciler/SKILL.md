---
name: reconciler
version: 1.0.0
description: Semantic-to-data reconciliation - checks that ontology concepts, semantic mappings, data assets and KPIs agree; lists resolved and unresolved items and a readiness verdict.
dependencies: []
validation:
  required_input: [semantic_mappings]
  required_output: [resolved, unresolved, readiness, score]
---

# Reconciler (plan 5.9)

Deterministic cross-check of the build-time outputs before a knowledge package is published.

## Input
- `semantic_mappings` (required): output of `semantic-mapper` (`mappings[{entity, table, column?, confidence}]`, `gaps[]`).
- `data_assets` (optional): output of `data-readiness-report` (`tables[{name, status, synthetic}]`, `readiness_status`).
- `ontology` (optional): lower ontology (`classes[{id, name, source{entity, table}}]`); concepts default to the mapped entities.
- `alignment` (optional): `unaligned[]` classes become unresolved items.
- `kag_release` (optional): `published`/`validation` add findings.
- `requirements` (optional): `kpis[{name, definition}]` are checked for resolvability against mapped entities/tables/columns.
- `min_confidence` (optional, default 0.5): mappings below it count as unresolved.

## Rules
- A concept is **resolved** when it has a mapping with confidence >= `min_confidence` and (when data assets are given) the mapped table has a landed or schema-only asset.
- Unresolved kinds: `unmapped_entity`, `low_confidence_mapping`, `no_data`, `unmapped_table`, `unaligned_class`, `kpi_unresolvable`.
- `readiness`: `ready` when nothing is unresolved, `partial` when at least half of the concepts resolved, else `blocked`.
- `score` = resolved / (resolved + unresolved). `explanation` is a plain-language summary (LLM-refined when a provider is configured; `llm_error` recorded otherwise).
