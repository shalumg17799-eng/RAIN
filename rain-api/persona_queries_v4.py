"""RAIN v0.4 persona queries API: each persona's synthetic-data and public-data queries as backend endpoints.

The queries are the validated pack in doc/queries/rain_v4_persona_queries.sql (7 personas x 5 synthetic +
5 public; override the path with RAIN_QUERY_PACK). The patient keeps her pack id (patient_linda_garcia); her app
id (rain_linda) is accepted as an alias. Every run is read-only, as the backend login
(rain_app), with a 15 s statement timeout, and is logged with its request id.

  GET /api/v4/queries                       every query: id, persona, data (synthetic|public), question, url
  GET /api/v4/queries?persona=rain_cmo      one persona's queries (optionally &data=synthetic|public)
  GET /api/v4/queries/{id}                  run one query: columns, rows, row count, timing, the SQL itself

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

router = APIRouter(tags=["persona-queries-v4"])
log = logging.getLogger("rain.api.queries")

PACK = Path(os.getenv("RAIN_QUERY_PACK", Path(__file__).resolve().parents[1] / "doc/queries/rain_v4_persona_queries.sql"))
PERSONA_IDS = ("rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access", "patient_linda_garcia")
# The patient is an app persona (rain_linda); the pack keeps her own id. Either id names the same queries.
PERSONA_ALIASES = {"rain_linda": "patient_linda_garcia"}
# A patient sees only their own record: in the chat, a patient persona can run only its own queries.
SELF_ONLY = {"patient_linda_garcia"}


def pack_persona(persona_id: str | None) -> str | None:
    """The pack's id for a persona (an app id such as rain_linda, or the pack id itself)."""
    return PERSONA_ALIASES.get(persona_id, persona_id) if persona_id else persona_id


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


def cell(v):
    """JSON-safe table cell: strings, numbers or null (Decimal and dates become plain values)."""
    from decimal import Decimal
    if v is None or isinstance(v, bool) or isinstance(v, (int, float)):
        return ("Yes" if v else "No") if isinstance(v, bool) else v
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def _conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DB_V4", "rain_v4"), user=os.getenv("PG_USER", "rain_app"),
        password=os.getenv("PG_PASSWORD", "rain_dev_pw"))


def _summary(q: dict) -> dict:
    return {"id": q["id"], "persona": q["persona"], "data": q["data"], "question": q["question"],
            "url": f"/api/v4/queries/{q['id']}"}


@router.get("")
def list_queries(persona: str | None = None, data: str | None = None):
    persona = pack_persona(persona)
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
    return {**_summary(q), "schema": f"rain_v4.{schema}", "sql": q["sql"], "columns": columns,
            "rowCount": len(rows), "ms": round(ms, 1), "rows": rows}


# ─── Finding a query from what someone typed in the chat ──────────────────────

_QUERY_ID = re.compile(r"\b(CEO|CMO|CIO|STATE|CHW|ACCESS|GAR)-[SP][1-5]\b", re.I)
_STOP = {"the", "a", "an", "is", "are", "to", "for", "of", "on", "in", "at", "me", "my", "our", "we", "i", "what",
         "show", "tell", "give", "about", "this", "that", "it", "can", "do", "does", "how", "which", "who", "and",
         "or", "by", "with", "each", "every", "have", "has", "per", "vs", "from", "their", "they", "still", "most",
         "did", "get", "got", "see", "list", "all", "any", "please", "was", "were", "been", "am"}


def _loose(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s%-]", " ", text.lower())).strip()


def _key(text: str) -> str:
    """Letters and digits only: "Winnemucca's per-member cost?" and "winnemuccas permember cost" compare equal."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# words a person types for the same thing as the pack question (a light stem and a few synonyms)
_SYNONYM = {"appointment": "visit", "appt": "visit", "visit": "visit", "booking": "visit", "bp": "blood", "reading": "reading",
            "text": "reminder", "sms": "reminder", "message": "reminder", "insurance": "coverage", "plan": "coverage",
            "drive": "drive", "driving": "drive", "far": "drive", "doctor": "physician", "doctors": "physician"}


def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return _SYNONYM.get(w, w)


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.split(r"[^\w%]+", text.lower()) if len(w) > 1 and w not in _STOP and (len(w) > 2 or w == "bp")}


def find_query(persona_id: str, text: str, level: str) -> dict | None:
    """The pack query a chat input asks for.

    level "exact": the query id (e.g. CEO-P1) or the question exactly as written (any persona, own first).
    level "close": the question modulo case, punctuation and spacing, or a 20+ character part of it (own persona
                   first); or every word typed (2 or more, lightly stemmed: "my blood pressure readings") appears in
                   one of this persona's own questions.
    level "fuzzy": most of the input's words appear in one of this persona's questions (used only when the
                   chat would otherwise give its generic answer). A patient asks short first-person questions
                   ("show my visits"), so for a patient one or two shared words are enough among its own ten.

    A patient persona (SELF_ONLY) finds only its own queries: never another persona's, by id or by question.
    """
    pack = _pack()
    persona_id = pack_persona(persona_id)
    own = [q for q in pack.values() if q["persona"] == persona_id]
    others = [] if persona_id in SELF_ONLY else [q for q in pack.values() if q["persona"] != persona_id]
    if level == "exact":
        m = _QUERY_ID.search(text)
        if m:
            q = pack.get(m.group(0).upper())
            return q if q and (q in own or q in others) else None
        t = text.strip().lower()
        return next((q for q in own + others if q["question"].strip().lower() == t), None)
    kt = _key(text)
    words = _words(text)
    patient = persona_id in SELF_ONLY
    if level == "close":
        if len(kt) >= 10:
            for q in own + others:
                kq = _key(q["question"])
                if kt == kq or (len(kt) >= 16 and kt in kq) or (len(kq) >= 16 and kq in kt):
                    return q
        # every typed word is in one own question (the smallest such question: the most specific match)
        if len(words) >= 2:
            hits = [q for q in own if words <= _words(q["question"])]
            if hits:
                return min(hits, key=lambda q: len(_words(q["question"])))
        return None
    if len(words) < (1 if patient else 3):
        return None
    best, score = None, 0.0
    for q in own:
        shared = len(words & _words(q["question"]))
        ratio = shared / len(words)
        if shared >= (1 if patient else 3) and ratio > score:
            best, score = q, ratio
    return best if score >= 0.6 else None


def owner_of(text: str) -> dict | None:
    """The pack query this text names (id, or its question exactly or loosely), whoever it belongs to."""
    pack = _pack()
    m = _QUERY_ID.search(text)
    if m:
        return pack.get(m.group(0).upper())
    kt = _key(text)
    if len(kt) < 10:
        return None
    return next((q for q in pack.values() if _key(q["question"]) == kt), None)


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
        "X-RAIN-Data-Source": f"postgres://rain_v4/{schema}",
        "X-RAIN-Rows": str(len(rows)),
        "Server-Timing": f"db;dur={ms:.1f}",
    })
