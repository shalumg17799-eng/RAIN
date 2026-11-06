---
name: hitl-reviewer
version: 1.0.0
pack: insights
stage: hitl_review
kind: guarded
capabilities:
  intents: [data_query]
  consumes: [assessment]
  produces: [hitl_review]
description: Pauses the run for a human when confidence is low, a governance flag fired or the intent looks sensitive; resolves as approved, edited or rejected via the review API, or times out to an honest "could not verify".
dependencies: []
restricted: false
labels: [clear, approved, edited, rejected, timeout]
validation:
  required_input: [question]
  required_output: [hitl_review]
---

# hitl-reviewer (stage: hitl_review)

The deterministic gate between an assessed answer and the composer. The gate rules cannot be
bypassed and use no model:

1. **forced** — the caller asked for review (`force_review`).
2. **sensitive_intent** — the router's screening suspected prompt injection.
3. **governance_flag** — the execution returned masked columns, or the synthesis is partial
   (a source failed).
4. **low_confidence** — the assessment confidence is below the spec threshold.

No trigger → label `clear` and the run continues untouched. A trigger registers a hold in the
HITL store (question, SQL, reason, confidence, proposed narrative — never rows), emits a typed
`hitl_waiting` event, and blocks — bounded by the spec `timeout_ms` AND the run deadline. A
reviewer resolves it through the review API as approve / edit / reject; no decision in time
resolves as `timeout`, and the composer answers "could not be verified". Every resolution —
including the timeout — is written to the audit log as a `hitl_decision` event.

## Input
- `question` (required).
- `assessment` (optional): `{confidence, label, critique}` from the assessor.
- `execution` / `synthesis` / `route` / `generation` (optional): hold-trigger signals and the
  material a reviewer sees (SQL, masked columns, partial-source accounting).
- `force_review` (optional bool).
- `proposed_narrative` (optional): what the reviewer is approving, when already known.

## Output
- `hitl_review`: `{held, reason, decision, decided_by, edited_narrative, waited_ms}`.
- `label`: `clear` | `approved` | `edited` | `rejected` | `timeout`.
