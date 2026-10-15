"""What the engine stores about a finished run. No rows: outputs pass the no-rows guard first."""

from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from insights.contracts.common import Contract, Identifier, SemVer, SkillName
from insights.contracts.enums import RunFailureReason
from insights.contracts.events import TokenUsage
from insights.contracts.response import TraceId
from insights.contracts.state import RefineState


class StepTrace(Contract):
    """One execution of one step. A step that is re-run in the refine loop appears again."""

    step_id: Identifier
    skill: SkillName
    skill_version: SemVer
    attempt: int = Field(ge=0)
    label: Identifier | None = None
    duration_ms: int = Field(ge=0)
    tokens: TokenUsage = TokenUsage()


class RunFailure(Contract):
    reason: RunFailureReason
    step_id: Identifier | None = None
    message: str = Field(default="", max_length=300)
    """Short and sanitized. Skills must never put data values in an exception message."""


class StepRecord(Contract):
    """The latest output of a step (outputs are plain JSON with no row data)."""

    skill: SkillName
    version: SemVer
    output: dict[str, Any]
    label: Identifier | None = None
    runs: int = Field(ge=1)


class RunRecord(Contract):
    run_id: str
    request_id: str | None = None
    """The caller's request id, when the input carried one."""
    trace_id: TraceId
    thread_id: str
    owner_subject: str
    owner_tenant: str
    app_id: Identifier
    app_version: SemVer
    agent_name: SkillName
    agent_version: SemVer
    outcome: Literal["completed", "failed"]
    failure: RunFailure | None = None
    steps: dict[str, StepRecord] = Field(default_factory=dict)
    trace: tuple[StepTrace, ...] = ()
    refine: RefineState = RefineState()
    usage: TokenUsage = TokenUsage()
    output: dict[str, Any] | None = None
    started_at: AwareDatetime
    finished_at: AwareDatetime
    duration_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _outcome_rules(self) -> "RunRecord":
        if (self.outcome == "failed") != (self.failure is not None):
            raise ValueError("a failure is present exactly when the outcome is failed")
        if self.outcome == "completed" and self.output is None:
            raise ValueError("a completed run needs its output")
        return self
