"""persona-question-designer: SkillAgent shim. The bounded loop, tools and validators live in
insights.runtime.skill_agent and insights.prd.questions; this file only satisfies the registry's
run(input, ctx) contract."""

from typing import Any

from insights.prd.questions import persona_question_designer_agent


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return persona_question_designer_agent().run(input, ctx)
