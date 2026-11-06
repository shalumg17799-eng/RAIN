"""The golden set: questions with gold SQL and an expected status, in dev and held-out splits.

A case's expected result set is the gold SQL run on the sample database under the case's own role
(so a branch manager's gold result is filtered like the real one). The file carries a review block:
version 0 is SYNTHETIC and marked `needs_sme_review`; nothing in it is a business truth yet.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from insights.catalog.examples import columns_resolve, tables_read_by
from insights.catalog.snapshot import CatalogError, CatalogSnapshot
from insights.contracts.common import Contract, Identifier
from insights.contracts.enums import Intent, Status
from insights.contracts.profile import AppProfile
from insights.contracts.request import AskContext
from insights.yamlio import load_yaml

Split = Literal["dev", "held_out"]


class Expectation(Contract):
    status: Status
    intent: Intent | None = None
    tables: tuple[str, ...] = ()
    """Gold tables: the ones the sliver must contain (sliver recall)."""
    sql: str | None = None
    """Gold SQL; its result on the database is the expected result set."""
    empty: bool = False
    """The gold result has no rows (for example a window with no data yet)."""
    reason: str | None = None
    """Expected `reason.code` on the answer, for example `no_data_in_period` (P1)."""
    note: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def _consistent(self) -> "Expectation":
        if self.status is Status.ANSWERED and not self.sql:
            raise ValueError("an answered case needs gold sql")
        if self.status is not Status.ANSWERED and self.sql:
            raise ValueError("only an answered case carries gold sql")
        return self


class GoldenCase(Contract):
    id: Identifier
    split: Split
    role: Identifier | None
    """None means a caller with no role in the app."""
    attributes: dict[str, str] = Field(default_factory=dict)
    question: str = Field(min_length=1, max_length=2000)
    context: AskContext = AskContext()
    tags: tuple[str, ...] = ()
    expect: Expectation


class Review(Contract):
    status: Literal["needs_sme_review", "reviewed"]
    note: str = ""
    reviewed_by: str | None = None


class GoldenSet(Contract):
    version: int
    app: Identifier
    review: Review
    cases: tuple[GoldenCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "GoldenSet":
        ids = [c.id for c in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case ids must be unique")
        return self

    def split(self, name: str) -> tuple[GoldenCase, ...]:
        if name == "all":
            return self.cases
        return tuple(c for c in self.cases if c.split == name)


def load_golden_set(path: Path, app: AppProfile, snapshot: CatalogSnapshot) -> GoldenSet:
    """Load and validate: roles exist, gold SQL is one SELECT over catalog objects, tables exist."""
    try:
        parsed = GoldenSet.model_validate(load_yaml(path.read_text(encoding="utf-8")) or {})
    except OSError as exc:
        raise CatalogError(f"cannot read the golden set {path}: {exc}") from exc
    except (ValidationError, ValueError, TypeError) as exc:
        raise CatalogError(f"invalid golden set {path}: {exc}") from exc
    if parsed.app != app.id:
        raise CatalogError(f"golden set is for app {parsed.app!r}, not {app.id!r}")
    schema = {t.name: {c.name: c.type for c in t.columns} for t in snapshot.tables}
    problems: list[str] = []
    for case in parsed.cases:
        if case.role is not None and case.role not in app.roles:
            problems.append(f"{case.id}: unknown role {case.role!r}")
        unknown = [t for t in case.expect.tables if snapshot.table(t) is None]
        if unknown:
            problems.append(f"{case.id}: unknown gold table(s) {', '.join(unknown)}")
        if case.expect.sql:
            try:
                tables = tables_read_by(case.expect.sql, snapshot.dialect.value)
            except ValueError as exc:
                problems.append(f"{case.id}: gold sql: {exc}")
                continue
            if any(snapshot.table(t) is None for t in tables):
                problems.append(f"{case.id}: gold sql reads a table the catalog lacks")
            column_problem = columns_resolve(case.expect.sql, schema, snapshot.dialect.value)
            if column_problem:
                problems.append(f"{case.id}: gold sql: {column_problem}")
    if problems:
        raise CatalogError("; ".join(problems))
    return parsed
