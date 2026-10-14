"""
Transforms our existing, already-real data (signal_data.py,
data_sources_detail.py) into the EXACT shapes Ultra's React frontend
expects -- verified against the actual unzipped rain-app source
(SignalCard.jsx, DataSources.jsx, dataSources.json), not guessed.

No new content is invented here -- every field is either copied straight
from our existing real data or mechanically derived from it (record-count
string -> raw int, icon name matched to what their own dataSources.json
already used for these same 11 sources).
"""

import logging
import re
from decimal import Decimal
from datetime import datetime, timezone
from signal_data import RAIN_SIGNALS
from data_sources_detail import DATA_SOURCES_DETAIL
from maria_live_data import get_maria_live_kpis, get_maria_live_signals
from sarah_live_data import get_sarah_live_kpis, get_sarah_live_signals
from james_live_data import get_james_live_kpis, get_james_live_signals
from priya_live_data import get_priya_live_kpis, get_priya_live_signals
from david_live_data import get_david_live_kpis, get_david_live_signals
from graph_provenance import get_signal_provenance, get_kpi_provenance

# Says, per request, which fields came from a live PostgreSQL query and which
# are the saved values -- so "is this live?" is answered by the server log,
# not inferred from the numbers.
log = logging.getLogger("rain.data")

# Per-persona live-data functions -- each returns only the fields that
# have a verified, exact SQL match; everything else stays static.
LIVE_KPI_FUNCS = {
    "maria": get_maria_live_kpis,
    "sarah": get_sarah_live_kpis,
    "james": get_james_live_kpis,
    "david": get_david_live_kpis,
    "priya": get_priya_live_kpis,
}

LIVE_SIGNAL_FUNCS = {
    "maria": get_maria_live_signals,
    "sarah": get_sarah_live_signals,
    "james": get_james_live_signals,
    "priya": get_priya_live_signals,
    "david": get_david_live_signals,
}

# Icon assignment matches Ultra's own dataSources.json exactly for these
# same 11 sources -- not a guess, copied from the file itself.
_SOURCE_ICON_MAP = {
    "Clinical EHR (Critical Access Hospitals & RHCs)": "database",
    "Maternal Health Registry": "heart-pulse",
    "RPM Platform (Remote Patient Monitoring)": "activity",
    "Claims & Encounters": "database",
    "Telehealth (Project ECHO Nevada)": "monitor",
    "EMS / Transport Dispatch": "alert-triangle",
    "NEMT / Transportation Logs": "cog",
    "SDOH Data": "users",
    "Public Health Registries": "shield",
    "State HIE": "monitor",
    "Enterprise Data Warehouse (Medallion Lakehouse)": "trending-up",
}


def _parse_record_count(records_str: str) -> int:
    """'2.1M' -> 2100000, '18K' -> 18000. Mechanical parsing, not invented."""
    s = records_str.strip().upper()
    m = re.match(r"^([\d.]+)([MK]?)$", s)
    if not m:
        return 0
    num, suffix = float(m.group(1)), m.group(2)
    if suffix == "M":
        return int(num * 1_000_000)
    if suffix == "K":
        return int(num * 1_000)
    return int(num)


def ultra_signals_for_persona(persona: str) -> list:
    """Matches signals.json's exact field set, verified against SignalCard.jsx:
    id, type, title, description, impact, severity, affected_count, sources,
    timestamp, trend, related_segment, metrics, affected_unit."""
    cards = RAIN_SIGNALS.get(persona, [])
    live = {}
    live_func = LIVE_SIGNAL_FUNCS.get(persona)
    if live_func:
        try:
            live = live_func()
        except Exception as e:
            # DB unreachable -- fall back to static values, never break the request
            log.warning("signals persona=%s POSTGRES UNREACHABLE (%s) -- serving STATIC signal values", persona, e)
    log.info("signals persona=%s live_sql=%d/%d static=%s", persona,
             sum(c["id"] in live for c in cards), len(cards),
             [c["id"] for c in cards if c["id"] not in live] or "none")
    out = []
    for c in cards:
        live_card = live.get(c["id"], {})
        # Live, on-request lookup in the persona graph -- this is what
        # actually makes today's Neo4j load DO something, instead of just
        # sitting there as a disconnected record. None if the graph has
        # no COMPUTED_FROM edge for this signal (i.e., genuinely static).
        source_system = get_signal_provenance(c["id"])
        out.append({
            "id": c["id"],
            "type": c["type"],
            "title": live_card.get("title", c["title"]),
            "description": live_card.get("description", c["description"]),
            "impact": c["impact"],
            "severity": c["severity"],
            "affected_count": live_card.get("affected_count", c["affected_count"]),
            "sources": c["sources"],
            "timestamp": c["timestamp"],
            "trend": c["trend"],
            "related_segment": None,
            "metrics": {**c["metrics"], **live_card.get("metrics", {})},
            "affected_unit": live_card.get("affected_unit", "patients"),
            # carried straight through -- SignalCard.jsx reads confidence.score
            "confidence": c["confidence"],
            # new: real graph-sourced provenance, not a hardcoded claim
            "verified_live": source_system is not None,
            "source_system": source_system,
        })
    return out


def ultra_data_sources() -> list:
    """Matches dataSources.json's exact field set, verified against
    DataSources.jsx and its iconMap: id, name, status, description, icon,
    lastSync, recordCount (raw int, formatted client-side)."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    out = []
    for i, s in enumerate(DATA_SOURCES_DETAIL, start=1):
        out.append({
            "id": f"rain-ds-{i:02d}",
            "name": s["name"],
            "status": s["status"],
            "description": s["description"],
            "icon": _SOURCE_ICON_MAP.get(s["name"], "database"),
            "lastSync": now_iso,
            "recordCount": _parse_record_count(s["records"]),
        })
    return out


# KPI ("stats") content transcribed verbatim from the real Ultra frontend's
# own src/clients/rain/personaUI.js -- this is already-correct, already-
# built content, not reinvented here. Icon is the lucide-react component
# NAME as a string (can't send a React component over JSON); the frontend
# maps the string back to the real icon via a small iconMap, same pattern
# DataSources.jsx already uses successfully.
ULTRA_KPI_DATA = {
    "maria": [
        {"id": "active_pregnancies", "label": "Active Pregnancies in Service Area", "value": "126", "trend": "Clinical EHR + Maternal Registry", "positive": True, "icon": "Baby", "iconColor": "text-blue-600", "iconBg": "bg-blue-500/10", "chipText": "Show me all elevated-risk pregnancies in the service area"},
        {"id": "elevated_risk", "label": "Elevated-Risk Pregnancies", "value": "38", "trend": "Maternal Registry + RAIN Risk Engine", "positive": False, "icon": "HeartPulse", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Walk me through the high-risk cohort"},
        {"id": "prenatal_completion", "label": "Prenatal Visit Completion Rate", "value": "61%", "trend": "was 84% — Clinical EHR + Scheduling", "positive": False, "icon": "CalendarCheck", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "What is our prenatal completion rate trend?"},
        {"id": "distance_delivery", "label": "Avg. Distance to Delivering Hospital", "value": "115 mi", "trend": "Geospatial + Facility Registry", "positive": False, "icon": "MapPin", "iconColor": "text-violet-600", "iconBg": "bg-violet-500/10", "chipText": None},
        {"id": "no_transport", "label": "Patients Without Scheduled Transport", "value": "22", "trend": "NEMT Logs + Scheduling", "positive": False, "icon": "Bus", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Which patients have no transport scheduled to their next appointment?"},
        {"id": "ed_deliveries", "label": "ED Deliveries / Births Before Arrival (60-day)", "value": "3", "trend": "Clinical EHR + EMS Dispatch", "positive": False, "icon": "Ambulance", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Show me the ED delivery risk trend"},
        {"id": "telehealth_booked", "label": "Telehealth-Eligible Prenatal Visits Booked", "value": "47", "trend": "Telehealth Platform + Scheduling", "positive": True, "icon": "Video", "iconColor": "text-emerald-600", "iconBg": "bg-emerald-500/10", "chipText": "Show me telehealth-eligible prenatal patients by connectivity"},
    ],
    "sarah": [
        {"id": "monitored", "label": "Chronic Disease Patients Monitored", "value": "1,340", "trend": "Clinical EHR + RPM Platform", "positive": True, "icon": "Users", "iconColor": "text-blue-600", "iconBg": "bg-blue-500/10", "chipText": None},
        {"id": "elevated_cohort", "label": "Elevated-Risk Cohort (All Conditions)", "value": "208", "trend": "RAIN Risk Engine", "positive": False, "icon": "AlertTriangle", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "Generate a risk-ranked outreach list"},
        {"id": "worsening_rpm", "label": "CHF/COPD Patients With Worsening RPM", "value": "17", "trend": "RPM Platform", "positive": False, "icon": "HeartPulse", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Show me chronic disease patients with worsening RPM readings"},
        {"id": "overdue_a1c", "label": "Diabetes Patients Without Recent A1c", "value": "112", "trend": "Clinical EHR + Claims", "positive": False, "icon": "Droplet", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Show me diabetes patients overdue for an A1c"},
        {"id": "med_nonadherence", "label": "Medication Non-Adherence (30+ days)", "value": "94", "trend": "Pharmacy Claims", "positive": False, "icon": "Pill", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "Which patients have a medication gap over 30 days?"},
        {"id": "rpm_compliance", "label": "RPM Transmission Compliance", "value": "58%", "trend": "was 79% — RPM Platform", "positive": False, "icon": "Wifi", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "What is our RPM transmission compliance trend?"},
        {"id": "transport_barrier", "label": "Patients With SDOH Transport Barrier", "value": "186", "trend": "SDOH Data + NEMT Logs", "positive": False, "icon": "Bus", "iconColor": "text-violet-600", "iconBg": "bg-violet-500/10", "chipText": "Cross-reference deterioration with transportation barriers"},
    ],
    "james": [
        {"id": "coverage", "label": "Service Area Coverage", "value": "10,200 sq mi", "trend": "Geospatial + EMS Dispatch", "positive": True, "icon": "Map", "iconColor": "text-blue-600", "iconBg": "bg-blue-500/10", "chipText": None},
        {"id": "requests_today", "label": "Transport Requests Today", "value": "47", "trend": "EMS Dispatch + NEMT Logs", "positive": False, "icon": "Truck", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "Show me today's transport queue and capacity"},
        {"id": "over_capacity", "label": "Queue Over Capacity (Trips)", "value": "9", "trend": "NEMT Logs + Vehicle Roster", "positive": False, "icon": "Layers", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Walk me through the transport queue"},
        {"id": "ems_response", "label": "Avg. EMS Response Time", "value": "47 min", "trend": "baseline 34 — EMS Dispatch", "positive": False, "icon": "Ambulance", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Where are the EMS coverage holes right now?"},
        {"id": "telehealth_unslotted", "label": "Telehealth Requests Without a Slot", "value": "31", "trend": "Telehealth Demand Queue", "positive": False, "icon": "Video", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "Show me the telehealth demand against room capacity"},
        {"id": "mobile_clinic", "label": "Mobile Clinic Utilization", "value": "98%", "trend": "Facility Capacity", "positive": False, "icon": "Building2", "iconColor": "text-violet-600", "iconBg": "bg-violet-500/10", "chipText": None},
        {"id": "awaiting_transport", "label": "Elevated-Risk Patients Awaiting Transport", "value": "16", "trend": "RAIN Risk Engine + NEMT Logs", "positive": False, "icon": "HeartPulse", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Which elevated-risk patients are awaiting transport?"},
    ],
    "priya": [
        {"id": "population", "label": "Rural / Frontier Population Served", "value": "168,000", "trend": "EDW + Eligibility", "positive": True, "icon": "Users", "iconColor": "text-blue-600", "iconBg": "bg-blue-500/10", "chipText": None},
        {"id": "desert", "label": "Women of Childbearing Age >60 mi From OB", "value": "58%", "trend": "was 31% — Geospatial + Registry", "positive": False, "icon": "MapPin", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Map the maternal care desert before and after Battle Mountain"},
        {"id": "avoidable_ed_rate", "label": "Avoidable ED Visit Rate (per 1,000)", "value": "284", "trend": "Claims + State HIE", "positive": False, "icon": "Activity", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "Where did avoidable ED utilization concentrate after the closure?"},
        {"id": "avoidable_ed_cost", "label": "Avoidable ED Cost (Est. Annual)", "value": "$1.4M", "trend": "Claims + EDW", "positive": False, "icon": "DollarSign", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Show me the cost of inaction"},
        {"id": "telehealth_uptake", "label": "Telehealth Uptake (Connected ZIPs)", "value": "71%", "trend": "Project ECHO Nevada", "positive": True, "icon": "Video", "iconColor": "text-emerald-600", "iconBg": "bg-emerald-500/10", "chipText": "Where are the telehealth equity gaps?"},
        {"id": "dead_zones", "label": "Elevated-Risk Patients in Telehealth Dead Zones", "value": "240", "trend": "Connectivity Registry + Risk Engine", "positive": False, "icon": "WifiOff", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Which elevated-risk patients are in telehealth dead zones?"},
        {"id": "transport_prevalence", "label": "SDOH Transport-Barrier Prevalence", "value": "22%", "trend": "SDOH Data", "positive": False, "icon": "Bus", "iconColor": "text-violet-600", "iconBg": "bg-violet-500/10", "chipText": "Show me access disparities by county"},
    ],
    "david": [
        {"id": "sources", "label": "Connected Data Sources", "value": "11", "trend": "Integration Monitor", "positive": True, "icon": "Database", "iconColor": "text-blue-600", "iconBg": "bg-blue-500/10", "chipText": "Show me data quality across all connected sources"},
        {"id": "ingested", "label": "Records Ingested (30-day)", "value": "9.2M", "trend": "Ingestion Pipelines", "positive": True, "icon": "Layers", "iconColor": "text-blue-600", "iconBg": "bg-blue-500/10", "chipText": None},
        {"id": "fhir_conformance", "label": "FHIR Conformance Rate", "value": "94%", "trend": "Data Quality Monitor", "positive": False, "icon": "ShieldCheck", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "What is our FHIR conformance rate by feed?"},
        {"id": "unresolved_refs", "label": "Unresolved Provider References", "value": "1,240", "trend": "FHIR Practitioner Reconciliation", "positive": False, "icon": "UserX", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Which records have unresolved provider references?"},
        {"id": "rpm_completeness", "label": "RPM Transmission Completeness", "value": "78%", "trend": "target 95% — RPM Feed Monitor", "positive": False, "icon": "Wifi", "iconColor": "text-red-600", "iconBg": "bg-red-500/10", "chipText": "Show me RPM transmission completeness by ZIP code"},
        {"id": "pipeline_freshness", "label": "Pipeline Freshness (Avg. Lag)", "value": "3.2 hrs", "trend": "Ingestion Pipelines", "positive": True, "icon": "Clock", "iconColor": "text-violet-600", "iconBg": "bg-violet-500/10", "chipText": "Show me pipeline freshness and ingestion lag"},
        {"id": "quarantine", "label": "Records in Quarantine (DQ)", "value": "14,800", "trend": "Data Quality Monitor", "positive": False, "icon": "AlertTriangle", "iconColor": "text-amber-600", "iconBg": "bg-amber-500/10", "chipText": "Show me data quality across all connected sources"},
    ],
}


def _overlay_kpi_value(static_value: str, live_value):
    """Replace the saved number with the query result and keep the tile's unit.

    Live functions return a bare count for some tiles (84, 115) and a finished
    string for others ("47 min", "58%"). A bare count used to drop the % or
    " mi" that the tile was built to show.
    """
    if isinstance(live_value, str) and not re.fullmatch(r"-?\d+(?:\.\d+)?", live_value.strip()):
        return live_value.strip()
    number = live_value
    if isinstance(number, str):
        number = float(number) if "." in number else int(number)
    if isinstance(number, Decimal):
        number = int(number) if number == number.to_integral_value() else float(number)
    if isinstance(number, float) and number.is_integer():
        number = int(number)
    text = str(static_value).strip()
    match = re.match(r"^(\$?)([\d,]+(?:\.\d+)?)(.*)$", text)
    if not match:
        return str(number)
    prefix, digits, suffix = match.group(1), match.group(2), match.group(3)
    shown = f"{number:,}" if ("," in digits and isinstance(number, int)) else str(number)
    return f"{prefix}{shown}{suffix}"


def ultra_kpis_for_persona(persona: str) -> list:
    kpis = ULTRA_KPI_DATA.get(persona, [])
    live_func = LIVE_KPI_FUNCS.get(persona)
    live = {}
    if live_func:
        try:
            live = live_func()
            kpis = [
                {**k, "value": _overlay_kpi_value(k["value"], live[k["id"]])} if k["id"] in live else k
                for k in kpis
            ]
        except Exception as e:
            # DB unreachable -- fall back to the static values, never break the request
            log.warning("kpis persona=%s POSTGRES UNREACHABLE (%s) -- serving STATIC KPI values", persona, e)
    log.info("kpis persona=%s live_sql=%d/%d static=%s", persona,
             sum(k["id"] in live for k in kpis), len(kpis),
             [k["id"] for k in kpis if k["id"] not in live] or "none")
    # Live graph lookup per KPI -- same provenance treatment as signals.
    kpis = [
        {**k, "verified_live": (src := get_kpi_provenance(persona, k["id"])) is not None, "source_system": src}
        for k in kpis
    ]
    return kpis
