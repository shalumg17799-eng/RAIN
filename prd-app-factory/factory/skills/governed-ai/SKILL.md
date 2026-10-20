---
name: governed-ai
description: Build the knowledge layer (ontology, glossary, knowledge graph, join hints, reviewed examples) and the governed AI profile (per-persona table access and row-level security) for the app's natural-language question answering.
---

# Knowledge layer and governed AI profile

## Ontology (`save_ontology`)

- 10-25 business concepts the PRD uses: the cohorts, statuses and measures people will ask about.
- Each with a precise definition matching the metric layer, synonyms people actually say, the
  table.column fields it maps to, and an `expression` (a SQL predicate or aggregate) when it is a
  computed concept. Phrases must be unique across all terms.

## Join hints (`save_join_hints`)

Every foreign-key style link between tables (child.fk -> parent.key, shared codes like ZIP).
Call this before `save_ontology` so the graph gets the links.

## Examples (`save_examples`)

5-10 reviewed question/SQL pairs for the most important PRD questions, reusing the metric layer's
SQL. They teach the AI layer the house definitions.

## Governed profile (`save_governed_profile`)

- One entry per persona. Grant only the tables the persona's job needs (least privilege): an
  operations role does not need clinical detail tables; a data-engineering role gets feed and
  quality tables, not personal records.
- Row-level security: when personas have a `scope` in the manifest, filter the table holding that
  attribute with `col = ANY(string_to_array({attr}, ':'))` and make child tables follow it with
  `fk IN (SELECT key FROM <schema>.<parent>)`. At least one row filter is required.
- A child-table filter that reads a parent table only works for personas granted the parent too.
- `sql_visible`: technical/analyst personas only.
- Exemplars: data_query from the personas' questions; metadata_question ("what does X mean",
  "which tables hold Y"); out_of_scope and needs_clarification with 2 examples each.
