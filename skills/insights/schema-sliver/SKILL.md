---
name: schema-sliver
version: 1.0.0
pack: insights
stage: schema_slicing
kind: guarded
capabilities:
  intents: [data_query]
  data_sources: [catalog, knowledge_graph]
  consumes: [route]
  produces: [sliver]
description: Finds the few entitled tables, columns, joins and glossary terms a question needs, by the KAG path when preferred and available, else by catalog retrieval (bypass).
dependencies: []
restricted: false
labels: [ok, empty]
validation:
  required_input: [query]
  required_output: [sliver, coverage, path_used]
examples:
  - input: {query: "approval rate by product type last quarter", path_preference: bypass}
---

# schema-sliver (stage 5, Schema Sliver)

Turns a question into a small schema sliver: tables, columns, joins, glossary terms, a coverage
score and provenance. Uses no model. The entitlement filter runs before any ranking, so nothing the
caller may not query can appear in the sliver, influence a score or change the coverage number.

## Input
- `query` (required).
- `path_preference` (optional, default `bypass`): `kag` or `bypass`, from the router.
- `context` (optional): market, product and domain narrow the candidates (relevance, never access).
- `attempt` (optional, default 0): the refine attempt. Each attempt widens the search by one hop
  and adds neighbouring tables (a `refine_sliver` retry).
- `critique` (optional): the assessor's note from the previous attempt (recorded, not parsed).

## Output
- `sliver`: the `Sliver` contract as JSON (tables with columns, joins, glossary terms, coverage,
  `path_used`, `catalog_version`, provenance).
- `coverage`: the share of the question's concepts the sliver can speak to.
- `path_used`: `bypass` or `kag`. `unmatched`: concepts nothing visible can answer.
- `label`: `ok`, or `empty` when no table could be retrieved (no role, or nothing matched).

## Probe and fall back
When `path_preference` is `kag`, the KAG is probed first. If it is unavailable, fails, or covers
too little of the question, retrieval falls back to the catalog (`bypass`) and the reason is
emitted as a progress note (`kag_unavailable`, `kag_error`, `kag_low_coverage`). Today the KAG is a
stub that reports itself unavailable, so every run takes the bypass path and says so.
