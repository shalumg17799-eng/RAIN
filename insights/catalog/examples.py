"""Reviewed question-to-SQL examples: few-shot material for the query generator.

Only REVIEWED pairs are ever shown to the model (design report 5.7: verified examples become
few-shot examples only after approval). Each file entry names its reviewer and date, and at load
time its SQL must parse as one SELECT that touches only tables and columns the catalog has; the
tables it reads are derived from the SQL, never trusted from the file. The generator shows a caller
only the examples whose tables are all inside that caller's sliver.
"""

from datetime import date
from pathlib import Path

import sqlglot
from pydantic import Field, ValidationError
from sqlglot import exp
from sqlglot.errors import OptimizeError, SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from insights.catalog.snapshot import CatalogError, CatalogSnapshot
from insights.contracts.common import Contract
from insights.yamlio import load_yaml


class ReviewedExample(Contract):
    question: str = Field(min_length=3, max_length=300)
    sql: str = Field(min_length=6, max_length=4000)
    reviewed_by: str = Field(min_length=1, max_length=80)
    reviewed_on: date
    note: str = Field(default="", max_length=300)
    tables: tuple[str, ...] = ()
    """Derived from the SQL at load time."""


class ExamplesFile(Contract):
    version: int = 1
    examples: tuple[ReviewedExample, ...] = ()


def tables_read_by(sql: str, dialect: str) -> list[str]:
    """Lower-case names of the real tables a single SELECT reads. Raises ValueError otherwise."""
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except (SqlglotError, RecursionError) as exc:
        raise ValueError(f"SQL does not parse: {str(exc)[:120]}") from None
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("SQL must be exactly one statement")
    root = statements[0]
    if not isinstance(root, exp.Select | exp.SetOperation):
        raise ValueError(f"SQL must be a SELECT, not {type(root).__name__}")
    if any(isinstance(n, exp.Insert | exp.Update | exp.Delete | exp.Drop) for n in root.walk()):
        raise ValueError("SQL must not contain a write")
    names: set[str] = set()
    for scope in traverse_scope(root):
        for source in scope.sources.values():
            if isinstance(source, exp.Table) and not isinstance(source.this, exp.Func):
                names.add(source.name.lower())
    return sorted(names)


def columns_resolve(sql: str, schema: dict[str, dict[str, str]], dialect: str) -> str | None:
    """None when every column resolves against `schema`, else a short message."""
    try:
        qualify(
            sqlglot.parse_one(sql, read=dialect),
            schema=schema,
            dialect=dialect,
            validate_qualify_columns=True,
            quote_identifiers=False,
            identify=False,
        )
    except OptimizeError as exc:
        return str(exc)[:160]
    except (SqlglotError, RecursionError, ValueError, KeyError) as exc:
        return f"{type(exc).__name__}"
    return None


def load_examples(path: Path, snapshot: CatalogSnapshot) -> tuple[ReviewedExample, ...]:
    try:
        raw = load_yaml(path.read_text(encoding="utf-8")) or {}
        parsed = ExamplesFile.model_validate(raw)
    except OSError as exc:
        raise CatalogError(f"cannot read the examples {path}: {exc}") from exc
    except (ValidationError, ValueError, TypeError) as exc:
        raise CatalogError(f"invalid examples {path}: {exc}") from exc

    schema = {t.name: {c.name: c.type for c in t.columns} for t in snapshot.tables}
    dialect = snapshot.dialect.value
    problems: list[str] = []
    out: list[ReviewedExample] = []
    for index, example in enumerate(parsed.examples):
        label = f"example #{index} ({example.question[:40]!r})"
        try:
            tables = tables_read_by(example.sql, dialect)
        except ValueError as exc:
            problems.append(f"{label}: {exc}")
            continue
        unknown = [t for t in tables if snapshot.table(t) is None]
        if unknown:
            problems.append(f"{label}: unknown table(s) {', '.join(unknown)}")
            continue
        if not tables:
            problems.append(f"{label}: reads no table")
            continue
        column_problem = columns_resolve(example.sql, schema, dialect)
        if column_problem:
            problems.append(f"{label}: {column_problem}")
            continue
        out.append(example.model_copy(update={"tables": tuple(tables)}))
    if problems:
        raise CatalogError("; ".join(problems))
    return tuple(out)
