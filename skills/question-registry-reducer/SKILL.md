---
name: question-registry-reducer
version: 0.2.0
description: Deterministically merge the per-persona question-designer fan-out results into one question registry — keep only the latest dispatch attempt, drop exact duplicates per persona, and re-validate the merged whole (tier vocabulary, persona referential integrity, preservation of every extracted question). No model is ever called. Use as the reduce node after the persona-question-designer map step.
labels:
- ok
- escalate
validation:
  required_input:
  - requirements_ir
  - results
  required_output: []
---

# Question registry reducer

The reduce node of the PRD graph's per-persona question fan-out. Pure code:
latest-attempt filtering, duplicate removal by (persona_id, normalized text),
and the same global validation that judges a single-run registry. Any persona
run that escalated, or a merged registry that fails validation, escalates with
the specific reasons; nothing is repaired silently.
