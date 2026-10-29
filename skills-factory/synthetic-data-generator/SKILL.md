---
name: synthetic-data-generator
version: 1.0.0
description: Generates deterministic, seeded synthetic rows for a set of typed tables with foreign-key integrity (parents first), name/type value heuristics via Faker, and per-table row counts. Output is always marked synthetic.
dependencies: []
validation:
  required_input: []
  required_output: [tables, synthetic, seed, row_counts, notes]
examples:
  - input: {tables: [{name: member, columns: [{name: id, type: BIGINT, primary_key: true, nullable: false}, {name: full_name, type: "VARCHAR(120)", primary_key: false, nullable: false}]}], rows_per_table: 20, seed: 7}
  - input: {extraction: "<output of schema-metadata-extractor>", rows_per_table: 100}
---

# Synthetic Data Generator (plan 5.7)

No LLM: `random.Random(seed)` + `Faker` seeded with the same seed, so the same input yields the same rows.

## Input
One table specification (first match wins):
- `tables`: `[{name, columns: [{name, type, primary_key, nullable, references?}]}]` (provisional-schema or `parse_ddl` shape).
- `tables_from_schema` / `tables_provisional` + `scenario`: the agent passes both; `uc1` prefers the provisional tables,
  `uc2`/`uc3` prefer the schema tables, falling back to whichever is present.
- `extraction`: `schema-metadata-extractor` output (`tables`, `columns`, `keys`, `metadata_graph`); column types are taken
  from the graph nodes' `data_type`, VARCHAR otherwise.

Options: `rows_per_table` (default 50, clamped 1..5000), `overrides` `{table: rows}`, `seed` (default 42),
`anchor_date` (ISO date for "within the last 3 years"; default today).

## Generation
- Tables referenced by foreign keys are generated first (topological order, stable); cycles are broken with a note.
- Primary keys are sequential (`1..n`, or `<TABLE>000001` for character types); FK values are drawn from the parent's
  generated keys, so every FK resolves. Nullable, non-key columns get ~5% nulls.
- Values by column name (`email`, `*name*`, `phone`, `address`, `city`, `state`, `country`, `zip`, `status`,
  `product_type`, `*_type`, `amount|price|balance|total`, `rate|ratio|score`, `*_at|*_date`, `is_*|has_*`, `count|qty`) and
  otherwise by SQL type (boolean, integer, numeric, date, timestamp, character).

## Output
`{tables: [{name, columns: [names], rows: [dict], row_count, source?}], synthetic: true, seed, row_counts: {table: n},
notes[], order: [table names in generation order]}`. Rows carry no marker column; the landing manifest marks them synthetic.
