"""metadata-answerer: answers a question ABOUT the schema or glossary from the KAG/catalog.

No model, no SQL, no execution (DIF-33). It retrieves the caller's ENTITLED schema sliver exactly
as schema-sliver does (KAG preferred, bypass fallback), turns those facts -- glossary definitions,
tables, columns and 1-hop joins -- into a small result set held by reference, and returns a short
deterministic summary. Read-only; entitlements are the authority, the graph's persona links hints.
"""

from typing import Any

from insights.catalog.kag import StubKag, retrieve_with_fallback
from insights.contracts.enums import ColumnRole, PathName
from insights.contracts.request import AskContext
from insights.contracts.response import Column
from insights.contracts.state import Sliver

MAX_COLUMNS_PER_TABLE = 40
MAX_ROWS = 500


def _rows(sliver: Sliver) -> list[list[str]]:
    rows: list[list[str]] = []
    for term in sliver.glossary_terms:
        rows.append(["definition", term.term, term.definition])
    for table in sliver.tables:
        rows.append(["table", table.name, table.description or f"{len(table.columns)} columns"])
        for col in table.columns[:MAX_COLUMNS_PER_TABLE]:
            detail = col.type + (f" -- {col.description}" if col.description else "")
            rows.append(["column", f"{table.name}.{col.name}", detail])
    for join in sliver.joins:
        rows.append(["join", f"{join.left} = {join.right}", join.kind])
    return rows[:MAX_ROWS]


def _narrative(sliver: Sliver) -> str:
    def plural(n: int, word: str) -> str:
        return f"{n} {word}" + ("" if n == 1 else "s")

    parts = []
    if sliver.glossary_terms:
        parts.append(plural(len(sliver.glossary_terms), "definition"))
    parts.append(plural(len(sliver.tables), "table"))
    if sliver.joins:
        parts.append(plural(len(sliver.joins), "join"))
    tables = ", ".join(t.name for t in sliver.tables)
    return f"Schema information you can access: {', '.join(parts)}. Tables: {tables}."


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    app, principal, services = ctx["app"], ctx["principal"], ctx["services"]
    query = input["query"]
    if not isinstance(query, str):
        raise ValueError("query must be text")
    context = AskContext.model_validate(input.get("context") or {})

    retriever = services.need("catalogs").for_app(app).retriever
    kag = services.kag.for_app(app) if services.kag is not None else StubKag()
    choice = retrieve_with_fallback(
        PathName.KAG,
        kag,
        lambda: retriever.retrieve(query, principal, context),
        query,
        principal,
        context,
        min_coverage=app.router.kag_min_coverage,
    )
    for note in choice.result.notes:
        ctx["emit"](note.replace(":", "_"))  # a progress note is an identifier; output keeps ":"
    sliver = choice.result.to_sliver()
    ctx["emit"](f"metadata_{sliver.path_used.value}")  # metadata_kag or metadata_bypass

    if not sliver.tables:
        return {"label": "empty", "path_used": sliver.path_used.value, "tables": []}

    columns = [
        Column(name="aspect", type="text", role=ColumnRole.DIMENSION),
        Column(name="name", type="text", role=ColumnRole.DIMENSION),
        Column(name="detail", type="text", role=ColumnRole.DIMENSION),
    ]
    rows = _rows(sliver)
    ref = ctx["results"].put(
        run_id=ctx["run_id"], owner=principal.subject, columns=columns, rows=rows
    )
    ctx["emit"]("rows_held", len(rows))
    return {
        "label": "answered",
        "result_ref": ref.model_dump(mode="json"),
        "columns": [c.model_dump(mode="json") for c in columns],
        "row_count": len(rows),
        "tables": [t.name for t in sliver.tables],
        "narrative": _narrative(sliver),
        "path_used": sliver.path_used.value,
    }
