---
name: upper-ontology-aligner
version: 1.0.0
description: Aligns every class of a lower ontology to a concept of the governed upper ontology by keyword scoring (class name, description, properties, source table/entity), with confidence, relation kind, and extension proposals for classes below the threshold; optional LLM pass for unaligned classes.
dependencies: []
validation:
  required_input: [ontology]
  required_output: [upper_ontology_version, mappings, extensions_proposed, unaligned, confidence, validation]
examples:
  - input: {ontology: "<ontology.v1.json>"}
  - input: {ontology: "<ontology.v1.json>", upper_ontology: "<platform/ontology/upper-ontology.v1.json>", min_confidence: 0.4}
---

# Upper Ontology Aligner (PRD US-013)

Generic implementation (PRD US-012..US-015). To be reconciled with the ontology definitions from DIF-8 / DIF-9.

## Input
- `ontology` (required): `ontology.v1.json`.
- `upper_ontology` (optional): object with `concepts[{id, name, parent, keywords}]`; defaults to
  `platform/ontology/upper-ontology.v1.json` under `DIF_PLATFORM_DIR`.
- `semantic_mappings` (optional): tables mapped to a class's entity add their name tokens as evidence.
- `domain_model` (optional): entity description and evidence texts add evidence.
- `min_confidence` (default 0.3): below it a class is `unaligned` and an extension is proposed.
- `use_llm` (default true): only with `DIF_LLM_PROVIDER` != `none`; asks the model to pick a concept for unaligned classes
  (accepted only when the answer is a real concept id; confidence 0.4, evidence `llm`).

## Scoring (deterministic)
Tokens are taken from the class name (camel/snake split, plural-insensitive). A concept keyword (or its name) scores
3 per hit on class-name tokens, 2 on source table/entity tokens, 1 on description/evidence tokens (max 3) and 1 on data
property names (max 2). Keywords with `_` match as phrases. Confidence = min(1, score / 6). Ties go to the more specific
(deeper) concept. Relation: `exact` when the class name equals the concept name, `narrower` when confidence >= 0.5,
otherwise `related`.

## Output
`alignment.v1.json`: `upper_ontology_version, mappings[{class, upper_concept, relation, confidence, evidence}],
extensions_proposed[{name, parent, rationale, classes}], unaligned[], confidence (mean over all classes), validation{passed, issues}`,
plus `llm_error` when the optional LLM pass failed.
