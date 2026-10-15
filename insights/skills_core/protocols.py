"""Interfaces a skill's `ctx` exposes. Implemented elsewhere (gateway in S4, runtime in S3).

Defined here, at the bottom of the dependency order, so skills_core imports nothing above it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from insights.contracts.common import JsonScalar
from insights.contracts.enums import Purpose
from insights.contracts.events import AuditEvent, TokenUsage
from insights.contracts.gateway import CompletionResult, Message
from insights.contracts.response import Column
from insights.contracts.state import ResultRef


class Gateway(Protocol):
    """The only way a skill reaches a model. Skills name a purpose, never a model or provider."""

    def complete(
        self,
        messages: Sequence[Message],
        purpose: Purpose,
        ctx: Mapping[str, Any],
        response_schema: dict[str, Any] | None = None,
    ) -> CompletionResult: ...


class AuditSink(Protocol):
    def write(self, event: AuditEvent) -> None: ...


@dataclass(frozen=True)
class StoredResult:
    columns: tuple[Column, ...]
    rows: tuple[tuple[JsonScalar, ...], ...]


class ResultStore(Protocol):
    """Rows by reference: in memory, scoped to one request and one owner."""

    def put(
        self,
        *,
        run_id: str,
        owner: str,
        columns: Sequence[Column],
        rows: Sequence[Sequence[JsonScalar]],
    ) -> ResultRef: ...

    def get(self, ref: ResultRef, *, owner: str) -> StoredResult: ...

    def drop_run(self, run_id: str) -> None: ...

    def run_sensitive_strings(self, run_id: str) -> tuple[str, ...]:
        """Identifying-looking text values held for this run, for the gateway's leak check."""
        ...


class UsageMeter(Protocol):
    def add(self, prompt_tokens: int, completion_tokens: int) -> None: ...

    def total(self) -> TokenUsage: ...


class Deadline(Protocol):
    def remaining_ms(self) -> int: ...

    def expired(self) -> bool: ...


class Emit(Protocol):
    """Typed progress note from a skill: a code and an optional count. Never free text."""

    def __call__(self, note: str, count: int | None = None) -> None: ...


class ServiceNotConfiguredError(LookupError):
    """A skill asked for a shared service the runtime was not given."""


@dataclass(frozen=True)
class Services:
    """Per-process shared services, injected by the runtime and reached through `ctx["services"]`.

    Skills never build these themselves and never keep module-level state: a skill that needs the
    app's catalog asks `services.catalogs`, one that needs the data platform asks `services.data`.
    Fakes go here in tests. `catalogs.for_app(app)` returns the loaded catalog and retriever;
    `kag.for_app(app)` the knowledge-graph seam; `data.adapter_for(app)` the data-source adapter.
    """

    catalogs: Any = None
    kag: Any = None
    data: Any = None

    def need(self, name: str) -> Any:
        value = getattr(self, name)
        if value is None:
            raise ServiceNotConfiguredError(f"the runtime has no {name!r} service configured")
        return value
