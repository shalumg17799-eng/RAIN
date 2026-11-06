"""upper-ontology-curator: SkillAgent shim. The bounded loop, tools and validators live in
insights.runtime.skill_agent and insights.prd.ontology; this file only satisfies the registry's
run(input, ctx) contract."""

from typing import Any

from insights.prd.ontology import upper_ontology_curator_agent


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return upper_ontology_curator_agent().run(input, ctx)
