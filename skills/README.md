# Skills

One folder per skill, scanned by `insights/skills_core/registry.py` at server start:

    skills/<skill-name>/
      SKILL.md          # YAML front matter (name, version, labels, validation) + the prompt body
      scripts/run.py    # run(input, ctx) — the skill's implementation (or a SkillAgent shim)
      tests/            # the skill's own tests

Naming: folders are kebab-case and must match the `name` in SKILL.md front matter exactly.
Folders starting with `_` or `.` are ignored by the registry.

Three kinds of skill live here; the registry treats them identically (every one is
`run(input, ctx) -> dict` with a declared label set):

| Kind | Skills | LLM use |
|---|---|---|
| deterministic | governed-executor, metadata-answerer, build-data-map, question-registry-reducer, upper-ontology-reducer, prd-finalizer | none |
| hybrid | skill-router, answer-composer | at most one bounded call |
| agentic | requirements-interpreter, persona-question-designer, entity-model-designer, scenario-designer, upper-ontology-curator, schema-sliver (Cypher path), query-generator, result-assessor (judge) | SkillAgent bounded loop (`insights/runtime/skill_agent.py`), paired spec in `agents/skills/<name>.yaml`, typed read-only tools from `insights/runtime/tools.py` |

Safety fixtures that never change kind: **governed-executor is the only path to the database**;
the result-assessor's judge never sees row values; schema-sliver's tools never widen beyond the
principal's entitlements (filtering runs inside the KAG); PRD tools are read-only; scenario SQL
is proposal-only against a synthetic state and is never executed by the pipeline.

Adding a skill agent = SKILL.md + spec YAML + factory module + run.py shim; the runner, engine,
graph compiler and registry are never edited (see the root README for the walkthrough).
