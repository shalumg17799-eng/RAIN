---
name: domain-model-normalizer
version: 1.0.0
description: Deterministically normalises a draft domain model (snake_case singular ids, de-duplicated entities and attributes, validated relationships, evidence per entity) into a domain-model.v1.json artifact.
dependencies: []
validation:
  required_input: [domain_model]
  required_output: [entities, relationships, constraints, glossary, assumptions, confidence]
examples:
  - input: {domain_model: "<output of domain-model-extractor>"}
---

# Domain Model Normalizer (plan 5.1)

Second step of `domain-modelling-agent`. Pure function, idempotent: `normalize(normalize(x)) == normalize(x)`.

## Input
- `domain_model` (required): draft model (`entities[]` at least; `relationships`, `constraints`, `glossary`,
  `assumptions`, `confidence` optional). Entities may be strings or `{id|name, attributes, keys, evidence, description}`.

## Rules
- Entity ids are snake_case and singular (`Loan Applications` -> `loan_application`); entities that collapse to the same
  id are merged (attributes, keys, evidence unioned; first name wins).
- Attribute names are snake_case and unique per entity; `type`/`required`/`description` are kept when well-typed.
  Keys are kept as attributes (added when missing).
- Relationship `type` must be `one-to-one | one-to-many | many-to-many | many-to-one` (default `one-to-many`);
  `from`/`to` are normalised like entity ids and relationships whose ends do not exist are dropped with an entry in
  `assumptions`.
- Every entity keeps at least one evidence record (the contract requires it): entities without evidence get
  `{"source": "assumption", ...}` and an `assumptions` entry.
- `confidence` = share of entities with at least one `prd` evidence record.

## Output
`entities`, `relationships`, `constraints`, `glossary`, `assumptions`, `confidence` - valid against
`contracts/domain-model.v1.json`.
