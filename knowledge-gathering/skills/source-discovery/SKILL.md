---
name: source-discovery
version: 1.0.0
description: Probes the declared schema sources (Bitbucket through MCP, local schema catalog, inline DDL, none) and returns a source inventory with per-file hashes and sizes and an access status; never raises, failures are recorded per source.
dependencies: []
validation:
  required_input: [sources]
  required_output: [sources, summary]
examples:
  - input: {sources: [{name: bb, type: mcp-bitbucket, server: atlassian, calls: [{tool: getBitbucketFile, arguments: {path: db/member.sql}}]}, {name: cat, type: catalog, paths: ["*.sql"]}]}
---

# Source discovery (plan 5.3)

Member of the discovery group. Output satisfies `contracts/source-inventory.v1.json`.

## Input
`sources` (required): list of `{name, type, ...}` with `type`:
- `mcp-bitbucket`: `server` + `calls: [{tool, arguments}]`; each call's text result is one file (`path` from the `path` /
  `file` / `filename` / `name` argument, else the tool name). Status `reachable` when at least one call succeeded
  (failures listed in `error`), `unreachable` when all failed, `not_configured` without `server`/`calls`.
- `catalog`: `paths` globs (default `*.sql`) in `DIF_SCHEMA_CATALOG`; `reachable` when files match, else `unreachable`.
- `ddl-inline`: `ddl` (text or list); status `inline`.
- `none` or unknown type: `not_configured` (unknown types carry an `error`).

## Output
`sources[{name, type, status, files[{path, hash (sha256 of the text), bytes}], error}]` and
`summary {reachable (sources with status reachable or inline, i.e. usable), total, files}`.
The skill never raises: an exception while probing a source gives it status `unreachable` and the message in `error`.
