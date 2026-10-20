"""PostgreSQL adapter. Every call is one short read-only transaction:

    BEGIN READ ONLY
    SET LOCAL ROLE <role from the Binding>          (the role carries the grants and RLS policies)
    SET LOCAL search_path / statement_timeout / lock_timeout
    set_config('insights.<name>', <value>, true)    (session variables the policies read)
    <the checked query, on a server-side cursor, at most max_rows + 1 rows fetched>
    ROLLBACK

The adapter, not the SQL, sets role and session variables: L1 refuses SET, RESET and set_config in a
query, and the connecting user can reach other roles only through SET, which a query cannot issue.
"""

import json
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any

import psycopg
from psycopg import errors, sql
from psycopg.rows import tuple_row

from insights.config import resolve_secret
from insights.contracts.profile import DataSource
from insights.datasources.base import (
    AccessDeniedError,
    PlanEstimate,
    QueryError,
    QueryResult,
    QueryTimeoutError,
    ResultColumn,
    ensure_single_statement,
    to_json_scalar,
)
from insights.datasources.identity import Binding

CONNECT_TIMEOUT_S = 5
DIALECT = "postgres"


def _translate(exc: psycopg.Error) -> Exception:
    """Map a driver error to a typed one, without carrying any database text."""
    if isinstance(exc, errors.QueryCanceled):
        return QueryTimeoutError("statement exceeded its timeout")
    if isinstance(exc, errors.InsufficientPrivilege | errors.ReadOnlySqlTransaction):
        return AccessDeniedError("the database refused the operation")
    if isinstance(exc, errors.UndefinedTable | errors.UndefinedColumn | errors.UndefinedObject):
        return QueryError("unknown_object", exc.sqlstate or "")
    if isinstance(exc, errors.SyntaxError | errors.ProgrammingError):
        return QueryError("syntax", exc.sqlstate or "")
    if isinstance(exc, psycopg.OperationalError) and not exc.sqlstate:
        return QueryError("unavailable")
    return QueryError("database", exc.sqlstate or "")


class PostgresAdapter:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: str,
        connect: Callable[..., psycopg.Connection[Any]] = psycopg.connect,
    ) -> None:
        self._conninfo: dict[str, Any] = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "connect_timeout": CONNECT_TIMEOUT_S,
            "application_name": "insights-server",
        }
        self._connect = connect

    def __repr__(self) -> str:  # never show the password
        c = self._conninfo
        return f"PostgresAdapter({c['user']}@{c['host']}:{c['port']}/{c['dbname']})"

    # ---- public ----------------------------------------------------------------------------

    def execute(
        self, sql_text: str, binding: Binding, *, max_rows: int, timeout_ms: int
    ) -> QueryResult:
        ensure_single_statement(sql_text, DIALECT)
        started = time.monotonic()
        try:
            with self._connect(**self._conninfo) as conn:
                conn.read_only = True
                try:
                    self._prepare(conn, binding, timeout_ms)
                    with conn.cursor(
                        name=f"insights_{uuid.uuid4().hex}", row_factory=tuple_row
                    ) as cur:
                        cur.execute(sql_text)  # type: ignore[arg-type]
                        fetched = cur.fetchmany(max_rows + 1)
                        description = cur.description or ()
                        columns = tuple(
                            ResultColumn(c.name, self._type_name(conn, c.type_code))
                            for c in description
                        )
                finally:
                    conn.rollback()
        except psycopg.Error as exc:
            raise _translate(exc) from None
        rows = tuple(tuple(to_json_scalar(v) for v in row) for row in fetched[:max_rows])
        return QueryResult(
            columns=columns,
            rows=rows,
            truncated=len(fetched) > max_rows,
            duration_ms=round((time.monotonic() - started) * 1000),
        )

    def ping(self) -> None:
        """Open a connection and run `SELECT 1`. Raises a typed error when the platform is down."""
        try:
            with self._connect(**self._conninfo) as conn:
                conn.read_only = True
                conn.execute("SELECT 1")
                conn.rollback()
        except psycopg.Error as exc:
            raise _translate(exc) from None

    def explain(self, sql_text: str, binding: Binding, *, timeout_ms: int) -> PlanEstimate:
        ensure_single_statement(sql_text, DIALECT)
        try:
            with self._connect(**self._conninfo) as conn:
                conn.read_only = True
                try:
                    self._prepare(conn, binding, timeout_ms)
                    with conn.cursor(row_factory=tuple_row) as cur:
                        # prepare=True sends one prepared statement, so PostgreSQL itself refuses
                        # "...; RESET ROLE" ("cannot insert multiple commands into a prepared
                        # statement"). Sent as plain text it ran both: the hole found in S5.
                        # (`execute` is safe too: DECLARE ... CURSOR FOR takes exactly one query.)
                        cur.execute(f"EXPLAIN (FORMAT JSON) {sql_text}", prepare=True)  # type: ignore[arg-type]
                        raw = cur.fetchone()
                finally:
                    conn.rollback()
        except psycopg.Error as exc:
            raise _translate(exc) from None
        try:
            payload = raw[0] if raw else None
            plan = (json.loads(payload) if isinstance(payload, str) else payload)[0]["Plan"]
            return PlanEstimate(
                total_cost=float(plan["Total Cost"]), plan_rows=int(plan["Plan Rows"])
            )
        except (TypeError, KeyError, IndexError, ValueError):
            raise QueryError("plan_unreadable") from None

    # ---- inside the transaction ------------------------------------------------------------

    @staticmethod
    def _prepare(conn: psycopg.Connection[Any], binding: Binding, timeout_ms: int) -> None:
        """Set the role, the search_path and every session GUC in ONE round trip.

        Each of these used to be its own `execute()`, so one query cost about a dozen round trips;
        through Docker on Windows a round trip is ~47 ms and this dominated a call (E7). They are
        all built by the adapter from the validated binding -- the role and search_path are
        identifiers, the GUC names are fixed, and the GUC values (which include the caller's
        subject and attributes) are escaped with `sql.Literal` -- so sending them as one batch
        changes the round-trip count, not what runs or who runs it. With no parameters psycopg
        uses the simple query protocol, which runs several statements in a single round trip.

        The caller's own SQL is never part of this batch: it stays isolated to one statement, by
        the server-side cursor declaration in `execute` and the prepared EXPLAIN in `explain`.
        """
        settings = (
            ("statement_timeout", str(timeout_ms)),
            ("lock_timeout", "2000"),
            ("idle_in_transaction_session_timeout", str(timeout_ms + 5000)),
            *binding.settings.items(),
        )
        statements = []
        if binding.role:
            statements.append(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(binding.role)))
        if binding.search_path:
            path = sql.SQL(", ").join(sql.Identifier(p) for p in binding.search_path)
            statements.append(sql.SQL("SET LOCAL search_path TO {}").format(path))
        set_configs = sql.SQL(", ").join(
            sql.SQL("set_config({}, {}, true)").format(sql.Literal(name), sql.Literal(value))
            for name, value in settings
        )
        statements.append(sql.SQL("SELECT {}").format(set_configs))
        # One execute(), no parameters -> one simple-protocol round trip for the whole batch.
        with conn.cursor() as cur:
            cur.execute(sql.SQL("; ").join(statements))

    @staticmethod
    def _type_name(conn: psycopg.Connection[Any], oid: int) -> str:
        info = conn.adapters.types.get(oid)
        return info.name if info is not None else "unknown"


def adapter_for(source: DataSource, environ: Mapping[str, str]) -> PostgresAdapter:
    """Build an adapter from a profile's data source. Secrets are resolved from `environ` here."""
    if source.kind != "postgres" or source.user is None or source.password is None:
        raise ValueError(f"data source {source.id!r} is not a configured PostgreSQL source")
    return PostgresAdapter(
        host=source.host,
        port=source.port or 5432,
        dbname=source.database or "",
        user=resolve_secret(source.user, environ),
        password=resolve_secret(source.password, environ),
    )
