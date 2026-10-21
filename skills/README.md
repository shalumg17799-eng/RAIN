# Skills

One folder per skill, scanned by `insights/skills_core/registry.py` at server start:

    skills/<skill-name>/
      SKILL.md          # YAML front matter (name, version, labels, validation) + the prompt body
      scripts/run.py    # run(input, ctx) — the skill's implementation
      tests/            # the skill's own tests

Naming: folders are kebab-case and must match the `name` in SKILL.md front matter exactly.
Folders starting with `_` or `.` are ignored by the registry.

Three kinds of skill live here; the registry treats them identically (every one is
`run(input, ctx) -> dict` with a declared label set):

| Kind | Skills | LLM use |
|---|---|---|
| deterministic | governed-executor, metadata-answerer | none |
| hybrid | skill-router, schema-sliver, query-generator, result-assessor, answer-composer | at most one call (query-generator adds a bounded repair loop) |
| agentic | requirements-interpreter | SkillAgent bounded loop (`insights/runtime/skill_agent.py`), paired spec in `agents/skills/<name>.yaml`, tools from `insights/runtime/tools.py` |

## `_prd_pending/`

PRD design prompts **not yet migrated** to the registry: persona-question-designer,
entity-model-designer, scenario-designer, upper-ontology-curator. They are prompt-only (no
run.py, no version) and are read directly by `insights/prd/pipeline.py` for the legacy
single-shot stages. Each one moves up into `skills/<name>/` — gaining a run.py shim, front-matter
labels and an `agents/skills/<name>.yaml` spec — in its migration slice, and this folder empties
out as the migration completes.
