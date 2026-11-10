"""RAIN v0.3 persona queries API: each persona's synthetic-data and public-data queries as backend endpoints.

The queries are the validated pack in doc/queries/rain_v3_persona_queries.sql (6 personas x 5 synthetic +
5 public; override the path with RAIN_QUERY_PACK). Every run is read-only, as the backend login
(rain_app), with a 15 s statement timeout, and is logged with its request id.

  GET /api/v3/queries                       every query: id, persona, data (synthetic|public), question, url
  GET /api/v3/queries?persona=rain_cmo      one persona's queries (optionally &data=synthetic|public)
  GET /api/v3/queries/{id}                  run one query: columns, rows, row count, timing, the SQL itself

Proof headers: X-RAIN-Query-Id, X-RAIN-Data-Source (the schema read), X-RAIN-Rows, Server-Timing.
"""
import logging
import os
import re
import time
from functools import lru_cache
from pathlib import Path

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

router = APIRouter(tags=["persona-queries-v3"])
log = logging.getLogger("rain.api.queries")

PACK = Path(os.getenv("RAIN_QUERY_PACK", Path(__file__).resolve().parents[1] / "doc/queries/rain_v3_persona_queries.sql"))
PERSONA_IDS = ("rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access")


@lru_cache(maxsize=1)
def _pack() -> dict[str, dict]:
    """Parse the query pack: blocks start with `-- @id X`, carry `-- @persona/@data/@question`."""
    text = PACK.read_text(encoding="utf-8")
    queries: dict[str, dict] = {}
    for block in re.split(r"(?m)^-- @id ", text)[1:]:
        qid, _, rest = block.partition("\n")
        meta = dict(re.findall(r"(?m)^-- @(\w+) (.*)$", rest))
        sql = "\n".join(line for line in rest.splitlines() if not line.startswith("-- @"))
        sql = sql.split("\n-- ####")[0].strip()
        queries[qid.strip()] = {"id": qid.strip(), "persona": meta.get("persona"), "data": meta.get("data"),
                                "question": meta.get("question"), "sql": sql}
    return queries


def _conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DB_V3", "rain_v3"), user=os.getenv("PG_USER", "rain_app"),
        password=os.getenv("PG_PASSWORD", "rain_dev_pw"))


def _summary(q: dict) -> dict:
    return {"id": q["id"], "persona": q["persona"], "data": q["data"], "question": q["question"],
            "url": f"/api/v3/queries/{q['id']}"}


@router.get("")
def list_queries(persona: str | None = None, data: str | None = None):
    if persona and persona not in PERSONA_IDS:
        raise HTTPException(404, f'No persona "{persona}"')
    if data and data not in ("synthetic", "public"):
        raise HTTPException(400, 'data must be "synthetic" or "public"')
    items = [_summary(q) for q in _pack().values()
             if (not persona or q["persona"] == persona) and (not data or q["data"] == data)]
    log.info("persona query list persona=%s data=%s -> %d queries", persona or "all", data or "all", len(items))
    return JSONResponse({"pack": PACK.name, "count": len(items), "queries": items},
                        headers={"X-RAIN-Data-Source": f"query pack doc/queries/{PACK.name}"})


def execute(q: dict, request_id: str = "-") -> dict:
    """Run one pack query read-only as rain_app. Raises psycopg2.Error (logged) on failure."""
    t0 = time.perf_counter()
    try:
        with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '15s'")
            cur.execute(q["sql"])
            rows = [dict(r) for r in cur.fetchall()]
            columns = [d.name for d in cur.description]
    except psycopg2.Error as exc:
        log.warning("persona query %s (%s, %s data) FAILED: %s req=%s", q["id"], q["persona"], q["data"],
                    str(exc).strip().splitlines()[0], request_id)
        raise
    ms = (time.perf_counter() - t0) * 1000
    schema = "synthetic" if q["data"] == "synthetic" else "public_data"
    log.info("persona query %s (%s, %s data) -> %d rows in %.0f ms req=%s", q["id"], q["persona"], q["data"],
             len(rows), ms, request_id)
    return {**_summary(q), "schema": f"rain_v3.{schema}", "sql": q["sql"], "columns": columns,
            "rowCount": len(rows), "ms": round(ms, 1), "rows": rows}


# ─── Finding a query from what someone typed in the chat ──────────────────────

_QUERY_ID = re.compile(r"\b(CEO|CMO|CIO|STATE|CHW|ACCESS)-[SP][1-5]\b", re.I)
_STOP = {"the", "a", "an", "is", "are", "to", "for", "of", "on", "in", "at", "me", "my", "our", "we", "i", "what",
         "show", "tell", "give", "about", "this", "that", "it", "can", "do", "does", "how", "which", "who", "and",
         "or", "by", "with", "each", "every", "have", "has", "per", "vs", "from", "their", "they", "still", "most"}


def _loose(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s%-]", " ", text.lower())).strip()


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^\w%]+", text.lower()) if len(w) > 2 and w not in _STOP}


def find_query(persona_id: str, text: str, level: str) -> dict | None:
    """The pack query a chat input asks for.

    level "exact": the query id (e.g. CEO-P1) or the question exactly as written (any persona, own first).
    level "close": the question modulo case and punctuation, or a 20+ character part of it (own persona first).
    level "fuzzy": most of the input's words appear in one of this persona's questions (used only when the
                   chat would otherwise give its generic answer).
    """
    pack = _pack()
    own = [q for q in pack.values() if q["persona"] == persona_id]
    others = [q for q in pack.values() if q["persona"] != persona_id]
    if level == "exact":
        m = _QUERY_ID.search(text)
        if m:
            return pack.get(m.group(0).upper())
        t = text.strip().lower()
        return next((q for q in own + others if q["question"].strip().lower() == t), None)
    lt = _loose(text)
    if level == "close":
        if len(lt) < 12:
            return None
        for q in own + others:
            lq = _loose(q["question"])
            if lt == lq or (len(lt) >= 20 and lt in lq) or (len(lq) >= 20 and lq in lt):
                return q
        return None
    words = _words(text)
    if len(words) < 3:
        return None
    best, score = None, 0.0
    for q in own:
        shared = len(words & _words(q["question"]))
        ratio = shared / len(words)
        if shared >= 3 and ratio > score:
            best, score = q, ratio
    return best if score >= 0.6 else None


@router.get("/{query_id}")
def run_query(query_id: str, request: Request):
    q = _pack().get(query_id)
    if not q:
        raise HTTPException(404, f'No query "{query_id}"')
    request_id = getattr(request.state, "request_id", "-")
    try:
        body = execute(q, request_id)
    except psycopg2.Error as exc:
        raise HTTPException(500, f"query {q['id']} failed: {str(exc).strip().splitlines()[0]}")
    ms, rows, schema = body["ms"], body["rows"], body["schema"].split(".", 1)[1]
    return JSONResponse(jsonable_encoder(body), headers={
        "X-RAIN-Query-Id": q["id"],
        "X-RAIN-Data-Source": f"postgres://rain_v3/{schema}",
        "X-RAIN-Rows": str(len(rows)),
        "Server-Timing": f"db;dur={ms:.1f}",
    })
