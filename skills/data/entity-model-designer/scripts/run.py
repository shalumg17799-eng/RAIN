"""entity-model-designer: SkillAgent shim. The bounded loop, tools and validators live in
insights.runtime.skill_agent and insights.prd.entities; this file only satisfies the registry's
run(input, ctx) contract."""

from typing import Any

from insights.prd.entities import entity_model_designer_agent


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return entity_model_designer_agent().run(input, ctx)
