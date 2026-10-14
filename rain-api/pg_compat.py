"""
A thin compatibility layer so the many SQL strings already written and
verified against SQLite (rain.db) run unchanged against Postgres, instead
of hand-editing every query across 15+ modules -- a much smaller, far more
verifiable surface than touching every "sql": "..." string by hand.

Differences between the two databases that this shim absorbs
(each one found by a real failure, not by guessing):

  1. Postgres is case-sensitive for the mixed-case table names this
     dataset uses (PregnancyEpisode, ChronicConditionEnrollment, ...) and
     requires them double-quoted; SQLite does not. preprocess() quotes
     every bare occurrence of the 17 real table names, longest name first
     so "ProviderReferenceIssue" is never partially matched as "Provider",
     and never re-quotes a name that's already quoted.
  2. SQLite's julianday('2026-05-15') - julianday(col) date-arithmetic
     idiom has a direct Postgres equivalent: subtracting two dates gives
     a plain integer number of days. preprocess() rewrites the pattern
     with a regex rather than requiring every caller to know Postgres
     syntax.
  3. An unaliased SUM() is named "sum". SELECT SUM(a), SUM(b) therefore
     returns two columns with the same name. psycopg2's DictRow is
     dict-keyed, so the second value is dropped before any Python code
     sees the row, and row[1] raises IndexError. Found in
     priya_equity_brief.py and priya_intervention_comparison.py. Rows are
     built from cursor.description in positional order, never via DictRow.

Usage mirrors sqlite3 closely enough that most call sites only need to
change their import and their connect() call:

    import pg_compat as sqlite3          # instead of: import sqlite3
    conn = pg_compat.connect()           # instead of: sqlite3.connect(DB_PATH)
    row = conn.execute(sql).fetchone()   # unchanged
    conn.row_factory = pg_compat.Row     # unchanged (sqlite3.Row equivalent)

The action-package audit log (decisions, routed_actions) also uses this
connection. Those tables are created in Postgres by action_engine.log_conn.
Inserts that need the new row id use RETURNING id, not lastrowid.
"""

import datetime
import decimal
import os
import re

import psycopg2

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DB", "rain"),
    "user": os.environ.get("PG_USER", "rain_app"),
    "password": os.environ.get("PG_PASSWORD", "rain_dev_pw"),
}

# The 17 real tables, longest name first so a longer name (ProviderReferenceIssue)
# is matched -- and thus excluded from matching as the shorter name (Provider) --
# before the shorter one is ever tried.
_TABLES = sorted([
    "ChronicConditionEnrollment", "ClaimEncounter", "ConnectivityRegistry", "DataQualityEvent",
    "DataSourceFeed", "EMSCoverage", "Facility", "MedicationFill", "MetricTrend", "Patient",
    "PregnancyEpisode", "Provider", "ProviderReferenceIssue", "RPMReading", "SDOHFlag",
    "TelehealthSession", "TransportRequest",
], key=len, reverse=True)

# Matches a bare table name only when NOT already preceded by a double quote
# (so re-running preprocess() on already-quoted SQL is a safe no-op) and only
# at a word boundary (so "Provider" never matches inside "ProviderReferenceIssue"
# -- though the longest-first ordering above already prevents that case, this
# is the second, independent safeguard).
_TABLE_PATTERNS = [(re.compile(r'(?<!")\b' + re.escape(t) + r'\b'), f'"{t}"') for t in _TABLES]

# julianday(X) - julianday(Y)  ->  ((X)::date - (Y)::date)
# Generic over X/Y being a literal date string, a parameter placeholder (?),
# or a column/expression (e.g. substr(last_ts, 1, 10)) -- Postgres: subtracting
# two dates is a plain integer day count. Every date column in this schema is
# already a native DATE type (confirmed against the Postgres schema directly),
# so no column needs its own cast beyond this.
_JULIANDAY_DIFF = re.compile(
    r"julianday\(\s*(.+?)\s*\)\s*-\s*julianday\(\s*(.+?)\s*\)"
)


# SUM(expr = 'literal')  ->  SUM(CASE WHEN expr = 'literal' THEN 1 ELSE 0 END)
# SQLite stores booleans as 0/1 integers, so SUM() over a boolean comparison
# just works; Postgres's SUM() flatly rejects a boolean argument, regardless
# of whether the comparison came from a native boolean column or a text one.
_SUM_BOOL = re.compile(r"SUM\(\s*([\w.]+)\s*=\s*('[^']*'|true|false)\s*\)", re.IGNORECASE)


def preprocess(sql: str) -> str:
    """Translate one SQLite-flavored SQL string to run against Postgres.
    Idempotent -- safe to call more than once on the same string."""
    sql = _JULIANDAY_DIFF.sub(lambda m: f"(({m.group(1)})::date - ({m.group(2)})::date)", sql)
    sql = _SUM_BOOL.sub(lambda m: f"SUM(CASE WHEN {m.group(1)} = {m.group(2)} THEN 1 ELSE 0 END)", sql)
    for pattern, replacement in _TABLE_PATTERNS:
        sql = pattern.sub(replacement, sql)
    # SQLite's '?' positional placeholder -> psycopg2's '%s'. Safe as a blanket
    # replace: no SQL string in this codebase has a literal '?' inside a quoted
    # value (confirmed by scanning every production file before relying on this).
    sql = sql.replace("?", "%s")
    return sql


def _clean(value):
    """Two Postgres-vs-SQLite return-type differences this dataset actually
    hits, both left unconverted being a real crash, not a cosmetic issue:

    1. ROUND()/SUM()/AVG() on a numeric column returns a Decimal in
       Postgres (SQLite returns a plain float) -- not JSON-serializable,
       and renders with a trailing '.0' the rest of the app's whole-number
       percentages don't have. Found via david_remediation_plan.py's audit
       log. Converts to int when the value is a whole number, float
       otherwise.
    2. A DATE/TIMESTAMP column comes back as a native datetime.date /
       datetime.datetime object in Postgres (SQLite returns a plain
       string) -- also not JSON-serializable. Found via
       priya_equity_brief.py embedding MetricTrend's before_date/after_date
       directly into a response. Converts to its ISO string
       ('2026-05-15'), matching the plain-string form every date already
       took on SQLite and the str(...) normalization already applied by
       hand in the files migrated before this fix existed.

    Every other type passes through unchanged.
    """
    if isinstance(value, decimal.Decimal):
        f = float(value)
        return int(f) if f.is_integer() else f
    if isinstance(value, datetime.date):  # also matches datetime.datetime (a subclass of date)
        return value.isoformat()
    return value


class Row:
    """sqlite3.Row-equivalent: supports both row["col"] and row[0], and
    dict(row). Built fresh from each fetched row (with every Decimal
    cleaned) rather than reusing psycopg2's own DictRow, which isn't safely
    mutable in place."""

    def __init__(self, pairs):
        self._keys = [k for k, _ in pairs]
        self._values = [_clean(v) for _, v in pairs]

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else self._values[self._keys.index(key)]

    def keys(self):
        return list(self._keys)

    def values(self):
        return list(self._values)

    def items(self):
        return list(zip(self._keys, self._values))

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(self.items())!r})"


class _Cursor:
    """Wraps a psycopg2 cursor so conn.execute(sql).fetchone()/.fetchall()
    works the way sqlite3's implicit-cursor style does."""

    def __init__(self, raw_cursor, as_row=False):
        self._cur = raw_cursor
        # True when the caller set conn.row_factory (sqlite3.Row style).
        # Rows are built from cursor.description plus the tuple, NOT from
        # psycopg2's DictCursor: two unaliased aggregates are both named
        # "sum", and a dict collapses them into one column. That made
        # row[1] raise IndexError in priya_equity_brief.py and
        # priya_intervention_comparison.py (two SUM() expressions, then
        # ed[0] / ed[1]).
        self._as_row = as_row

    def execute(self, sql, params=None):
        self._cur.execute(preprocess(sql), params)
        return self

    @property
    def description(self):
        """DB-API cursor.description passthrough -- psycopg2's own
        description attribute is already in the same shape sqlite3's is
        (a sequence of 7-tuples, [0] the column name), so no translation
        is needed, just exposing it. Without this, any caller that reads
        cur.description after conn.execute(sql) (e.g. sql_generator.py,
        to get generated-SQL column names) hits AttributeError, since
        _Cursor didn't forward it."""
        return self._cur.description

    @property
    def rowcount(self):
        """Same passthrough reasoning as description -- action_engine.py
        and action_package.py read cur.rowcount after an INSERT to check
        whether their own row actually landed (vs. another request already
        having inserted it first)."""
        return self._cur.rowcount

    @property
    def lastrowid(self):
        """SQLite's AUTOINCREMENT id. Postgres inserts that need the new
        id use RETURNING id and fetchone() instead. Raising here is safer
        than silently returning None."""
        raise AttributeError(
            "lastrowid has no Postgres equivalent via pg_compat. "
            "Use INSERT ... RETURNING id and fetchone() instead."
        )

    def _wrap(self, row):
        if row is None:
            return None
        if self._as_row:
            names = [d[0] for d in self._cur.description]
            return Row(list(zip(names, row)))
        return tuple(_clean(v) for v in row)

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]

    def __iter__(self):
        return (self._wrap(r) for r in self._cur)


class Connection:
    """Wraps a psycopg2 connection so the handful of sqlite3.Connection
    methods this codebase actually uses (execute, cursor, close, commit,
    row_factory) behave the same way against Postgres."""

    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._row_factory = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        # sqlite3.Row -> dict-and-index-accessible rows; anything else (e.g. None) -> plain tuples.
        # The cursor stays a plain tuple cursor either way. Switching to
        # DictCursor here dropped duplicate column names (see _Cursor).
        self._row_factory = value

    def cursor(self):
        return _Cursor(self._conn.cursor(), as_row=self._row_factory is not None)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def connect(*_args, **_kwargs):
    """Drop-in replacement for sqlite3.connect(DB_PATH) -- the DB_PATH
    argument (if any) is accepted and ignored, since Postgres connection
    details come from PG_CONFIG / the environment, not a file path."""
    return Connection(psycopg2.connect(**PG_CONFIG))
