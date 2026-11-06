"""Ultra API v1 for the PRD v0.3 frontend (frontend/rain-app).

Serves the endpoints the app's http mode calls — GET /context, GET /briefing,
POST /ask, POST /actions/{id}, GET /catalog — from fixtures the app exports
about itself (frontend/rain-app: `npm run fixtures:backend` writes
rain-api/fixtures/ultra_v3/). A fixture carries the exact recorded payloads,
so a backend response and the app's recorded mode are byte-identical.

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
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ultra-v3"])

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

_fixtures: dict[str, dict] = {}
_catalog: list | None = None


def _loose(text: str) -> str:
    """flowKit.ts `loose`: typed questions match in any case, sans punctuation."""
    return re.sub(r"\s+", " ", re.sub(r"[?.!,':]", "", text.lower())).strip()


def _load(persona_id: str) -> dict:
    if persona_id not in _fixtures:
        path = FIXTURES_DIR / f"{persona_id}.json"
        if not path.is_file():
            raise HTTPException(404, f'No persona "{persona_id}" for client "{CLIENT_ID}"')
        _fixtures[persona_id] = json.loads(path.read_text(encoding="utf-8"))
    return _fixtures[persona_id]


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


@router.get("/context")
def get_context(clientId: str, personaId: str):
    _require_client(clientId)
    return _load(personaId)["context"]


@router.get("/briefing")
def get_briefing(clientId: str, personaId: str):
    _require_client(clientId)
    return _load(personaId)["briefing"]


@router.post("/ask")
def ask(body: dict):
    _require_client(str(body.get("clientId")))
    fixture = _load(str(body.get("personaId")))
    user_input = str(body.get("input") or "")
    match = fixture["match"]

    flow_key = None
    if user_input in _SIGNAL_WALKTHROUGH_INPUTS:
        # resolveNextSignal: RAIN personas have an empty signalSequence, so
        # the walkthrough falls through to the default turn, as in the app.
        seq = match.get("signalSequence") or []
        flow_key = seq[0] if seq else None
    else:
        flow_key = _resolve_flow_key(match, user_input)
    if not flow_key:
        flow_key = _DEFAULT_FLOW_KEY if _DEFAULT_FLOW_KEY in fixture["turns"] else None
    if not flow_key:
        raise HTTPException(422, f'No answer for "{user_input}"')
    return fixture["turns"][flow_key]


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
    """Convenience (not part of the Ultra contract): which personas are servable."""
    return sorted(p.stem for p in FIXTURES_DIR.glob("rain_*.json"))
