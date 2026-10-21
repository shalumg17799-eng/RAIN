---
name: answer-composer
version: 1.0.0
pack: insights
stage: answer_composition
kind: guarded
capabilities:
  produces: [answer]
description: Builds the response contract from whatever the run produced (every exit path), applies the app's confidence threshold and SQL visibility, and adds the optional narrative over a masked sample.
dependencies: []
restricted: false
labels: []
validation:
  required_input: [question, steps, refine]
  required_output: [status]
examples:
  - input: {question: "approval rate by product type", steps: "$.steps", refine: "$.refine"}
---

# answer-composer (stage 9, Answer; HITL later)

The last step on every path. It reads whatever steps ran (`$.steps`) and the engine's refine state
(`$.refine`) and returns the `AnswerRecord` contract: the response body with data by reference. The
API joins the rows in from the result store when it builds the HTTP response.

## Status mapping
| What happened | Status |
|---|---|
| router said `denied` | `denied` (no role in this app) |
| router said `out_of_scope` / `needs_clarification` | that status, with hints drawn from the glossary and the app's exemplars |
| the sliver was empty, or no valid query could be produced | `abstained` with the reason |
| executor `policy_denied` / `access_denied` | `denied` |
| executor `timeout`, or a query error with no refine left | `failed` |
| assessor `escalate` after a run that produced rows | `abstained` (`low_confidence_after_refines`) |
| assessor `answer` but score below the app's `confidence_threshold` | `abstained` (`low_confidence`) |
| assessor `answer` above the threshold | `answered` |

Every answer carries assumptions, provenance and the confidence composite (uncalibrated until the
golden set exists), and the SQL only when the caller's role may see it (`sql_visibility`).

## Narrative
Off by default. When the app enables the `narrate` purpose, the model sees the column names, the
row count and a small MASKED sample (identifying text replaced by `***`), flagged `contains_rows`
so the gateway marks the call no-store. A failed narrative never fails the answer.
