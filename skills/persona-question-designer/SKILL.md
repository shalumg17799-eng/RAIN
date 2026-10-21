---
name: persona-question-designer
version: 0.2.0
description: Expand a Requirements IR into a complete tiered question registry organized by persona — keeping the questions stated in the document, deriving the ones each persona would plausibly ask but the document never listed, and generating systematic coverage questions from the entity model. Use this after the requirements interpreter has run; whenever a requirements document has personas but no question list; whenever the entity model changes and the question set must be resynced; or when someone asks whether the question set is hardcoded.
labels:
- ok
- escalate
- refine_self
validation:
  required_input:
  - requirements_ir
  required_output:
  - confidence
---

# Persona question designer

Stage 2. Input is `requirements-ir.yaml`. Output is a tiered question registry.

This is where the system stops being a list of questions someone typed and
starts being a measurable claim about what the data supports.

## The three tiers

| Tier | Where it comes from | Contractual? | May trigger schema change? |
|---|---|---|---|
| `extracted` | Stated in the document | Yes | Yes, automatically |
| `derived` | Inferred from the persona's role and problems | No | No — human decides |
| `schema_generated` | Walked from the entity model | No | No — human decides |

The last column is load-bearing. If derived questions could force schema
additions, the gap-closure loop never converges: propose a question, find it
unanswerable, add a table, propose questions about the new table, repeat.

## Hard rule: no domain logic

The same process runs for any vertical. Do not use industry knowledge. Work
only from what the IR records about each persona — their role, altitude, and
stated problems.

## Your task here

You are given personas with their existing questions. Propose **additional**
questions each persona would plausibly ask that the document does not list.

Useful angles, none domain-specific:

- Each stated problem, turned into a question that would diagnose it
- The persona's altitude: executives ask about aggregates and trends,
  operational roles ask about current state and what to do next, frontline
  roles ask about one case at a time, technical roles ask about the data itself
- Follow-ups to existing questions — after any answer, the natural next
  question is usually why, compared to what, or what now
- Their systems: each one they use is something they might ask about

Aim to cover each persona's stated problems rather than hit a target count. A
persona with two problems does not need fifteen questions.

Skip anything equivalent to a question already listed. The stated one wins.

## When the document stated no questions at all

If a persona has no existing questions, the entire set for them will be your
proposals and none of it is contractual. Be more conservative in that case:
propose what the stated problems clearly imply, and no more. Somebody will read
these and may mistake them for client requirements, so do not pad.

## Flagging non-data questions

Some questions cannot be answered from data — a UI action, an offline sync, a
mapping to an external taxonomy. Mark these rather than carrying them forward
as unsatisfiable requirements.

## Output

YAML only. A list of items, each with `persona_id`, `text`, and `signal`.
No commentary before or after.