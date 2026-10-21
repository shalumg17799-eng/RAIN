"""prd-finalizer: deterministic run-report assembly. Logic in insights.prd.reducers."""

from typing import Any

from insights.prd.reducers import finalize_run


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return finalize_run(input, ctx)
