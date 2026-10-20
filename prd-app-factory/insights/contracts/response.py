"""Response contract (design report 4.4) and the status rules that keep it honest.

Added to the report's draft, both optional and additive: `reason` (why a run was abstained, denied,
failed or out of scope, with rephrase hints) because the report asks for "abstained with reason and
hints" but the draft body has no field for it.
"""

from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from insights.contracts.common import Contract, JsonScalar, SqlIdentifier
from insights.contracts.enums import (
    ColumnRole,
    Dialect,
    ExecutionFailure,
    PathName,
    Status,
)

TraceId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
"""W3C / OpenTelemetry trace id: 32 lowercase hex characters."""


class Column(Contract):
    name: str
    type: str
    role: ColumnRole


class Data(Contract):
    columns: tuple[Column, ...]
    rows: tuple[tuple[JsonScalar, ...], ...]
    row_count: int
    truncated: bool = False

    @model_validator(mode="after")
    def _shape(self) -> "Data":
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal the number of rows returned")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("every row must have one value per column")
        return self


class QueryInfo(Contract):
    """`sql` and `tables` are empty when the caller's role may not see the SQL (Q15)."""

    sql: str | None = None
    dialect: Dialect
    tables: tuple[SqlIdentifier, ...] = ()


class Confidence(Contract):
    score: float
    calibrated: bool = False
    signals: dict[str, JsonScalar] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _range(self) -> "Confidence":
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be within 0..1")
        return self


class Provenance(Contract):
    table: str
    source: str
    freshness: str | None = None


class Clarification(Contract):
    question: str
    options: tuple[str, ...] = ()


class RefineInfo(Contract):
    attempts: int = 0
    path_used: PathName | None = None


class Reason(Contract):
    code: str
    message: str
    hints: tuple[str, ...] = ()


def status_for_failure(failure: ExecutionFailure) -> Status:
    """policy_denied and access_denied -> denied; timeout and error -> failed."""
    if failure in (ExecutionFailure.POLICY_DENIED, ExecutionFailure.ACCESS_DENIED):
        return Status.DENIED
    return Status.FAILED


def check_status_fields(
    *,
    status: Status,
    has_data: bool,
    confidence: Confidence | None,
    provenance: tuple[Provenance, ...],
    clarification: Clarification | None,
    reason: Reason | None,
) -> None:
    """Which fields each status requires. Shared by the wire response and the stored answer."""
    if status is Status.ANSWERED:
        if not has_data or confidence is None or not provenance:
            raise ValueError("answered requires data, confidence and provenance")
        return
    if has_data:
        raise ValueError(f"{status.value} must not carry data")
    if status is Status.NEEDS_CLARIFICATION:
        if clarification is None:
            raise ValueError("needs_clarification requires a clarification")
    elif reason is None:
        raise ValueError(f"{status.value} requires a reason")


class AskResponse(Contract):
    request_id: UUID
    status: Status
    data: Data | None = None
    query: QueryInfo | None = None
    confidence: Confidence | None = None
    assumptions: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    clarification: Clarification | None = None
    refine: RefineInfo = RefineInfo()
    narrative: str | None = None
    reason: Reason | None = None
    trace_id: TraceId

    @model_validator(mode="after")
    def _status_rules(self) -> "AskResponse":
        check_status_fields(
            status=self.status,
            has_data=self.data is not None,
            confidence=self.confidence,
            provenance=self.provenance,
            clarification=self.clarification,
            reason=self.reason,
        )
        return self
