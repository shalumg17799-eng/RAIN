---
name: package-assembler
version: 1.0.0
description: Assembles the versioned Knowledge Package tree (manifest, requirements, domain model, ontology, mappings, rules, data assets, provenance, quality, gaps) with checksums from the build-time artifacts.
dependencies: []
validation:
  required_input: []
  required_output: [package_version, files, manifest]
---

# Package assembler (plan 5.10, PRD section 7 of the architecture document)

Builds the `knowledge-package/` file set in memory; `package-store` writes it to the object store.

## Input
- `package_version` (semver string; defaults to `1.0.<n+1>` where n = knowledge packages already published for the enterprise), optional `enterprise_id` (defaults to the run's enterprise).
- Optional artifacts: `requirements`, `domain_model`, `ontology`, `alignment`, `semantic_mappings`, `domain_catalog`,
  `data_assets`, `kag_release`, `reconciliation`, `validation_reports` (list), `evaluation_report`, `business_rules`.
- Optional `artifact_ids` ({kind: id}) and `agent_versions`/`skill_versions`; when a `store` is in the context the
  versions of the agents and skills in this run's lineage (root run, its children) and the artifact ids they persisted are collected from the audit trail.

## Output
- `files[{path, kind, sha256, bytes, content}]` (content is the JSON/YAML text), `manifest` (contracts/manifest.v1.json
  minus `uri`s, which `package-store` fills in), `package_version`, `readiness`, `data_status`.
