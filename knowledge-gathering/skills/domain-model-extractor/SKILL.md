---
name: domain-model-extractor
version: 1.0.0
description: Extracts a draft domain model (entities, attributes, keys, relationships, constraints, glossary) from a PRD with sentence-level evidence; deterministic baseline, optional LLM refinement.
dependencies: []
validation:
  required_input: [prd]
  required_output: [entities, relationships, constraints, glossary, assumptions, confidence]
examples:
  - input: {prd: "The dashboard shows loan applications and members. Each member has many loan applications."}
---

# Domain Model Extractor (plan 5.1)

First step of `domain-modelling-agent`. Produces a **draft** model that `domain-model-normalizer` turns into a
`domain-model.v1.json` artifact.

## Input
- `prd` (required): PRD text.
- `requirements` (optional): output of `prd-intake` (`entities_mentioned[]` are added as candidates; `use_cases`,
  `kpis`, `evidence` are ignored for now).
- `domain_model` (optional): an existing model whose entities / relationships / constraints / glossary are merged in.
- `glossary` (optional): `[{term, definition}]` or `{term: definition}`; merged into the output glossary.
- `use_llm` (optional, default true): refinement only runs when `DIF_LLM_PROVIDER` is not `none`.

## Deterministic baseline
- **Entities**: snake_case identifiers (minus source-system names such as `... sourced from core_banking`), Title Case
  noun phrases (not at sentence start), object lists after verbs like *shows / tracks / needs* ("shows loan applications
  and members"), and `requirements.entities_mentioned`.
- **Attributes**: "`<entity>` has / with / includes a, b", `<entity>.<attr>` and `<entity>_<attr>` identifiers. Types are
  inferred from naming (`*_at` timestamp, `*_id` integer, `amount|rate|score` number, ...).
- **Keys**: id-like attributes (`id`, `<entity>_id`, `*_key`, `*_number`, `*_code`).
- **Relationships** (`one-to-many`): "`a` has many `b`", "`b` of `a`", "`b` belongs to `a`", and `<a>_id` attributes on `b`.
- **Constraints**: sentences with *must / cannot / only / at least / at most / never / always*.
- **Glossary**: "`X` is a/the ..." definitions.
- **Evidence**: every PRD sentence that mentions the entity, as `{"source": "prd", "text": sentence}`.

## LLM refinement (optional)
Asks for `{"entities": [{"name", "description", "attributes": [{"name", "type"}], "relationships": [{"to", "type"}]}]}`
and merges by normalised name. Entities known only to the LLM get `{"source": "llm", ...}` evidence. On any failure the
baseline is returned with `llm_error`.

## Output
`entities[{id, name, description?, attributes[{name, type}], keys[], evidence[]}]`, `relationships[]`, `constraints[]`,
`glossary[]`, `assumptions[]`, `confidence` (share of entities backed by a PRD sentence), `llm_error?`.
