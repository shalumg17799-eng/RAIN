---
name: prd-finalizer
version: 0.2.0
description: Deterministically assemble the PRD run report from whatever the run produced, on every exit path — which stages ran with what labels, runs and confidences, the schema-audit summary and the merged ontology audit. No model is ever called. Always the last step of the PRD graph, reached both on success and on every escalation route.
validation:
  required_input:
  - steps
  required_output:
  - run_report
---

# PRD finalizer

The PRD graph's answer-composer analogue: every route, success or escalation,
ends here, and the report says honestly what happened. Pure code over the
$.steps container; tolerant of stages that never ran.
