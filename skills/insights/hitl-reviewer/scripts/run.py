"""hitl-reviewer: deterministic hold gate + bounded wait on the HITL store. No model."""

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from insights.contracts.enums import AuditEventType, EventType
from insights.contracts.events import AuditEvent, StageEvent
from insights.runtime.skill_agent import load_skill_agent_spec

SPEC_PATH = Path(__file__).resolve().parents[4] / "agents" / "insights" / "skills" / "hitl-reviewer.yaml"
_SPEC = load_skill_agent_spec(SPEC_PATH)

DECISION_LABELS = {"approve": "approved", "edit": "edited", "reject": "rejected"}


def _trigger(input: dict[str, Any], threshold: float) -> str | None:
    """The first matching hold rule, most severe first. None means the answer is clear."""
    if input.get("force_review") is True:
        return "forced"
    route = input.get("route") if isinstance(input.get("route"), dict) else {}
    screening = route.get("screening") if isinstance(route.get("screening"), dict) else {}
    if screening.get("injection_suspected") is True:
        return "sensitive_intent"
    execution = input.get("execution") if isinstance(input.get("execution"), dict) else {}
    synthesis = input.get("synthesis") if isinstance(input.get("synthesis"), dict) else {}
    if execution.get("masked_columns") or synthesis.get("partial") is True:
        return "governance_flag"
    assessment = input.get("assessment") if isinstance(input.get("assessment"), dict) else {}
    confidence = assessment.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < threshold:
        return "low_confidence"
    return None


def _emit_event(ctx: dict[str, Any], **fields: Any) -> None:
    events = ctx.get("events")
    if events is not None:
        events.emit(
            StageEvent(
                run_id=ctx["run_id"],
                trace_id=ctx["trace_id"],
                ts=datetime.now(UTC),
                step_id=ctx["step_id"],
                skill="hitl-reviewer",
                **fields,
            )
        )


def _audit(ctx: dict[str, Any], label: str) -> None:
    audit = ctx.get("audit")
    if audit is None:
        return
    principal, app = ctx["principal"], ctx["app"]
    audit.write(
        AuditEvent(
            event_id=str(uuid.uuid4()),
            type=AuditEventType.HITL_DECISION,
            ts=datetime.now(UTC),
            run_id=ctx["run_id"],
            trace_id=ctx["trace_id"],
            principal_subject=principal.subject,
            principal_tenant=principal.tenant,
            app_id=app.id,
            app_version=app.version,
            step_id=ctx["step_id"],
            skill="hitl-reviewer",
            skill_version="1.0.0",
            label=label,
        )
    )


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    question = input["question"]
    if not isinstance(question, str):
        raise ValueError("question must be text")
    assessment = input.get("assessment") if isinstance(input.get("assessment"), dict) else {}
    confidence = assessment.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) else 0.0

    reason = _trigger(input, _SPEC.confidence_threshold)
    if reason is None:
        return {
            "label": "clear",
            "hitl_review": {"held": False, "reason": None, "decision": None,
                            "decided_by": None, "edited_narrative": None, "waited_ms": 0},
            "confidence": confidence,
        }

    generation = input.get("generation") if isinstance(input.get("generation"), dict) else {}
    store = getattr(ctx["services"], "hitl", None)
    started = time.monotonic()

    def finish(label: str, decision: Any = None) -> dict[str, Any]:
        waited_ms = round((time.monotonic() - started) * 1000)
        _emit_event(ctx, type=EventType.HITL_DECIDED, label=label)
        _audit(ctx, label)
        ctx["emit"](f"hitl_{label}")
        return {
            "label": label,
            "hitl_review": {
                "held": True,
                "reason": reason,
                "decision": getattr(decision, "action", None),
                "decided_by": getattr(decision, "decided_by", None),
                "edited_narrative": getattr(decision, "edited_narrative", None),
                "waited_ms": waited_ms,
            },
            "confidence": confidence,
        }

    if store is None:
        # Fail closed: a hold without a review channel can never silently pass.
        ctx["emit"]("hitl_unconfigured")
        return finish("timeout")

    store.hold(
        run_id=ctx["run_id"],
        trace_id=ctx["trace_id"],
        reason=reason,
        question=question,
        sql=str(generation.get("sql")) if generation.get("sql") else None,
        confidence=confidence,
        proposed_narrative=(
            str(input.get("proposed_narrative")) if input.get("proposed_narrative") else None
        ),
    )
    _emit_event(ctx, type=EventType.HITL_WAITING, reason=reason)
    ctx["emit"](f"hitl_waiting_{reason}")

    timeout_s = min(_SPEC.timeout_ms, max(0, ctx["deadline"].remaining_ms())) / 1000.0
    decision = store.wait(ctx["run_id"], timeout_s)
    if decision is None:
        return finish("timeout")
    return finish(DECISION_LABELS[decision.action], decision)
