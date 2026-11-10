"""Ultra API v1 for the PRD v0.3 frontend (frontend/rain-app).

Serves the endpoints the app's http mode calls — GET /context, GET /briefing,
POST /ask, POST /actions/{id}, GET /catalog. Every context, briefing and answer is
BUILT AT REQUEST TIME from the backend's data (chat_v3.build_persona over
ui_data_v3.load_sections: Postgres rain_v3.ui_v3.dataset with live public_data
figures), so editing a contract, dataset or record in the database changes the chat
on the next request. Persona queries asked in the chat run live against rain_v3.
rain-api/fixtures/ultra_v3/<persona>.json are the frontend's recordings, kept as the
golden copy that test_chat_v3_build.py compares the built chat against.

POST /ask is a faithful port of the app's chatFlowEngine resolution ladder
(src/core/engine/chatFlowEngine.ts + the RAIN flowKit's loose matcher):
  1. explicit chip map (original, lowercase and loose spellings)
  2. exact user_query match
  2b. loose-normalized chip map (the persona's matchUtterance)
  3. substring match (strictMatch: input >= 8 chars and contains a user_query)
  4. keyword-scored match over query+answer text (strict: score >= 2)
  5. the persona's __default__ turn

Point the frontend here with frontend/rain-app/.env.local:
  VITE_ULTRA_API_MODE=http
  VITE_ULTRA_API_BASE=http://127.0.0.1:8000/api/v3/ui
"""
import json
import logging
import re
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

import chat_v3
import persona_queries_v3 as pq
import ui_data_v3

router = APIRouter(tags=["ultra-v3"])
log = logging.getLogger("rain.api.ui")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ultra_v3"
CLIENT_ID = "rain"

_STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "for", "of", "on", "in", "at", "me", "my", "our", "i",
    "what", "show", "tell", "give", "about", "this", "that", "these", "those", "it", "can",
    "do", "does", "please", "some", "any", "how", "why", "where", "which", "who", "and", "or", "but",
}
_NEXT_SIGNAL_TOKEN = "__next_signal__"
_DEFAULT_FLOW_KEY = "__default__"
_STRICT_MIN_LENGTH = 8
_SIGNAL_WALKTHROUGH_INPUTS = ("Next signal", "Yes, walk me through them")

_catalog: list | None = None
CHAT_SOURCE = "postgres://rain_v3/ui_v3.dataset"


def _loose(text: str) -> str:
    """flowKit.ts `loose`: typed questions match in any case, sans punctuation."""
    return re.sub(r"\s+", " ", re.sub(r"[?.!,':]", "", text.lower())).strip()


def _load(persona_id: str) -> dict:
    """The persona's context, briefing, answers and matching tables, built now from the database."""
    sections, _overlay, _rows, _loaded = ui_data_v3.load_sections(CLIENT_ID)
    try:
        return chat_v3.build_persona(sections, persona_id)
    except KeyError:
        raise HTTPException(404, f'No persona "{persona_id}" for client "{CLIENT_ID}"')


def _require_client(client_id: str) -> None:
    if client_id != CLIENT_ID:
        raise HTTPException(404, f'No client "{client_id}"')


def _resolve_flow_key(match: dict, user_input: str) -> str | None:
    """chatFlowEngine.resolveFlowKey, rung for rung."""
    chip_map, flows = match["chipToFlowKey"], match["flows"]
    strict = match.get("strictMatch") is True

    # 1. explicit chip map (the map already holds lowercase and loose spellings)
    mapped = chip_map.get(user_input)
    if mapped and mapped != _NEXT_SIGNAL_TOKEN and mapped in flows:
        return mapped

    # 2. exact user_query
    for key, f in flows.items():
        if f.get("user_query") == user_input:
            return key

    # 2b. the persona's matchUtterance: loose lookup of the chip map
    mapped = chip_map.get(_loose(user_input))
    if mapped and mapped != _NEXT_SIGNAL_TOKEN and mapped in flows:
        return mapped

    # 3. substring match (strictMatch: only "typed a whole known question", floor 8)
    lower = user_input.lower()
    for key, f in flows.items():
        q = (f.get("user_query") or "").lower().strip()
        if not q:
            continue
        if strict:
            if len(lower) >= _STRICT_MIN_LENGTH and q in lower:
                return key
        elif q in lower or lower in q:
            return key

    # 4. keyword-scored match
    words = [w for w in re.split(r"\W+", lower) if len(w) > 2 and w not in _STOPWORDS]
    if words:
        best_key, best_score = None, 0
        for key, f in flows.items():
            if key.startswith("__"):
                continue
            corpus = f.get("corpus") or ""
            score = sum(1 for w in words if w in corpus)
            if score > best_score:
                best_key, best_score = key, score
        min_score = 2 if strict else (1 if len(words) <= 2 else 2)
        if best_key and best_score >= min_score:
            return best_key

    # 5. per-persona default
    return _DEFAULT_FLOW_KEY if _DEFAULT_FLOW_KEY in flows else None


def _source(persona_id: str) -> str:
    return f"{CHAT_SOURCE} (contracts.{persona_id.removeprefix('rain_')}, built live)"


def _proof(response: Response, persona_id: str, turn: str | None = None) -> None:
    """Proof headers the frontend logs: the data the answer was built from, and which turn."""
    response.headers["X-RAIN-Data-Source"] = _source(persona_id)
    if turn:
        response.headers["X-RAIN-Turn"] = turn


@router.get("/context")
def get_context(clientId: str, personaId: str, response: Response):
    _require_client(clientId)
    ctx = _load(personaId)["context"]
    _proof(response, personaId)
    return ctx


@router.get("/briefing")
def get_briefing(clientId: str, personaId: str, response: Response):
    _require_client(clientId)
    briefing = _load(personaId)["briefing"]
    _proof(response, personaId, (briefing.get("greeting") or {}).get("id"))
    log.info("briefing persona=%s turn=%s built from %s", personaId,
             (briefing.get("greeting") or {}).get("id"), _source(personaId))
    return briefing


def _scripted_exact(match: dict, user_input: str) -> str | None:
    """Rungs 1-2 only: an explicit chip or a recorded question, exactly as written."""
    mapped = match["chipToFlowKey"].get(user_input)
    if mapped and mapped != _NEXT_SIGNAL_TOKEN and mapped in match["flows"]:
        return mapped
    return next((k for k, f in match["flows"].items() if f.get("user_query") == user_input), None)


def _scripted_questions(match: dict) -> set[str]:
    """Every scripted question and chip of a persona, normalized like the query pack's questions."""
    texts = [f.get("user_query") or "" for f in match["flows"].values()] + list(match["chipToFlowKey"])
    return {pq._loose(t) for t in texts if t}


def _scripted_loose_chip(match: dict, user_input: str) -> str | None:
    """Rung 2b only: a chip typed in any case, without punctuation."""
    mapped = match["chipToFlowKey"].get(_loose(user_input))
    return mapped if mapped and mapped != _NEXT_SIGNAL_TOKEN and mapped in match["flows"] else None


_MAX_ROWS_SHOWN = 25


def _cell(v):
    """data_table cells are strings, numbers or null."""
    if v is None or isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def _query_turn(q: dict) -> tuple[dict, dict | None]:
    """A chat answer built from a live run of one persona query (rows from rain_v3)."""
    try:
        result = pq.execute(q)
    except Exception as exc:  # the chat must answer even if the database does not
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return {"id": f"query:{q['id']}", "text": f"Backend query {q['id']} could not run: {first}",
                "citations": [], "components": [], "chips": [], "confidence": 0}, None
    rows = [{k: _cell(v) for k, v in r.items()} for r in result["rows"]]
    shown = rows[:_MAX_ROWS_SHOWN]
    columns = []
    for col in result["columns"]:
        values = [r[col] for r in rows if r[col] is not None]
        numeric = bool(values) and all(isinstance(v, (int, float)) for v in values)
        columns.append({"key": col, "label": col.replace("_", " ").capitalize(),
                        **({"kind": "number", "align": "right"} if numeric else {})})
    tables = sorted({f"rain_v3.{s}.{t}" for s, t in re.findall(r"\b(synthetic|public_data)\.(\w+)", q["sql"])})
    n = result["rowCount"]
    text = (f"{q['question']} Live result of backend query {q['id']}: {n} row{'s' if n != 1 else ''} from "
            f"{result['schema']} in {result['ms']} ms.")
    if n > _MAX_ROWS_SHOWN:
        text += f" Showing the first {_MAX_ROWS_SHOWN}."
    if q["data"] == "synthetic":
        text += " Synthetic data: the keys are consistent, but codes, names and amounts are generator placeholders."
    siblings = [x for x in pq._pack().values() if x["persona"] == q["persona"] and x["id"] != q["id"]]
    chips = [x["question"] for x in siblings if x["data"] == q["data"]][:2] + \
            [x["question"] for x in siblings if x["data"] != q["data"]][:1]
    turn = {
        "id": f"query:{q['id']}",
        "text": text,
        "citations": [*tables, f"Backend query {q['id']} (GET /api/v3/queries/{q['id']})"],
        "components": [{"type": "data_table", "version": 1, "props": {
            "caption": f"{q['id']} · {result['schema']} · {n} rows", "columns": columns, "rows": shown}}],
        "chips": chips,
        "confidence": 99,
    }
    return turn, result


@router.post("/ask")
def ask(body: dict, response: Response):
    _require_client(str(body.get("clientId")))
    persona_id = str(body.get("personaId"))
    chat = _load(persona_id)
    user_input = str(body.get("input") or "")
    match = chat["match"]

    flow_key = None
    query = None
    if user_input in _SIGNAL_WALKTHROUGH_INPUTS:
        # resolveNextSignal: RAIN personas have an empty signalSequence, so
        # the walkthrough falls through to the default turn, as in the app.
        seq = match.get("signalSequence") or []
        flow_key = seq[0] if seq else None
    else:
        # Scripted chips and questions win; then a persona query asked for by id or by its
        # question; then the rest of the scripted ladder; and a persona query again, loosely,
        # before falling back to the generic answer.
        flow_key = _scripted_exact(match, user_input)
        if not flow_key:
            query = pq.find_query(persona_id, user_input, "exact")
        if not flow_key and not query:
            flow_key = _scripted_loose_chip(match, user_input)
        if not flow_key and not query:
            query = pq.find_query(persona_id, user_input, "close")
            # A query whose question is also a scripted question (CEO-S5 "Compare our sites on cost
            # per member") is left to the scripted answer here; its id or exact text still runs it.
            if query and pq._loose(query["question"]) in _scripted_questions(match):
                query = None
        if not flow_key and not query:
            flow_key = _resolve_flow_key(match, user_input)
            if flow_key == _DEFAULT_FLOW_KEY:
                query = pq.find_query(persona_id, user_input, "fuzzy")
    if query:
        turn, result = _query_turn(query)
        source = f"postgres://{result['schema'].replace('.', '/')} (query {query['id']})" if result else "query failed"
        response.headers["X-RAIN-Data-Source"] = source
        response.headers["X-RAIN-Turn"] = turn["id"]
        log.info("ask persona=%s turn=%s source=%s rows=%s", persona_id, turn["id"], source,
                 result["rowCount"] if result else 0)
        return turn
    if not flow_key:
        flow_key = _DEFAULT_FLOW_KEY if _DEFAULT_FLOW_KEY in chat["turns"] else None
    if not flow_key:
        raise HTTPException(422, f'No answer for "{user_input}"')
    _proof(response, str(body.get("personaId")), flow_key)
    log.info("ask persona=%s turn=%s built from %s", persona_id, flow_key, _source(persona_id))
    return chat["turns"][flow_key]


@router.post("/actions/{action_id}")
def run_action(action_id: str, body: dict):
    _require_client(str(body.get("clientId")))
    _load(str(body.get("personaId")))  # 404 for unknown personas first
    # RAIN's flowKit defines no actionConfirmMap: actions run in the UI store.
    raise HTTPException(404, f'No action "{action_id}"')


@router.get("/catalog")
def get_catalog():
    global _catalog
    if _catalog is None:
        path = FIXTURES_DIR / "catalog.json"
        if not path.is_file():
            raise HTTPException(503, "catalog fixture missing: run `npm run fixtures:backend` in frontend/rain-app")
        _catalog = json.loads(path.read_text(encoding="utf-8"))
    return _catalog


@router.get("/personas")
def list_personas():
    """Convenience (not part of the Ultra contract): which personas the database can serve."""
    sections, _overlay, _rows, _loaded = ui_data_v3.load_sections(CLIENT_ID)
    return sorted(sections["constants"]["PERSONAS"].values())
