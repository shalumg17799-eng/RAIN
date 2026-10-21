# Agents

Two kinds of definition live here, each in its own place. Nothing in this folder contains code —
these files configure runtimes that live under `insights/runtime/`.

## Graph agents — `agents/<name>-agent.yaml`

A whole pipeline defined as a routed graph of skills: which skill runs at each step, how a step's
label routes to the next step, per-persona fan-out (`map` steps compiled to LangGraph Send), and
the run limits (max_refines, max_tokens, deadline). Loaded and validated by
`insights/runtime/agent.py`, compiled by `insights/runtime/graph.py` (the only module that
imports LangGraph). Any edit requires a version bump — the graph cache enforces it.

| File | Pipeline | Status |
|---|---|---|
| `insights-agent.yaml` | NLQ ask path: route → sliver → generate → execute → assess → compose, bounded refine loops | live |
| `prd-agent.yaml` | PRD design graph: audit loop-backs, per-persona fan-out, SQLite checkpoint + resume | live |

## Skill-agent specs — `agents/skills/<skill-name>.yaml`

One file per **agentic** skill: its gateway purpose group, `capabilities` (pipeline, stage,
intents, data sources, artifacts — so a stage can later hold several selectable skills), prompt
path, allowed tools, loop bounds (`max_iterations`, `max_repairs`, `token_budget`, `timeout_ms`),
`confidence_threshold`, `retry_on_low_confidence` and allowed escalation reasons. Loaded by
`insights/runtime/skill_agent.py`. The prompt itself always stays in
`skills/<skill-name>/SKILL.md` — the spec configures the loop, never the content.

| Spec | Pipeline / stage | Status |
|---|---|---|
| `requirements-interpreter.yaml` | PRD · requirements | live |
| `persona-question-designer.yaml` | PRD · questions (per-persona fan-out) | live |
| `entity-model-designer.yaml` | PRD · entities | live |
| `scenario-designer.yaml` | PRD · scenario (synthetic db-state only) | live |
| `upper-ontology-curator.yaml` | PRD · ontology (per-persona fan-out) | live |
| `schema-sliver.yaml` | NLQ · Cypher proposer (KAG path) | live |
| `query-generator.yaml` | NLQ · SQL generation | live |
| `result-assessor.yaml` | NLQ · judge (never sees rows) | live |

Deliberately **never** agentic (deterministic or hybrid by design): skill-router,
metadata-answerer, **governed-executor (the only path to the database)**, answer-composer, and
the deterministic PRD steps build-data-map, question-registry-reducer, upper-ontology-reducer,
prd-finalizer.
