---
name: skill-router
version: 1.0.0
pack: insights
stage: routing
kind: guarded
capabilities:
  produces: [route]
description: Access pre-check, input screening, intent from a closed set and the retrieval path preference, by a rules then embedding then LLM cascade.
dependencies: []
restricted: false
labels: [data_query, metadata_question, out_of_scope, needs_clarification, denied]
validation:
  required_input: [query]
  required_output: [label, confidence, reason, layer, path_preference, screening]
examples:
  - input: {query: "approval rate by product type last quarter", context: {domain: lending}}
---

# skill-router (stage 4, Skill Routing)

Decides, cheaply and early, what kind of request this is. It never retrieves, never writes SQL and
never decides access to data: it checks that the caller may use this app at all, screens the input,
picks an intent from the app's closed set, and states the retrieval path preference.

## Input
- `query` (required): the question text.
- `context` (optional): market, product, domain, component, variant. Used only as hints.

## Output
- `label`: `data_query`, `metadata_question`, `out_of_scope`, `needs_clarification` or `denied`.
- `intent`: the chosen intent (absent when `denied`).
- `confidence`, `reason` (a short code, never the question text), `layer` (`rules`, `embedding`,
  `llm` or `fallback`), `path_preference` (`bypass` or `kag`), `screening` (empty, oversized,
  injection_suspected).

## The cascade
1. **Access pre-check.** A caller with no role in this app gets `denied`. Nothing else runs.
2. **Screening.** Empty input is `needs_clarification`; oversized input (the app's
   `max_query_chars`) is `needs_clarification`. Known injection patterns set
   `screening.injection_suspected`, which is logged as a signal and never changes the route.
3. **Rules** (free): a leading write verb is `out_of_scope`; an off-topic request with no data words
   is `out_of_scope`; a definitional, structural or lineage cue ("what does X mean", "which tables",
   "how are X and Y related") is `metadata_question` and takes the KAG-only metadata chain, no SQL;
   a single content word is `needs_clarification` unless it names something the
   catalog knows and comes with a time window ("applications in Q3", "applications in the last 30
   days": `data_query`); a question with an aggregate word that names something the catalog knows
   is `data_query`. Period words, months, quarters and years count as a time window; bare numbers,
   "this" or "last" alone, and the modal "may" do not.
4. **Embedding similarity** to the app's exemplar utterances per intent, accepted above the app's
   thresholds (`embedding_accept`, `embedding_margin`).
5. **LLM classifier** (gateway purpose `route`, structured output), only when 3 and 4 are unsure.
   An answer outside the closed set, below `llm_accept`, or no answer at all, means the app's
   `unsure_policy` (`needs_clarification` by default). The model never decides access.

The catalog vocabulary used by rule 3 is the whole catalog, not the caller's entitled part, so the
router gives the same answer to every caller and a status never reveals what a role may not see.
