---
name: domain-enricher
version: 1.0.0
description: Rain override of domain-enricher - identical scoring, but the Rain business taxonomy (enterprises/rain/config/taxonomy.yaml) is the default instead of the platform sample taxonomy.
enterprise: rain
dependencies: []
validation:
  required_input: [extraction]
  required_output: [domain_catalog, tables, unmapped, confidence]
examples:
  - input: {extraction: "<output of schema-metadata-extractor>"}
---

# Domain Enricher - Rain override

Returned by the skill registry only for runs started with `enterprise="rain"`; every other tenant keeps the shared
`skills/domain-enricher`. Same input/output contract (the registry rejects overrides that drop it).

## What differs
- Default `taxonomy` is `enterprises/rain/config/taxonomy.yaml` (version `rain-1`). An explicit `taxonomy` input still wins.
- Scoring, evidence, LLM fallback and output shape come from the shared implementation (`scripts/run.py` imports it by
  path) - no duplicated scoring code to drift.
