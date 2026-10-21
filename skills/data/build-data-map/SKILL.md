---
name: build-data-map
version: 0.2.0
pack: data
stage: data_mapping
kind: deterministic
capabilities:
  consumes: [entity_model]
  produces: [data_map]
description: Deterministically turn an entity model into the connected data map (the lower ontology of Entity and Attribute nodes with HAS_ATTRIBUTE and REFERENCES edges) and audit it against the known source CSV headers and the committed PostgreSQL catalog snapshot. No model is ever called. Use after the entity model exists; its label routes near-miss names back to the entity designer while genuinely new proposed tables flow forward as review items.
labels:
- ok
- refine_entity_model
- escalate
validation:
  required_input:
  - entity_model
  required_output:
  - lower_ontology
  - schema_audit
---

# Build data map

Stage 4 of the PRD design chain, and deliberately the one with no model anywhere:
the data map and its audit are facts derived from the entity model, not judgment.

- `build_lower_ontology` flattens the model into Entity/Attribute nodes and
  HAS_ATTRIBUTE/REFERENCES edges.
- `compare_schema` audits the model's names against the source CSV headers and the
  committed catalog snapshot (never a live database).
- `datamap_label` turns the audit into a routing label: a model table or column whose
  name NEARLY matches a source one (similarity >= 0.55) is a defect worth one bounded
  refine of the entity model, with the specific near-misses as the critique; everything
  else — including genuinely new proposed tables — is a review item and flows forward.
