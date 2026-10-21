"""The human-in-the-loop decision store: pending reviews, blocking waits, audited decisions.

One process-wide store is shared between the hitl-reviewer skill (which registers a hold and
blocks, bounded by its spec timeout and the run deadline) and the HTTP API (which lists pending
holds and posts decisions). Everything is bounded and typed: a decision is approve, edit or
reject; no decision within the timeout resolves as `timeout`, and the run answers honestly that
it could not be verified. The store holds NO rows — only the question, the SQL, the hold reason
and the proposed narrative, which are exactly what a reviewer needs to judge.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Literal

HoldReason = Literal["low_confidence", "governance_flag", "sensitive_intent", "forced"]
DecisionAction = Literal["approve", "edit", "reject"]
ResolutionLabel = Literal["approved", "edited", "rejected", "timeout"]

MAX_NARRATIVE_CHARS = 2000


@dataclass(frozen=True)
class HitlDecision:
    action: DecisionAction
    decided_by: str
    edited_narrative: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.action == "edit" and not (self.edited_narrative or "").strip():
            raise ValueError("an edit decision needs an edited_narrative")
        if self.edited_narrative is not None and len(self.edited_narrative) > MAX_NARRATIVE_CHARS:
            raise ValueError(f"edited_narrative is longer than {MAX_NARRATIVE_CHARS} chars")


@dataclass
class _Hold:
    run_id: str
    trace_id: str
    reason: str
    question: str
    sql: str | None
    confidence: float
    proposed_narrative: str | None
    created_at: float
    event: threading.Event = field(default_factory=threading.Event)
    decision: HitlDecision | None = None


@dataclass(frozen=True)
class PendingReview:
    """The read model the API serves to reviewers."""

    run_id: str
    trace_id: str
    reason: str
    question: str
    sql: str | None
    confidence: float
    proposed_narrative: str | None
    waiting_s: float


class HitlStore:
    def __init__(self, clock=time.time) -> None:
        self._holds: dict[str, _Hold] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def hold(
        self,
        *,
        run_id: str,
        trace_id: str,
        reason: str,
        question: str,
        sql: str | None = None,
        confidence: float = 0.0,
        proposed_narrative: str | None = None,
    ) -> None:
        with self._lock:
            if run_id in self._holds:
                raise ValueError(f"run {run_id} already has a pending review")
            self._holds[run_id] = _Hold(
                run_id=run_id,
                trace_id=trace_id,
                reason=reason,
                question=question,
                sql=sql,
                confidence=confidence,
                proposed_narrative=proposed_narrative,
                created_at=self._clock(),
            )

    def pending(self) -> list[PendingReview]:
        now = self._clock()
        with self._lock:
            return [
                PendingReview(
                    run_id=h.run_id,
                    trace_id=h.trace_id,
                    reason=h.reason,
                    question=h.question,
                    sql=h.sql,
                    confidence=h.confidence,
                    proposed_narrative=h.proposed_narrative,
                    waiting_s=round(now - h.created_at, 1),
                )
                for h in self._holds.values()
                if not h.event.is_set()
            ]

    def decide(self, run_id: str, decision: HitlDecision) -> bool:
        """Record the decision and wake the waiting run. False when there is nothing to decide."""
        with self._lock:
            hold = self._holds.get(run_id)
            if hold is None or hold.event.is_set():
                return False
            hold.decision = decision
            hold.event.set()
            return True

    def wait(self, run_id: str, timeout_s: float) -> HitlDecision | None:
        """Block until a decision or the timeout. None means the hold timed out."""
        with self._lock:
            hold = self._holds.get(run_id)
        if hold is None:
            raise LookupError(f"run {run_id} has no pending review")
        decided = hold.event.wait(timeout=max(0.0, timeout_s))
        with self._lock:
            self._holds.pop(run_id, None)
        return hold.decision if decided else None

    def abandon(self, run_id: str) -> None:
        with self._lock:
            self._holds.pop(run_id, None)
