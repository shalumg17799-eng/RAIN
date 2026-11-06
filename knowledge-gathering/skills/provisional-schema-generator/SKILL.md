---
name: provisional-schema-generator
version: 1.0.0
description: Derives a provisional relational schema (typed tables, keys, foreign keys and DDL) from a domain model when no source schema exists (UC1). Deterministic name-based type inference; every table is marked source synthetic.
dependencies: []
validation:
  required_input: [domain_model]
  required_output: [ddl, tables, assumptions]
examples:
  - input: {domain_model: "<domain-model.v1 object: entities[{id, name, attributes[{name, type}], keys}], relationships[{from, to, type}]>"}
---

# Provisional Schema Generator (UC1, plan 5.7)

Turns a `domain-model.v1` object into tables so synthetic data can be generated and landed without a source system.

## Rules
- One table per entity; the table name is the snake_cased entity `id`.
- Columns come from `attributes`. Declared attribute types are mapped (`string`, `integer`, `number`, `boolean`, `date`,
  `datetime` ...); otherwise the type is inferred from the name:
  `*_id` -> BIGINT, `*_at` / `*_date` / `date*` -> TIMESTAMP, `amount|price|balance|total|score|rate|ratio` -> NUMERIC(12,2),
  `is_*|has_*|*flag*` -> BOOLEAN, `count|number|qty|quantity` -> INTEGER, else VARCHAR(100).
- Primary key: `entity.keys` (added as BIGINT when not an attribute), else an added `id BIGINT`.
- Foreign keys from `relationships`: `one-to-many` / `has_many` from A to B gives B `a_id BIGINT REFERENCES a(<pk>)`;
  `many-to-one` gives A `b_id`; `one-to-one` gives B `a_id`; `many-to-many` creates a junction table `a_b`.
  An existing attribute named like the FK column is reused.

## Output
- `ddl`: one `CREATE TABLE` per table, each preceded by `-- source: synthetic` (parseable by `schema-metadata-extractor`).
- `tables`: `[{name, columns: [{name, type, primary_key, nullable, references?}], source: "synthetic"}]`
  (`references` is `"table.column"`).
- `assumptions[]`: every inference that was not stated by the domain model.
