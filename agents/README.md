# Agents

This folder holds ONLY the RAIN insights-runtime packs. The DIF build-time (knowledge gathering)
agents live in `knowledge-gathering/agents/` beside their skills (`knowledge-gathering/skills/`).

Nothing in this folder contains code — these files configure runtimes that live under
`insights/runtime/`. The layout mirrors the two independent skill packs:

    agents/insights/            # the Insights Server pack (NLQ)
      orchestrator.yaml         # the pack's supervisor (runs on every NLQ)
      skills/<name>.yaml        # one agent spec per insights skill
    agents/data/                # the data pack (PRD design)
      orchestrator.yaml         # the pack's supervisor (runs when PRD Studio is invoked)
      skills/<name>.yaml        # one agent spec per data skill

## Orchestrators — `agents/<pack>/orchestrator.yaml`

Each pack has ONE orchestrator: a supervisor that picks the next agent **at runtime** from the
skill registry by capabilities (pack, stage, intents, data sources, consumes/produces) and run
state (confidence, errors, audit results, retries) — never a hardcoded sequence. It records why it
chose each agent as a typed decision event, supports loop-backs bounded by `max_refines`,
per-persona / per-source fan-out (LangGraph `Send`), and checkpoint resume. Loaded by
`insights/runtime/supervisor.py`, compiled by `insights/runtime/graph.py` (the only module that
imports LangGraph). Any edit requires a version bump — the graph cache enforces it.

The legacy fixed-sequence graphs (`insights-agent.yaml`, `prd-agent.yaml`) remain only until the
supervisors replace them and are then removed.

## Skill-agent specs — `agents/<pack>/skills/<skill-name>.yaml`

One file per skill — every skill has an agent. The spec carries the pack, stage and kind, the
skill's `capabilities` (intents, data source types, consumes/produces artifacts), and, for skills
that use a model, the gateway purpose, prompt path, allowed tools, loop bounds (`max_iterations`,
`max_repairs`, `token_budget`, `timeout_ms`), `confidence_threshold`,
`retry_on_low_confidence` and allowed escalation reasons. Loaded by
`insights/runtime/skill_agent.py`. The prompt itself always stays in the skill's `SKILL.md` —
the spec configures the loop, never the content.

Three kinds of agent:

- **agentic** — a bounded plan→tool→observe SkillAgent loop with semantic validators
  (query-generator, result-assessor, the five generative PRD stages, schema-sliver's Cypher path).
- **guarded** — the agent picks parameters and handles errors, but a deterministic core cannot be
  bypassed (**governed-executor — the only path to a data source**, answer-composer, the
  skill-router's rules, metadata-answerer, schema-sliver's retrieval).
- **deterministic** — no LLM at all (build-data-map, question-registry-reducer,
  upper-ontology-reducer, prd-finalizer).
