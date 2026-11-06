"""Bootstrap entry point and PostgreSQL access provisioning."""

from collections.abc import Mapping, Sequence
from typing import Any

from insights.catalog.entitlements import normalize_table
from insights.contracts.profile import AppProfile
from insights.datasources import naming
from insights.datasources.pg_access import all_roles, render_access_sql


def setup_pg_governance(
    conn: Any,
    app: AppProfile,
    columns_by_table: Mapping[str, Sequence[str]],
    runtime_user: str,
) -> int:
    """Apply profile grants and RLS policies, refusing incomplete or unprivileged setups."""
    from psycopg import sql

    statements = render_access_sql(app, columns_by_table)
    policy_statements = [statement for statement in statements if statement.startswith("CREATE POLICY")]
    if not policy_statements:
        raise RuntimeError("app profile defines no row-filter policies; refusing to provision without RLS")

    with conn.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user")
        privileges = cursor.fetchone()
        if privileges is None or not any(privileges):
            raise PermissionError("PostgreSQL provisioning requires a superuser or CREATEROLE account")

        for role_name in all_roles(app):
            cursor.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (role_name,))
            existing = cursor.fetchone()
            if existing is None:
                cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role_name)))
            elif existing[0]:
                cursor.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(sql.Identifier(role_name)))

        for statement in statements:
            cursor.execute(statement)
        for persona in app.roles:
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(naming.per_user_role(persona)),
                    sql.Identifier(runtime_user),
                )
            )
    return len(policy_statements)


from bootstrap import main


if __name__ == "__main__":
    raise SystemExit(main())