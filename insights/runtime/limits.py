"""Effective limits for a run, and the explicit recursion bound.

A request may only tighten limits: each effective value is the minimum of the agent, the app
profile and the request. The graph is always invoked with an explicit recursion_limit derived from
the step count and max_refines, never LangGraph's default of 10007.
"""

from dataclasses import dataclass

from insights.contracts.agent import AgentDef
from insights.contracts.profile import AppProfile
from insights.contracts.request import AskOptions

RECURSION_MARGIN = 2


@dataclass(frozen=True)
class EffectiveLimits:
    max_refines: int
    max_tokens: int
    deadline_ms: int


def effective_limits(
    agent: AgentDef, app: AppProfile, options: AskOptions | None
) -> EffectiveLimits:
    max_refines = min(agent.limits.max_refines, app.limits.max_refines)
    deadline_ms = min(agent.limits.deadline_ms, app.limits.deadline_ms)
    if options is not None:
        if options.max_refines is not None:
            max_refines = min(max_refines, options.max_refines)
        if options.timeout_ms is not None:
            deadline_ms = min(deadline_ms, options.timeout_ms)
    return EffectiveLimits(
        max_refines=max_refines,
        max_tokens=min(agent.limits.max_tokens, app.limits.max_tokens),
        deadline_ms=deadline_ms,
    )


def compute_recursion_limit(step_count: int, max_refines: int, *, map_steps: int = 0) -> int:
    """Upper bound on graph supersteps: every pass may run every step, a map step adds its
    dispatch and item supersteps, plus a small margin."""
    return (step_count + 2 * map_steps) * (max_refines + 1) + RECURSION_MARGIN
