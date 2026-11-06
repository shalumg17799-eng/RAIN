"""Data-source adapter interface, typed errors and result types.

The adapter is where a query meets the data platform, and the platform is the authority: roles,
grants, row-level security, a read-only transaction and a statement timeout all live there. Error
messages carry a kind and a code, never database text, which can repeat data values.
"""

import datetime
import decimal
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import sqlglot
from sqlglot.errors import SqlglotError

from insights.contracts.common import JsonScalar
from insights.contracts.enums import ColumnRole
from insights.datasources.identity import Binding


class DataSourceError(Exception):
    """Base for adapter failures."""


class AccessDeniedError(DataSourceError):
    """The platform refused: missing privilege, or a write inside a read-only transaction."""


class QueryTimeoutError(DataSourceError):
    """The statement ran past its timeout and was cancelled."""


class QueryError(DataSourceError):
    """Any other failure. `kind` is coarse; `code` is the database error code when there is one."""

    def __init__(self, kind: str, code: str = "") -> None:
        super().__init__(f"database error ({kind}{f', {code}' if code else ''})")
        self.kind = kind
        self.code = code


class AdapterUnavailableError(DataSourceError):
    """The driver is not installed or the adapter is not configured."""


@dataclass(frozen=True)
class ResultColumn:
    name: str
    type_name: str


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[ResultColumn, ...]
    rows: tuple[tuple[JsonScalar, ...], ...]
    truncated: bool
    duration_ms: int


@dataclass(frozen=True)
class PlanEstimate:
    total_cost: float
    plan_rows: int


class DataSourceAdapter(Protocol):
    def execute(
        self, sql: str, binding: Binding, *, max_rows: int, timeout_ms: int
    ) -> QueryResult: ...

    def explain(self, sql: str, binding: Binding, *, timeout_ms: int) -> PlanEstimate: ...

    def ping(self) -> None: ...


FailureKind = Literal["access_denied", "timeout", "error"]


def failure_kind(error: DataSourceError) -> FailureKind:
    if isinstance(error, AccessDeniedError):
        return "access_denied"
    if isinstance(error, QueryTimeoutError):
        return "timeout"
    return "error"


def ensure_single_statement(sql: str, dialect: str) -> None:
    """Refuse anything that is not exactly one statement, before any connection is made.

    Defense in depth behind L1, which already generates one statement from a checked tree. A second
    statement is the way to change the role or a session variable inside the transaction, so every
    adapter calls this first. The database is a second line: see the prepared EXPLAIN in
    `PostgresAdapter.explain`, and the cursor declaration in `execute`.
    """
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except (SqlglotError, RecursionError):
        raise AccessDeniedError(
            "the adapter refused SQL it cannot read as exactly one statement"
        ) from None
    if len(parsed) != 1 or parsed[0] is None:
        raise AccessDeniedError("the adapter refused SQL that is not exactly one statement")


def to_json_scalar(value: Any) -> JsonScalar:
    """Rows must be plain JSON values. Numbers stay numbers; everything else becomes text."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return value.total_seconds()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).hex()
    return str(value)


_TIME_TYPES = ("date", "time", "timestamp", "interval")
_NUMBER_TYPES = frozenset(
    [
        "int",
        "int2",
        "int4",
        "int8",
        "integer",
        "bigint",
        "smallint",
        "tinyint",
        "mediumint",
        "numeric",
        "decimal",
        "number",
        "float",
        "float4",
        "float8",
        "double",
        "real",
        "money",
        "serial",
        "bigserial",
        "smallserial",
    ]
)


def column_role(type_name: str, name: str = "") -> ColumnRole:
    """A first guess from the database type. The composer refines it with the catalog."""
    lowered = type_name.lower()
    if lowered.startswith(_TIME_TYPES):
        return ColumnRole.TIME
    base = lowered.split("(")[0].strip().removesuffix(" precision")
    if base in _NUMBER_TYPES and not name.lower().endswith(("_id", "id")):
        return ColumnRole.MEASURE
    return ColumnRole.DIMENSION


def column_names(columns: Sequence[ResultColumn]) -> list[str]:
    return [c.name for c in columns]
