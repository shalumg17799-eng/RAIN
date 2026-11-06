---
name: schema-metadata-extractor
version: 1.0.0
description: Reads a PRD and source schemas (names, DDL or column dicts) and produces a normalized metadata graph - entities, tables, columns, keys and lineage.
dependencies: []
validation:
  required_input: [prd, schemas]
  required_output: [metadata_graph, tables, columns, keys, lineage]
examples:
  - input:
      prd: "USSFCU Compliance Dashboard PRD"
      schemas: [loan_application, member, fair_lending_snapshot]
---

# Schema Metadata Extractor

**Process:** read schemas -> read PRD -> discover entities -> discover columns -> detect keys -> detect lineage.

## Input
- `prd` (str): PRD text.
- `schemas` (list): each item is a schema *name* (resolved from the schema catalog `samples/schemas/<name>.sql`),
  raw `CREATE TABLE` DDL, or `{name, columns:[{name,type,primary_key,references}], source}`.

## Output
`metadata_graph` (`nodes`, `edges`) plus flat views `tables`, `columns`, `keys`, `lineage`, and `undeclared_entities`
(snake_case identifiers in the PRD without a schema).

## Lineage rules
1. `-- source: <system>` comment in DDL. 2. PRD sentence "`<table>` ... sourced from/comes from `<system>`".
