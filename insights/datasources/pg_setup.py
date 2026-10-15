"""Admin-side PostgreSQL helpers used by product code (catalog build, eval freshness).

`admin_connection` opens a fail-fast admin connection to the app's data source. The synthetic-data
seeding and role/RLS setup that the tests need lives under tests/ (insights_test_support.
synthetic_setup); it is test-only and never imported by product code.
"""

from collections.abc import Mapping
from typing import Any

import psycopg

from insights.config import resolve_secret
from insights.contracts.common import SecretRef
from insights.contracts.profile import AppProfile


class SetupError(RuntimeError):
    """An admin database operation could not be completed."""


def admin_connection(
    app: AppProfile,
    environ: Mapping[str, str],
    *,
    lock_timeout_ms: int = 5_000,
    statement_timeout_ms: int = 60_000,
    connect_timeout_s: int = 5,
) -> psycopg.Connection[Any]:
    """An admin connection that fails fast: a lock it cannot get in 5 s is an error, not a wait."""
    source = app.datasources[0]
    user = environ.get("INSIGHTS_PG_ADMIN_USER", "insights_admin")
    try:
        password = resolve_secret(SecretRef(env="INSIGHTS_PG_ADMIN_PASSWORD"), environ)
    except LookupError as exc:
        raise SetupError(str(exc)) from exc
    return psycopg.connect(
        host=environ.get("INSIGHTS_PG_HOST", source.host),
        port=int(environ.get("INSIGHTS_PG_PORT", source.port or 5432)),
        dbname=source.database or "",
        user=user,
        password=password,
        connect_timeout=connect_timeout_s,
        options=f"-c lock_timeout={lock_timeout_ms} -c statement_timeout={statement_timeout_ms}",
    )
