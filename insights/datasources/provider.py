"""The `Services.data` implementation: one adapter per app, from its profile and the environment.

Secrets are resolved from the environment only here, at build time, never stored in the profile.
`INSIGHTS_PG_HOST` and `INSIGHTS_PG_PORT` override the profile's host and port so the same profile
works on a developer machine (127.0.0.1:55432) and inside the compose network (postgres:5432).
"""

import threading
from collections.abc import Mapping

from insights.config import resolve_secret
from insights.contracts.profile import AppProfile
from insights.datasources import databricks
from insights.datasources.base import AdapterUnavailableError, DataSourceAdapter
from insights.datasources.postgres import PostgresAdapter


class EnvDataSources:
    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = dict(environ)
        self._adapters: dict[tuple[str, str], DataSourceAdapter] = {}
        self._lock = threading.Lock()

    def adapter_for(self, app: AppProfile) -> DataSourceAdapter:
        key = (app.id, app.version)
        with self._lock:
            if key not in self._adapters:
                self._adapters[key] = self._build(app)
            return self._adapters[key]

    def _build(self, app: AppProfile) -> DataSourceAdapter:
        source = app.datasources[0]
        if source.kind == "postgres":
            if source.user is None or source.password is None:
                raise AdapterUnavailableError(f"data source {source.id!r} has no credentials")
            return PostgresAdapter(
                host=self._environ.get("INSIGHTS_PG_HOST", source.host),
                port=int(self._environ.get("INSIGHTS_PG_PORT", source.port or 5432)),
                dbname=source.database or "",
                user=resolve_secret(source.user, self._environ),
                password=resolve_secret(source.password, self._environ),
            )
        return databricks.adapter_for(source, self._environ)
