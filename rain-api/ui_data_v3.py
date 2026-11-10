"""RAIN v0.3 UI data API: every value the frontend shows, served from Postgres.

GET /api/v3/ui/data?clientId=rain returns the whole UI data set in one response:

  sections.contracts     the six persona contracts (signals, KPIs, steps, queries, viz, hand-offs)
  sections.constants     master numbers (contract, gap, measures, sites, counties, ...)
  sections.records       row-level records (campaign members, slots, bookings, reminders)
  sections.governance    subgroup check, model features, top-300 swaps, drive-time points
  sections.geo           map geometry
  sections.sources       the public / synthetic / engine source list
  sections.capabilities  capability callouts and diagrams
  sections.datasets      chart and table datasets referenced by the contracts

Stored in rain_v3.ui_v3.dataset (loaded by deploy/scripts/load_ui_data.py). On every request the
county public fields (hypertension, diabetes, SVI, primary care HPSA) and the record counts of the
loaded public sources are replaced with live values from rain_v3.public_data.

Proof headers (exposed to the browser): X-RAIN-Source, X-RAIN-Request-Id, X-RAIN-Server,
X-RAIN-Data-Source, X-RAIN-Data-Sha256 (SHA-256 of the exact response body), Server-Timing.
"""
import hashlib
import json
import logging
import os
import socket
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import psycopg2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

router = APIRouter(tags=["ui-data-v3"])
log = logging.getLogger("rain.api.ui")

DATA_SOURCE = "postgres://rain_v3/ui_v3.dataset + public_data (live)"
COUNTY_FIPS = {"elko": 32007, "humboldt": 32013, "lander": 32015,
               "pershing": 32027, "whitePine": 32033, "churchill": 32001}

_COUNTY_SQL = """
WITH c(id, fips) AS (SELECT * FROM unnest(%s::text[], %s::bigint[]))
SELECT c.id, s.county, s.e_totpop,
       (SELECT p.data_value FROM public_data.cdc_places p
         WHERE p.locationid = c.fips AND p.measureid = 'BPHIGH' AND p.data_value_type = 'Crude prevalence'
         ORDER BY p.year DESC LIMIT 1)                                                     AS htn,
       (SELECT p.year FROM public_data.cdc_places p
         WHERE p.locationid = c.fips AND p.measureid = 'BPHIGH' AND p.data_value_type = 'Crude prevalence'
         ORDER BY p.year DESC LIMIT 1)                                                     AS htn_year,
       (SELECT p.data_value FROM public_data.cdc_places p
         WHERE p.locationid = c.fips AND p.measureid = 'DIABETES' AND p.data_value_type = 'Crude prevalence'
         ORDER BY p.year DESC LIMIT 1)                                                     AS dm,
       s.rpl_themes                                                                        AS svi,
       (SELECT bool_or(h.hpsa_component_type_description = 'Single County')
          FROM public_data.hpsa_primary_care h
         WHERE h.common_county_name = s.county || ', NV' AND h.hpsa_status = 'Designated'
           AND h.designation_type ILIKE '%%Geographic%%')                                   AS whole_county
FROM c JOIN public_data.svi_county s ON s.fips = c.fips
"""

_SOURCE_COUNTS_SQL = """
SELECT 'rain-places', 'public_data.cdc_places', count(*) FROM public_data.cdc_places WHERE stateabbr = 'NV'
UNION ALL SELECT 'rain-svi', 'public_data.svi_county', count(*) FROM public_data.svi_county WHERE st_abbr = 'NV'
UNION ALL SELECT 'rain-hpsa', 'public_data.hpsa_primary_care + hpsa_mental_health',
       (SELECT count(*) FROM public_data.hpsa_primary_care WHERE primary_state_abbreviation = 'NV')
     + (SELECT count(*) FROM public_data.hpsa_mental_health WHERE primary_state_abbreviation = 'NV')
UNION ALL SELECT 'rain-rucc', 'public_data.rucc_county', count(DISTINCT fips) FROM public_data.rucc_county WHERE state = 'NV'
UNION ALL SELECT 'rain-zcta', 'public_data.zcta_centroids', count(*) FROM public_data.zcta_centroids
       WHERE geoid BETWEEN '88900' AND '89899'
UNION ALL SELECT 'rain-hrsaSites', 'public_data.health_center_sites', count(*) FROM public_data.health_center_sites
       WHERE site_state_abbreviation = 'NV'
UNION ALL SELECT 'rain-nppes', 'public_data.providers', count(*) FROM public_data.providers WHERE state = 'NV'
"""


def _conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DB_V3", "rain_v3"), user=os.getenv("PG_USER", "rain_app"),
        password=os.getenv("PG_PASSWORD", "rain_dev_pw"))


def _overlay_counties(cur, counties: list) -> list:
    """Replace the county public fields with live public_data values; return what changed."""
    ids = [c["id"] for c in counties if c.get("id") in COUNTY_FIPS]
    cur.execute(_COUNTY_SQL, (ids, [COUNTY_FIPS[i] for i in ids]))
    live = {r[0]: r for r in cur.fetchall()}
    changes = []
    for c in counties:
        row = live.get(c.get("id"))
        if not row:
            continue
        _, county, pop, htn, htn_year, dm, svi, whole_county = row
        new = {
            "htnPct": round(htn, 1) if htn is not None else c["htnPct"],
            "diabetesPct": round(dm, 1) if dm is not None else c["diabetesPct"],
            "svi": round(svi, 2) if svi is not None else c["svi"],
            # HRSA's own designation geography: a "Single County" geographic HPSA covers the whole county.
            "hpsa": "Whole county" if whole_county else "Part of county",
        }
        src = {"htnPct": f"CDC PLACES {htn_year} BPHIGH crude prevalence (public_data.cdc_places)",
               "diabetesPct": f"CDC PLACES {htn_year} DIABETES crude prevalence (public_data.cdc_places)",
               "svi": "CDC/ATSDR SVI 2022 RPL_THEMES (public_data.svi_county)",
               "hpsa": "HRSA primary care HPSA, designated geographic, component type (public_data.hpsa_primary_care)"}
        for field, value in new.items():
            changes.append({"county": c["name"], "field": field, "value": value,
                            "previous": c.get(field), "source": src[field]})
            c[field] = value
        c["publicSources"] = src
    return changes


def _overlay_sources(cur, public_sources: list) -> list:
    cur.execute(_SOURCE_COUNTS_SQL)
    counts = {sid: (table, n) for sid, table, n in cur.fetchall()}
    changes = []
    for s in public_sources:
        if s.get("id") in counts:
            table, n = counts[s["id"]]
            changes.append({"source": s["name"], "field": "recordCount", "value": n, "previous": s.get("recordCount"),
                            "table": table})
            s.update(recordCount=n, live=True, table=table, scope="Nevada rows")
    return changes


def load_sections(client_id: str = "rain") -> tuple[dict, list, int, datetime]:
    """Every section of the UI data from Postgres, with the live public overlay applied.

    Returns (sections, overlay changes, row count, seed loaded_at). The chat (chat_v3) builds its
    answers from the same call, so the conversation and the workbenches read one source.
    """
    sections: dict = defaultdict(dict)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT section, key, payload, loaded_at FROM ui_v3.dataset WHERE client_id = %s", (client_id,))
        rows = cur.fetchall()
        if not rows:
            raise HTTPException(404, f'No UI data for client "{client_id}": run deploy/scripts/load_ui_data.py')
        for section, key, payload, _ in rows:
            sections[section][key] = payload
        overlay = _overlay_counties(cur, sections["constants"].get("COUNTIES", []))
        overlay += _overlay_sources(cur, sections["sources"].get("PUBLIC_SOURCES", []))
    return dict(sections), overlay, len(rows), max(r[3] for r in rows)


@router.get("/data")
def ui_data(clientId: str, request: Request):
    t0 = time.perf_counter()
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]
    sections, overlay, row_count, loaded_at = load_sections(clientId)
    rows = range(row_count)
    db_ms = (time.perf_counter() - t0) * 1000

    records = sections.get("records", {})
    meta = {
        "source": "rain-api",
        "server": socket.gethostname(),
        "dataSource": DATA_SOURCE,
        "database": {"name": "rain_v3", "table": "ui_v3.dataset", "rows": len(rows),
                     "seedLoadedAt": loaded_at.isoformat()},
        "publicOverlay": overlay,
        "counts": {name: len(sec) for name, sec in sections.items()},
        "records": {name: len(v) for name, v in records.items() if isinstance(v, list)},
        "requestId": request_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "dbMs": round(db_ms, 1),
    }
    body = json.dumps({"meta": meta, "sections": sections}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    log.info("ui data client=%s: %d datasets from %s, %d live public values, %d bytes in %.0f ms req=%s",
             clientId, len(rows), "rain_v3.ui_v3.dataset", len(overlay), len(body), db_ms, request_id)
    return Response(content=body, media_type="application/json", headers={
        "X-RAIN-Request-Id": request_id,
        "X-RAIN-Server": meta["server"],
        "X-RAIN-Data-Source": DATA_SOURCE,
        "X-RAIN-Data-Sha256": hashlib.sha256(body).hexdigest(),
        "Server-Timing": f"db;dur={db_ms:.1f}",
        "Cache-Control": "no-store",
    })
