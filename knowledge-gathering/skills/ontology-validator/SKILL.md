---
name: ontology-validator
version: 1.0.0
description: Deterministic checks on a lower ontology (unique classes, class provenance, dangling property domains/ranges, naming rules, entity coverage) and, when an alignment is given, that every class is aligned or proposed as an extension to a known upper concept.
dependencies: []
validation:
  required_input: [ontology]
  required_output: [passed, issues, checks, score]
examples:
  - input: {ontology: "<ontology.v1.json>", domain_model: "<domain-model.v1.json>"}
  - input: {ontology: "<ontology.v1.json>", alignment: "<alignment.v1.json>"}
---

# Ontology Validator (PRD US-012 / US-013)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

Gate skill for `lower-ontology-agent` and `upper-ontology-alignment-agent`. No LLM; all checks are rules.

## Input
- `ontology` (required): `ontology.v1.json` object.
- `domain_model` (optional): when given, every entity must be covered by a class (`source.entity`).
- `extraction` (optional): `source.table` references are checked against the extracted tables (warning).
- `alignment` (optional): `alignment.v1.json`; every class must be in `mappings`, `extensions_proposed[].classes` or
  `unaligned`, and every `upper_concept` / extension `parent` must exist in the upper ontology.
- `upper_ontology` (optional): defaults to `platform/ontology/upper-ontology.v1.json` (`DIF_PLATFORM_DIR`).

## Checks
| name | rule |
|---|---|
| `unique_classes` | class ids and names are unique |
| `class_provenance` | every class has `source.entity` or `source.table` |
| `object_property_refs` | `domain` and `range` of each object property are class ids |
| `data_property_refs` | `domain` of each data property is a class id |
| `naming` | classes `PascalCase`, properties `camelCase` |
| `entity_coverage` | (domain_model) 100% of entities have a class |
| `table_refs` | (extraction) `source.table` exists in the extraction; warning only |
| `alignment_coverage` | (alignment) every class aligned, proposed or listed as unaligned |
| `alignment_concepts` | (alignment) every `upper_concept` and extension `parent` exists in the upper ontology |

## Output
`{passed, issues: [{severity: error|warning, message, subject}], checks: [{name, passed, detail}], score}`.
`passed` is false when any `error` issue exists; `score` is the fraction of checks without errors (1.0 = clean), used as
the acceptance `min_confidence` of the ontology agents.
