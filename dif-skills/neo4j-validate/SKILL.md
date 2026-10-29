---
name: neo4j-validate
version: 1.0.0
description: Validates a KAG release in Neo4j (orphan Enterprise nodes, classes without ALIGNS_TO, tables without MAPS_TO, nodes missing provenance); without a configured driver or on dry runs it runs the same checks on the in-memory records.
dependencies: []
validation:
  required_input: [release]
  required_output: [passed, issues, checks]
examples:
  - input: {release: "rel-42"}
  - input: {release: "rel-42", nodes: "<records>", relationships: "<records>"}
---

# Neo4j Validate (PRD US-014, plan 4.3)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

## Input
- `release` (required); `enterprise` (default ctx enterprise, else `default`).
- `nodes`, `relationships` (optional): records from `kag-model-mapper`, used for the in-memory validation when there is
  no driver (`DIF_NEO4J_URI` empty), `ctx.dry_run` is set, or `in_memory: true` is passed (used by `kag-builder-agent` to
  validate the records *before* anything is written to Neo4j).

## Checks
| name | severity | rule |
|---|---|---|
| `release_present` | error | the release has at least one Enterprise node |
| `orphan_nodes` | error | Enterprise nodes with no relationship |
| `classes_aligned` | warning | `Class` nodes without `ALIGNS_TO` (unaligned classes await the extension gate) |
| `tables_mapped` | warning | `Table` nodes no class `MAPS_TO` |
| `provenance_present` | error | Enterprise nodes with an empty `provenance` list |

With a driver the checks are Cypher counts scoped by `enterprise_id` and `release`; `_driver_factory` is injectable like
in `neo4j-publish`.

## Output
`{passed, issues[{severity, message, count, subjects?}], checks[{name, passed, detail}], mode: graph|memory}`;
`passed` is false when an `error` issue exists.
