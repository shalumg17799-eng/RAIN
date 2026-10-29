---
name: data-profiler
version: 1.0.0
description: Profiles landed or in-memory tables (row count and per column null rate, distinct count, min, max, sample values), reading files back through the artifact store when needed. Deterministic, no LLM.
dependencies: []
validation:
  required_input: []
  required_output: [profiles, tables_profiled]
examples:
  - input: {tables: [{name: member, rows: [{id: 1, full_name: Ada}, {id: 2, full_name: null}]}]}
  - input: {files: [{table: member, uri: "file:///data/artifacts/landing/platform/run/member.csv"}]}
---

# Data Profiler (plan 5.7)

## Input (at least one)
- `tables`: `[{name, columns?, rows: [dict]}]` (for example the synthetic-data-generator output).
- `files`: `[{table, uri, format?}]`; a URI under the artifact store URL is read through `ctx["artifacts"]`, anything else
  is a local path (`file://` optional). CSV is always supported; Parquet needs `pyarrow`. Tables already profiled from
  `tables` are not re-read from `files`.

## Profile
Per table: `rows`, `columns: {name: {null_rate, distinct, min, max, sample}}`.
Null = `None` or empty string. When every non-null value parses as a number, min/max are numeric; otherwise they are the
lexicographic min/max of the string form. `sample` holds up to 3 distinct non-null values in order of appearance.
A file that cannot be read yields `{rows: null, columns: {}, error}` instead of failing the step.

## Output
`{profiles: {table: {rows, columns, source: rows|file, uri?}}, tables_profiled: [names]}`
