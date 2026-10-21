---
name: upper-ontology-curator
version: 0.2.0
description: Derive the business vocabulary from a question registry, emit the personas that use it, and map the vocabulary onto the tables discovered in the lower ontology — concepts, the synonyms people actually use, one-line definitions, the business relationships between concepts, and which table each concept lives in. Use this after the lower ontology exists; whenever new questions introduce vocabulary the graph does not cover; whenever the schema changed and existing mappings need repointing; or when someone asks why a plain-English question cannot find its data.
labels:
- ok
- escalate
- refine_self
validation:
  required_input:
  - requirements_ir
  - question_registry
  - lower_ontology
  required_output:
  - confidence
---

# Upper ontology curator

Stage 7. Input is `requirements-ir.yaml`, `question-registry.yaml` and
`lower-ontology.json`. Output is `upper-ontology.json`.

The lower ontology is a schema dump. This layer is what lets a person's own
words reach it.

## The critical difference from every other stage

**This layer is reconciled, never regenerated.**

Every other artifact in the factory is rebuilt from scratch on each run. This
one is not. Concepts, synonyms and definitions are curated — some by a human —
and rebuilding from zero silently discards that work. Nobody notices until a
synonym someone added stops matching.

If an existing `upper-ontology.json` is supplied, you are editing it. Keep every
concept id. Keep every synonym. Change only what the evidence requires.

## Hard rule: no domain logic

The vocabulary comes from the questions, not from what you know about the
industry. If a term is not used in the registry and not implied by a persona's
stated problems, it is not a concept. Do not add `Claim` because healthcare
usually has claims.

## Workflow

### 1. Collect the vocabulary

Read every question in the registry. Pull out the nouns people use to refer to
things: the entities they ask about, the measures they ask for, the events they
reference.

Weight `extracted`-tier questions highest — that is the client's actual
language. Derived and generated tiers are useful for coverage but their wording
came from a model, not from the business.

### 2. Merge synonyms

Several words will mean one thing. Call, contact, interaction, conversation,
chat. One concept, several synonyms.

Merge on meaning, not spelling. The test: could one answer satisfy a question
using either word? If yes, same concept.

The synonym list is the single most load-bearing field in this layer. It is the
entire mechanism by which a user's phrasing reaches a table whose name they have
never seen. Be generous: include plurals, abbreviations, and the informal terms
that appear in golden-path dialogue.

### 3. Write a definition

One sentence per concept, in business language, stating what one of them is.

Write it so it would still be true at a different client in a different
industry where possible. "One contact between the organisation and a person it
serves" travels; "one call to the credit union" does not. This costs nothing now
and is what lets concepts be reused later.

### 4. Connect concepts to each other

Business relationships, not joins. `Member initiates Interaction`.
`Campaign drives Interaction`. `Interaction routedTo Queue`.

These are what let a question about one thing reach a related thing nobody
named. "Why did calls spike" finds Campaign only because an edge says campaigns
drive interactions.

Some of these will have no equivalent in the lower ontology, and that is
correct. A business relationship can be real while the database records it only
as a nullable column that is mostly empty.

### 5. Emit the personas

One Persona node per persona in the IR, carrying its `persona_id`, role and
altitude. Then a `SERVES` edge to every concept that persona's questions touch.

Three rules that matter:

**Personas connect to concepts only.** Never to entities, and never as a parent
that owns them. A persona is a view over the concept layer, not a partition of
it — the same data serves several roles.

**Overlap is correct.** A concept served by three personas is expected, and
that overlap is where cross-persona questions live. Do not force each concept
to a single owner.

**Keep the concept layer flat.** Deep nesting looks elegant and makes traversal
slow and unreliable, because every question has to walk the graph. Loosely
coupled concepts, each reaching a small number of tables, is the shape that
works.

### 6. Map each concept to the lower ontology

For each concept, find the entity it lives in. Evidence, strongest first:

**Grain match.** The lower ontology records what one row of each table means.
Compare that to your concept's definition. This is the strongest signal and it
is free.

**Name and synonym match.** Concept name or any synonym against the table name.

**Attribute overlap.** Does the table have columns matching what this concept is
described as having?

**Question co-occurrence.** Which tables do the questions using this word need?

Record for each mapping:

- `identity` — the column that identifies one of them, so counting works
- `attribute_map` — business term to column name for the attributes people ask
  about
- `also_referenced_in` — other tables holding this concept's id, which is what
  makes cross-source joins findable
- `confidence` and `basis` — how sure, and why

Map concepts directly to tables. Do not introduce intermediate grouping nodes;
they add depth without adding meaning.

### 7. Handle the cases that do not map cleanly

**Computed concepts.** "Service level" is not a table; it is a formula over two
columns. Record it with `derived: true` and the formula. This is common and
expected for anything people call a metric.

**Unmapped concepts.** A word people use that nothing in the database holds.
Record it with `unmapped: true` and say what would be needed. Do not force a
weak mapping to avoid an empty field — an unmapped concept is a finding about
the data, and a wrong mapping is a wrong answer.

**Entities with no concept.** Tables nobody asks about. List them. Either
harmless plumbing or a sign that vocabulary is missing.

### 8. Reconcile, if a previous version exists

Compare your mappings against the previous file and classify each concept:

| State | Action |
|---|---|
| Table and columns still exist | Leave untouched |
| Table renamed, clear match | Repoint the mapping, note the change |
| Target gone, no clear match | Keep the concept, mark `needs_review` |
| New table no concept covers | Propose a concept, mark `proposed` |

Never delete a concept because its table disappeared. The word is still in use;
it is the mapping that broke.

### 9. Report

Concept count, persona count, mapped, computed, unmapped. Concepts served by
more than one persona. Entities with no concept. Anything marked `needs_review`
or `proposed`. Lead with those, not the totals.

## Output

`upper-ontology.json`, same node-and-edge shape as the lower layer so the two
compose into one graph:

- Nodes of kind `Concept`, with `synonyms`, `definition`, and stable ids
  (`C-0001`). Ids never change, even when a concept is renamed — a rename with
  a stable id costs nothing, and a rename without one breaks every mapping.
- Nodes of kind `Persona`, with `persona_id`, role and altitude (`P-0001`)
- Edges of type `SERVES` from persona to concept
- Edges of type `RELATES_TO` between concepts, carrying the relationship name
- Edges of type `MAPS_TO` from concept to entity, carrying identity,
  attribute map, confidence and basis

Output JSON only. No commentary.