# Agents

Two kinds of definition live here, each in its own place. Nothing in this folder contains code —
these files configure runtimes that live under `insights/runtime/`.

## Graph agents — `agents/<name>-agent.yaml`

A whole pipeline defined as a routed graph of skills: which skill runs at each step, how a step's
label routes to the next step, and the run limits (max_refines, max_tokens, deadline). Loaded and
validated by `insights/runtime/agent.py`, compiled to LangGraph by `insights/runtime/graph.py`.

| File | Pipeline | Status |
|---|---|---|
| `insights-agent.yaml` | NLQ ask path: route → sliver → generate → execute → assess → compose | live |
| `prd-agent.yaml` | PRD design pipeline as a graph with audit loop-backs and per-persona fan-out | planned (migration slice 6) |

## Skill-agent specs — `agents/skills/<skill-name>.yaml`

One file per **agentic** skill: its gateway purpose group, prompt path, allowed tools, loop bounds
(`max_iterations`, `max_repairs`, `token_budget`, `timeout_ms`), `confidence_threshold` and
allowed escalation reasons. Loaded by `insights/runtime/skill_agent.py`. The prompt itself always
stays in `skills/<skill-name>/SKILL.md` — the spec configures the loop, never the content.

A spec appears here only when its skill is migrated to the SkillAgent loop, one slice at a time:

| Spec | Stage | Status |
|---|---|---|
| `requirements-interpreter.yaml` | PRD stage 1 | migrated (pilot) |
| persona-question-designer | PRD stage 2 | next, pending pilot approval |
| entity-model-designer | PRD stage 3 | planned |
| upper-ontology-curator | PRD stage 5 | planned |
| scenario-designer | PRD optional stage | planned |
| schema-sliver, query-generator, result-assessor | NLQ upgrades | planned |

Deliberately **never** agentic (deterministic or hybrid by design, per the migration decision):
skill-router, metadata-answerer, governed-executor, answer-composer.
