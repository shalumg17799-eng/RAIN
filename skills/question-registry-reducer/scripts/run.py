"""question-registry-reducer: deterministic reduce node. Logic in insights.prd.reducers."""

from typing import Any

from insights.prd.reducers import reduce_question_registry


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return reduce_question_registry(input, ctx)
