---
name: metadata-answerer
version: 1.0.0
pack: insights
stage: metadata_answer
kind: guarded
capabilities:
  intents: [metadata_question]
  data_sources: [catalog, knowledge_graph]
  consumes: [route]
  produces: [metadata_answer]
description: Answers a question ABOUT the schema or glossary from the KAG/catalog -- a term's definition, which entitled tables and columns exist, how they join -- with no model, no SQL and no execution.
dependencies: []
restricted: false
labels: [answered, empty]
validation:
  required_input: [query]
  required_output: [label, path_used]
examples:
  - input: {query: "what does approval rate mean and which tables hold it", context: {domain: lending}}
---

# metadata-answerer (DIF-33, the metadata chain)

The second selectable chain. When the router classifies a request as `metadata_question`, the agent
runs this skill instead of the SQL chain (schema-sliver -> query-generator -> executor -> assessor).
It answers questions about the schema and glossary themselves -- definitions, which tables and
columns exist, how tables relate -- and never produces or runs SQL.

## Input
- `query` (required): the question text.
- `context` (optional): hints, same as the other stages.

## Output
- `label`: `answered` (with `result_ref`, `columns`, `row_count`, `tables`, `narrative`) or `empty`.
- `path_used`: `kag` or `bypass` (which retrieval path produced the facts).

## How it works
1. It retrieves the caller's ENTITLED schema sliver exactly as schema-sliver does: KAG preferred,
   bypass as fallback. The app profile is the authority; the graph's persona links are hints only.
   No tables the caller may not see are ever revealed.
2. It turns the sliver's facts -- glossary definitions, tables, columns and 1-hop joins -- into a
   small result set (`aspect`, `name`, `detail`), held by reference like any other result. Rows are
   never copied into run state.
3. It returns a short, deterministic one-line summary as the narrative. No model is called.

If the caller is entitled to no table that matches the question, the label is `empty` and the
composer abstains ("no schema you can access matches this question"), which never leaks the
existence of tables the caller may not see.
