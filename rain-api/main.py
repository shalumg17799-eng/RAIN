"""
Radiant V2 API -- same contract as Charan's USSFCU service
(ussfcu_api_v2_swagger.md), with RAIN registered as a second product.

The point of this rebuild: the contract (4 unified endpoints, persona-in-
body, market/product/persona routing, the USFCUResponse envelope, the MD5
query-cache flow for /ask) is the actual integration surface Ultra's
frontend expects. Adding a client to this system should mean adding an
entry to PRODUCTS, not inventing a new shape. RAIN is that proof.

Run:
    pip install fastapi uvicorn
    python3 build_ask_cache.py
    uvicorn main:app --reload --port 8000
    docs at http://127.0.0.1:8000/docs
"""

import logging
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from datetime import datetime, timezone
from insights.api.rain_adapter import get_rain_router

from signal_data import RAIN_SIGNALS, DATA_SOURCES_USED
from data_sources_detail import DATA_SOURCES_DETAIL, DATA_SOURCES_HEALTH_KPIS
from rural_health_data import CASCADE_ROOT, CASCADE_BRANCHES, COUNTY_ACCESS_DATA, COUNTY_RISK_SUMMARY
from ultra_adapter import ultra_signals_for_persona, ultra_data_sources, ultra_kpis_for_persona
from graph_provenance import get_cascade_branch_provenance, get_county_region_provenance, get_data_source_field_count
from kpi_data import RAIN_KPIS
from neo4j_fallback import try_live_fallback
from persona_scope import normalize_persona
from action_package import build_tier1_package, decide as decide_action_package, get_audit, ActionInputError
import action_engine
from maria_action_package import build_maternal_package, decide_maternal, get_maternal_audit
from david_data_health import get_data_health_board, get_reconciliation_breakdown
from james_ops_live import get_ops_traffic_tiles, get_trip_telehealth_conversion, get_transport_queue_breakdown
from david_downstream_impact import get_downstream_impact
from david_remediation_plan import build_remediation_plan, decide_remediation, get_remediation_audit
from james_operations_plan import build_operations_plan, decide_operations, get_operations_audit
from priya_intervention_comparison import get_intervention_comparison
from priya_equity_brief import build_equity_brief, decide_equity_brief, get_equity_brief_audit
from sarah_deterioration_live import get_deterioration_board
from sarah_risk_tiers import get_risk_tiered_outreach
from maria_risk_stratification import get_maternal_risk_stratification
from maria_telehealth_scenario import get_telehealth_scenario

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s")
log = logging.getLogger("rain.api")

app = FastAPI(title="Radiant V2 API", version="2.0")
app.include_router(get_rain_router(), prefix="/api/v2")
# expose_headers lets the browser's fetch() read X-RAIN-Source, which the
# frontend logs as proof a response came from this server.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-RAIN-Source"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One line per request, so every value the UI shows can be traced to a
    server hit. Request bodies are not logged -- /ask carries free text."""
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-RAIN-Source"] = "rain-api"
    if request.method != "OPTIONS":
        log.info("%s %s -> %d (%.0f ms)", request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
    return response

with open("ask_cache.json") as f:
    ASK_CACHE = json.load(f)

# --- Product registry -- this is the actual extension point. Adding a
# third client means adding one entry here, nothing else changes. ---
PRODUCTS = {
    "rain": {
        "market": "healthcare",
        "signals": RAIN_SIGNALS,
        "kpis": RAIN_KPIS,
        "ask_cache": ASK_CACHE,
        "data_sources": DATA_SOURCES_USED,
        "personas": {"maria", "sarah", "james", "priya", "david"},
    },
    # "ussfcu": {...}  <- Charan's own service owns this; not reimplemented
    # here. Registering it would mean pointing at his real backend/DB,
    # not duplicating his data.
}


class CategoryItem(BaseModel):
    component: str
    variant: Optional[str] = None


class BaseRequest(BaseModel):
    market: str
    product: str
    persona: str


class SignalsRequest(BaseRequest):
    category: list[CategoryItem]


class KpisRequest(BaseRequest):
    category: list[CategoryItem]


class AskRequest(BaseRequest):
    query: str
    conversation_history: list = []


class GenericRequest(BaseRequest):
    category: list[CategoryItem]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def envelope(persona_id, client_id, ai_message=None, suggested_chips=None,
             confidence=None, data_sources_used=None, visualization=None,
             data=None, freshness="live"):
    return {
        "meta": {
            "as_of": now_iso(),
            "freshness": freshness,
            "persona_id": persona_id,
            "client_id": client_id,
        },
        "ai_message": ai_message,
        "suggested_chips": suggested_chips or [],
        "confidence": confidence,
        "data_sources_used": data_sources_used or [],
        "visualization": visualization,
        "data": data,
        "report": None,
    }


def resolver_error(components):
    return {
        "meta": {"as_of": now_iso(), "freshness": "live", "persona_id": None, "client_id": None},
        "ai_message": None, "suggested_chips": [], "confidence": None,
        "data_sources_used": [], "visualization": None,
        "data": {"error": f"No resolver found for components: {components}"},
        "report": None,
    }


@app.post("/api/v2/signals")
def get_signals(req: SignalsRequest):
    product = PRODUCTS.get(req.product)
    if not product or req.persona not in product["signals"]:
        return resolver_error([req.persona])

    cards = product["signals"][req.persona]
    persona_id = f"{req.product}_{req.persona}"
    return envelope(
        persona_id=persona_id,
        client_id=req.product,
        data_sources_used=product["data_sources"],
        visualization=[{"type": "SignalCard", "variant": None, "data": c} for c in cards],
        data={"count": len(cards)},
    )


@app.post("/api/v2/kpis")
def get_kpis(req: KpisRequest):
    product = PRODUCTS.get(req.product)
    if not product or req.persona not in product["kpis"]:
        return resolver_error([req.persona])

    kpis = product["kpis"][req.persona]
    persona_id = f"{req.product}_{req.persona}"
    return envelope(
        persona_id=persona_id,
        client_id=req.product,
        freshness="daily",
        data_sources_used=product["data_sources"],
        visualization=[{"type": "KpiCarousel", "variant": None, "data": {"kpis": kpis}}],
        data=None,
    )


@app.post("/api/v2/ask")
def ask(req: AskRequest):
    """Every answer is computed live -- no hand-written text is ever returned
    here. The pre-written ask_cache.json (40 example Q&A pairs) is kept only
    as a reference / regression fixture for validate_cache_against_kg.py; it
    is no longer consulted to answer a real request. See ultra_adapter.py /
    signal_data.py / kpi_data.py for the separate (and separately tracked)
    static-card gap this change does not cover -- this is the answer-text
    path only."""
    product = PRODUCTS.get(req.product)
    persona_id = f"{req.product}_{req.persona}"

    if not product or req.persona not in product["ask_cache"]:
        return envelope(
            persona_id=persona_id, client_id=req.product,
            ai_message="I don't have a pre-built answer for that question yet. Try one of the suggested chips, or rephrase your question.",
        )

    # Always compute live. try_live_fallback is the one path to an answer:
    # verified business rules first, then concept detection, then LLM SQL,
    # then the ontology narrative. It returns None only for a genuine
    # non-data question (e.g. "cache this plan offline for the field" --
    # a device/sync action, not something rain.db or the graph can answer).
    live = try_live_fallback(req.query, product=req.product, persona=req.persona)
    log.info("ask persona=%s answered_by=%s sources=%s", req.persona,
             [v.get("type") for v in (live or {}).get("visualization") or []] or "none (not-found reply)",
             (live or {}).get("data_sources_used") or [])
    if live:
        return envelope(
            persona_id=persona_id, client_id=req.product,
            ai_message=live["ai_message"],
            suggested_chips=live["suggested_chips"],
            confidence=live["confidence"],
            data_sources_used=live["data_sources_used"],
            visualization=live["visualization"],
        )
    return envelope(
        persona_id=persona_id, client_id=req.product,
        ai_message="I don't have a pre-built answer for that question yet. Try one of the suggested chips, or rephrase your question.",
    )


# --- Generic page resolver ---------------------------------------------
# RAIN's non-Ask pages: "Data Sources" (real, detailed, below) and
# "Care & Risk Signals" (aggregates every persona's signal cards into one
# feed). "Rural Health Intelligence" needs the cascade-diagram content
# described in the spec, not yet built -- next piece.
def data_sources_panel(product_key, persona=None):
    if product_key == "rain":
        return {"sources": DATA_SOURCES_DETAIL, "health_kpis": DATA_SOURCES_HEALTH_KPIS}
    # Fallback for any future product without detailed source data yet
    product = PRODUCTS[product_key]
    return {"sources": [{"name": s, "status": "connected"} for s in product["data_sources"]]}


def risk_signal_feed(product_key, persona=None):
    """Every signal card across every persona, tagged with who it belongs
    to -- 'across participating rural healthcare organizations' per the
    Care & Risk Signals page description, not just one persona's view.

    Uses ultra_signals_for_persona() per persona (not the raw static
    RAIN_SIGNALS dict) so this feed gets the exact same live PostgreSQL
    values and live Neo4j provenance as every other page -- a signal
    shouldn't show live data on Ask the AI but stale/unverified data here.
    """
    product = PRODUCTS[product_key]
    feed = []
    for persona_slug in product["signals"].keys():
        cards = ultra_signals_for_persona(persona_slug)
        for card in cards:
            feed.append({**card, "persona": persona_slug})
    # Most severe first, matching how a real alert feed should read
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    feed.sort(key=lambda c: severity_order.get(c.get("severity", "info"), 3))
    return {"signals": feed, "total": len(feed)}


def cascade_impact_map(product_key, persona=None):
    """The Battle Mountain closure cascade -- 5 real branches, matching the
    diagram already shown. RAIN-specific for now; a future product without
    a single-event cascade root would just not register this component."""
    return {"root": CASCADE_ROOT, "branches": CASCADE_BRANCHES}


def county_access_map(product_key, persona=None):
    """Real Nevada county-level aggregates, computed from rain.db, keyed by
    real US Census FIPS codes so the frontend can color actual county
    boundaries (fetched live from us-atlas) rather than invented shapes."""
    return {"counties": COUNTY_ACCESS_DATA}


# --- Card-data resolvers, registered under /api/v2/generic ---------------
# Each of these used to be its own @app.get route (one per card). That
# broke the 4-generic-API contract (signals / kpis / ask / generic) the
# Insights Factory is supposed to follow -- a new card or a new domain
# should never need a new endpoint, only a new resolver entry below. A
# frontend component asks for its data by Component name (optionally a
# Variant) through POST /api/v2/generic; see GENERIC_RESOLVERS.
def data_health_board(product_key, persona=None):
    """Live data for DataHealthBoard.jsx -- see david_data_health.py."""
    return get_data_health_board()


def reconciliation_breakdown(product_key, persona=None):
    """Live data for ReconciliationBreakdown.jsx -- see david_data_health.py."""
    return get_reconciliation_breakdown()


def ops_traffic_tiles(product_key, persona=None):
    """Live data for OpsTrafficLightTiles.jsx -- see james_ops_live.py."""
    return get_ops_traffic_tiles()


def trip_telehealth_conversion(product_key, persona=None):
    """Live data for TripTelehealthConversion.jsx -- see james_ops_live.py."""
    return get_trip_telehealth_conversion()


def deterioration_board(product_key, persona=None):
    """Live data for DeteriorationBoard.jsx -- see sarah_deterioration_live.py."""
    return get_deterioration_board()


def risk_tiered_outreach(product_key, persona=None):
    """Live data for RiskTieredOutreach.jsx -- see sarah_risk_tiers.py."""
    return get_risk_tiered_outreach()


def maternal_risk_stratification(product_key, persona=None):
    """Live data for MaternalRiskStratification.jsx -- see maria_risk_stratification.py."""
    return get_maternal_risk_stratification()


def telehealth_scenario(product_key, persona=None):
    """Live data for TelehealthScenarioModel.jsx -- see maria_telehealth_scenario.py."""
    return get_telehealth_scenario()


def transport_queue_breakdown(product_key, persona=None):
    """Live data for TransportQueueTimeline.jsx -- see james_ops_live.py."""
    return get_transport_queue_breakdown()


def downstream_impact(product_key, persona=None):
    """Live data for DownstreamImpactMap.jsx -- see david_downstream_impact.py."""
    return get_downstream_impact()


def intervention_comparison(product_key, persona=None):
    """Live data for InterventionComparison.jsx -- see priya_intervention_comparison.py."""
    return get_intervention_comparison()

GENERIC_RESOLVERS = {
    "DataSourcesPanel": data_sources_panel,
    "RiskSignalFeed": risk_signal_feed,
    "CascadeImpactMap": cascade_impact_map,
    "CountyAccessMap": county_access_map,
    "DataHealthBoard": data_health_board,
    "ReconciliationBreakdown": reconciliation_breakdown,
    "OpsTrafficTiles": ops_traffic_tiles,
    "TripTelehealthConversion": trip_telehealth_conversion,
    "DeteriorationBoard": deterioration_board,
    "RiskTieredOutreach": risk_tiered_outreach,
    "MaternalRiskStratification": maternal_risk_stratification,
    "TelehealthScenario": telehealth_scenario,
    "TransportQueueBreakdown": transport_queue_breakdown,
    "DownstreamImpact": downstream_impact,
    "InterventionComparison": intervention_comparison,
}


@app.post("/api/v2/generic")
def generic(req: GenericRequest):
    product = PRODUCTS.get(req.product)
    if not product:
        return resolver_error([c.component for c in req.category])

    viz = []
    unresolved = []
    for item in req.category:
        resolver = GENERIC_RESOLVERS.get(item.component)
        if resolver:
            viz.append({"type": item.component, "variant": item.variant, "data": resolver(req.product, req.persona)})
        else:
            unresolved.append(item.component)
    log.info("generic persona=%s resolved=%s unresolved=%s", req.persona,
             [v["type"] for v in viz], unresolved or "none")

    if unresolved and not viz:
        return resolver_error(unresolved)

    persona_id = f"{req.product}_{req.persona}"
    return envelope(
        persona_id=persona_id, client_id=req.product,
        data_sources_used=product["data_sources"], visualization=viz,
    )


# --- Ultra frontend plain endpoints ---------------------------------
# These return the EXACT shapes Ultra's React hooks already expect from
# their static JSON files (signals.json, dataSources.json) -- no Charan-
# style envelope, no wrapper. This is the direct drop-in replacement the
# README's "Backend integration" section describes: swap the static
# import for a fetch to these URLs and the existing components render
# unchanged.
@app.get("/ultra/rain/{persona}/signals")
def ultra_signals(persona: str):
    return ultra_signals_for_persona(persona)


@app.get("/ultra/rain/dataSources")
def ultra_data_sources_endpoint():
    sources = ultra_data_sources()
    # Live lookup: how many real ontology field mappings this source
    # actually backs, per the graph -- not a stored number.
    for s in sources:
        s["ontology_field_count"] = get_data_source_field_count(s["name"])
    return sources


@app.get("/ultra/rain/{persona}/kpis")
def ultra_kpis(persona: str):
    return ultra_kpis_for_persona(persona)


@app.get("/ultra/rain/cascade")
def ultra_cascade():
    """Matches CascadeDiagram.jsx's exact branches array, enriched with
    live provenance (concept/persona) pulled straight from the graph."""
    branches = [dict(b) for b in CASCADE_BRANCHES]
    for b in branches:
        prov = get_cascade_branch_provenance(b["id"])
        b["graph_provenance"] = prov
    return branches


@app.get("/ultra/rain/countyRisk")
def ultra_county_risk():
    """Matches NevadaCountyChoropleth.jsx's exact content shape, with each
    region's provenance pulled live from the graph."""
    result = dict(COUNTY_RISK_SUMMARY)
    result["regions"] = [dict(r) for r in COUNTY_RISK_SUMMARY["regions"]]
    for r in result["regions"]:
        r["graph_provenance"] = get_county_region_provenance(r["name"])
    return result


# ---------------------------------------------------------------------------
# Tier 1 action package (Sarah). Builds draft actions from the real data and
# records a person's route / hold decision. DRAFT-ONLY: "route" writes an audit
# entry and marks actions as routed; nothing is ever sent to an external system
# (delivery is always "simulated"). See action_package.py.
# ---------------------------------------------------------------------------
class ActionInputs(BaseModel):
    inputs: Optional[dict] = None


class ActionDecision(BaseModel):
    decision: str
    decided_by: str
    inputs: Optional[dict] = None
    note: Optional[str] = None


# persona -> the functions that build / decide / audit that persona's package.
# Each package is draft-only; see action_engine.py and the module of each package.
ACTION_PACKAGES = {
    "sarah": {"build": build_tier1_package, "decide": decide_action_package, "audit": get_audit, "errors": (ActionInputError,)},
    "maria": {"build": build_maternal_package, "decide": decide_maternal, "audit": get_maternal_audit, "errors": (action_engine.ActionInputError,)},
    "david": {"build": build_remediation_plan, "decide": decide_remediation, "audit": get_remediation_audit, "errors": (action_engine.ActionInputError,)},
    "james": {"build": build_operations_plan, "decide": decide_operations, "audit": get_operations_audit, "errors": (action_engine.ActionInputError,)},
    "priya": {"build": build_equity_brief, "decide": decide_equity_brief, "audit": get_equity_brief_audit, "errors": (action_engine.ActionInputError,)},
}


def _action_package(persona: str):
    entry = ACTION_PACKAGES.get(normalize_persona(persona))
    if not entry:
        raise HTTPException(status_code=404, detail="No action package exists for this persona.")
    return entry


@app.get("/ultra/rain/{persona}/actionPackage")
def ultra_action_package(persona: str):
    return _action_package(persona)["build"]()


@app.post("/ultra/rain/{persona}/actionPackage/preview")
def ultra_action_package_preview(persona: str, body: ActionInputs):
    """The package as it would look with these inputs applied. Records nothing."""
    entry = _action_package(persona)
    try:
        return entry["build"](body.inputs)
    except entry["errors"] as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ultra/rain/{persona}/actionPackage/decision")
def ultra_action_package_decision(persona: str, body: ActionDecision):
    entry = _action_package(persona)
    try:
        return entry["decide"](body.decision, body.decided_by, body.inputs, body.note)
    except entry["errors"] as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/ultra/rain/{persona}/actionPackage/audit")
def ultra_action_package_audit(persona: str):
    return _action_package(persona)["audit"]()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "products_registered": list(PRODUCTS.keys()),
        "rain_personas": sorted(PRODUCTS["rain"]["personas"]),
        "rain_signals_loaded": sum(len(v) for v in RAIN_SIGNALS.values()),
        "rain_ask_cache_size": sum(len(v) for v in ASK_CACHE.values()),
    }
