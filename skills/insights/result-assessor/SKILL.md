---
name: result-assessor
version: 1.0.0
pack: insights
stage: assessment
kind: agentic
capabilities:
  intents: [data_query]
  consumes: [execution]
  produces: [assessment]
description: Deterministic checks on the executed result (ran, empty, row count, null ratio, sliver coverage), an optional cheap judge, and a decision label that drives the refine loop.
dependencies: []
restricted: false
labels: [answer, refine_sliver, refine_query, escalate]
validation:
  required_input: [question, execution, sliver]
  required_output: [label, score, signals]
examples:
  - input: {question: "approval rate by product type", execution: "<output of governed-executor>", sliver: "<output of schema-sliver>"}
---

# result-assessor (the "A" between stages 7 and 9)

Decides whether the result can be answered, or whether the sliver or the query should be tried
again, and with what critique. Deterministic checks come first; a model judge is optional, off by
default, and never sees rows.

## Input
- `question`, `execution` (governed-executor output), `sliver` (the `Sliver` JSON).
- `generation` (optional: query-generator output, for `repairs` and the SQL), `attempt` (optional).

## Output
- `label`: `answer`, `refine_sliver`, `refine_query` or `escalate`.
- `score` (0 to 1, uncalibrated), `signals` (every check's value), `critique` (text for the next
  attempt, never containing row values).

## Decisions
| Situation | Label |
|---|---|
| `policy_denied`, `access_denied`, `timeout` (should not reach here: the agent ends them) | `escalate` |
| the query ran and failed (`error`) | `refine_query` with the error kind as critique |
| sliver coverage below 0.5 | `refine_sliver` naming the unmatched concepts |
| no rows, and coverage below 0.8 | `refine_sliver` |
| more than half of all cells NULL | `refine_query` |
| the judge (when enabled) says the SQL does not answer the question | `refine_query` with its issue |
| otherwise | `answer` |

The engine turns a refine label into `escalate` once `max_refines` is spent. When this skill asks
for a refine it drops the run's held rows: a refined query produces new ones, and stale rows must
not sit in memory or trip the gateway's rows-in-prompt check on the next attempt.
