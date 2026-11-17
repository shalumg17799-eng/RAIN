"""RAIN v0.4 API for the new Ultra UI (frontend/ultra-rain-v2): everything under /api/v4/ui2.

The new UI ("Ultra for RAIN", cut from Ultra main 9009990) shows the same seven personas as the v0.4 UI
(frontend/rain-app), with three differences in what it reads:

  * six visuals that were bespoke cards are now catalog `stack` cards drawn from named datasets
    (pmpm_trend, quality_gate, winnemucca_trend, pc_trend, banner_pending_fix, banner_freshness);
  * the patient Linda Garcia is `rain_patient`, a bilingual phone view with its own contract
    (`contracts.patient`), not the operator-style `rain_linda`;
  * Linda's own Use Case C adds four synthetic sources and a few facts about her (goal, readings, refill,
    mobile clinic), and the State view adds a primary care trend (PC_TREND).

This module is ADDITIVE. It reads the v0.4 data exactly as /api/v4/ui does (ui_data_v4.load_sections:
numbers computed per request from rain_v4.synthetic and rain_v4.public_data, contracts rendered from the
templates in ui_v4.dataset) and layers the new UI's extras on a copy. The extras are configuration and
templates kept in the same table under their own client id, `rain_ui2` (loader:
deploy/scripts/load_ui2_data_v4.py, seed rain-api/seed/rain_v4_ui2_overlay.json), which /api/v4/ui never
reads. No existing table, row, endpoint or response changes.

Endpoints (the Ultra API contract the new UI's http mode calls, plus its data boot):
  GET  /data?clientId=rain                      every value the UI shows (same proof headers as /api/v4/ui/data)
  GET  /context?clientId=rain&personaId=...     persona context
  GET  /briefing?clientId=rain&personaId=...    greeting turn, signals, KPIs, chips
  POST /ask                                     one answer (scripted ladder, then the persona query pack; the
                                                patient rain_patient runs her own GAR-* queries only)
  GET  /queries?personaId=...                   a persona's pack queries (the patient's ten: 5 synthetic, 5 public)
  POST /actions/{id}                            RAIN runs actions in the UI store: always 404 for a known persona
  GET  /catalog                                 the new UI's component catalog (frontend/ultra-rain-v2/docs/catalog)
  GET  /personas                                persona ids this API serves
Write-back stays on the existing /api/v4/flow endpoints (flow_v4.py), unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

import chat_v4
import persona_queries_v4 as pq
import ui_data_v4
import ultra_v4_api as v4
from templating_v4 import render_obj

router = APIRouter(tags=["ultra-v4-ui2"])
log = logging.getLogger("rain.api.ui2")

CLIENT_ID = "rain"
OVERLAY_CLIENT_ID = "rain_ui2"
PATIENT_KEY = "patient"
DATA_SOURCE = ("postgres://rain_v4/synthetic + public_data (computed per request) + ui_v4.dataset "
               "(templates, config; new UI extras under client_id rain_ui2)")
CHAT_SOURCE = "postgres://rain_v4/ui_v4.dataset"

_REPO = Path(__file__).resolve().parent.parent
CATALOG_PATHS = (_REPO / "frontend" / "ultra-rain-v2" / "docs" / "catalog" / "catalog.json",
                 Path(__file__).resolve().parent / "fixtures" / "ultra_rain_v2" / "catalog.json")

ES_DAYS = {"Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles", "Thursday": "jueves",
           "Friday": "viernes", "Saturday": "sábado", "Sunday": "domingo"}
ES_MONTHS = {"January": "enero", "February": "febrero", "March": "marzo", "April": "abril", "May": "mayo",
             "June": "junio", "July": "julio", "August": "agosto", "September": "septiembre",
             "October": "octubre", "November": "noviembre", "December": "diciembre"}
ES_MONTH_ABBR = {"Jan": "ene.", "Feb": "feb.", "Mar": "mar.", "Apr": "abr.", "May": "may.", "Jun": "jun.",
                 "Jul": "jul.", "Aug": "ago.", "Sep": "sept.", "Oct": "oct.", "Nov": "nov.", "Dec": "dic."}

js = chat_v4.js
spec = chat_v4.spec


# ─── The overlay (configuration and templates under client_id rain_ui2) ───────────────────────────────

def _overlay_rows() -> tuple[dict, int]:
    """{section: {key: payload}} for the new UI's extras, and how many rows they are."""
    out: dict = {}
    with ui_data_v4._conn() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT section, key, payload FROM ui_v4.dataset WHERE client_id = %s", (OVERLAY_CLIENT_ID,))
        rows = cur.fetchall()
    for section, key, payload in rows:
        out.setdefault(section, {})[key] = payload
    if not rows:
        raise HTTPException(500, "No new-UI configuration in ui_v4.dataset (client_id rain_ui2): "
                                 "run deploy/scripts/load_ui2_data_v4.py")
    return out, len(rows)


# ─── Linda's facts for the new UI ─────────────────────────────────────────────────────────────────────

def _reading(text: str) -> dict:
    sys_, dia = (int(x) for x in str(text).split("/"))
    return {"sys": sys_, "dia": dia}


def _linda(computed: dict, config: dict) -> dict:
    """The computed LINDA (her rows) with the new UI's fields: the computed ones derived, the rest configured."""
    linda = copy.deepcopy(computed)
    visit = linda.get("visit") or {}
    day = visit.get("day", "")
    month_abbr, _, day_num = str(visit.get("date", "")).partition(" ")
    visit["esDay"] = ES_DAYS.get(day, day.lower())
    visit["esDate"] = f"{day_num} de {ES_MONTH_ABBR.get(month_abbr, month_abbr.lower())}"
    linda["visit"] = visit
    last = _reading(linda["bp"])
    month = linda.get("bpMonth", "")
    last["month"] = {"en": month, "es": ES_MONTHS.get(month, month.lower())}
    linda["last"] = last
    for k, v in config.items():
        linda.setdefault(k, copy.deepcopy(v))
    return linda


# ─── The six datasets the new UI draws as catalog stacks (port of ultra-rain-v2 datasets.ts) ──────────

def _titled_stack(eyebrow: str, title: str, children: list) -> dict:
    return {"eyebrow": eyebrow, "title": title, "gap": "sm", "children": children}


def _is_met(m: dict) -> bool:
    return m["current"] >= m["target"] if m["higherIsBetter"] else m["current"] <= m["target"]


def _new_datasets(c: dict) -> dict:
    contract, low, bp, model = c["CONTRACT"], c["LOW_VALUE"], c["BP"], c["MODEL"]
    measures, locums, pc = c["MEASURES"], c["LOCUMS"], c["PC_TREND"]

    met = len([m for m in measures if _is_met(m)])
    passes = met >= contract["gateNeeded"]
    gate_rows = []
    for m in measures:
        ok = _is_met(m)
        verdict = "Met" if ok else (f"Not met: about {js(bp['needed'])} more" if m["id"] == "CMS165"
                                    else f"Not met: {js(abs(m['target'] - m['current']))} pts")
        gate_rows.append(spec("stack", {"gap": "sm", "children": [
            spec("text", {"text": f"{m['name']} ({m['id']}{'' if m['higherIsBetter'] else ', lower is better'})"}),
            spec("target_bar", {"value": m["current"], "target": m["target"], "percent": True,
                                "status": "good" if ok else "critical",
                                "valueLabel": f"Current {js(m['current'])}% · {verdict}",
                                "targetLabel": f"Target {js(m['target'])}% or {'higher' if m['higherIsBetter'] else 'lower'}"}),
        ]}))
    gate_rows.append(spec("callout", {"status": "good" if passes else "critical",
                                      "title": "Gate passes" if passes else "Gate at risk"}))

    rates = [x["ratePct"] for x in locums]
    return {
        "pmpm_trend": _titled_stack("Cost against expected", "PMPM, actual vs expected, by month since January", [
            spec("trend_chart", {
                "points": [{"label": p["month"], "value": p["actual"]} for p in c["PMPM_TREND"]],
                "format": {"prefix": "$"},
                "target": contract["expectedPmpm"],
                "targetLabel": f"Expected ${js(contract['expectedPmpm'])}",
                "summary": f"Year to date: ${js(contract['actualPmpm'])} vs ${js(contract['expectedPmpm'])}, "
                           f"+{js(contract['abovePct'])}%.",
                "tone": "worsening",
                "tableCaption": "PMPM by month since January",
            })]),
        "winnemucca_trend": _titled_stack("Winnemucca", "Low back pain imaging rate by month", [
            spec("trend_chart", {
                "points": [{"label": p["month"], "value": p["value"]} for p in c["WINNEMUCCA_TREND"]],
                "format": {"suffix": "%"},
                "target": low["networkRatePct"],
                "targetLabel": f"Network {js(low['networkRatePct'])}%",
                "marker": {"at": low["rotationMonth"][:3], "label": "Locum rotation begins"},
                "summary": f"{len(locums)} rotating clinicians at {js(min(rates))} to {js(max(rates))}%: a protocol gap.",
                "tone": "worsening",
                "tableCaption": "Winnemucca low back pain imaging rate by month",
            })]),
        "quality_gate": _titled_stack("Quality gate", f"{met} of {len(measures)} met · {js(contract['gateNeeded'])} "
                                                      "needed for shared savings", gate_rows),
        "pc_trend": _titled_stack("Since January", "Primary care visits, indexed to January = 100", [
            spec("chart", {
                "kind": "line", "height": 200, "yMin": 80, "yMax": 102, "colors": ["critical", "chart-1"],
                "series": [
                    {"name": "Lander and Pershing",
                     "points": [{"label": m, "value": pc["landerPershing"][i]} for i, m in enumerate(pc["months"])]},
                    {"name": "Other four counties",
                     "points": [{"label": m, "value": pc["otherFour"][i]} for i, m in enumerate(pc["months"])]},
                ],
            }),
            spec("text", {"tone": "muted", "text": "Members moved into managed care on January 1. Monthly path is "
                                                   "illustrative; the September change is the reported figure."}),
        ]),
        "banner_pending_fix": _titled_stack("Banner preview", "As the care team will see it on the Worklist", [
            spec("callout", {"status": "warning",
                             "title": f"Ranking update pending sign-off: {js(model['missingFromTop'])} high-need frontier "
                                      "members will join the top 300. Keep working the current list."})]),
        "banner_freshness": _titled_stack("Banner preview", "As every view now shows it", [
            spec("callout", {"status": "info", "title": f"Data as of: {c['FRESHNESS']}. ED and low-value care figures "
                                                        "trail by about six weeks."})]),
    }


# ─── The new UI's data set ────────────────────────────────────────────────────────────────────────────

def _apply_overrides(contracts: dict, overrides: dict, ctx: dict) -> list:
    """Swap the visuals and KPI values the new UI changed; return what changed."""
    changes = []
    for key, o in overrides.items():
        contract = contracts.get(key)
        if contract is None:
            continue
        for viz_id, viz in (o.get("viz") or {}).items():
            changes.append({"persona": key, "viz": viz_id, "previous": (contract["viz"].get(viz_id) or {}).get("type"),
                            "value": viz["type"]})
            contract["viz"][viz_id] = copy.deepcopy(viz)
        for kpi_id, kpi in (o.get("kpis") or {}).items():
            for k in contract.get("kpis", []):
                if k.get("id") == kpi_id:
                    rendered = render_obj(kpi, ctx)
                    changes.append({"persona": key, "kpi": kpi_id, "previous": k.get("value"), "value": rendered.get("value")})
                    k.update(rendered)
    return changes


def apply_overlay(sections: dict, extra: dict) -> tuple[dict, list]:
    """The new UI's view of a set of v0.4 sections: a copy with the extras applied. Pure (no database).

    `extra` is {"config": {...}, "templates": {...}} as stored under client_id rain_ui2 (or as in the seed file).
    Returns (sections, the contract changes made).
    """
    s = copy.deepcopy(sections)
    config, templates = extra.get("config", {}), extra.get("templates", {})
    c = s["constants"]

    # personas: the six operators keep their v0.4 ids; the patient is rain_patient with her own contract
    pcfg = config.get("personas", {})
    for key in pcfg.get("drop", []):
        c["PERSONAS"].pop(key, None)
        s["contracts"].pop(key, None)
        s["personas"].pop(key, None)
    c["PATIENT_PERSONA_ID"] = pcfg.get("patientId", "rain_patient")

    # constants the new UI adds
    c["LINDA"] = _linda(c["LINDA"], config.get("linda", {}))
    synthetic = s["sources"]["SYNTHETIC_SOURCES"]
    have = {x["id"] for x in synthetic}
    synthetic.extend(copy.deepcopy(x) for x in config.get("synthetic_sources", []) if x["id"] not in have)
    c["MODEL"]["syntheticSources"] = len(synthetic)
    c["PC_TREND"] = render_obj(config.get("pc_trend", {}), s)

    # the six datasets the new contracts draw as stacks
    s["datasets"].update(_new_datasets(c))

    # contracts: the new UI's visuals and KPI values, then the patient's contract and copy
    changes = _apply_overrides(s["contracts"], templates.get("contract_overrides", {}), s)
    s["contracts"][PATIENT_KEY] = render_obj(templates.get("patient_contract", {}), s)
    s["personas"][PATIENT_KEY] = render_obj(templates.get("patient_persona", {}), s)
    return s, changes


def load_sections_v2(client_id: str = CLIENT_ID) -> tuple[dict, dict]:
    """The v0.4 sections (computed per request) with the new UI's extras. Returns (sections, info)."""
    if client_id != CLIENT_ID:
        raise HTTPException(404, f'No client "{client_id}"')
    sections, overlay, row_count, loaded_at = ui_data_v4.load_sections(client_id)
    extra, extra_rows = _overlay_rows()
    s, changes = apply_overlay(sections, extra)
    info = {"overlay": overlay, "configRows": row_count, "configLoadedAt": loaded_at,
            "ui2Rows": extra_rows, "ui2Changes": changes}
    return s, info


@router.get("/data")
def ui2_data(clientId: str, request: Request):
    t0 = time.perf_counter()
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]
    sections, info = load_sections_v2(clientId)
    db_ms = (time.perf_counter() - t0) * 1000
    overlay = info["overlay"]
    records = sections.get("records", {})
    meta = {
        "source": "rain-api",
        "server": socket.gethostname(),
        "dataSource": DATA_SOURCE,
        "ui": "ultra-rain-v2",
        "database": {"name": "rain_v4", "computedFrom": ["synthetic", "public_data"], "configTable": "ui_v4.dataset",
                     "configRows": info["configRows"], "configLoadedAt": info["configLoadedAt"].isoformat(),
                     "uiClientId": OVERLAY_CLIENT_ID, "uiRows": info["ui2Rows"]},
        "computed": overlay[0] if overlay and "computed" in overlay[0] else None,
        "publicOverlay": overlay,
        "uiOverrides": info["ui2Changes"],
        "counts": {name: len(sec) for name, sec in sections.items()},
        "records": {name: len(v) for name, v in records.items() if isinstance(v, list)},
        "requestId": request_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "dbMs": round(db_ms, 1),
    }
    body = json.dumps({"meta": meta, "sections": sections}, separators=(",", ":"), ensure_ascii=False,
                      default=str).encode("utf-8")
    log.info("ui2 data client=%s: %d config + %d new-UI rows, %d bytes in %.0f ms req=%s", clientId,
             info["configRows"], info["ui2Rows"], len(body), db_ms, request_id)
    return Response(content=body, media_type="application/json", headers={
        "X-RAIN-Request-Id": request_id,
        "X-RAIN-Server": meta["server"],
        "X-RAIN-Data-Source": DATA_SOURCE,
        "X-RAIN-Data-Sha256": hashlib.sha256(body).hexdigest(),
        "Server-Timing": f"db;dur={db_ms:.1f}",
        "Cache-Control": "no-store",
    })


# ─── The conversation ─────────────────────────────────────────────────────────────────────────────────

WEEK_CHIP = "What is on Linda's phone this week?"

# The new UI's patient id → her persona queries in the v0.4 pack (doc/queries/rain_v4_persona_queries.sql: GAR-S1..S5
# on her own synthetic records, GAR-P1..P5 on public data for her town and county). persona_queries_v4 keeps the pack
# id in SELF_ONLY, so the patient runs only her own ten and is refused anyone else's.
QUERY_PERSONA = {"rain_patient": "patient_linda_garcia"}


def query_persona(persona_id: str) -> str:
    return QUERY_PERSONA.get(persona_id, persona_id)


def _build_patient(s: dict, persona_id: str) -> dict:
    """Linda's manifest (personas/patient/manifest.tsx) as API payloads: her conversation itself is her phone view."""
    contract, ui = s["contracts"][PATIENT_KEY], s["personas"][PATIENT_KEY]
    identity = ui["identity"]
    sources = set(ui.get("dataSourceIds") or [])
    week = contract["steps"]["pt_week"]
    turns = {
        "pt_open": {"id": "pt_open", "text": "Opening Linda's phone.", "citations": [], "components": [],
                    "chips": [WEEK_CHIP], "confidence": 100},
        "pt_week": {"id": "pt_week", "text": week["ai"]["en"], "citations": [str(x) for x in week.get("sources", [])],
                    "components": [], "chips": [], "confidence": 100},
        "__default__": {"id": "__default__", "text": "Linda's conversation is on her phone. Use the button above to open it.",
                        "citations": [], "components": [], "chips": [WEEK_CHIP]},
    }
    all_sources = [*s["sources"]["PUBLIC_SOURCES"], *s["sources"]["SYNTHETIC_SOURCES"], *s["sources"]["ENGINES"]]
    personas = s["constants"]["PERSONAS"]
    context = {
        "client": s["client"]["branding"],
        "persona": {"id": persona_id, "name": identity["name"], "initials": identity["initials"], "role": identity["role"],
                    "layout": "full", "capabilities": ["Friction Observability"], "navSlots": ["ask"]},
        "personas": [*({"id": personas[k], "name": s["personas"][k]["identity"]["name"],
                        "role": s["personas"][k]["identity"]["role"]} for k in personas),
                     {"id": persona_id, "name": identity["name"], "role": identity["role"]}],
        "dataSources": [x for x in all_sources if x["id"] in sources],
    }
    briefing = {"greeting": turns["pt_open"], "signals": [], "kpis": [], "chips": [WEEK_CHIP]}
    flows = {k: {"user_query": WEEK_CHIP if k == "pt_week" else "", "corpus": f"{WEEK_CHIP if k == 'pt_week' else ''} {t['text']} ".lower()}
             for k, t in turns.items()}
    match = {"chipToFlowKey": {WEEK_CHIP: "pt_week", WEEK_CHIP.lower(): "pt_week", chat_v4.loose(WEEK_CHIP): "pt_week"},
             "strictMatch": False, "signalSequence": [], "flows": flows}
    return {"context": context, "briefing": briefing, "turns": turns, "match": match}


def _with_patient_in_switcher(chat: dict, s: dict) -> dict:
    """An operator's context lists every persona in the switcher, the patient last (client.manifest.ts order)."""
    ui = s["personas"].get(PATIENT_KEY)
    if ui:
        pid = s["constants"]["PATIENT_PERSONA_ID"]
        chat["context"]["personas"] = [p for p in chat["context"]["personas"] if p["id"] != pid] + \
                                      [{"id": pid, "name": ui["identity"]["name"], "role": ui["identity"]["role"]}]
    return chat


def _load(persona_id: str) -> dict:
    s, _info = load_sections_v2(CLIENT_ID)
    if persona_id == s["constants"]["PATIENT_PERSONA_ID"]:
        return _build_patient(s, persona_id)
    try:
        return _with_patient_in_switcher(chat_v4.build_persona(s, persona_id), s)
    except KeyError:
        raise HTTPException(404, f'No persona "{persona_id}" for client "{CLIENT_ID}"')


def _source(persona_id: str) -> str:
    return f"{CHAT_SOURCE} (contracts.{persona_id.removeprefix('rain_')}, built live for ultra-rain-v2)"


def _proof(response: Response, persona_id: str, turn: str | None = None) -> None:
    response.headers["X-RAIN-Data-Source"] = _source(persona_id)
    if turn:
        response.headers["X-RAIN-Turn"] = turn


def _require_client(client_id: str) -> None:
    if client_id != CLIENT_ID:
        raise HTTPException(404, f'No client "{client_id}"')


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
    turn = (briefing.get("greeting") or {}).get("id")
    _proof(response, personaId, turn)
    log.info("ui2 briefing persona=%s turn=%s built from %s", personaId, turn, _source(personaId))
    return briefing


@router.post("/ask")
def ask(body: dict, response: Response):
    """The v0.4 /ask ladder (ultra_v4_api.ask), over the new UI's data.

    The patient (rain_patient) asks with her own pack queries (GAR-*): her own records (synthetic) and public data for
    her town and county; another persona's query is refused, never run (persona_queries_v4 SELF_ONLY).
    """
    _require_client(str(body.get("clientId")))
    persona_id = str(body.get("personaId"))
    chat = _load(persona_id)
    user_input = str(body.get("input") or "")
    match = chat["match"]
    qp = query_persona(persona_id)

    flow_key = None
    query = None
    if user_input in v4._SIGNAL_WALKTHROUGH_INPUTS:
        seq = match.get("signalSequence") or []
        flow_key = seq[0] if seq else None
    else:
        flow_key = v4._scripted_exact(match, user_input)
        if not flow_key:
            query = pq.find_query(qp, user_input, "exact")
        if not flow_key and not query:
            flow_key = v4._scripted_loose_chip(match, user_input)
        if not flow_key and not query:
            query = pq.find_query(qp, user_input, "close")
            if query and pq._loose(query["question"]) in v4._scripted_questions(match):
                query = None
        if not flow_key and not query:
            flow_key = v4._resolve_flow_key(match, user_input)
            if flow_key == v4._DEFAULT_FLOW_KEY:
                owner = pq.owner_of(user_input)
                if owner and not pq.find_query(qp, owner["id"], "exact"):
                    turn = v4._refused_turn(qp, owner)
                    response.headers["X-RAIN-Turn"] = turn["id"]
                    response.headers["X-RAIN-Data-Source"] = "not run (data access rule)"
                    return turn
                query = pq.find_query(qp, user_input, "fuzzy")
    if query:
        turn, result = v4._query_turn(query)
        source = f"postgres://{result['schema'].replace('.', '/')} (query {query['id']})" if result else "query failed"
        response.headers["X-RAIN-Data-Source"] = source
        response.headers["X-RAIN-Turn"] = turn["id"]
        log.info("ui2 ask persona=%s turn=%s source=%s", persona_id, turn["id"], source)
        return turn
    if not flow_key:
        flow_key = v4._DEFAULT_FLOW_KEY if v4._DEFAULT_FLOW_KEY in chat["turns"] else None
    if not flow_key:
        raise HTTPException(422, f'No answer for "{user_input}"')
    _proof(response, persona_id, flow_key)
    log.info("ui2 ask persona=%s turn=%s built from %s", persona_id, flow_key, _source(persona_id))
    return chat["turns"][flow_key]


@router.post("/actions/{action_id}")
def run_action(action_id: str, body: dict):
    _require_client(str(body.get("clientId")))
    _load(str(body.get("personaId")))  # 404 for unknown personas first
    raise HTTPException(404, f'No action "{action_id}"')


_catalog: list | None = None


@router.get("/catalog")
def get_catalog():
    global _catalog
    if _catalog is None:
        path = next((p for p in CATALOG_PATHS if p.is_file()), None)
        if path is None:
            raise HTTPException(503, "catalog missing: frontend/ultra-rain-v2/docs/catalog/catalog.json")
        _catalog = json.loads(path.read_text(encoding="utf-8"))
    return _catalog


@router.get("/queries")
def list_persona_queries(personaId: str, response: Response):
    """A persona's pack queries by its new-UI id (the patient's are GAR-*): id, data (synthetic|public), question."""
    qp = query_persona(personaId)
    items = [{"id": q["id"], "data": q["data"], "question": q["question"], "url": f"/api/v4/queries/{q['id']}"}
             for q in pq._pack().values() if q["persona"] == qp]
    if not items:
        raise HTTPException(404, f'No queries for persona "{personaId}"')
    response.headers["X-RAIN-Data-Source"] = f"query pack doc/queries/{pq.PACK.name} (persona {qp})"
    return {"personaId": personaId, "packPersona": qp, "count": len(items), "queries": items}


@router.get("/personas")
def list_personas():
    s, _info = load_sections_v2(CLIENT_ID)
    return [*s["constants"]["PERSONAS"].values(), s["constants"]["PATIENT_PERSONA_ID"]]
