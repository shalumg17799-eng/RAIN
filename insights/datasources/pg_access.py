"""Turn an app profile into PostgreSQL roles, grants, row-level security and masked views.

The profile is the single source of truth, so the database cannot drift from what the profile says
each role may see. Statements are rendered as text (identifiers quoted, never free text) so they can
be unit-tested without a database; `pg_setup` runs them.

  per_user (the target)   one NOLOGIN role per app role. Column grants limit columns; row-level
                          security policies apply the row filters; a role with masks reads a view
                          in schema v_<role> (filter baked in) and has no grant on the base table.
  views fallback          one role per app role that can read only schema sp_<role>: views with the
                          columns, masks and row filter baked in. No base-table grants.
  predicates fallback     one broad read role; the application injects the row filters (L1).

`{attr}` in a row filter becomes `current_setting('insights.attr', true)`; the adapter sets those
variables from the principal's claims, and an unset one makes the comparison NULL (no rows).
"""

import re
from collections.abc import Callable, Mapping, Sequence

from insights.catalog.entitlements import default_schema_of, normalize_table
from insights.contracts.enums import MaskKind
from insights.contracts.profile import AppProfile, TableAccess
from insights.datasources import naming

_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")
_MASKS: dict[MaskKind, Callable[[str], str]] = {
    MaskKind.REDACT: lambda col: "'***'::text",
    MaskKind.HASH: lambda col: f"md5({col}::text)",
    MaskKind.LAST4: lambda col: f"('****' || right({col}::text, 4))",
    MaskKind.NULL: lambda col: "NULL::text",
}


def q(identifier: str) -> str:
    """Quote an identifier. Names come from a validated profile; this is belt and braces."""
    return '"' + identifier.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def rls_filter(template: str) -> str:
    """Row filter as a SQL condition reading the session variables the adapter sets."""
    return _PLACEHOLDER.sub(
        lambda m: f"current_setting({sql_literal(naming.guc(m.group(1)))}, true)", template
    )


def _select_list(columns: Sequence[str], access: TableAccess) -> str:
    parts = []
    for column in columns:
        mask = access.masks.get(column)
        parts.append(f"{_MASKS[mask](q(column))} AS {q(column)}" if mask is not None else q(column))
    return ", ".join(parts)


def _visible(access: TableAccess, table_columns: Sequence[str]) -> list[str]:
    if access.columns == "*":
        return list(table_columns)
    wanted = {c.lower() for c in access.columns}
    return [c for c in table_columns if c.lower() in wanted]


def _tables(app: AppProfile, role: str) -> dict[str, TableAccess]:
    schema = default_schema_of(app)
    return {normalize_table(t, schema): a for t, a in app.roles[role].tables.items()}


def render_access_sql(app: AppProfile, table_columns: Mapping[str, Sequence[str]]) -> list[str]:
    """Every statement, in order, that makes the database enforce the profile.

    `table_columns` maps each table to its column names (read from the database by the caller).
    Re-running after the tables were recreated restores all grants, policies and views.
    """
    schema = default_schema_of(app) or "public"
    public = q(schema)
    out: list[str] = []
    roles = list(app.roles)
    sql_table_names: dict[str, str] = {}
    for role in roles:
        for profile_name in app.roles[role].tables:
            normalized = normalize_table(profile_name, schema)
            sql_table_names.setdefault(normalized, profile_name.split(".")[-1])

    for role in roles:
        for schema_name in (naming.per_user_view_schema(role), naming.views_schema(role)):
            out.append(f"DROP SCHEMA IF EXISTS {q(schema_name)} CASCADE")
            out.append(f"CREATE SCHEMA {q(schema_name)}")

    # which tables carry row filters for any role (they need row-level security switched on)
    filtered_tables: set[str] = set()
    for role in roles:
        for table, access in _tables(app, role).items():
            if access.row_filter:
                filtered_tables.add(table)
    for table in sorted(filtered_tables):
        out.append(f"ALTER TABLE {public}.{q(sql_table_names[table])} ENABLE ROW LEVEL SECURITY")

    for role in roles:
        user_role = q(naming.per_user_role(role))
        views_role = q(naming.views_role(role))
        out.append(f"GRANT USAGE ON SCHEMA {public} TO {user_role}")
        for table, access in _tables(app, role).items():
            visible = _visible(access, table_columns[table])
            masked = bool(access.masks)
            sql_table = q(sql_table_names[table])
            if masked:
                view_schema = q(naming.per_user_view_schema(role))
                where = f" WHERE {rls_filter(access.row_filter)}" if access.row_filter else ""
                out.append(
                    f"CREATE VIEW {view_schema}.{q(table)} AS SELECT "
                    f"{_select_list(visible, access)} FROM {public}.{sql_table}{where}"
                )
                out.append(f"GRANT USAGE ON SCHEMA {view_schema} TO {user_role}")
                out.append(f"GRANT SELECT ON {view_schema}.{q(table)} TO {user_role}")
            else:
                if access.columns == "*":
                    out.append(f"GRANT SELECT ON {public}.{sql_table} TO {user_role}")
                else:
                    cols = ", ".join(q(c) for c in visible)
                    out.append(f"GRANT SELECT ({cols}) ON {public}.{sql_table} TO {user_role}")
                if table in filtered_tables:
                    condition = rls_filter(access.row_filter) if access.row_filter else "true"
                    policy = q(f"insights_{role}_{table}")
                    out.append(f"DROP POLICY IF EXISTS {policy} ON {public}.{sql_table}")
                    out.append(
                        f"CREATE POLICY {policy} ON {public}.{sql_table} FOR SELECT "
                        f"TO {user_role} USING ({condition})"
                    )

            # the views fallback: columns, masks and filter all baked into sp_<role>
            sp_schema = q(naming.views_schema(role))
            sp_where = f" WHERE {rls_filter(access.row_filter)}" if access.row_filter else ""
            out.append(
                f"CREATE VIEW {sp_schema}.{q(table)} AS SELECT {_select_list(visible, access)} "
                f"FROM {public}.{sql_table}{sp_where}"
            )
        out.append(f"GRANT USAGE ON SCHEMA {q(naming.views_schema(role))} TO {views_role}")
        out.append(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA {q(naming.views_schema(role))} TO {views_role}"
        )

    # the predicates fallback: broad read access, filters applied by the application
    union = sorted({t for role in roles for t in _tables(app, role)})
    out.append(f"GRANT USAGE ON SCHEMA {public} TO {q(naming.PREDICATE_ROLE)}")
    for table in union:
        sql_table = q(sql_table_names[table])
        out.append(f"GRANT SELECT ON {public}.{sql_table} TO {q(naming.PREDICATE_ROLE)}")
        if table in filtered_tables:
            # row-level security is on for the other roles; here the application applies the filter
            policy = q(f"{naming.PREDICATE_ROLE}_{table}")
            out.append(f"DROP POLICY IF EXISTS {policy} ON {public}.{sql_table}")
            out.append(
                f"CREATE POLICY {policy} ON {public}.{sql_table} FOR SELECT "
                f"TO {q(naming.PREDICATE_ROLE)} USING (true)"
            )
    return out


def all_roles(app: AppProfile) -> list[str]:
    """Every NOLOGIN role the setup creates."""
    names = [naming.PREDICATE_ROLE]
    for role in app.roles:
        names += [naming.per_user_role(role), naming.views_role(role)]
    return names
