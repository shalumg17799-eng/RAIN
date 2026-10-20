"""The `ctx` handed to every skill: run_id, principal, app, gateway, emit, plus the run's handles.

It is a plain dict (TypedDict) so a skill is `run(input: dict, ctx: dict) -> dict` as the
convention says. Principal and app profile reach a skill only through here, never through the
agent YAML, the request body or a prompt.
"""

from typing import TypedDict

from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.skills_core.protocols import (
    AuditSink,
    Deadline,
    Emit,
    Gateway,
    ResultStore,
    Services,
    UsageMeter,
)


class SkillContext(TypedDict):
    run_id: str
    trace_id: str
    step_id: str
    attempt: int
    principal: Principal
    app: AppProfile
    gateway: Gateway
    emit: Emit
    audit: AuditSink
    results: ResultStore
    usage: UsageMeter
    deadline: Deadline
    services: Services


def make_context(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    attempt: int,
    principal: Principal,
    app: AppProfile,
    gateway: Gateway,
    emit: Emit,
    audit: AuditSink,
    results: ResultStore,
    usage: UsageMeter,
    deadline: Deadline,
    services: Services | None = None,
) -> SkillContext:
    if not isinstance(principal, Principal):
        raise TypeError("ctx principal must be a Principal")
    if not isinstance(app, AppProfile):
        raise TypeError("ctx app must be an AppProfile")
    return SkillContext(
        run_id=run_id,
        trace_id=trace_id,
        step_id=step_id,
        attempt=attempt,
        principal=principal,
        app=app,
        gateway=gateway,
        emit=emit,
        audit=audit,
        results=results,
        usage=usage,
        deadline=deadline,
        services=services or Services(),
    )
