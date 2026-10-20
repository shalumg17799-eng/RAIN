"""The run engine: one request in, one RunRecord out. Never raises for a failed run.

Failures are values. A bad request, a skill error, a breached limit or a broken audit store all end
as an `outcome: failed` record with a typed reason; only a bad agent definition (a deploy-time
mistake) raises, and it raises before anything runs.
"""

import hashlib
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from insights.contracts.agent import AgentDef
from insights.contracts.enums import AuditEventType, EventType, RunFailureReason
from insights.contracts.events import StageEvent
from insights.contracts.guards import RowsLeakError, assert_json_safe, assert_no_rows
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.contracts.record import RunFailure, RunRecord, StepRecord, StepTrace
from insights.contracts.request import AskOptions
from insights.contracts.state import RefineState
from insights.obs.logging import log_event
from insights.runtime.events import EventEmitter, EventSink
from insights.runtime.graph import Execution, GraphCache
from insights.runtime.limits import compute_recursion_limit, effective_limits
from insights.runtime.refs import RefError, resolve_value
from insights.runtime.scope import RunScope
from insights.runtime.steps import MAX_MESSAGE
from insights.runtime.stores import MonotonicDeadline, TokenMeter
from insights.skills_core.protocols import AuditSink, Gateway, ResultStore, Services
from insights.skills_core.registry import SkillRegistry

_log = logging.getLogger("insights.runtime.engine")

SERVER_SIDE_KEYS = frozenset({"principal", "app", "app_profile", "token", "authorization"})


class RunStore(Protocol):
    """Structural type for the run store (see InMemoryRunStore)."""

    def save(self, record: RunRecord) -> None: ...

    def get(self, run_id: str, principal: Principal) -> RunRecord | None: ...


def _failure(reason: RunFailureReason, step_id: str | None, message: str) -> RunFailure:
    return RunFailure(reason=reason, step_id=step_id, message=message[:MAX_MESSAGE])


class Runtime:
    def __init__(
        self,
        *,
        registry: SkillRegistry,
        gateway: Gateway,
        audit: AuditSink,
        results: ResultStore,
        runs: RunStore,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        recursion_limit_override: int | None = None,
        graphs: GraphCache | None = None,
        services: Services | None = None,
    ) -> None:
        self.registry = registry
        self.gateway = gateway
        self.audit = audit
        self.results = results
        self.runs = runs
        self.graphs = graphs or GraphCache()
        self._clock = clock
        self._now = now
        self._recursion_override = recursion_limit_override
        self.services = services or Services()

    def run(
        self,
        agent: AgentDef,
        *,
        input: dict[str, Any],
        principal: Principal,
        app: AppProfile,
        options: AskOptions | None = None,
        on_event: EventSink | None = None,
        conversation_id: str | None = None,
        trace_id: str | None = None,
    ) -> RunRecord:
        """One request in, one RunRecord out; `trace_id` (32 hex) links the run to a trace."""
        # A definition problem is a deploy mistake: raise before any audit or run exists.
        compiled = self.graphs.get(agent, self.registry)

        run_id = str(uuid.uuid4())
        limits = effective_limits(agent, app, options)
        meter = TokenMeter()
        scope = RunScope(
            run_id=run_id,
            trace_id=trace_id or uuid.uuid4().hex,
            thread_id=conversation_id or run_id,
            registry=self.registry,
            gateway=self.gateway,
            audit=self.audit,
            results=self.results,
            meter=meter,
            deadline=MonotonicDeadline(self._clock, limits.deadline_ms),
            emitter=EventEmitter([on_event] if on_event else [], run_id),
            principal=principal,
            app=app,
            limits=limits,
            clock=self._clock,
            now=self._now,
            services=self.services,
        )
        started_at, t0 = self._now(), self._clock()

        failure: RunFailure | None = None
        request_id = input.get("request_id") if isinstance(input.get("request_id"), str) else None
        final: dict[str, Any] = {"steps": {}, "trace": [], "refine": None}

        try:
            query = input.get("query")
            scope.audit.write(
                scope.audit_event(
                    AuditEventType.RUN_STARTED,
                    question_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest()
                    if isinstance(query, str)
                    else None,
                )
            )
        except Exception as exc:
            failure = _failure(
                RunFailureReason.INTERNAL, None, f"audit unavailable: {type(exc).__name__}"
            )

        if failure is None:
            failure = self._check_input(input)

        if failure is None:
            refine0 = RefineState(max_refines=limits.max_refines).model_dump(mode="json")
            initial = {
                "input": input,
                "steps": {},
                "exec_counts": {},
                "refine": refine0,
                "trace": [],
                "failure": None,
            }
            limit = self._recursion_override or compute_recursion_limit(
                len(agent.steps), limits.max_refines
            )
            outcome = compiled.execute(initial, scope, limit)
            final = {**outcome.state, "request_id": request_id}
            failure = self._failure_from(outcome)

        output: dict[str, Any] | None = None
        if failure is None:
            output, failure = self._resolve_output(agent, final)

        final.setdefault("request_id", request_id)
        record = self._record(
            agent, scope, final, failure, output, started_at, t0, meter.total().total
        )
        try:
            self.runs.save(record)
        except Exception as exc:
            log_event(
                _log, logging.ERROR, "run_save_failed", run_id=run_id, error=type(exc).__name__
            )
            record = self._record(
                agent,
                scope,
                {"steps": {}, "trace": [], "refine": None, "request_id": request_id},
                _failure(RunFailureReason.ROWS_IN_STATE, None, f"run record refused: {exc}")
                if isinstance(exc, RowsLeakError)
                else _failure(RunFailureReason.INTERNAL, None, "run record could not be stored"),
                None,
                started_at,
                t0,
                meter.total().total,
            )
            self.runs.save(record)

        self._finish(scope, record)
        return record

    # ---- pieces ----------------------------------------------------------------------------

    @staticmethod
    def _check_input(input: dict[str, Any]) -> RunFailure | None:
        smuggled = sorted(SERVER_SIDE_KEYS & set(input))
        if smuggled:
            return _failure(
                RunFailureReason.INVALID_INPUT,
                None,
                f"input carries server-side keys: {', '.join(smuggled)}",
            )
        try:
            assert_no_rows(input, "input")
            assert_json_safe(input, "input")
        except ValueError as exc:
            return _failure(RunFailureReason.INVALID_INPUT, None, str(exc))
        return None

    @staticmethod
    def _failure_from(outcome: Execution) -> RunFailure | None:
        if outcome.recursion_limit_hit:
            return _failure(
                RunFailureReason.RECURSION_LIMIT, None, "explicit recursion limit reached"
            )
        if outcome.error is not None:
            return _failure(
                RunFailureReason.INTERNAL, None, f"{type(outcome.error).__name__}: {outcome.error}"
            )
        recorded = outcome.state.get("failure")
        return RunFailure(**recorded) if recorded else None

    @staticmethod
    def _resolve_output(
        agent: AgentDef, final: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, RunFailure | None]:
        root = {k: final[k] for k in ("input", "steps", "refine")}
        try:
            output = resolve_value(dict(agent.output), root)
        except RefError as exc:
            return None, _failure(RunFailureReason.REF_ERROR, None, f"agent output: {exc}")
        try:
            assert_no_rows(output, "agent output")
            assert_json_safe(output, "agent output")
        except RowsLeakError as exc:
            return None, _failure(RunFailureReason.ROWS_IN_STATE, None, str(exc))
        except ValueError as exc:
            return None, _failure(RunFailureReason.SKILL_ERROR, None, str(exc))
        return output, None

    def _record(
        self,
        agent: AgentDef,
        scope: RunScope,
        final: dict[str, Any],
        failure: RunFailure | None,
        output: dict[str, Any] | None,
        started_at: datetime,
        t0: float,
        tokens_total: int,
    ) -> RunRecord:
        usage = scope.meter.total()
        request_id = final.get("request_id")
        refine_state = final.get("refine")
        refine = (
            RefineState(**{**refine_state, "tokens_used": tokens_total})
            if refine_state
            else RefineState(max_refines=scope.limits.max_refines, tokens_used=tokens_total)
        )
        try:
            return RunRecord(
                run_id=scope.run_id,
                request_id=request_id,
                trace_id=scope.trace_id,
                thread_id=scope.thread_id,
                owner_subject=scope.principal.subject,
                owner_tenant=scope.principal.tenant,
                app_id=scope.app.id,
                app_version=scope.app.version,
                agent_name=agent.name,
                agent_version=agent.version,
                outcome="failed" if failure else "completed",
                failure=failure,
                steps={k: StepRecord(**v) for k, v in final.get("steps", {}).items()},
                trace=tuple(StepTrace(**t) for t in final.get("trace", [])),
                refine=refine,
                usage=usage,
                output=output,
                started_at=started_at,
                finished_at=self._now(),
                duration_ms=round((self._clock() - t0) * 1000),
            )
        except ValidationError as exc:  # a malformed step record: keep the run, drop the detail
            log_event(
                _log,
                logging.ERROR,
                "run_record_invalid",
                run_id=scope.run_id,
                errors=exc.error_count(),
            )
            return RunRecord(
                run_id=scope.run_id,
                trace_id=scope.trace_id,
                thread_id=scope.thread_id,
                owner_subject=scope.principal.subject,
                owner_tenant=scope.principal.tenant,
                app_id=scope.app.id,
                app_version=scope.app.version,
                agent_name=agent.name,
                agent_version=agent.version,
                outcome="failed",
                failure=_failure(RunFailureReason.INTERNAL, None, "run record was malformed"),
                started_at=started_at,
                finished_at=self._now(),
                duration_ms=round((self._clock() - t0) * 1000),
            )

    def _finish(self, scope: RunScope, record: RunRecord) -> None:
        reason = record.failure.reason if record.failure else None
        try:
            scope.audit.write(
                scope.audit_event(
                    AuditEventType.RUN_FINISHED,
                    duration_ms=record.duration_ms,
                    tokens=record.usage,
                    outcome=record.outcome,
                    failure_reason=reason,
                )
            )
        except Exception as exc:
            log_event(
                _log,
                logging.ERROR,
                "audit_finish_failed",
                run_id=scope.run_id,
                error=type(exc).__name__,
            )
        scope.emitter.emit(
            StageEvent(
                type=EventType.RUN_FINISHED,
                run_id=scope.run_id,
                trace_id=scope.trace_id,
                ts=self._now(),
                duration_ms=record.duration_ms,
                tokens=record.usage,
                outcome=record.outcome,
                failure_reason=reason,
            )
        )
        log_event(
            _log,
            logging.INFO,
            "run_finished",
            run_id=scope.run_id,
            trace_id=scope.trace_id,
            outcome=record.outcome,
            failure_reason=reason.value if reason else None,
            duration_ms=record.duration_ms,
            steps=len(record.trace),
        )
