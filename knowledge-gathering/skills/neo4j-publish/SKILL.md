---
name: neo4j-publish
version: 1.0.0
description: Idempotently writes node and relationship records to Neo4j (MERGE on key, enterprise_id and release; batched UNWIND); skips the connection on dry runs or when DIF_NEO4J_URI is not configured and reports counts.
dependencies: []
validation:
  required_input: [nodes, relationships, release]
  required_output: [published, release, counts, dry_run]
examples:
  - input: {nodes: "<kag-model-mapper nodes>", relationships: "<kag-model-mapper relationships>", release: "rel-42"}
---

# Neo4j Publish (PRD US-014, plan 4.3)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

Shared skill: writes KAG records produced by `kag-model-mapper` (use-case KAG) or `platform-kag-seed` (platform KAG).

## Input
- `nodes` (required): `[{key, labels, props}]`; `relationships` (required): `[{type, from, to, props}]`.
- `release` (required): snapshot id; `enterprise` (default: ctx enterprise, else `default`); `batch_size` (default 500).

## Writes
Labels and relationship types cannot be parameterised in Cypher, so rows are grouped per label set / type and the label
string is built from a whitelist (`[A-Za-z]+` labels, `[A-Z_]+` types). Per label set:
```
UNWIND $rows AS r MERGE (n:Enterprise:Class {key: r.key, enterprise_id: r.enterprise_id, release: r.release}) SET n += r.props
```
`Platform` nodes (no `Enterprise` label) merge on `key` only. Relationships match both ends by key within the same
enterprise/release (or any `Platform` node) and `MERGE` the typed relationship, then `SET rel += r.props`. Re-running the
same release is a no-op apart from property refresh.

## Connection
`DIF_NEO4J_URI`, `DIF_NEO4J_USER`, `DIF_NEO4J_PASSWORD` (`dif.config.settings`). The module-level `_driver_factory(uri, user,
password)` returns the driver (default `neo4j.GraphDatabase.driver`); tests replace it with a fake exposing
`session()` and `session.run(cypher, **params)`. With `ctx.dry_run` or an empty URI nothing is connected:
`published: false` with counts computed from the records and a `note`.

## Output
`{published, release, counts{nodes, relationships, by_label, by_type}, dry_run, note?}`.
