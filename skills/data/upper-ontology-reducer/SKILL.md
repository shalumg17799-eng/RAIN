---
name: upper-ontology-reducer
version: 0.2.0
pack: data
stage: ontology_reduction
kind: deterministic
capabilities:
  consumes: [ontology_drafts]
  produces: [upper_ontology]
description: Deterministically merge the per-persona upper-ontology slices into one graph — Personas by id, Concepts by normalized name with synonym union and an id remap, edges rewritten and deduped — then run the real ontology audit on the merged whole. Invalid edges, missing personas or dropped existing concept ids route back to the curator map (refine_ontology) with the specific problems as critique, bounded by max_refines. No model is ever called.
labels:
- ok
- refine_ontology
- escalate
validation:
  required_input:
  - requirements_ir
  - lower_ontology
  - results
  required_output: []
---

# Upper ontology reducer

The reduce node of the PRD graph's per-persona ontology fan-out. Pure code:
latest-attempt filtering, concept merge by meaning-preserving name key (first id
wins, synonyms union, duplicate_candidates recorded), edge id-remap and dedupe,
then `audit_upper_ontology` on the merged result. Audit findings become the
critique of a bounded refine loop back to the curator map; a clean audit flows
forward as ok.
