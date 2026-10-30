---
name: validation-summary
version: 1.0.0
description: Merges the deterministic acceptance-check result and the optional llm-judge verdict into one validation report (passed, mean score, checks, concatenated findings, judge).
dependencies: []
validation:
  required_input: [check]
  required_output: [passed, score, checks, findings, judge]
examples:
  - input: {check: "<acceptance-check output>", judge: "<llm-judge output or null>"}
---

# Validation summary

Last step of the `validation-agent`. Exists because an agent's `persist.from` can only reference inputs and steps, and
the judge step may be skipped (its output is then `null`).

- `passed` = `check.passed` and (`judge.passed` when a judge ran).
- `score` = mean of `check.score` and `judge.score` (or `check.score` alone).
- `checks` = `check.checks`; `findings` = `check.findings` + `judge.findings`; `judge` = the judge output or `null`.

Output satisfies `contracts/validation-report.v1.json`.
