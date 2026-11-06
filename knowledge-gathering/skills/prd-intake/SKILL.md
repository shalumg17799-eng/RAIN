---
name: prd-intake
version: 1.0.0
description: Parses a PRD into a requirements artifact (title, use cases, entities, KPIs, policies, evidence) and detects the build scenario (uc1 provisional schema, uc2 supplied schemas, uc3 schemas through MCP). Deterministic baseline, optional LLM refinement.
dependencies: []
validation:
  required_input: [prd]
  required_output: [title, use_cases, entities_mentioned, scenario]
examples:
  - input: {prd: "<PRD text>", schemas: [loan_application, member]}
---

# PRD intake (plan 5.0)

Turns the PRD text into `requirements` (contract `contracts/requirements.v1.json`).

## Input
- `prd` (required): PRD text.
- `schemas` (optional): DDL texts or schema catalog names. Table names found in them are matched against the PRD
  (plural and spaced forms included) and added to the entities.
- `schema_calls` (optional): MCP calls `[{server, tool, arguments}]` whose results are DDL (scenario uc3).
- `sources` (optional): declared sources `[{name, type}]`; an `mcp*` / `*bitbucket*` type selects scenario uc3.
- `requirements` (optional): an existing requirements artifact to merge into (lists are unioned, nothing is dropped).
- `use_llm` (optional, default true): refine use cases and KPIs with the LLM when `DIF_LLM_PROVIDER` is not `none`.

## Deterministic rules
- `title`: first non-empty line (markdown `#` stripped); `summary`: the first two sentences of the body.
- `use_cases`: one per sentence mentioning dashboard | report | needs | shows | must | should | track | monitor,
  with `id` (`uc-<n>`), `name` (leading words), `description` (the sentence), `actors` (role words such as regulator,
  member, analyst, officer), `entities` and `kpis` found in that sentence.
- `entities_mentioned`: snake_case identifiers plus Title Case noun phrases (two or more words) from the body; system
  names that follow "sourced from" / "loaded from" and the like are excluded, schema table names mentioned in the text are added.
- `kpis`: phrases ending in rate | ratio | count | percent | % | score | total | average with the sentence as `definition`.
- `policies`: sentences mentioning regulator | compliance | policy | must | shall | audit.
- `scenario`: `uc3` when a `schema_calls` entry or an MCP/Bitbucket source is given, `uc2` when `schemas` are given,
  otherwise `uc1`; `scenario_reason` explains the choice.
- `evidence`: `{entity: [sentences]}`; `assumptions`: scenario and gap notes (for example an entity without a table).

## Output
`title`, `summary`, `use_cases[]`, `entities_mentioned[]`, `kpis[{name, definition}]`, `policies[]`, `scenario`,
`scenario_reason`, `sources_declared[{name, type}]`, `evidence`, `assumptions[]`, `method` (`rules` | `rules+llm`) and
`llm_error` when the optional LLM step failed (the baseline is still returned; LLM results only add, never remove).
