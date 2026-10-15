"""Run state (design report 4.5). JSON-serializable, no rows, no secrets.

Rows by reference: `ExecutionRecord` and `AnswerRecord` hold `row_count` and a `ResultRef`. The rows
themselves live in the per-request result store and are joined back in only when the HTTP response
is built. There is deliberately no field anywhere in this module that could hold a row.

`app_profile` is a reference (id, version, content hash) rather than a copy of the profile; it is
enough to reproduce the run (report R7) and keeps entitlements out of stored state.
"""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from insights.contracts.common import (
    Contract,
    Identifier,
    JsonScalar,
    Sha256Hex,
    SqlIdentifier,
)
from insights.contracts.enums import (
    AssessorLabel,
    Dialect,
    ExecutionFailure,
    ExecutionStatus,
    Intent,
    PathName,
    PolicyDecisionKind,
    PolicyLayer,
    RouterLayer,
    Status,
)
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfileRef
from insights.contracts.request import AskRequest
from insights.contracts.response import (
    Clarification,
    Column,
    Confidence,
    Provenance,
    QueryInfo,
    Reason,
    RefineInfo,
    TraceId,
    check_status_fields,
)


class ResultRef(Contract):
    """Opaque handle to rows held in memory for the life of one request."""

    ref: str = Field(min_length=8, max_length=128)
    kind: Literal["memory"] = "memory"


class Screening(Contract):
    """Input screening signals. Suspicion is a signal, never an authority."""

    empty: bool = False
    oversized: bool = False
    injection_suspected: bool = False


class Route(Contract):
    intent: Intent
    path_preference: PathName
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    layer: RouterLayer
    screening: Screening = Screening()


class SliverColumn(Contract):
    name: str
    type: str
    description: str = ""


class SliverTable(Contract):
    source_id: Identifier
    name: SqlIdentifier
    description: str = ""
    columns: tuple[SliverColumn, ...]
    score: float | None = None
    freshness: dict[str, str] = Field(default_factory=dict)
    """Latest value per date column (ISO date) among the columns above, from the catalog."""


class SliverJoin(Contract):
    left: SqlIdentifier
    right: SqlIdentifier
    kind: Literal["declared", "hint"] = "declared"


class GlossaryTerm(Contract):
    term: str
    definition: str
    maps_to: tuple[SqlIdentifier, ...] = ()


class Sliver(Contract):
    tables: tuple[SliverTable, ...]
    joins: tuple[SliverJoin, ...] = ()
    glossary_terms: tuple[GlossaryTerm, ...] = ()
    coverage: float = Field(ge=0.0, le=1.0)
    path_used: PathName
    catalog_version: str
    provenance: tuple[Provenance, ...] = ()


class QueryAttempt(Contract):
    """One entry per attempt, so the refine history is kept."""

    attempt: int = Field(ge=0)
    sql: str
    assumptions: tuple[str, ...] = ()
    tables_used: tuple[SqlIdentifier, ...] = ()
    dialect: Dialect
    model: str
    prompt_version: str
    prompt_hash: Sha256Hex
    repairs: int = Field(default=0, ge=0, le=2)


class PolicyDecision(Contract):
    layer: PolicyLayer
    decision: PolicyDecisionKind
    rules_fired: tuple[str, ...] = ()
    rewritten_sql: str | None = None
    limits_applied: dict[str, JsonScalar] = Field(default_factory=dict)


class ExecutionRecord(Contract):
    status: ExecutionStatus
    failure: ExecutionFailure | None = None
    columns: tuple[Column, ...] = ()
    row_count: int | None = Field(default=None, ge=0)
    truncated: bool = False
    result_ref: ResultRef | None = None
    duration_ms: int = Field(default=0, ge=0)
    masked_columns: tuple[str, ...] = ()
    detail: str = Field(default="", max_length=200)
    """Short, sanitized error text. Never a value from the data."""

    @model_validator(mode="after")
    def _outcome_fields(self) -> "ExecutionRecord":
        if self.status is ExecutionStatus.OK:
            if self.row_count is None or self.result_ref is None or self.failure is not None:
                raise ValueError("an ok execution needs row_count and result_ref and no failure")
        else:
            if self.failure is None or self.failure.value != self.status.value:
                raise ValueError("a failed execution needs the matching typed failure")
            if self.row_count is not None or self.result_ref is not None:
                raise ValueError("a failed execution carries no rows and no result_ref")
        return self


class Assessment(Contract):
    score: float = Field(ge=0.0, le=1.0)
    signals: dict[str, JsonScalar] = Field(default_factory=dict)
    label: AssessorLabel
    critique: str | None = None


class RefineEntry(Contract):
    attempt: int = Field(ge=1)
    step_id: Identifier
    label: Identifier
    critique: str | None = None


class RefineState(Contract):
    """Owned by the engine with its own counter, not the framework's."""

    attempt: int = Field(default=0, ge=0)
    max_refines: int = Field(default=2, ge=0, le=5)
    history: tuple[RefineEntry, ...] = ()
    tokens_used: int = Field(default=0, ge=0)
    exhausted: bool = False
    critique: str | None = None
    """The latest critique, handed to the next attempt as `$.refine.critique`."""


class AnswerRecord(Contract):
    """The response body with data by reference. The API joins rows in from the result store."""

    status: Status
    columns: tuple[Column, ...] = ()
    row_count: int | None = Field(default=None, ge=0)
    truncated: bool = False
    result_ref: ResultRef | None = None
    query: QueryInfo | None = None
    confidence: Confidence | None = None
    assumptions: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    clarification: Clarification | None = None
    refine: RefineInfo = RefineInfo()
    narrative: str | None = None
    reason: Reason | None = None

    @model_validator(mode="after")
    def _status_rules(self) -> "AnswerRecord":
        has_data = self.result_ref is not None
        if has_data != (self.row_count is not None):
            raise ValueError("row_count and result_ref go together")
        check_status_fields(
            status=self.status,
            has_data=has_data,
            confidence=self.confidence,
            provenance=self.provenance,
            clarification=self.clarification,
            reason=self.reason,
        )
        return self


class RunState(Contract):
    """Everything about one run that may be stored. Thread id is the conversation id."""

    run_id: UUID
    thread_id: str
    trace_id: TraceId
    request: AskRequest
    principal: Principal
    app_profile: AppProfileRef
    route: Route | None = None
    sliver: Sliver | None = None
    query: tuple[QueryAttempt, ...] = ()
    policy: tuple[PolicyDecision, ...] = ()
    execution: ExecutionRecord | None = None
    assessment: Assessment | None = None
    refine: RefineState = RefineState()
    answer: AnswerRecord | None = None
