"""requirements-interpreter: SkillAgent shim. The bounded loop, tools and validators live in
insights.runtime.skill_agent and insights.prd.tools; this file only satisfies the registry's
run(input, ctx) contract."""

from typing import Any

from insights.prd.tools import requirements_interpreter_agent


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return requirements_interpreter_agent().run(input, ctx)
