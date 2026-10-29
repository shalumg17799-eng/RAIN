---
name: llm-judge
version: 1.0.0
description: Scores an artifact against a stage rubric with the LLM (JSON verdict with findings); falls back to a heuristic key-presence verdict when the LLM is unavailable or fails.
dependencies: []
validation:
  required_input: [subject, rubric]
  required_output: [passed, score, findings, method]
examples:
  - input: {subject: "<artifact>", rubric: ["entities each have evidence", "relationships name both ends"], threshold: 0.6}
---

# LLM judge (plan 5.V)

Judgement half of the `validation-agent`; also used by the reconciliation agent to explain gaps.

## Input
- `subject` (required): artifact object or text.
- `rubric` (required): list of criteria strings, or one text (split on newlines / `; `).
- `context` (optional): extra text for the judge (stage, PRD excerpt).
- `threshold` (optional, default 0.6): minimum score for `passed` on the LLM path.

## LLM path (`DIF_LLM_PROVIDER` not `none`)
Asks for JSON `{passed, score, findings: [{severity, message}]}`; the score is clamped to 0..1, unknown severities
become `info`, and `passed` = model passed **and** score >= `threshold`. `method: llm`.

## Heuristic path (LLM unavailable or failed)
Checks the subject is non-empty, and every criterion that starts with an identifier (`title ...`, `entities_mentioned ...`,
`` `score` ... ``) for the presence of that key (substring for text subjects). Score = fraction of checks passed, or 0.5
when no criterion is checkable (0 for an empty subject); `passed` = score >= 0.5. Adds the info finding
`LLM unavailable: heuristic verdict` and, after an LLM failure, `llm_error`. `method: heuristic`.

## Output
`passed`, `score`, `findings[{severity, message}]`, `method`, plus `checks` (heuristic) / `threshold` (llm) and `llm_error` when degraded.
