---
name: synthesizer
version: 1.0.0
pack: insights
stage: synthesis
kind: guarded
capabilities:
  intents: [data_query]
  consumes: [execution]
  produces: [synthesis]
description: Merges per-source execution summaries into one synthesis — counts, shapes and failure accounting only, never rows — and labels the result ok, partial (some sources failed) or all_failed.
dependencies: []
restricted: false
labels: [ok, partial, all_failed]
validation:
  required_input: [question]
  required_output: [synthesis]
---

# synthesizer (stage: synthesis)

Combines what the governed executor produced — for one source or for a fan-out over several —
into a single synthesis the assessor and composer can reason about. The merge is a deterministic
core that cannot be bypassed: per-source status, row counts, column shapes, masked-column counts
and typed failures. A model (purpose `narrate`) may add one short cross-source note when more
than one source succeeded; a gateway failure just drops the note.

## Invariants
- The synthesizer NEVER sees rows. Its input is execution summaries (status, counts, columns,
  result refs); a `rows` key anywhere in the input is refused outright.
- A failed source never kills the answer: the synthesis is labeled `partial` and says which
  sources failed and why, so the composer can answer from what succeeded and say what is missing.

## Input
- `question` (required).
- `executions` (optional): a list of `{source, execution}` entries from a per-source fan-out.
- `execution` (optional): a single execution record (the 1-source path). One of the two is
  required.

## Output
- `synthesis`: `{sources: [{source, status, row_count, truncated, masked_columns, result_ref}],
  succeeded, failed: [{source, status}], partial, note}`.
- `confidence_hint`: the fraction of sources that succeeded.
- `label`: `ok` (every source answered), `partial` (some failed), `all_failed`.
