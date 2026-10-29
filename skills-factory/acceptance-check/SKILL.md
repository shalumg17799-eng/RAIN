---
name: acceptance-check
version: 1.0.0
description: Deterministic validation of any artifact - JSON Schema contract, numeric thresholds, required keys and cross references - returning a validation report with per-check results and findings.
dependencies: []
validation:
  required_input: [subject]
  required_output: [passed, score, checks, findings]
examples:
  - input: {subject: "<artifact>", contract: domain-model.v1.json, thresholds: {"$.confidence": 0.7}, required_keys: [entities]}
---

# Acceptance check (plan 5.V)

Deterministic half of the `validation-agent`. Output satisfies `contracts/validation-report.v1.json`.

## Input
- `subject` (required): the artifact (object) to validate.
- `contract` (optional): JSON Schema file name in `DIF_CONTRACTS_DIR` (for example `requirements.v1.json`).
- `thresholds` (optional): `{"$.path": minimum}`; every value at the path must be a number `>= minimum`.
  Paths are relative to the subject: `$.a.b`, `$.items[0].score`, `$.tables[*].confidence` (`[*]` expands lists and dict values).
- `required_keys` (optional): top-level keys that must be present and non-empty.
- `cross_refs` (optional): `[{from: "$.a[*].x", in: "$.b[*].id"}]`; every value at `from` must occur among the values at `in`.

## Checks
`subject:non_empty` always; `schema:<contract>`, `threshold:<path>`, `key:<name>`, `cross_ref:<from>-><in>` as configured.
A missing contract file or an unresolvable threshold path is a failed check, never an exception.

## Output
`passed` (all checks passed), `score` (fraction of checks passed), `checks[{name, passed, detail}]`,
`findings[{severity, message}]` (one `error` per failed check; an `info` when nothing was configured), `judge: null`.
