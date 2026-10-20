"""Databricks SQL adapter: a SKELETON. Not verified against a workspace (docs/open-questions.md V1).

It follows the same interface as the PostgreSQL adapter so the executor does not change. It needs
the `databricks-sql-connector` package, which is deliberately not a pinned dependency yet: the
driver is imported only when a connection is made, and a clear error says what is missing.

On Databricks the authority is Unity Catalog under the caller's own identity (identity mode
`per_user`: the caller's OAuth token reaches the warehouse, so row filters and column masks apply
to that person). A service-principal token is the weaker fallback and needs a recorded risk.
"""

import importlib
import time
from collections.abc import Callable, Mapping
from typing import Any

from insights.contracts.profile import DataSource
from insights.datasources.base import (
    AdapterUnavailableError,
    PlanEstimate,
    QueryError,
    QueryResult,
    ResultColumn,
    ensure_single_statement,
    to_json_scalar,
)
from insights.datasources.identity import Binding

DRIVER_HINT = (
    "the Databricks driver is not installed; add a pinned `databricks-sql-connector` "
    "to pyproject.toml and run scripts/relock.py before using this adapter"
)


def _default_connect(**kwargs: Any) -> Any:
    try:
        module = importlib.import_module("databricks.sql")
    except ImportError as exc:
        raise AdapterUnavailableError(DRIVER_HINT) from exc
    return module.connect(**kwargs)


class DatabricksAdapter:
    def __init__(
        self,
        *,
        host: str,
        http_path: str,
        token: str,
        catalog: str | None = None,
        schema: str | None = None,
        connect: Callable[..., Any] = _default_connect,
    ) -> None:
        if not host or not http_path or not token:
            raise AdapterUnavailableError("host, http_path and an access token are all required")
        self._host, self._http_path, self._token = host, http_path, token
        self._catalog, self._schema = catalog, schema
        self._connect = connect

    def __repr__(self) -> str:  # never show the token
        return f"DatabricksAdapter({self._host}, http_path={self._http_path!r})"

    def _connection(self) -> Any:
        return self._connect(
            server_hostname=self._host,
            http_path=self._http_path,
            access_token=self._token,
            catalog=self._catalog,
            schema=self._schema,
        )

    def execute(self, sql: str, binding: Binding, *, max_rows: int, timeout_ms: int) -> QueryResult:
        ensure_single_statement(sql, "databricks")
        started = time.monotonic()
        try:
            with self._connection() as conn, conn.cursor() as cursor:
                cursor.execute(sql)
                fetched = cursor.fetchmany(max_rows + 1)
                description = cursor.description or ()
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise QueryError("database", type(exc).__name__) from None
        columns = tuple(ResultColumn(str(d[0]), str(d[1])) for d in description)
        rows = tuple(tuple(to_json_scalar(v) for v in row) for row in fetched[:max_rows])
        return QueryResult(
            columns=columns,
            rows=rows,
            truncated=len(fetched) > max_rows,
            duration_ms=round((time.monotonic() - started) * 1000),
        )

    def ping(self) -> None:
        try:
            with self._connection() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise QueryError("unavailable", type(exc).__name__) from None

    def explain(self, sql: str, binding: Binding, *, timeout_ms: int) -> PlanEstimate:
        raise AdapterUnavailableError(
            "EXPLAIN cost parsing is not implemented for Databricks and has not been verified"
        )


def adapter_for(source: DataSource, environ: Mapping[str, str]) -> DatabricksAdapter:
    from insights.config import resolve_secret

    if source.kind != "databricks" or source.token is None or not source.http_path:
        raise ValueError(f"data source {source.id!r} is not a configured Databricks source")
    return DatabricksAdapter(
        host=source.host,
        http_path=source.http_path,
        token=resolve_secret(source.token, environ),
        catalog=source.database,
        schema=source.default_schema,
    )
