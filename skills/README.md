# Skills — two independent packs

Skills live in two packs, scanned together by `insights/skills_core/registry.py` at server start.
The packs are independent: **nothing in one pack may import, call or reference the other**
(enforced at registry load for dependencies and by `python -m insights.ci` for any reference),
and there is no publish step between them.

    skills/insights/<skill-name>/   # the Insights Server pack: runs on every NLQ
    skills/data/<skill-name>/       # the data pack: PRD design and all other data-side work

Each skill is a folder of exactly four parts (no runtime edits needed to add one):

    skills/<pack>/<skill-name>/
      SKILL.md                      # front matter: name, version, pack, stage, kind,
                                    #   capabilities (intents, data sources, consumes/produces),
                                    #   labels, validation — plus the prompt body
      scripts/run.py                # run(input, ctx) — a thin shim; logic in libraries or SkillAgent
    agents/<pack>/skills/<name>.yaml  # the skill's agent spec (budgets, tools, thresholds)

Naming: folders are kebab-case and must match the `name` in SKILL.md front matter exactly; a
skill's `pack` must match its pack folder. Folders starting with `_` or `.` are ignored.

## The insights pack (one agent per NLQ stage)

| Skill | Stage | Kind |
|---|---|---|
| skill-router | routing | guarded |
| metadata-answerer | metadata_answer | guarded |
| schema-sliver | schema_slicing | guarded |
| query-generator | query_generation | agentic |
| governed-executor | governed_execution | guarded |
| result-assessor | assessment | agentic |
| answer-composer | answer_composition | guarded |

## The data pack (PRD design pipeline)

| Skill | Stage | Kind |
|---|---|---|
| requirements-interpreter | requirements_interpretation | agentic |
| persona-question-designer | question_design | agentic |
| question-registry-reducer | question_reduction | deterministic |
| entity-model-designer | entity_modeling | agentic |
| build-data-map | data_mapping | deterministic |
| scenario-designer | scenario_design | agentic |
| upper-ontology-curator | ontology_curation | agentic |
| upper-ontology-reducer | ontology_reduction | deterministic |
| prd-finalizer | finalization | deterministic |

Kinds: **agentic** = a bounded plan→tool→observe SkillAgent loop with semantic validators;
**guarded** = an agent may pick parameters and handle errors but a deterministic core cannot be
bypassed; **deterministic** = no LLM at all. Every kind is still `run(input, ctx) -> dict` with a
closed label set to the registry.
