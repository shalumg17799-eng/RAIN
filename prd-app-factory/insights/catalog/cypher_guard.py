"""The mandatory guard for model-written Cypher (DIF-34). Nothing runs until it passes.

The LLM may write only a single read-only query over the known labels and relationship types. This
guard is the authority: it rejects writes, procedure calls, multiple statements, unknown labels or
relationships and over-cap LIMITs, and appends the cap when none is given. Read routing and the
configured-database binding are enforced separately at execution; a rejected query makes the sliver
step fall back to the deterministic path. The guard never runs the query and never touches a graph.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# writes, DDL and administrative clauses -- none may appear
_FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|FOREACH|CALL|LOAD|USE|SHOW|DROP|DETACH|GRANT|DENY|REVOKE"
    r"|ALTER|RENAME|TERMINATE|START|CONSTRAINT|INDEX|TRIGGER)\b",
    re.IGNORECASE,
)
_PROCEDURE = re.compile(r"\b(apoc|db|dbms|gds)\s*\.", re.IGNORECASE)
# a label or relationship type: an upper-case-initial name that follows a colon (node `:Label`,
# relationship `[:REL]`). Lower-case map keys and string values do not match.
_LABEL_OR_REL = re.compile(r":\s*([A-Z][A-Za-z0-9_]*)")
_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


class CypherRejected(ValueError):
    """The guard refused a query. The message names the kind of violation, never the query body."""


def guard_cypher(
    cypher: str, *, allowed_labels: Iterable[str], allowed_rels: Iterable[str], limit_cap: int
) -> str:
    """Return a safe, single, read-only Cypher query (with a LIMIT no larger than `limit_cap`), or
    raise `CypherRejected`. The returned text is what may run; the input is never trusted as-is."""
    text = (cypher or "").strip()
    if not text:
        raise CypherRejected("empty query")
    body = text[:-1].rstrip() if text.endswith(";") else text
    if ";" in body:
        raise CypherRejected("only a single statement is allowed")
    if _FORBIDDEN.search(body):
        raise CypherRejected("a write or administrative clause is not allowed")
    if _PROCEDURE.search(body):
        raise CypherRejected("procedure calls (apoc/db/dbms/gds) are not allowed")
    allowed = {x.upper() for x in allowed_labels} | {x.upper() for x in allowed_rels}
    for name in _LABEL_OR_REL.findall(body):
        if name.upper() not in allowed:
            raise CypherRejected(f"label or relationship not in the allowlist: {name}")
    limits = [int(n) for n in _LIMIT.findall(body)]
    if any(n > limit_cap for n in limits):
        raise CypherRejected(f"LIMIT exceeds the cap of {limit_cap}")
    return body if limits else f"{body}\nLIMIT {limit_cap}"
