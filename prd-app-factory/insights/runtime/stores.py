"""In-memory implementations: audit sink, result store, run store, token meter, deadline.

Each takes its clock as an argument and holds its own state, so there is no module-level mutable
state. Everything is guarded by a lock because requests run in worker threads.
"""

import threading
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from insights.contracts.common import JsonScalar
from insights.contracts.events import AuditEvent, TokenUsage
from insights.contracts.guards import assert_no_rows
from insights.contracts.principal import Principal
from insights.contracts.record import RunRecord
from insights.contracts.response import Column
from insights.contracts.state import ResultRef
from insights.skills_core.protocols import AuditSink, StoredResult

Clock = Callable[[], float]


MAX_SENSITIVE_STRINGS = 2000
MIN_SENSITIVE_LENGTH = 12


def _looks_identifying(text: str) -> bool:
    return len(text) >= MIN_SENSITIVE_LENGTH and any(
        ch.isspace() or ch.isdigit() or ch == "@" for ch in text
    )


class ResultNotFoundError(LookupError):
    """No such result for this owner. Unknown and foreign references look the same."""


class InMemoryAuditSink:
    """Append-only. `events()` returns a snapshot tuple, never the live list."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> None:
        if not isinstance(event, AuditEvent):
            raise TypeError("the audit sink accepts AuditEvent only")
        with self._lock:
            self._events.append(event)

    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)


class JsonlAuditSink:
    """Append-only JSON lines. One event per line, no rows by construction (AuditEvent is typed)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: AuditEvent) -> None:
        if not isinstance(event, AuditEvent):
            raise TypeError("the audit sink accepts AuditEvent only")
        line = event.model_dump_json() + "\n"
        with self._lock, open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line)


class FanOutAuditSink:
    """Writes to every sink; the first failure propagates, so a lost audit fails the run closed."""

    def __init__(self, *sinks: AuditSink) -> None:
        self._sinks = sinks

    def write(self, event: AuditEvent) -> None:
        for sink in self._sinks:
            sink.write(event)


@dataclass
class _Held:
    run_id: str
    owner: str
    stored: StoredResult
    expires_at: float


class InMemoryResultStore:
    """Rows by reference. Rows live here for the request and are never copied into state."""

    def __init__(self, clock: Clock = time.monotonic, ttl_seconds: float = 300.0) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._held: dict[str, _Held] = {}
        self._lock = threading.Lock()

    def put(
        self,
        *,
        run_id: str,
        owner: str,
        columns: Sequence[Column],
        rows: Sequence[Sequence[JsonScalar]],
    ) -> ResultRef:
        if any(len(row) != len(columns) for row in rows):
            raise ValueError("every row must have one value per column")
        stored = StoredResult(columns=tuple(columns), rows=tuple(tuple(row) for row in rows))
        ref = ResultRef(ref=f"mem-{uuid.uuid4().hex}")
        with self._lock:
            self._purge_expired()
            self._held[ref.ref] = _Held(run_id, owner, stored, self._clock() + self._ttl)
        return ref

    def get(self, ref: ResultRef, *, owner: str) -> StoredResult:
        with self._lock:
            self._purge_expired()
            held = self._held.get(ref.ref)
            if held is None or held.owner != owner:
                raise ResultNotFoundError("result not found")
            return held.stored

    def drop_run(self, run_id: str) -> None:
        with self._lock:
            for key in [k for k, h in self._held.items() if h.run_id == run_id]:
                del self._held[key]

    def run_sensitive_strings(self, run_id: str) -> tuple[str, ...]:
        """Text cells that look like names, emails or identifiers (a heuristic, see U-I15).

        Short category words such as `auto` or `personal_loan` are deliberately left out: they
        appear in questions and glossaries all the time and would block ordinary prompts.
        """
        found: dict[str, None] = {}
        with self._lock:
            self._purge_expired()
            for held in self._held.values():
                if held.run_id != run_id:
                    continue
                for row in held.stored.rows:
                    for cell in row:
                        if isinstance(cell, str) and _looks_identifying(cell):
                            found[cell] = None
                            if len(found) >= MAX_SENSITIVE_STRINGS:
                                return tuple(found)
        return tuple(found)

    def _purge_expired(self) -> None:
        now = self._clock()
        for key in [k for k, h in self._held.items() if h.expires_at <= now]:
            del self._held[key]


class InMemoryRunStore:
    """Run records, readable only by the principal who owns them."""

    def __init__(self) -> None:
        self._records: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def save(self, record: RunRecord) -> None:
        assert_no_rows(record.model_dump(mode="json"), "run record")
        with self._lock:
            self._records[record.run_id] = record

    def get(self, run_id: str, principal: Principal) -> RunRecord | None:
        with self._lock:
            record = self._records.get(run_id)
        if record is None:
            return None
        if record.owner_subject != principal.subject or record.owner_tenant != principal.tenant:
            return None  # same answer as "no such run": existence is not disclosed
        return record


class TokenMeter:
    def __init__(self) -> None:
        self._prompt = 0
        self._completion = 0
        self._lock = threading.Lock()

    def add(self, prompt_tokens: int, completion_tokens: int) -> None:
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts cannot be negative")
        with self._lock:
            self._prompt += prompt_tokens
            self._completion += completion_tokens

    def total(self) -> TokenUsage:
        with self._lock:
            return TokenUsage(prompt_tokens=self._prompt, completion_tokens=self._completion)


class MonotonicDeadline:
    """Cooperative deadline: checked between steps; adapters apply their own timeouts."""

    def __init__(self, clock: Clock, budget_ms: int) -> None:
        self._clock = clock
        self._end = clock() + budget_ms / 1000.0

    def remaining_ms(self) -> int:
        return round(max(0.0, self._end - self._clock()) * 1000)

    def expired(self) -> bool:
        return self._clock() >= self._end
