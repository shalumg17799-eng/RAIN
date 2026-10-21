"""Execute one agent step. Plain Python: no LangGraph here, so it can be tested on its own.

Returns a state patch. A failure is a patch too (`failure` key), never a raised exception, so the
partial trace survives and the graph routes to its end.
"""

from typing import Any

from insights.contracts.agent import Step
from insights.contracts.enums import AuditEventType, EventType, RunFailureReason
from insights.contracts.events import StageEvent, TokenUsage
from insights.contracts.guards import RowsLeakError, assert_json_safe, assert_no_rows
from insights.runtime.agent import ESCALATE, REFINE_PREFIX
from insights.runtime.refs import RefError, resolve_ref, resolve_value
from insights.runtime.scope import RunScope
from insights.skills_core.context import make_context
from insights.skills_core.errors import SkillError, SkillNotFoundError

MAX_MESSAGE = 300


def failure_patch(reason: RunFailureReason, step_id: str | None, message: str) -> dict[str, Any]:
    return {
        "failure": {"reason": reason.value, "step_id": step_id, "message": message[:MAX_MESSAGE]}
    }


def _delta(before: TokenUsage, after: TokenUsage) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=after.prompt_tokens - before.prompt_tokens,
        completion_tokens=after.completion_tokens - before.completion_tokens,
    )


def _progress(scope: RunScope, step_id: str):
    def emit(note: str, count: int | None = None) -> None:
        scope.emitter.emit(
            StageEvent(
                type=EventType.PROGRESS,
                run_id=scope.run_id,
                trace_id=scope.trace_id,
                ts=scope.now(),
                step_id=step_id,
                note=note,
                count=count,
            )
        )

    return emit


def map_items_and_input(
    step: Step, state: dict[str, Any], scope: RunScope
) -> tuple[list[Any], dict[str, Any]] | dict[str, Any]:
    """Resolve a map step's item list and base input, or return a failure patch."""
    root = {
        "input": state["input"],
        "steps": state["steps"],
        "refine": state["refine"],
        "fanout": state.get("fanout") or {},
    }
    try:
        items = resolve_ref(step.map.over, root)  # type: ignore[union-attr]
        base_input = resolve_value(step.input, root)
    except RefError as exc:
        return failure_patch(RunFailureReason.REF_ERROR, step.id, str(exc))
    if not isinstance(items, list) or not items:
        return failure_patch(
            RunFailureReason.INVALID_INPUT,
            step.id,
            f"map over {step.map.over} must resolve to a non-empty list",  # type: ignore[union-attr]
        )
    return items, base_input


def execute_map_item(
    step: Step, payload: dict[str, Any], scope: RunScope
) -> dict[str, Any]:
    """Run one fan-out item. A per-item skill failure becomes an `escalate` entry for the
    reducer to judge, never a dead run; a safety breach (rows in output) still fails the run."""
    attempt = int(payload.get("attempt") or 0)
    index = int(payload.get("index") or 0)
    branch = payload.get("branch") if isinstance(payload.get("branch"), str) else None
    item_input = payload.get("input") or {}
    try:
        loaded = scope.registry.get(step.skill, step.version)
    except SkillNotFoundError as exc:
        return failure_patch(RunFailureReason.SKILL_ERROR, step.id, str(exc))
    manifest = loaded.manifest

    scope.emitter.emit(
        StageEvent(
            type=EventType.STAGE_STARTED,
            run_id=scope.run_id,
            trace_id=scope.trace_id,
            ts=scope.now(),
            step_id=step.id,
            skill=manifest.name,
            skill_version=manifest.version,
            attempt=index,
            branch=branch,
        )
    )
    ctx = make_context(
        run_id=scope.run_id,
        trace_id=scope.trace_id,
        step_id=step.id,
        attempt=index,
        principal=scope.principal,
        app=scope.app,
        gateway=scope.gateway,
        emit=_progress(scope, step.id),
        audit=scope.audit,
        results=scope.results,
        usage=scope.meter,
        deadline=scope.deadline,
        services=scope.services,
        events=scope.emitter,
    )
    tokens_before = scope.meter.total()
    started = scope.clock()
    try:
        output = scope.registry.invoke(manifest.name, manifest.version, item_input, ctx)
    except SkillError as exc:
        output = {"label": "escalate", "reason": f"item failed: {str(exc)[:200]}", "confidence": 0.0}
    try:
        assert_no_rows(output, f"map step {step.id!r} item output")
        assert_json_safe(output, f"map step {step.id!r} item output")
    except (RowsLeakError, ValueError) as exc:
        return failure_patch(RunFailureReason.ROWS_IN_STATE, step.id, str(exc))

    duration_ms = round((scope.clock() - started) * 1000)
    tokens = _delta(tokens_before, scope.meter.total())
    scope.emitter.emit(
        StageEvent(
            type=EventType.STAGE_FINISHED,
            run_id=scope.run_id,
            trace_id=scope.trace_id,
            ts=scope.now(),
            step_id=step.id,
            skill=manifest.name,
            skill_version=manifest.version,
            attempt=index,
            branch=branch,
            label=str(output.get("label")) if output.get("label") else None,
            duration_ms=duration_ms,
            tokens=tokens,
        )
    )
    entry = {
        "step_id": step.id,
        "skill": manifest.name,
        "skill_version": manifest.version,
        "attempt": attempt,
        "label": str(output.get("label")) if output.get("label") else None,
        "duration_ms": duration_ms,
        "tokens": tokens.model_dump(),
    }
    patch: dict[str, Any] = {
        "fanout": {step.id: [{"attempt": attempt, "index": index, "branch": branch,
                              "item": payload.get("item"), "output": output}]},
        "trace": [entry],
    }
    if scope.meter.total().total > scope.limits.max_tokens:
        patch["failure"] = failure_patch(
            RunFailureReason.TOKEN_BUDGET,
            step.id,
            f"{scope.meter.total().total} tokens used, budget {scope.limits.max_tokens}",
        )["failure"]
    return patch


def execute_step(step: Step, state: dict[str, Any], scope: RunScope) -> dict[str, Any]:
    if state.get("failure"):
        return {}
    attempt = state["exec_counts"].get(step.id, 0)
    if scope.deadline.expired():
        return failure_patch(RunFailureReason.DEADLINE, step.id, "deadline reached before the step")

    root = {
        "input": state["input"],
        "steps": state["steps"],
        "refine": state["refine"],
        "fanout": state.get("fanout") or {},
    }
    try:
        step_input = resolve_value(step.input, root)
        loaded = scope.registry.get(step.skill, step.version)
    except RefError as exc:
        return failure_patch(RunFailureReason.REF_ERROR, step.id, str(exc))
    except SkillNotFoundError as exc:
        return failure_patch(RunFailureReason.SKILL_ERROR, step.id, str(exc))
    manifest = loaded.manifest

    scope.emitter.emit(
        StageEvent(
            type=EventType.STAGE_STARTED,
            run_id=scope.run_id,
            trace_id=scope.trace_id,
            ts=scope.now(),
            step_id=step.id,
            skill=manifest.name,
            skill_version=manifest.version,
            attempt=attempt,
        )
    )
    ctx = make_context(
        run_id=scope.run_id,
        trace_id=scope.trace_id,
        step_id=step.id,
        attempt=attempt,
        principal=scope.principal,
        app=scope.app,
        gateway=scope.gateway,
        emit=_progress(scope, step.id),
        audit=scope.audit,
        results=scope.results,
        usage=scope.meter,
        deadline=scope.deadline,
        services=scope.services,
        events=scope.emitter,
    )
    tokens_before = scope.meter.total()
    started = scope.clock()

    def trace_entry(label: str | None) -> dict[str, Any]:
        return {
            "step_id": step.id,
            "skill": manifest.name,
            "skill_version": manifest.version,
            "attempt": attempt,
            "label": label,
            "duration_ms": round((scope.clock() - started) * 1000),
            "tokens": _delta(tokens_before, scope.meter.total()).model_dump(),
        }

    def finish_audit(label: str | None, entry: dict[str, Any]) -> None:
        scope.audit.write(
            scope.audit_event(
                AuditEventType.STEP_FINISHED,
                step_id=step.id,
                skill=manifest.name,
                skill_version=manifest.version,
                label=label,
                attempt=attempt,
                duration_ms=entry["duration_ms"],
                tokens=TokenUsage(**entry["tokens"]),
            )
        )

    try:
        output = scope.registry.invoke(manifest.name, manifest.version, step_input, ctx)
    except SkillError as exc:
        entry = trace_entry(None)
        finish_audit(None, entry)
        return {
            **failure_patch(RunFailureReason.SKILL_ERROR, step.id, str(exc)),
            "trace": [entry],
            "exec_counts": {step.id: attempt + 1},
        }

    try:
        assert_no_rows(output, f"step {step.id!r} output")
        assert_json_safe(output, f"step {step.id!r} output")
    except RowsLeakError as exc:
        entry = trace_entry(None)
        finish_audit(None, entry)
        return {
            **failure_patch(RunFailureReason.ROWS_IN_STATE, step.id, str(exc)),
            "trace": [entry],
            "exec_counts": {step.id: attempt + 1},
        }
    except ValueError as exc:
        entry = trace_entry(None)
        finish_audit(None, entry)
        return {
            **failure_patch(RunFailureReason.SKILL_ERROR, step.id, str(exc)),
            "trace": [entry],
            "exec_counts": {step.id: attempt + 1},
        }

    record = {
        "skill": manifest.name,
        "version": manifest.version,
        "output": output,
        "label": None,
        "runs": attempt + 1,
    }
    refine = dict(state["refine"])
    failure: dict[str, Any] | None = None
    effective: str | None = None

    if step.route is not None:
        try:
            raw = resolve_ref(step.route.on, {**root, "steps": {**state["steps"], step.id: record}})
        except RefError as exc:
            failure = failure_patch(RunFailureReason.REF_ERROR, step.id, str(exc))["failure"]
            raw = None
        if raw is not None:
            effective = str(raw)
            if effective.startswith(REFINE_PREFIX):
                if refine["attempt"] >= refine["max_refines"]:
                    effective = ESCALATE
                    refine["exhausted"] = True
                else:
                    refine["attempt"] += 1
                    refine["critique"] = output.get("critique")
                    refine["history"] = [
                        *refine["history"],
                        {
                            "attempt": refine["attempt"],
                            "step_id": step.id,
                            "label": str(raw),
                            "critique": output.get("critique"),
                        },
                    ]
                    scope.emitter.emit(
                        StageEvent(
                            type=EventType.REFINE,
                            run_id=scope.run_id,
                            trace_id=scope.trace_id,
                            ts=scope.now(),
                            step_id=step.id,
                            attempt=refine["attempt"],
                            label=str(raw),
                        )
                    )
            if failure is None and effective not in step.route.to:
                failure = failure_patch(
                    RunFailureReason.UNMAPPED_LABEL,
                    step.id,
                    f"label {effective!r} has no route from this step",
                )["failure"]
    record["label"] = effective

    entry = trace_entry(effective)
    refine["tokens_used"] = scope.meter.total().total
    finish_audit(effective, entry)
    scope.emitter.emit(
        StageEvent(
            type=EventType.STAGE_FINISHED,
            run_id=scope.run_id,
            trace_id=scope.trace_id,
            ts=scope.now(),
            step_id=step.id,
            skill=manifest.name,
            skill_version=manifest.version,
            attempt=attempt,
            label=effective,
            duration_ms=entry["duration_ms"],
            tokens=TokenUsage(**entry["tokens"]),
        )
    )

    if failure is None and scope.deadline.expired():
        failure = failure_patch(RunFailureReason.DEADLINE, step.id, "deadline passed during step")[
            "failure"
        ]
    if failure is None and scope.meter.total().total > scope.limits.max_tokens:
        failure = failure_patch(
            RunFailureReason.TOKEN_BUDGET,
            step.id,
            f"{scope.meter.total().total} tokens used, budget {scope.limits.max_tokens}",
        )["failure"]

    patch: dict[str, Any] = {
        "steps": {step.id: record},
        "exec_counts": {step.id: attempt + 1},
        "trace": [entry],
        "refine": refine,
    }
    if failure is not None:
        patch["failure"] = failure
    return patch
