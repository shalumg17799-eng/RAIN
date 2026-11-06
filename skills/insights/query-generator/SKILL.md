---
name: query-generator
version: 1.0.0
pack: insights
stage: query_generation
kind: agentic
capabilities:
  intents: [data_query]
  data_sources: [postgres]
  consumes: [sliver]
  produces: [sql]
description: Writes one validated SELECT for the question from the schema sliver, resolved dates, glossary definitions and reviewed examples, through the gateway purpose sql, with at most two repairs and never any execution.
dependencies: []
restricted: false
labels: [generated, unusable]
validation:
  required_input: [query, sliver]
  required_output: [label, dialect, model, prompt_version, prompt_hash, repairs, attempt]
examples:
  - input: {query: "approval rate by product type last quarter", sliver: "<output of schema-sliver>"}
---

# query-generator (stage 6, Query Generation)

The one stage that needs a strong model. Everything around it exists to make its output small,
grounded and checkable: the model sees only the entitlement-filtered sliver, explicit date ranges
resolved in code from the app calendar, the glossary's metric definitions and reviewed examples.
Its answer is untrusted text until the governed executor passes it; this skill never executes.

## Input
- `query` (required), `sliver` (required: the `Sliver` JSON from schema-sliver).
- `context` (optional): `component` and `variant` become result-shape hints.
- `intent` (optional): the router's classified intent, recorded as `router_intent`; advisory only.
- `concepts` (optional): the glossary terms the sliver matched, surfaced in the prompt as grounding.
- `critique` (optional): the assessor's note from the previous attempt. `attempt` (optional).

## Output
- `label`: `generated` (with `sql`, `assumptions`, `tables_used`, `dates`) or `unusable`
  (with `reason` and `problems`).
- `dialect`, `model` (the model id the gateway used), `prompt_version`, `prompt_hash`, `repairs`
  (0 to 2), `attempt`, `examples_used`.

## Checks on the model's answer
1. The gateway validates the JSON shape (`sql`, `assumptions`, `tables_used`).
2. sqlglot parses the SQL in the app's dialect: exactly one statement, a SELECT, no write anywhere.
3. Every table is in the sliver; every column resolves against the sliver's columns (AST check).
4. A failed check becomes a repair request naming the problems; at most two repairs, then
   `unusable`. `tables_used` is taken from the SQL itself, not from the model's claim.

Temperature is 0 (enforced by the gateway for the `sql` purpose). Prompts are versioned files in
`prompts/`; the hash of the rendered prompt travels with every answer for reproducibility.
