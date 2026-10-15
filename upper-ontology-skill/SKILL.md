---
name: upper-ontology-curator
description: Maps ANY incoming data source's raw schema (table/column names, types, relationships — from any client, vertical, or system) to Data Factory's shared upper ontology of domain-neutral business concepts (Constituent, Provider, Episode, etc. — never a domain-flavored name like "Patient" or "Care Episode" as the canonical concept), producing generic graph-shaped output (nodes/edges) rather than anything tied to one client's structure. Use this skill whenever a new data source needs to be connected, whenever mapping raw fields to business meaning, whenever checking whether a proposed concept already exists (duplicate detection), or whenever a vertical pack's ontology.yaml needs to be built or extended. Do not build one-off, hardcoded schema mappings for a single client when this skill applies — the whole point is that the same process runs unchanged for RAIN or any future source.
---

# Upper Ontology Curator

Maps a data source's raw schema to Data Factory's shared business-concept
layer (the "upper ontology" — see Knowledge Layer, E5 epic). This is a
**generic** process: it must work identically whether the incoming schema
is RAIN's 11 healthcare sources or a vertical nobody has built yet. Never write client-specific mapping logic —
if a step below needs client knowledge, that knowledge comes from the input
schema, not from code that only knows one client.

## When to use this

- A new data source is being onboarded (any vertical, any client)
- A vertical pack's `ontology.yaml` needs to be built or extended
- Someone asks "does a concept for X already exist" before adding a new one
- A mapping needs re-running because a source schema changed

## Input

Any schema description, in whatever form it's available:
- Table/column names and types (from schema introspection, a DDL dump, or
  a data dictionary)
- Sample field names + a few distinct values (never full rows — this skill
  never needs row-level data, matching the Semantic Twin's read-only
  contract: schema and structure only, no PII)
- An existing upper-ontology concept list, if one exists yet (empty on the
  very first run)

## PRD handoff

This schema-mapping skill does not interpret a raw PRD. When a PRD is the
starting point, first use `skills/skills/requirements-interpreter/SKILL.md`,
then the persona-question and entity-model skills, and build or inspect the
lower ontology from the resulting schema. Pass the resulting tables, columns,
relationships, and existing concepts into this skill; never invent missing
columns to make a PRD question appear answerable.

This skill's output is concept-to-source-field mappings. If the requested
artifact also needs Persona nodes and `SERVES` edges, use
`skills/skills/upper-ontology-curator/SKILL.md` as the PRD-workflow stage. Do
not treat this schema-only output as a complete PRD-to-ontology run.

## Process

1. **Infer candidate concepts.** For each table/field, infer what business
   concept it represents. Use naming, type, and relationship context —
   `patient_id` (string, FK-like) and `member_id` (string, FK-like) in two
   different sources are both candidate matches for the same concept, even
   though the field names differ. This step is where an LLM earns its keep;
   don't try to solve this with exact-string matching alone.

2. **Categorize each mapping's confidence.** No real scoring model exists
   yet, so don't fake precision with a made-up float — use a plain category:
   - **auto-eligible** — same field name/type/role across sources, or an
     unambiguous synonym (`patient_id` → `Constituent` in two sources
     spelled identically)
   - **needs-review** — a plausible match, but inferred across differently-
     named fields, or the concept's own name/definition might not fully fit
     the new domain yet
   - **low-confidence** — a weak or partial match; probably not the same
     concept, but worth surfacing rather than silently dropping
   When a real similarity/scoring mechanism exists later, these categories
   can be backed by actual numbers — don't invent numbers before that exists.

3. **Check for duplicate concepts.** Before adding a new concept, compare it
   against the existing upper-ontology list. Two concepts with different
   names but overlapping definitions are duplicate candidates — flag them,
   don't silently merge, and don't silently keep both. A human resolves
   which.

4. **Detect coverage gaps**, not just missing mappings. A gap is a place
   where two existing concepts *should* connect but nothing in the schema
   says so explicitly — these are easy to miss because nothing is technically
   wrong, the connection is just absent. See the worked example below for a
   real one this exact process caught.

5. **Gate on category, not on convenience.** `auto-eligible` mappings merge
   automatically. `needs-review` and `low-confidence` both go to the
   human-in-the-loop queue — don't auto-merge either just because the
   mapping-coverage number looks better if you do.

6. **Emit graph-shaped output.** Concepts are nodes. Mappings are edges from
   a concept node to a `(source_system, source_field)` pair. This is the
   part that makes the skill reusable: the output format doesn't change
   based on which graph store (Neo4j, Cosmos Gremlin, Fabric graph — still
   an open decision per the sprint plan) ends up holding it. Whatever gets
   chosen, this output loads into it without rework.

## Output format

See `references/rain-worked-example.json` for a complete, real example.
Shape:

```json
{
  "concepts": [ {"concept_id", "name", "definition", "synonyms", "status"} ],
  "mappings": [ {"concept_id", "source_system", "source_field", "confidence_category", "note?"} ],
  "duplicate_candidates": [ {"concept_id_a", "concept_id_b", "overlap_category", "resolution"} ],
  "coverage_gaps_detected": [ {"description", "impact", "recommendation", "status"} ],
  "run_metadata": {"mapping_coverage_pct", "hitl_queue_size", "source_systems_processed"}
}
```

## Definition of done (matches E5-S2)

- Mapping coverage threshold met (percentage of fields successfully mapped
  to at least a needs-review-or-better category)
- All merges outside the auto-eligible category are HITL-gated, not silently
  applied
- Duplicate concepts are detected and surfaced, not merged or ignored

## Worked example — RAIN

`references/rain-worked-example.json` shows this skill's output run against
RAIN's 11 source systems, producing 5 shared concepts (Constituent, Provider,
Episode, Risk Signal, Access Barrier). Two things in it are worth
reading closely:

- **A mapping that correctly stayed below auto-merge** (`Claims &
  Encounters.member_id` → `Constituent`, category needs-review) — the field name
  differs enough from the others that it shouldn't be silently accepted.
- **A real coverage gap** (compounding-risk patients — someone with both a
  pregnancy episode and a chronic-condition episode — have no explicit link
  between the two episodes). This is the exact gap that turned up by hand
  while building RAIN's synthetic data; this skill is designed to catch it
  automatically instead of needing someone to notice it in review.

## What this does NOT do

- Does not generate synthetic data (that's SyGen's job)
- Does not decide which graph database to use (that's a separate,
  still-open architecture decision)
- Does not touch row-level data at any point — schema and structure only,
  same boundary rule as the Semantic Twin
