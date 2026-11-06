---
name: domain-enricher
version: 1.0.0
description: Maps each table of a metadata graph to a business domain and capability using a taxonomy; returns confidence, evidence, unmapped tables and a domain catalog.
dependencies: []
validation:
  required_input: [extraction]
  required_output: [domain_catalog, tables, unmapped, confidence]
examples:
  - input: {extraction: "<output of schema-metadata-extractor>"}
---

# Domain Enricher (PRD US-010)

Turns technical metadata (tables, columns, keys, lineage) into business meaning: **domain -> capability -> tables**.

## Input
- `extraction` (required): output of `schema-metadata-extractor` (`tables`, `columns`, `lineage`).
- `taxonomy` (optional): an inline taxonomy object, or the name of a file in `assets/` (default `taxonomy`).
- `prd` (optional): PRD text; sentences that mention a table add evidence.
- `domain_model` (optional): a `domain-model.v1` artifact. An entity whose name tokens equal the table's (singular,
  order-insensitive: `Loan Applications` ~ `loan_application`) is attached to the table as `entity`; keyword hits in the
  entity's name, attributes and evidence sentences add evidence (`source: entity`, weight 2, max 2 per capability).
- `use_llm` (optional, default true): only acts when `DIF_LLM_PROVIDER` is not `none`, and only for tables left unmapped.

## Taxonomy format
```yaml
version: 1
domains:
  - name: Lending
    capabilities:
      - name: Loan Origination
        keywords: [loan, application, product_type]
```
## Scoring (deterministic)
Table-name keyword hit = 3, column-name hit = 1 (max 3 per capability), lineage source-system hit = 1, PRD sentence hit = 1 (max 2),
matching domain-model entity hit = 2 (max 2).
A table maps to its best capability when the score is at least `min_score` (default 3). Confidence = min(1, score / 6).
Tables below the threshold are listed in `unmapped` (confidence 0); they are never dropped.

## Output
- `tables`: per table `{domain, capability, confidence, score, evidence[], alternatives[], method, entity}` (`entity` is
  the matched domain-model entity id, or null)
- `domain_catalog`: `{taxonomy_version, domains: [{name, capabilities: [{name, tables}]}]}` (only non-empty entries)
- `unmapped`, overall `confidence` (mean over all tables), dominant `domain` and `capability`
- `llm_error` when the optional LLM step failed (the baseline result is still returned)
