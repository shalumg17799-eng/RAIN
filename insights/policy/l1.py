"""L1: parse and policy. The application's early exit; the data platform is the authority.

What runs is what was checked. The SQL that leaves this module is *generated from the checked syntax
tree*, never the original text, so a comment trick or a parser difference cannot smuggle anything
past the check: comments are gone, there is exactly one statement, and the generated text is parsed
and checked a second time.

A query is allowed only if all of these hold:
  - one statement, a SELECT (CTEs and set operations included); no DML, DDL, SET, COPY, INTO, locks
  - no function or schema on the dialect's denylist; functions unknown to the parser are refused
    unless allowlisted; table-valued functions are refused unless allowlisted
  - every table and column is inside the sliver AND the caller's entitlements (`allowed`); a `*`
    expands to entitled columns only
  - at least one real table is read
  - a LIMIT is present and no larger than the row cap (plus one row, to detect truncation)
"""

import logging
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope

from insights.catalog.entitlements import AllowedObjects, default_schema_of
from insights.contracts.common import JsonScalar
from insights.contracts.enums import PolicyDecisionKind, PolicyLayer
from insights.contracts.profile import AppProfile
from insights.contracts.state import PolicyDecision
from insights.policy.denylist import Denylist

# sqlglot warns "contains unsupported syntax" for statements it can only treat as a raw Command
# (SET, SHOW, DO, ...). Those are refused here anyway, so the warning is noise.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

MAX_SQL_CHARS = 20_000
MAX_NODES = 5_000

_FORBIDDEN_NODE_NAMES = [
    "Insert",
    "Update",
    "Delete",
    "Merge",
    "Create",
    "Drop",
    "Alter",
    "AlterTable",
    "Command",
    "Set",
    "SetItem",
    "Copy",
    "Into",
    "Lock",
    "Use",
    "Pragma",
    "TruncateTable",
    "Grant",
    "Revoke",
    "Transaction",
    "Commit",
    "Rollback",
    "Show",
    "Describe",
    "Analyze",
    "Kill",
    "LoadData",
    "Declare",
    "Execute",
    "Attach",
    "Detach",
    "Comment",
    "Cache",
    "Uncache",
    "Refresh",
    "Directory",
]
_FORBIDDEN_NODES = {name for name in _FORBIDDEN_NODE_NAMES if hasattr(exp, name)}


@dataclass(frozen=True)
class PolicyOutcome:
    allowed: bool
    rules: tuple[str, ...]
    """Every rule that fired: denials, and notes such as limit_added."""
    reason: str
    """The first denial. Empty when allowed. Never contains SQL text."""
    sql: str | None
    """The SQL to run, generated from the checked tree. None when denied."""
    tables: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    limits: Mapping[str, JsonScalar] = field(default_factory=dict)

    def decision(self) -> PolicyDecision:
        return PolicyDecision(
            layer=PolicyLayer.L1,
            decision=PolicyDecisionKind.ALLOW if self.allowed else PolicyDecisionKind.DENY,
            rules_fired=self.rules,
            rewritten_sql=self.sql,
            limits_applied=dict(self.limits),
        )


def _identifier_key(identifier: exp.Expression | str, dialect: str) -> str:
    """Entitlement identity is case-insensitive: the catalog's normalized (lowercased) name is
    authoritative, so a quoted "Patient" and an unquoted patient are the same entitlement key.
    The checked SQL itself keeps its quoting, so execution still hits the physical table."""
    name = identifier.name if isinstance(identifier, exp.Identifier) else str(identifier)
    return name.lower()


def table_key(table: exp.Table, dialect: str, default_schema: str | None) -> str:
    """The name a table is known by in `AllowedObjects`: lower case, default schema dropped."""
    key = _identifier_key(table.this, dialect)
    schema = table.args.get("db")
    if schema is not None:
        db = _identifier_key(schema, dialect)
        if db.lower() != (default_schema or "").lower():
            key = f"{db}.{key}"
    return key


def _deny(rules: Iterable[str]) -> PolicyOutcome:
    ordered = tuple(dict.fromkeys(rules))
    return PolicyOutcome(False, ordered, ordered[0] if ordered else "denied", None)


def _text_problems(sql: str) -> list[str]:
    problems = []
    if not sql.strip():
        problems.append("empty_sql")
    if len(sql) > MAX_SQL_CHARS:
        problems.append("too_long")
    for ch in sql:
        if ch not in "\t\n\r" and unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn"):
            problems.append("control_characters")
            break
    return problems


def _root_ok(root: exp.Expression) -> bool:
    return isinstance(root, exp.Select | exp.SetOperation)


def _structural(root: exp.Expression, deny: Denylist) -> list[str]:
    """Checks that need no schema: statement type, forbidden nodes, functions, complexity."""
    rules: list[str] = []
    if not _root_ok(root):
        rules.append("statement_not_select")
    for count, node in enumerate(root.walk(), start=1):
        if count > MAX_NODES:
            rules.append("too_complex")
            break
        name = type(node).__name__
        if name in _FORBIDDEN_NODES:
            rules.append(f"forbidden_{name.lower()}")
        if name in deny.nodes:
            rules.append("function_denied")
        if isinstance(node, exp.Anonymous):
            fn = str(node.name).lower()
            if deny.function_denied(fn):
                rules.append("function_denied")
            elif not deny.anonymous_function_allowed(fn):
                rules.append("function_not_allowed")
        elif isinstance(node, exp.Func):
            candidates = {node.sql_name().lower(), name.lower()}
            if any(deny.function_denied(c) for c in candidates):
                rules.append("function_denied")
        if (
            isinstance(node, exp.Column)
            and not node.table
            and str(node.name).lower() in deny.bare_identifiers
        ):
            rules.append("function_denied")
    return rules


def _physical_tables(root: exp.Expression) -> tuple[list[exp.Table], list[exp.Table]]:
    """(real tables, table-valued functions) from every scope. CTE references are not tables."""
    real: list[exp.Table] = []
    udtf: list[exp.Table] = []
    seen: set[int] = set()
    for scope in traverse_scope(root):
        for source in scope.sources.values():
            if isinstance(source, exp.Table) and id(source) not in seen:
                seen.add(id(source))
                (udtf if isinstance(source.this, exp.Func) else real).append(source)
    return real, udtf


def _func_names(table: exp.Table) -> list[str]:
    fn = table.this
    names = [type(fn).__name__.lower()]
    if isinstance(fn, exp.Anonymous):
        names.append(str(fn.name).lower())
    else:
        names.append(fn.sql_name().lower())
    return names


def _inject_predicates(
    work: exp.Expression, predicates: Mapping[str, str], dialect: str, default_schema: str | None
) -> list[str]:
    """Identity mode C: wrap each filtered table in a subquery that applies its row filter."""
    notes: list[str] = []
    real, _ = _physical_tables(work)
    for table in real:
        predicate = predicates.get(table_key(table, dialect, default_schema))
        if predicate is None:
            continue
        alias = table.alias or table.name
        inner_table = table.copy()
        inner_table.set("alias", None)
        filtered = (
            exp.select("*").from_(inner_table).where(sqlglot.condition(predicate, dialect=dialect))
        )
        table.replace(filtered.subquery(alias=alias))
        notes.append("row_predicate_injected")
    return notes


def _select_aliases(column: exp.Column) -> set[str]:
    select = column.find_ancestor(exp.Select)
    return {s.lower() for s in select.named_selects} if select is not None else set()


def _enforce_limit(root: exp.Expression, max_rows: int) -> tuple[dict[str, JsonScalar], list[str]]:
    """Cap the result at max_rows + 1. The extra row only flags truncation and is then dropped."""
    ceiling = max_rows + 1
    notes: list[str] = []
    limit = root.args.get("limit")
    wanted = ceiling
    if limit is None:
        notes.append("limit_added")
    else:
        expr = getattr(limit, "expression", None) if isinstance(limit, exp.Limit) else None
        if isinstance(expr, exp.Literal) and expr.is_int and 0 <= int(expr.this) <= ceiling:
            wanted = int(expr.this)  # the caller's own, smaller limit stands
        elif isinstance(expr, exp.Literal) and expr.is_int:
            notes.append("limit_lowered")
        else:
            notes.append("limit_replaced")
    root.set("limit", exp.Limit(expression=exp.Literal.number(wanted)))
    root.set("offset", root.args.get("offset"))
    return {"limit": wanted, "max_rows": max_rows}, notes


def check_sql(
    sql: str,
    *,
    allowed: AllowedObjects,
    app: AppProfile,
    denylist: Denylist,
    max_rows: int,
    row_predicates: Mapping[str, str] | None = None,
) -> PolicyOutcome:
    dialect = app.dialect.value
    default_schema = default_schema_of(app)

    if allowed.role is None:
        return _deny(["no_role_in_app"])
    problems = _text_problems(sql)
    if problems:
        return _deny(problems)

    try:
        statements = sqlglot.parse(sql, read=dialect)
    except (SqlglotError, RecursionError):
        return _deny(["parse_error"])
    if len(statements) != 1:
        return _deny(["multiple_statements"])
    root = statements[0]
    if root is None:
        return _deny(["empty_sql"])

    try:
        structural = _structural(root, denylist)
        if structural:
            return _deny(structural)
        real, udtf = _physical_tables(root)
    except (SqlglotError, RecursionError):
        return _deny(["too_complex"])

    denials: list[str] = []
    for table in udtf:
        if not denylist.table_function_allowed(*_func_names(table)):
            denials.append("table_function_denied")
    for table in real:
        if table.catalog:
            denials.append("catalog_not_allowed")
        elif table.db and denylist.schema_denied(table.db):
            denials.append("system_schema")
        elif table.db and table.db.lower() != (default_schema or "").lower():
            denials.append("schema_not_allowed")
        elif table_key(table, dialect, default_schema) not in allowed.tables:
            denials.append("table_not_allowed")
    if not real:
        denials.append("no_table")
    if denials:
        return _deny(denials)

    work = root.copy()
    notes: list[str] = []
    try:
        if row_predicates:
            notes += _inject_predicates(work, row_predicates, dialect, default_schema)
        real_work, _ = _physical_tables(work)
        for table in real_work:
            table.set("db", None)
            table.set("catalog", None)
        schema = {name: dict(columns) for name, columns in allowed.tables.items()}
        qualified = qualify(
            work,
            schema=schema,
            dialect=dialect,
            validate_qualify_columns=True,
            quote_identifiers=False,
            identify=False,
        )
    except OptimizeError:
        return _deny(["column_not_allowed"])
    except (SqlglotError, RecursionError, ValueError, KeyError):
        return _deny(["qualify_failed"])

    column_rules, tables_used, columns_used = _check_columns(qualified, allowed, dialect)
    if column_rules:
        return _deny(column_rules)

    limits, limit_notes = _enforce_limit(qualified, max_rows)
    notes += limit_notes

    final_sql = qualified.sql(dialect=dialect, comments=False)
    try:
        reparsed = sqlglot.parse(final_sql, read=dialect)
    except (SqlglotError, RecursionError):
        return _deny(["unstable_sql"])
    if len(reparsed) != 1 or reparsed[0] is None or _structural(reparsed[0], denylist):
        return _deny(["unstable_sql"])

    return PolicyOutcome(
        allowed=True,
        rules=tuple(dict.fromkeys(["select_only", *notes])),
        reason="",
        sql=final_sql,
        tables=tuple(sorted(tables_used)),
        columns=tuple(sorted(columns_used)),
        limits=limits,
    )


def _check_columns(
    qualified: exp.Expression, allowed: AllowedObjects, dialect: str
) -> tuple[list[str], set[str], set[str]]:
    """Every column must resolve, in its own scope, to an entitled column of a real table.

    sqlglot's `Scope.columns` already folds correlated references into the scope that owns their
    source and leaves out ORDER BY references to output aliases. A column that no scope claims is
    refused rather than assumed to be fine.
    """
    rules: list[str] = []
    tables_used: set[str] = set()
    columns_used: set[str] = set()
    scopes: list[Scope] = list(traverse_scope(qualified))
    claimed: set[int] = set()

    for star in qualified.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            rules.append("star_not_expanded")

    for scope in scopes:
        external = {id(c) for c in scope.external_columns}
        for source in scope.sources.values():
            if isinstance(source, exp.Table) and not isinstance(source.this, exp.Func):
                tables_used.add(table_key(source, dialect, None))
        for column in [*scope.columns, *scope.external_columns]:
            claimed.add(id(column))
            if column.is_star:
                continue
            source = scope.sources.get(column.table)
            if isinstance(source, exp.Table) and not isinstance(source.this, exp.Func):
                table = table_key(source, dialect, None)
                name = _identifier_key(column.this, dialect)
                if name not in allowed.columns_of(table):
                    rules.append("column_not_allowed")
                else:
                    columns_used.add(f"{table}.{name}")
            elif isinstance(source, Scope | exp.Table):
                continue  # a CTE, subquery or allowed function's output: no table data of its own
            elif id(column) not in external:
                rules.append("unresolved_column")

    for column in qualified.find_all(exp.Column):
        if id(column) in claimed or column.is_star:
            continue
        if not column.table and column.name.lower() in _select_aliases(column):
            continue  # ORDER BY / GROUP BY on an output alias
        rules.append("unresolved_column")
    return rules, tables_used, columns_used
