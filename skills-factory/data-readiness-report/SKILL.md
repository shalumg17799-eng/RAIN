---
name: data-readiness-report
version: 1.0.0
description: Builds the data-assets.v1 readiness report for a data-acquisition run - one entry per known table (landed, schema_only or missing), readiness_status, gaps, assumptions and landing URI.
dependencies: []
validation:
  required_input: [scenario]
  required_output: [scenario, readiness_status, tables, assumptions, gaps]
examples:
  - input: {scenario: uc2, extraction: "<schema-metadata-extractor output>", landed: "<data-landing output>", profiles: "<data-profiler output>"}
---

# Data Readiness Report (plan 5.7)

Output satisfies `contracts/data-assets.v1.json` and is persisted by `data-acquisition-agent` as `data_assets`.

## Input
- `scenario` (required): `uc1 | uc2 | uc3`.
- `extraction`: `tables`, `columns`, `lineage`, `unresolved_schemas` from `schema-metadata-extractor`.
- `landed`: `data-landing` output (`files[{table, uri, rows, format, schema_hash}]`, `written`, `synthetic`, `landing_uri`).
- `profiles`: `data-profiler` output (or its `profiles` map).
- `assumptions`: strings, possibly nested lists (flattened, nulls dropped).
- `provisional_schema`: `provisional-schema-generator` output (UC1); its tables count as known tables.

## Rules
- Known tables = extraction tables + provisional tables + landed tables (ordered, de-duplicated).
- `status`: `landed` when a written file with rows exists; `schema_only` when only columns are known; `missing` when
  nothing but the name is known (for example an unresolved schema).
- `source`: lineage system when known, else `synthetic` for synthetic data or provisional tables.
- `readiness_status`: `synthetic` when any synthetic data landed, otherwise `schema_only`. `validated` is reserved for
  real data in MVP-2 and is never produced here.
- `gaps`: one line per table without landed data and per landed table without a profile.

## Output
`{scenario, readiness_status, tables[{name, uri, format, rows, synthetic, source, schema_hash, status, profile}],
assumptions[], gaps[], landing_uri, provisional_schema, summary{landed, schema_only, missing}}`
