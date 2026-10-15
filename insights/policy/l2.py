"""L2: dry run. Ask the data platform what a query would cost before running it.

This is a second syntax check (sqlglot says outright that validation is not its goal) and a guard
against legitimate-looking queries that would scan far too much. It runs the checked SQL through the
platform's EXPLAIN under the caller's own binding, so privileges are tested too.
"""

from dataclasses import dataclass

from insights.contracts.enums import PolicyDecisionKind, PolicyLayer
from insights.contracts.profile import AppProfile
from insights.contracts.state import PolicyDecision
from insights.datasources.base import (
    DataSourceAdapter,
    DataSourceError,
    FailureKind,
    PlanEstimate,
    failure_kind,
)
from insights.datasources.identity import Binding


@dataclass(frozen=True)
class DryRunOutcome:
    allowed: bool
    rules: tuple[str, ...]
    estimate: PlanEstimate | None = None
    failure: FailureKind | None = None
    """Set when the platform itself refused or failed (access_denied, timeout, error)."""

    def decision(self) -> PolicyDecision:
        limits: dict[str, float | int | str | bool | None] = {}
        if self.estimate is not None:
            limits = {
                "estimated_cost": self.estimate.total_cost,
                "estimated_rows": self.estimate.plan_rows,
            }
        return PolicyDecision(
            layer=PolicyLayer.L2,
            decision=PolicyDecisionKind.ALLOW if self.allowed else PolicyDecisionKind.DENY,
            rules_fired=self.rules,
            limits_applied=limits,
        )


def dry_run(
    adapter: DataSourceAdapter, sql: str, binding: Binding, app: AppProfile
) -> DryRunOutcome:
    try:
        estimate = adapter.explain(sql, binding, timeout_ms=app.limits.statement_timeout_ms)
    except DataSourceError as exc:
        return DryRunOutcome(False, ("explain_failed",), failure=failure_kind(exc))

    rules: list[str] = []
    if (
        app.limits.max_estimated_cost is not None
        and estimate.total_cost > app.limits.max_estimated_cost
    ):
        rules.append("cost_limit")
    if (
        app.limits.max_estimated_rows is not None
        and estimate.plan_rows > app.limits.max_estimated_rows
    ):
        rules.append("row_limit")
    if rules:
        return DryRunOutcome(False, tuple(rules), estimate)
    return DryRunOutcome(True, ("within_limits",), estimate)
