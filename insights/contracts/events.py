"""SSE stage events and audit events.

Both are closed, fully typed records: there is no free-form field, so there is nowhere to put a row
or a secret. Audit holds hashes, counts and decisions (design report 5.4, layer 4).
"""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from insights.contracts.common import (
    Contract,
    Identifier,
    SemVer,
    Sha256Hex,
    SkillName,
    SqlIdentifier,
)
from insights.contracts.enums import (
    AuditEventType,
    EventType,
    ExecutionStatus,
    PolicyDecisionKind,
    PolicyLayer,
    RunFailureReason,
)
from insights.contracts.response import TraceId


class TokenUsage(Contract):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class StageEvent(Contract):
    """What the SSE stream carries: stage name, label and token counts. Never rows."""

    type: EventType
    run_id: str
    trace_id: TraceId
    ts: AwareDatetime
    step_id: Identifier | None = None
    skill: SkillName | None = None
    skill_version: SemVer | None = None
    attempt: int | None = Field(default=None, ge=0)
    label: Identifier | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    tokens: TokenUsage | None = None
    note: Identifier | None = None
    """A code a skill chose (for example `sliver_fallback`). Never free text."""
    count: int | None = Field(default=None, ge=0)
    outcome: Literal["completed", "failed"] | None = None
    failure_reason: RunFailureReason | None = None
    iteration: int | None = Field(default=None, ge=1)
    """Which turn of a skill agent's bounded loop this event belongs to."""
    tool: Identifier | None = None
    """The tool a skill agent called. A registered tool name, never free text."""
    status: Literal["ok", "error"] | None = None
    """How the tool call ended."""
    steps: tuple[Identifier, ...] | None = None
    """GRAPH_DEFINITION only: the agent's step ids in order."""
    agent_name: SkillName | None = None
    agent_version: SemVer | None = None
    reason: Identifier | None = None
    """SUPERVISOR_DECISION: why this agent was picked. HITL_WAITING: the hold trigger.
    Always a code from a closed set, never free text."""
    considered: tuple[SkillName, ...] | None = None
    """SUPERVISOR_DECISION only: the eligible skills the supervisor chose among."""
    stage: Identifier | None = None
    """SUPERVISOR_DECISION only: the pipeline stage being filled."""
    branch: Identifier | None = None
    """A fan-out branch identity (persona or data source), so a UI can show parallel branches."""
    demo: bool | None = None
    """True on replayed demo events, so a viewer can never mistake them for a live run."""

    @model_validator(mode="after")
    def _required_per_type(self) -> "StageEvent":
        needs: dict[EventType, tuple[str, ...]] = {
            EventType.STAGE_STARTED: ("step_id", "skill", "skill_version"),
            EventType.STAGE_FINISHED: (
                "step_id",
                "skill",
                "skill_version",
                "duration_ms",
                "tokens",
            ),
            EventType.REFINE: ("step_id", "attempt", "label"),
            EventType.PROGRESS: ("step_id", "note"),
            EventType.RUN_FINISHED: ("outcome",),
            EventType.AGENT_ITERATION: ("step_id", "skill", "iteration"),
            EventType.TOOL_CALL: ("step_id", "skill", "tool", "status"),
            EventType.GRAPH_DEFINITION: ("steps", "agent_name", "agent_version"),
            EventType.SUPERVISOR_DECISION: ("skill", "reason", "stage"),
            EventType.HITL_WAITING: ("step_id", "reason"),
            EventType.HITL_DECIDED: ("step_id", "label"),
        }
        missing = [name for name in needs[self.type] if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{self.type.value} event needs: {', '.join(missing)}")
        return self


class PolicyAudit(Contract):
    layer: PolicyLayer
    decision: PolicyDecisionKind
    rules_fired: tuple[str, ...] = ()


class AuditEvent(Contract):
    event_id: str
    type: AuditEventType
    ts: AwareDatetime
    run_id: str
    trace_id: TraceId
    principal_subject: str
    principal_tenant: str
    app_id: Identifier
    app_version: SemVer
    step_id: Identifier | None = None
    skill: SkillName | None = None
    skill_version: SemVer | None = None
    label: Identifier | None = None
    attempt: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    tokens: TokenUsage | None = None
    question_sha256: Sha256Hex | None = None
    sql_sha256: Sha256Hex | None = None
    tables: tuple[SqlIdentifier, ...] = ()
    policy: tuple[PolicyAudit, ...] = ()
    execution_status: ExecutionStatus | None = None
    row_count: int | None = Field(default=None, ge=0)
    outcome: Literal["completed", "failed"] | None = None
    failure_reason: RunFailureReason | None = None
