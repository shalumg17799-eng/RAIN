"""Who may see what, from the app profile. Shared by policy, the database setup and retrieval (S6).

A principal may hold several roles, but one query runs as exactly one: the first role in the app
profile's order that the principal holds. Profile order is therefore the precedence (list the most
privileged role first if that is what you want), and the choice is the same in every layer.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile, TableAccess
from insights.contracts.state import SliverTable


def effective_role(principal: Principal, app: AppProfile) -> str | None:
    held = set(principal.roles)
    return next((role for role in app.roles if role in held), None)


def normalize_table(name: str, default_schema: str | None = None) -> str:
    """Lowercase, and drop the default schema so `public.member` and `member` are one table."""
    parts = name.lower().split(".")
    if len(parts) > 1 and default_schema and parts[-2] == default_schema.lower():
        parts = parts[-1:]
    return ".".join(parts)


def default_schema_of(app: AppProfile) -> str | None:
    return app.datasources[0].default_schema


def source_schemas(app: AppProfile) -> tuple[str, ...]:
    """The schemas on the search path: the source's `schemas` (a multi-schema source like NFCU's
    13), else its single `default_schema`. Bare table names resolve against these."""
    source = app.datasources[0]
    if source.schemas:
        return tuple(source.schemas)
    return (source.default_schema,) if source.default_schema else ()


def role_tables(app: AppProfile, role: str) -> dict[str, TableAccess]:
    schema = default_schema_of(app)
    return {normalize_table(t, schema): a for t, a in app.roles[role].tables.items()}


@dataclass(frozen=True)
class AllowedObjects:
    """Tables and columns a query may touch: the sliver intersected with the role's entitlements."""

    role: str | None
    tables: Mapping[str, Mapping[str, str]]
    """table name -> {column name -> type}. Empty when the principal has no role in this app."""

    def columns_of(self, table: str) -> Mapping[str, str]:
        return self.tables.get(table, {})


def allowed_objects(
    sliver_tables: Iterable[SliverTable], app: AppProfile, principal: Principal
) -> AllowedObjects:
    role = effective_role(principal, app)
    if role is None:
        return AllowedObjects(None, {})
    schema = default_schema_of(app)
    entitled = role_tables(app, role)
    out: dict[str, dict[str, str]] = {}
    for table in sliver_tables:
        name = normalize_table(table.name, schema)
        access = entitled.get(name)
        if access is None:
            continue
        wanted = None if access.columns == "*" else {c.lower() for c in access.columns}
        columns = {
            c.name.lower(): c.type
            for c in table.columns
            if wanted is None or c.name.lower() in wanted
        }
        if columns:
            out[name] = columns
    return AllowedObjects(role, out)


def tables_for(app: AppProfile, roles: Sequence[str]) -> set[str]:
    schema = default_schema_of(app)
    return {
        normalize_table(t, schema)
        for role in roles
        if role in app.roles
        for t in app.roles[role].tables
    }
