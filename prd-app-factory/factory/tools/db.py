"""Database access for the factory's staging environment (PostgreSQL).

Each app gets its own schema app_<id> in the `factory` database. The agents
only ever get read-only SQL; loading is done by the deterministic loader."""
from __future__ import annotations

import datetime
import decimal

import psycopg
import sqlglot
from psycopg import sql as psql
from sqlglot import exp

from factory.config import pg_settings, schema_for


def ensure_database() -> None:
    """Create the factory database on first use (needs CREATEDB / superuser)."""
    admin = pg_settings(dbname="postgres")
    target = pg_settings()["dbname"]
    with psycopg.connect(**admin, autocommit=True, connect_timeout=5) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,)).fetchone()
        if not exists:
            conn.execute(psql.SQL("CREATE DATABASE {}").format(psql.Identifier(target)))


def connect(**kw):
    return psycopg.connect(**pg_settings(), connect_timeout=5, **kw)


def _plain(value):
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def check_select(sql: str) -> list[str]:
    """Parse with sqlglot; allow exactly one SELECT that reads at least one table.
    Returns the tables read (lower-case)."""
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"SQL does not parse: {str(exc)[:200]}") from None
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("send exactly one SQL statement")
    root = statements[0]
    if not isinstance(root, (exp.Select, exp.SetOperation)):
        raise ValueError(f"only SELECT is allowed, not {type(root).__name__}")
    for node in root.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command)):
            raise ValueError("writes are not allowed")
    ctes = {c.alias_or_name.lower() for c in root.find_all(exp.CTE)}
    tables = sorted({t.name.lower() for t in root.find_all(exp.Table) if t.name and t.name.lower() not in ctes})
    if not tables:
        raise ValueError("the query must read at least one table (no constant-only SELECTs)")
    return tables


def returns_literal(sql: str) -> bool:
    """True when the outermost SELECT's single output is a constant (a hard-coded answer)."""
    root = sqlglot.parse_one(sql, read="postgres")
    if not isinstance(root, exp.Select) or len(root.expressions) != 1:
        return False
    node = root.expressions[0]
    node = node.this if isinstance(node, exp.Alias) else node
    while isinstance(node, (exp.Cast, exp.Paren)):
        node = node.this
    return isinstance(node, (exp.Literal, exp.Null))


def run_readonly(app_id: str, sql: str, limit: int = 50, timeout_ms: int = 15000):
    check_select(sql)
    with connect() as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(psql.SQL("SET LOCAL search_path = {}").format(psql.Identifier(schema_for(app_id))))
            cur.execute(psql.SQL("SET LOCAL statement_timeout = {}").format(psql.Literal(timeout_ms)))
            cur.execute(sql)
            columns = [d.name for d in cur.description] if cur.description else []
            rows = [[_plain(v) for v in row] for row in cur.fetchmany(limit)]
        conn.rollback()
    return columns, rows


def scalar(app_id: str, sql: str):
    columns, rows = run_readonly(app_id, sql, limit=2)
    if len(rows) != 1 or len(columns) != 1:
        raise ValueError(f"metric SQL must return exactly one row and one column; got {len(rows)} row(s), "
                         f"{len(columns)} column(s)")
    return rows[0][0]


def describe_schema(app_id: str) -> list[dict]:
    schema = schema_for(app_id)
    with connect() as conn:
        cols = conn.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s ORDER BY table_name, ordinal_position", (schema,)).fetchall()
        out: dict[str, dict] = {}
        for table, column, dtype in cols:
            out.setdefault(table, {"table": table, "columns": []})["columns"].append({"name": column, "type": dtype})
        for table, info in out.items():
            ident = psql.Identifier(schema, table)
            info["rows"] = conn.execute(psql.SQL("SELECT COUNT(*) FROM {}").format(ident)).fetchone()[0]
            for col in info["columns"]:
                if col["type"] in ("text", "character varying", "boolean"):
                    q = psql.SQL("SELECT {c}, COUNT(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC LIMIT 8").format(
                        c=psql.Identifier(col["name"]), t=ident)
                    values = conn.execute(q).fetchall()
                    distinct = conn.execute(psql.SQL("SELECT COUNT(DISTINCT {c}) FROM {t}").format(
                        c=psql.Identifier(col["name"]), t=ident)).fetchone()[0]
                    col["distinct"] = distinct
                    if distinct <= 12:
                        col["values"] = {str(v): n for v, n in values}
                elif col["type"] in ("date", "integer", "numeric", "bigint", "double precision"):
                    lo, hi = conn.execute(psql.SQL("SELECT MIN({c}), MAX({c}) FROM {t}").format(
                        c=psql.Identifier(col["name"]), t=ident)).fetchone()
                    col["range"] = [_plain(lo), _plain(hi)]
    return list(out.values())
