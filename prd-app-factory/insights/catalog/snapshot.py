"""Versioned catalog snapshot: tables, columns, comments and keys, as one deterministic JSON file.

A snapshot is built by introspecting the data source with an admin connection (never at request
time), written to the app folder and committed, so retrieval needs no database. Its `version` is a
hash of its content: the same schema always gives the same file, a changed schema gives a new
version, and a file edited by hand fails to load.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from insights.contracts.common import Contract, Identifier
from insights.contracts.enums import Dialect

SNAPSHOT_FORMAT = 1


class CatalogError(ValueError):
    """The catalog (snapshot, glossary or join hints) is missing, invalid or inconsistent."""


class CatalogColumn(Contract):
    name: str
    type: str
    description: str = ""
    nullable: bool = True
    primary_key: bool = False


class ForeignKey(Contract):
    columns: tuple[str, ...]
    ref_table: str
    ref_columns: tuple[str, ...]


class CatalogTable(Contract):
    name: str
    description: str = ""
    columns: tuple[CatalogColumn, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    freshness: dict[str, str] = Field(default_factory=dict)
    """Latest value per date or timestamp column (ISO date), read at build time. Data freshness,
    not schema: it is left out of the content version and of the drift report."""

    def column(self, name: str) -> CatalogColumn | None:
        return next((c for c in self.columns if c.name == name), None)

    def latest(self) -> str | None:
        """The latest date the table holds, over its date columns; None when unknown."""
        return max(self.freshness.values(), default=None)


def _structure(table: CatalogTable) -> dict[str, Any]:
    return table.model_dump(mode="json", exclude={"freshness"})


def _content_hash(source_id: str, dialect: str, schema: str, tables: list[Any]) -> str:
    payload = {"source_id": source_id, "dialect": dialect, "schema": schema, "tables": tables}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


class CatalogSnapshot(Contract):
    format: Literal[1] = SNAPSHOT_FORMAT
    source_id: Identifier
    dialect: Dialect
    schema_name: str
    version: str
    tables: tuple[CatalogTable, ...]

    @model_validator(mode="after")
    def _version_matches_content(self) -> "CatalogSnapshot":
        expected = self.content_version()
        if self.version != expected:
            raise ValueError(f"version {self.version} does not match the content ({expected})")
        names = [t.name for t in self.tables]
        if len(set(names)) != len(names):
            raise ValueError("duplicate table names")
        return self

    def content_version(self) -> str:
        tables = [_structure(t) for t in self.tables]
        return _content_hash(self.source_id, self.dialect.value, self.schema_name, tables)

    def table(self, name: str) -> CatalogTable | None:
        return next((t for t in self.tables if t.name == name), None)


def make_snapshot(
    *, source_id: str, dialect: Dialect, schema_name: str, tables: list[CatalogTable]
) -> CatalogSnapshot:
    ordered = sorted(tables, key=lambda t: t.name)
    version = _content_hash(source_id, dialect.value, schema_name, [_structure(t) for t in ordered])
    return CatalogSnapshot(
        source_id=source_id,
        dialect=dialect,
        schema_name=schema_name,
        version=version,
        tables=tuple(ordered),
    )


def write_snapshot(snapshot: CatalogSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def load_snapshot(path: Path) -> CatalogSnapshot:
    try:
        return CatalogSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogError(f"cannot read the catalog snapshot {path}: {exc}") from exc
    except ValueError as exc:  # includes pydantic's ValidationError and a version mismatch
        raise CatalogError(f"invalid catalog snapshot {path}: {exc}") from exc


# ---- introspection (PostgreSQL) ----------------------------------------------------------------

_COLUMNS_SQL = """
SELECT c.relname, a.attnum, a.attname, format_type(a.atttypid, a.atttypmod),
       a.attnotnull, col_description(c.oid, a.attnum), obj_description(c.oid, 'pg_class')
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = %s AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
"""

_KEYS_SQL = """
SELECT con.contype, src.relname, con.conkey, dst.relname, con.confkey, con.conrelid, con.confrelid
FROM pg_constraint con
JOIN pg_class src ON src.oid = con.conrelid
JOIN pg_namespace n ON n.oid = src.relnamespace
LEFT JOIN pg_class dst ON dst.oid = con.confrelid
WHERE n.nspname = %s AND con.contype IN ('p', 'f')
ORDER BY src.relname, con.conname
"""


def introspect_postgres(conn: Any, schema: str) -> list[CatalogTable]:
    """Read tables, columns, comments, primary and foreign keys from a PostgreSQL schema."""
    with conn.cursor() as cur:
        cur.execute(_COLUMNS_SQL, (schema,))
        column_rows = cur.fetchall()
        cur.execute(
            "SELECT c.relname, a.attnum, a.attname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_attribute a ON a.attrelid = c.oid "
            "WHERE n.nspname = %s AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped",
            (schema,),
        )
        names: dict[tuple[str, int], str] = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        cur.execute(_KEYS_SQL, (schema,))
        key_rows = cur.fetchall()

    primary: dict[str, set[str]] = {}
    foreign: dict[str, list[ForeignKey]] = {}
    for contype, table, conkey, ref_table, confkey, _conrel, _confrel in key_rows:
        columns = tuple(names[(table, k)] for k in conkey)
        if contype == "p":
            primary.setdefault(table, set()).update(columns)
        else:
            ref_columns = tuple(names[(ref_table, k)] for k in confkey)
            foreign.setdefault(table, []).append(
                ForeignKey(columns=columns, ref_table=ref_table, ref_columns=ref_columns)
            )

    tables: dict[str, list[CatalogColumn]] = {}
    comments: dict[str, str] = {}
    for table, _num, column, type_name, not_null, comment, table_comment in column_rows:
        tables.setdefault(table, []).append(
            CatalogColumn(
                name=column,
                type=type_name,
                description=comment or "",
                nullable=not not_null,
                primary_key=column in primary.get(table, set()),
            )
        )
        comments[table] = table_comment or ""
    freshness = _freshness(conn, schema, tables)
    return [
        CatalogTable(
            name=name,
            description=comments[name],
            columns=tuple(columns),
            foreign_keys=tuple(
                sorted(foreign.get(name, []), key=lambda f: (f.ref_table, f.columns))
            ),
            freshness=freshness.get(name, {}),
        )
        for name, columns in tables.items()
    ]


def _freshness(
    conn: Any, schema: str, tables: dict[str, list[CatalogColumn]]
) -> dict[str, dict[str, str]]:
    """`table -> column -> latest value` for date and timestamp columns (one max() per column).

    Read with the operator's connection at build time; the answer composer uses it to say "no
    data for this period yet: the latest <table>.<column> is <date>" (P1, D74).
    """
    from psycopg import sql as pgsql

    out: dict[str, dict[str, str]] = {}
    with conn.cursor() as cur:
        for name, columns in tables.items():
            for column in columns:
                if not column.type.lower().startswith(("date", "timestamp")):
                    continue
                cur.execute(
                    pgsql.SQL("SELECT max({}) FROM {}.{}").format(
                        pgsql.Identifier(column.name),
                        pgsql.Identifier(schema),
                        pgsql.Identifier(name),
                    )
                )
                row = cur.fetchone()
                value = row[0] if row else None
                if value is not None:
                    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
                    out.setdefault(name, {})[column.name] = text[:10]
    return out


# ---- drift -------------------------------------------------------------------------------------


def diff_snapshots(old: CatalogSnapshot, new: CatalogSnapshot) -> list[str]:
    """Human-readable differences, for the nightly catalog-drift alert. Empty means identical."""
    changes: list[str] = []
    old_tables = {t.name: t for t in old.tables}
    new_tables = {t.name: t for t in new.tables}
    changes += [f"table added: {n}" for n in sorted(new_tables.keys() - old_tables.keys())]
    changes += [f"table removed: {n}" for n in sorted(old_tables.keys() - new_tables.keys())]
    for name in sorted(old_tables.keys() & new_tables.keys()):
        before = {c.name: c for c in old_tables[name].columns}
        after = {c.name: c for c in new_tables[name].columns}
        changes += [f"column added: {name}.{c}" for c in sorted(after.keys() - before.keys())]
        changes += [f"column removed: {name}.{c}" for c in sorted(before.keys() - after.keys())]
        for column in sorted(before.keys() & after.keys()):
            if before[column] != after[column]:
                changes.append(f"column changed: {name}.{column}")
        if old_tables[name].description != new_tables[name].description:
            changes.append(f"table description changed: {name}")
        if old_tables[name].foreign_keys != new_tables[name].foreign_keys:
            changes.append(f"foreign keys changed: {name}")
    return changes
