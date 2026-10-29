---
name: data-landing
version: 1.0.0
description: Lands table rows as CSV (or Parquet when pyarrow is available) plus a _manifest.json in the artifact object store under landing/<enterprise>/<run>/ ("Bronze-lite"); dry runs only plan the URIs.
dependencies: []
validation:
  required_input: [tables]
  required_output: [landing_uri, files, written]
examples:
  - input: {tables: [{name: member, columns: [id, full_name], rows: [{id: 1, full_name: Ada}]}], synthetic: true, source: synthetic-data-generator}
---

# Data Landing (plan 5.7, "Bronze-lite")

Writes through `ctx["artifacts"]` (`dif.artifacts.store.ArtifactStore`, fsspec: file://, az://, s3://, gs://).

## Input
- `tables` (required): `[{name, columns?, rows: [dict]}]`; `columns` defaults to the ordered union of row keys.
- `format`: `csv` (default) or `parquet` (only when `pyarrow` imports; otherwise CSV is written and `note` says so).
- `prefix`: default `landing`.
- `synthetic` (bool) and `source` (string): recorded in the manifest.

## Layout
`<prefix>/<enterprise or platform>/<run_id>/<table>.<format>` and `<prefix>/<enterprise>/<run_id>/_manifest.json`
(`{run_id, enterprise, synthetic, source, format, files[], created_at}`).
CSV cells: `None` -> empty, booleans -> `true`/`false`, everything else `str()`.

## Output
`{landing_uri, manifest_uri, files: [{table, uri, path, rows, bytes, schema_hash, format, columns}], written, synthetic,
source, format, note?}`. `schema_hash` is the sha256 of the comma-joined column names.
With `dry_run` or without an artifact store nothing is written: `written: false` and the URIs are the planned ones
(`<store url>/<path>` when a store exists, else `file://<path>`).
