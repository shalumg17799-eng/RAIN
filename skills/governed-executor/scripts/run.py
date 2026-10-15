"""governed-executor: L1 parse and policy, L2 dry run, L3 run as the user, L4 audit. No model."""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from insights.catalog.entitlements import allowed_objects, effective_role, role_tables
from insights.contracts.enums import (
    AuditEventType,
    ColumnRole,
    ExecutionFailure,
    ExecutionStatus,
    PolicyDecisionKind,
    PolicyLayer,
)
from insights.contracts.events import AuditEvent, PolicyAudit
from insights.contracts.response import Column
from insights.contracts.state import ExecutionRecord, PolicyDecision, Sliver
from insights.datasources.base import DataSourceError, column_role, failure_kind
from insights.datasources.identity import IdentityError, bind_identity
from insights.policy.denylist import load_denylist
from insights.policy.l1 import check_sql
from insights.policy.l2 import dry_run

MAX_DETAIL = 200


def _audit(ctx: dict[str, Any], type: AuditEventType, **fields: Any) -> None:
    principal, app = ctx["principal"], ctx["app"]
    ctx["audit"].write(
        AuditEvent(
            event_id=uuid.uuid4().hex,
            type=type,
            ts=datetime.now(UTC),
            run_id=ctx["run_id"],
            trace_id=ctx["trace_id"],
            principal_subject=principal.subject,
            principal_tenant=principal.tenant,
            app_id=app.id,
            app_version=app.version,
            step_id=ctx["step_id"],
            **fields,
        )
    )


def _masked_columns(app: Any, principal: Any, names: list[str]) -> tuple[str, ...]:
    role = effective_role(principal, app)
    if role is None:
        return ()
    masked = {col for access in role_tables(app, role).values() for col in access.masks}
    return tuple(n for n in names if n in masked)


def _columns(result: Any, sliver: Sliver) -> tuple[Column, ...]:
    sliver_types = {c.name.lower(): c.type for t in sliver.tables for c in t.columns}
    out = []
    for column in result.columns:
        type_name = column.type_name or sliver_types.get(column.name.lower(), "unknown")
        role = column_role(type_name, column.name)
        if sliver_types.get(column.name.lower(), "").lower().startswith(("date", "time")):
            role = ColumnRole.TIME
        out.append(Column(name=column.name, type=type_name, role=role))
    return tuple(out)


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    app, principal = ctx["app"], ctx["principal"]
    sql = input["sql"]
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("sql must be non-empty text")
    sliver = Sliver.model_validate(input["sliver"])
    sql_sha256 = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    decisions: list[PolicyDecision] = []
    tables: tuple[str, ...] = ()

    def finish(
        status: ExecutionStatus,
        *,
        detail: str = "",
        columns: tuple[Column, ...] = (),
        row_count: int | None = None,
        truncated: bool = False,
        result_ref: Any = None,
        duration_ms: int = 0,
        masked: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        record = ExecutionRecord(
            status=status,
            failure=None if status is ExecutionStatus.OK else ExecutionFailure(status.value),
            columns=columns,
            row_count=row_count,
            truncated=truncated,
            result_ref=result_ref,
            duration_ms=duration_ms,
            masked_columns=masked,
            detail=detail[:MAX_DETAIL],
        )
        _audit(
            ctx,
            AuditEventType.EXECUTION,
            sql_sha256=sql_sha256,
            tables=tables,
            policy=tuple(
                PolicyAudit(layer=d.layer, decision=d.decision, rules_fired=d.rules_fired)
                for d in decisions
            ),
            execution_status=status,
            row_count=row_count,
            duration_ms=duration_ms,
        )
        return {
            **record.model_dump(mode="json"),
            "label": status.value,
            "policy": [d.model_dump(mode="json") for d in decisions],
            "sql_sha256": sql_sha256,
            "tables": list(tables),
        }

    # ---- identity: who the query runs as ----------------------------------------------------
    try:
        binding = bind_identity(principal, app)
    except IdentityError as exc:
        decisions.append(
            PolicyDecision(
                layer=PolicyLayer.L1,
                decision=PolicyDecisionKind.DENY,
                rules_fired=("identity_not_bound",),
            )
        )
        return finish(ExecutionStatus.ACCESS_DENIED, detail=str(exc))

    # ---- L1: parse and policy ------------------------------------------------------------
    outcome = check_sql(
        sql,
        allowed=allowed_objects(sliver.tables, app, principal),
        app=app,
        denylist=load_denylist(app.dialect.value),
        max_rows=app.limits.max_rows,
        row_predicates=binding.row_predicates,
    )
    decisions.append(outcome.decision())
    tables = outcome.tables
    _audit(
        ctx,
        AuditEventType.POLICY_DECISION,
        sql_sha256=sql_sha256,
        tables=tables,
        policy=(
            PolicyAudit(
                layer=PolicyLayer.L1, decision=decisions[-1].decision, rules_fired=outcome.rules
            ),
        ),
    )
    if not outcome.allowed or outcome.sql is None:
        ctx["emit"]("policy_denied")
        return finish(ExecutionStatus.POLICY_DENIED, detail=f"policy: {outcome.reason}")
    checked_sql = outcome.sql

    try:
        adapter = ctx["services"].need("data").adapter_for(app)
    except Exception as exc:
        return finish(
            ExecutionStatus.ERROR, detail=f"data source unavailable: {type(exc).__name__}"
        )

    # ---- L2: dry run -----------------------------------------------------------------------
    dry = dry_run(adapter, checked_sql, binding, app)
    decisions.append(dry.decision())
    if not dry.allowed:
        ctx["emit"]("dry_run_denied")
        if dry.failure is not None:
            return finish(ExecutionStatus(dry.failure), detail="dry run: the platform refused")
        return finish(ExecutionStatus.POLICY_DENIED, detail=f"dry run: {', '.join(dry.rules)}")

    # ---- L3: run as the user ---------------------------------------------------------------
    try:
        result = adapter.execute(
            checked_sql,
            binding,
            max_rows=app.limits.max_rows,
            timeout_ms=app.limits.statement_timeout_ms,
        )
    except DataSourceError as exc:
        return finish(ExecutionStatus(failure_kind(exc)), detail=str(exc))
    decisions.append(
        PolicyDecision(
            layer=PolicyLayer.L3,
            decision=PolicyDecisionKind.ALLOW,
            rules_fired=(f"identity_{binding.mode.value}",),
        )
    )

    # ---- L4: rows by reference, audit ------------------------------------------------------
    columns = _columns(result, sliver)
    ref = ctx["results"].put(
        run_id=ctx["run_id"], owner=principal.subject, columns=columns, rows=result.rows
    )
    ctx["emit"]("rows_held", len(result.rows))
    return finish(
        ExecutionStatus.OK,
        columns=columns,
        row_count=len(result.rows),
        truncated=result.truncated,
        result_ref=ref,
        duration_ms=result.duration_ms,
        masked=_masked_columns(app, principal, [c.name for c in columns]),
    )
