---
name: entity-model-designer
description: Turn a Requirements IR and question registry into a database design — the tables, columns, keys, distributions, and relationships needed so every extracted question can be answered from real joins rather than from a script. Use this after the question registry exists; whenever the verifier reports a gap that needs a new table or column; or when someone asks what tables a set of questions requires. Also use when the entity model must be extended because a requirements document was revised.
---

# Entity model designer

Stage 3. Input is `requirements-ir.yaml` and `question-registry.yaml`. Output is
`entity-model.yaml`.

You design the database. Every extracted question, and every `frontend` question (one a
person can click in the product), must be answerable from it by a genuine query. That is the acceptance bar, and it is stricter than "plausible
schema" — a question that needs a trend cannot be served by a snapshot table, no
matter how sensible the table looks.

## Hard rule: no domain logic

You will design for healthcare, banking, telecom, and verticals nobody has built
yet. Work from the questions and the entity hints in the IR, not from industry
knowledge. If you are adding a table because you know the industry usually has
one, and no question needs it, do not add it.

## Workflow

### 1. Work backwards from the questions

For each extracted and frontend question, ask what the data must contain for it to be
answerable. A question about counts needs the entity. A question comparing two
periods needs history, not a current-state row. A question about why something
happened needs the two things being correlated plus a join path between them.

Build the table list from the union of those needs. Nothing else. Real source
systems have hundreds of entities; reproducing that surface area is a schedule
risk with no payoff.

### 2. Watch for questions that need aggregate history

The most common design failure. Questions phrased as trends, rates over time, or
before-and-after comparisons cannot be answered from a table of current records,
because the past state is gone. These need a separate table holding metric
history at a period grain.

Scan every question for this shape before finalising the table list. Discovering
it after generation means rebuilding.

### 3. Model absence deliberately

Several insights in any real document depend on something missing — a
notification that was not sent, a step that was skipped, a field never
populated. Absence is only derivable if it is representable: a nullable column
with a `null_rate`, or a row that legitimately does not exist.

A generator that fills every column destroys these insights silently. Record the
intent in the column's `note`.

### 4. Set distributions, never uniform

Every numeric and categorical column gets a distribution. Uniform random is the
default trap: real join selectivity, real query plans, and real answers all
depend on skew. Most entities have a long tail — most customers with one
account, a few with forty.

Use `lognormal` for durations and amounts, `zipf` for counts per parent,
`categorical` with explicit weights for enums, `faker` for identities.

### 5. Declare some relationships and not others

Within one source system, foreign keys are usually declared. Across source
systems they never are — there is no constraint spanning two vendors' databases.

Set `declared: false` for cross-source relationships with a reason. This matters
downstream: the ontology builder's relationship-inference path only gets
exercised if undeclared relationships exist.

Every table gets a `primary_key`, unless it appears in
`messiness_profile.tables_without_pk`. A table with no key cannot be referenced
by a foreign key, so any declared relationship pointing at it is unenforceable.

### 6. Set the messiness profile

Legacy or in-migration systems (flagged `is_legacy` in the IR) must not be
modelled clean. Opaque column names, tables without primary keys, coded values
with no lookup, orphan rows. Modern platform sources can be cleaner.

Record the rationale. Someone will later ask why the schema looks deliberately
bad.

### 7. Set primary_persona per table

Each table gets the persona whose questions it primarily serves. This tags the
knowledge graph so a persona-scoped view can be filtered out of one shared
graph, rather than needing a separate graph built per persona.

### 8. Report

Table and column counts, declared versus undeclared relationships, and then what
needs a human:

- Extracted or frontend questions you could not make answerable
- Questions whose committed figures have no clear derivation
- Tables no question touches
- Columns no question reads

## Output

YAML conforming to the supplied schema. Quote anything numeric-looking that is
not a number. No commentary before or after the YAML.

Copy `anchor_date` from the IR verbatim into the model. Do not recompute it, do
not omit it, do not set it to null if the IR has a value. The generator resolves
every timestamp against it, and a null here silently becomes the real current
date — which looks fine and makes every time-based question wrong.