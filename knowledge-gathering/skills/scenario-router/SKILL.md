---
name: scenario-router
version: 1.0.0
description: Decides the data-acquisition scenario (uc1 no sources, uc2 schema only, uc3 schema read from a source system through MCP) from the inputs available and states the assumptions behind the decision.
dependencies: []
validation:
  required_input: []
  required_output: [scenario, reason, assumptions, has_schema, has_sources]
examples:
  - input: {extraction: {tables: [member, loan_application]}}
  - input: {schema_calls: [{server: oracle-mcp, tool: get_ddl}]}
---

# Scenario Router (plan 5.7)

Deterministic routing for `data-acquisition-agent`. No LLM.

## Input (all optional)
- `scenario`: explicit `uc1 | uc2 | uc3`; always wins.
- `requirements`: a `requirements.v1` object; a `scenario` field on it is honoured next.
- `extraction`: output of `schema-metadata-extractor`; non-empty `tables` means a schema is known.
- `schemas`: schema names or DDL strings (same meaning).
- `schema_calls`: MCP calls that read DDL from a source system (UC3).
- `sources`: source descriptors; an entry with `type: mcp` (or `server`/`tool` keys) counts as an MCP source (UC3).

## Decision
1. explicit `scenario`, else `requirements.scenario`
2. `uc3` when MCP schema calls or MCP sources are given
3. `uc2` when a schema is known (`extraction.tables` or `schemas`)
4. `uc1` otherwise (provisional schema from the domain model, synthetic data)

## Output
`{scenario, reason, assumptions[], has_schema, has_sources, method: explicit|requirements|inferred}`
