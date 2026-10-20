---
name: metric-layer
description: Write one verified SQL query per PRD figure (KPIs, signal headlines, signal sub-figures) so dashboards, chat and verification all share one definition.
---

# Metric layer

Every figure in the manifest gets exactly one metric: a read-only SELECT returning one number.
Dashboards, the AI layer and the conformance check all read these, so a figure can never show
two different values in two places.

## Rules

- Start from `list_figures` and `describe_schema`. Work through every `todo`.
- Write SQL from the figure's DEFINITION. Then compare with the PRD value `save_metric` returns.
  A mismatch is information, not a target to hit: check the definition against the data with
  `run_sql` (wrong filter? wrong grain? distinct vs rows? date window?). Fix the definition only
  when the new definition is a better reading of the PRD text.
- Never hard-code results, add filters whose only purpose is to hit a number, or pick a date
  window that is not in the PRD. If the honest definition does not match, leave the mismatch -
  agent 5 decides whether the data or the definition is at fault.
- Percent figures return the percentage (61, not 0.61). Use the app's fixed `today` from the
  manifest for "today" and "last N days" when it is set.
- A trend figure ("was 84%, now 61%") may read a trend table if the data has one; otherwise
  compute both periods from row-level data.
- Figures no data can support (population of a state, an estimated cost): `save_metric` with
  sql '' and a note. They are shown as static, never as live matches. Use this sparingly.
- The same business term must be computed the same way everywhere (e.g. one definition of
  "elevated-risk patient" reused by every figure that mentions it).
