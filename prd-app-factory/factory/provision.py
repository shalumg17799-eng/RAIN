"""Provision an App Pack into a PostgreSQL server: load the latest data version
with its recorded types and apply the governed profile (roles, grants, RLS).

Used for deployment (the Azure provisioning job runs `python -m factory provision
--app <id>` against Azure Database for PostgreSQL) and is idempotent."""
from __future__ import annotations

import csv
import sys

from psycopg import sql as psql

from factory.apppack import AppPack
from factory.config import ROOT, pg_settings, schema_for
from factory.tools.data import _convert, snake
from factory.tools.db import connect, ensure_database

sys.path.insert(0, str(ROOT))


def provision(app_id: str) -> dict:
    from insights.bootstrap import setup_pg_governance
    from insights.catalog.entitlements import normalize_table
    from insights.contracts.profile import load_app_profile

    pack = AppPack(app_id)
    versions = pack.read_json("reports/data_versions.json", [])
    if not versions:
        raise SystemExit("no data version recorded; run agent 2 first")
    # Latest version of each table (a recalibration may reload only some tables).
    latest: dict[str, dict] = {}
    for v in versions:
        for t in v["tables"]:
            latest[t["table"]] = {**t, "version": v["version"]}
    ensure_database()
    schema = schema_for(app_id)
    loaded = {}
    with connect() as conn:
        conn.execute(psql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(psql.Identifier(schema)))
        for table, info in latest.items():
            files = list(pack.path("data", info["version"]).glob("*.csv"))
            src = next((f for f in files if snake(f.stem) == table), None)
            if src is None:
                raise SystemExit(f"{table}: CSV not found in data/{info['version']}")
            with src.open(newline="", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = [snake(h) for h in next(reader)]
                rows = [tuple(_convert(r[i] if i < len(r) else "", info["types"][c]) for i, c in enumerate(header))
                        for r in reader]
            ident = psql.Identifier(schema, table)
            conn.execute(psql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(ident))
            conn.execute(psql.SQL("CREATE TABLE {} ({})").format(ident, psql.SQL(", ").join(
                psql.SQL("{} {}").format(psql.Identifier(c), psql.SQL(info["types"][c])) for c in header)))
            with conn.cursor() as cur:
                cur.executemany(psql.SQL("INSERT INTO {} VALUES ({})").format(
                    ident, psql.SQL(", ").join(psql.Placeholder() * len(header))), rows)
            loaded[table] = len(rows)
    profile_path = pack.path("insights", app_id, "app.yaml")
    policies = 0
    if profile_path.is_file():
        profile = load_app_profile(profile_path)
        with connect() as conn:
            cols = conn.execute("SELECT table_name, column_name FROM information_schema.columns "
                                "WHERE table_schema = %s ORDER BY ordinal_position", (schema,)).fetchall()
            by_table: dict[str, list[str]] = {}
            for t, c in cols:
                by_table.setdefault(normalize_table(t, schema), []).append(c)
            policies = setup_pg_governance(conn, profile, by_table, pg_settings()["user"])
    return {"schema": schema, "tables": loaded, "row_level_policies": policies}
