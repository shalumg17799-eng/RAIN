"""
The real Slide-6 pattern: schema sliver -> query generation -> governed
execution -> synthesis. This module does the middle two steps for real --
takes a sliver (the real table/column facts the graph already returned)
and the user's question, asks Claude to write actual SQL, then executes
that SQL against the real dataset (PostgreSQL; see pg_compat.py), the same
synthetic dataset already validated throughout this project.

Requires ANTHROPIC_API_KEY. Same defensive pattern as llm_answer.py: if
the key is missing, the API call fails, or the generated SQL itself fails
to execute, this returns None and the caller falls back to the existing
ontology-only structural answer -- never breaks the request.
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in this folder, sets ANTHROPIC_API_KEY / PG_* / NEO4J_* automatically
import pg_compat as sqlite3
import re
import anthropic
from business_rules import rules_for_tables, format_rules_for_prompt
from persona_scope import scope_rows

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DB_PATH = os.path.join(os.path.dirname(__file__), "rain.db")

_client = None

def get_client():
    global _client
    if _client is None and ANTHROPIC_API_KEY:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def generate_sql(user_question: str, sliver_rows: list, persona: str = None) -> str | None:
    """
    sliver_rows: the exact {field, system, domain} rows the live graph
    query already returned -- 'system' here is a real table name, 'field'
    a real column name (see the corrected rain-worked-example.json).
    Returns a SQL string, or None if the LLM path is unavailable.
    """
    client = get_client()
    if client is None:
        print("[sql_generator] No ANTHROPIC_API_KEY -- cannot generate SQL, falling back.")
        return None

    # Withhold tables owned by another persona's domain unless the question
    # itself mentions that topic (see persona_scope.py). Nothing left means
    # nothing honest to query -- fall back to the ontology tier.
    sliver_rows = scope_rows(sliver_rows, persona, user_question)
    if not sliver_rows:
        return None

    tables_mentioned = sorted(set(r["system"] for r in sliver_rows))
    schema_lines = []
    for table in tables_mentioned:
        try:
            conn = sqlite3.connect(DB_PATH)
            # information_schema.columns, not PRAGMA table_info() -- PRAGMA is
            # SQLite-only and has no Postgres equivalent. information_schema is
            # ANSI-standard and already confirmed working against this exact
            # database (used throughout this migration to verify column types).
            cols = [row[0] for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position", (table,)
            )]
            conn.close()
            schema_lines.append(f"{table}({', '.join(cols)})")
        except Exception as e:
            print(f"[sql_generator] Could not read schema for {table}: {e}")

    business_rules_text = format_rules_for_prompt(rules_for_tables(tables_mentioned))

    prompt = f"""A user asked: "{user_question}"

The relevant tables and their real columns, from our PostgreSQL database, are:
{chr(10).join(schema_lines)}
{business_rules_text}

CRITICAL RULE, before anything else: if any business-rule definition is
listed above, it is MANDATORY. You must use that EXACT definition in your
SQL -- never substitute your own interpretation of an ambiguous term
("elevated-risk", "completion", etc.) when a definition for it is already
given above. This overrides your own judgment about what the term might
reasonably mean.

Write ONE PostgreSQL SELECT query that answers the question using only these
tables/columns. Rules:
- Business-rule definitions above are mandatory, not suggestions -- see above.
- Read-only SELECT only, never INSERT/UPDATE/DELETE/DROP
- No markdown, no explanation -- output ONLY the raw SQL statement
- If you cannot answer with only the given tables/columns, output exactly: NONE"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,  # was 300 -- too small for real multi-table joins, cut Q3's query off mid-statement
            extra_body={"temperature": 0},  # passed this way for SDK-version safety -- some installs reject temperature as a direct kwarg
            messages=[{"role": "user", "content": prompt}],
        )
        # Remove a surrounding ``` / ```sql fence only. The previous
        # str.strip("```sql") was a real bug (found via Shalini's team's
        # review) -- Python's str.strip() with a multi-char argument strips
        # ANY of those individual characters from the ends, not the literal
        # substring, so a lowercase "select" immediately after the fence
        # could get its leading "s" eaten too. This regex only matches an
        # actual fence marker.
        sql = re.sub(r"^```(?:sql)?\s*|\s*```$", "", response.content[0].text.strip(), flags=re.IGNORECASE).strip()
        if sql.upper() == "NONE" or not sql:
            return None
        return sql
    except Exception as e:
        print(f"[sql_generator] Anthropic API call failed: {type(e).__name__}: {e}")
        return None


# Safety net: only allow SELECT statements to actually execute, no matter
# what the model returns -- a generated-SQL feature must never be able to
# write/delete, even if a prompt somehow got a model to try.
_WRITE_KEYWORDS = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH)\b", re.IGNORECASE)

def execute_sql_safely(sql: str):
    """Returns (columns, rows) on success, or None on any failure/rejection."""
    if _WRITE_KEYWORDS.search(sql):
        print(f"[sql_generator] REJECTED -- generated SQL contained a write keyword: {sql}")
        return None
    # SELECT and WITH (a CTE -- "WITH ... AS (...) SELECT ...") are both
    # legitimate, safe, read-only query shapes. The write-keyword check
    # above already scans the entire string, CTE body included, so
    # allowing WITH here doesn't weaken the safety net -- it just stops
    # rejecting valid, safe queries the model correctly wrote as a CTE.
    if not sql.strip().upper().startswith(("SELECT", "WITH")):
        print(f"[sql_generator] REJECTED -- generated SQL did not start with SELECT or WITH: {sql}")
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()
        return columns, rows
    except Exception as e:
        print(f"[sql_generator] Generated SQL failed to execute: {type(e).__name__}: {e}\n  SQL: {sql}")
        return None
