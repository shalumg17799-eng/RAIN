"""Publish the RAIN v0.4 knowledge graph (KAG) as the app is NOW, as one release in the rain4 Neo4j.

Everything is read at run time, so a re-run picks up new personas, pack queries, tables, metric groups,
datasets, data sources and write-back flows without editing this file:

  PRD v0.4 seed     knowledge-gathering/seeds/rain_v4_prd_seed.py (build_records): organizations, counties,
                    sites, contract, checkpoint, quality gate, measures, segments, use cases, pages, workbenches,
                    capabilities, the 7 personas (role, data scope, origin, PRD questions), signals, guided steps
                    and success metrics
  ontology          artifacts/rain-v4-kag-records.json (the factory's classes, properties, class relations and
                    upper-ontology alignment; optional) + platform/ontology/upper-ontology.v1.json
  Postgres rain_v4  pg_catalog: every table of synthetic, public_data and ui_v4 with columns, types, primary and
                    foreign keys and exact row counts
  planned DDL       doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql: planned tables and their source feed; the
                    extension tables and columns are what Postgres has beyond it
  generator         scripts/e2e/synth/gen_load.py: the synthetic reference tables derived from public_data
  backend           rain-api: persona_queries_v4.PERSONA_IDS, ui_data_v4.load_sections (the computed context the UI
                    gets: constants groups, records, governance, datasets, data sources with live status, persona
                    contracts), metrics_v4.py (what each group computes from), flow_v4.py (write-back flows)
  query pack        doc/queries/rain_v4_persona_queries.sql (each query -> its persona and the tables it reads)
  frontend          contract.ts WORKBENCHES, client.manifest.ts (persona switcher), workbench components (which
                    metric groups they show and which flows they trigger)
  public manifest   .data/public/MANIFEST.md (optional): URL, release and the reason a source is blocked

Publishing is idempotent: every node and relationship is MERGEd under (key, release) and stamped with this run's
id; what an earlier run of the same release wrote and this run did not is removed. Then every other release of
enterprise `rain` (rain-v4.0.0) and the unreleased v1/v2 seed graph (neo4j-seed's rain-neo4j-graph/*.cypher:
Concept, KPI, Signal, SourceSystem... and the shared Platform upper-ontology nodes) are deleted, so the database
holds one coherent release and nothing older. Validation (doc/queries/RAIN_v4_kag_check.md) and the Neo4j
Browser pack (doc/queries/rain_v4_persona_graph.cypher) are rewritten at the end.

Run it on the rain4 network with the repo mounted at /app (the backend image has the drivers):

    MSYS_NO_PATHCONV=1 docker run --rm --network rain4_default -v "C:/Users/pa613/RAIN4.0-DIF_BT_integration:/app" \
        -w /app --entrypoint python rain4-backend scripts/e2e/kag_v4_refresh.py [--dry-run] [--keep-legacy]

Environment: NEO4J_URI (bolt://neo4j:7687), NEO4J_USER/NEO4J_PASSWORD (neo4j/password), NEO4J_DATABASE (neo4j),
PG_HOST (postgres), PG_PORT (5432), PG_DB_V4 (rain_v4), PG_ADMIN_USER/PG_ADMIN_PASSWORD (postgres/root, for the
catalog and row counts), PG_USER/PG_PASSWORD (rain_app, as the API reads), RAIN_KAG_RELEASE (rain-v4.1.0).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "rain-api"
FE = ROOT / "frontend/rain-app/src"

RELEASE = os.getenv("RAIN_KAG_RELEASE", "rain-v4.1.0")
ENTERPRISE = "rain"
EXIT_CHECKS_FAILED = 3        # published, but a release check failed (an exception exits 1)
SCHEMAS = ("synthetic", "public_data", "ui_v4")

PATHS = {
    "seed": ROOT / "knowledge-gathering/seeds/rain_v4_prd_seed.py",
    "factory": ROOT / "artifacts/rain-v4-kag-records.json",
    "upper": ROOT / "platform/ontology/upper-ontology.v1.json",
    "ddl": ROOT / "doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql",
    "gen_load": ROOT / "scripts/e2e/synth/gen_load.py",
    "pack": ROOT / "doc/queries/rain_v4_persona_queries.sql",
    "queries_api": API / "persona_queries_v4.py",
    "metrics": API / "metrics_v4.py",
    "metrics_personas": API / "metrics_personas_v4.py",
    "flow": API / "flow_v4.py",
    "templates": API / "seed/rain_v4_ui_templates.json",
    "loader": ROOT / "deploy/scripts/load_public_data.py",
    "manifest": ROOT / ".data/public/MANIFEST.md",
    "contract_ts": FE / "data/rain/_shared/contract.ts",
    "records_ts": FE / "data/rain/_shared/records.ts",
    "store_ts": FE / "components/rain/shell/store.ts",
    "client_manifest": FE / "markets/sled/clients/rain/client.manifest.ts",
    "personas_dir": FE / "markets/sled/clients/rain/personas",
    "components": FE / "components/rain",
}
OUT_CHECK = ROOT / "doc/queries/RAIN_v4_kag_check.md"
OUT_PACK = ROOT / "doc/queries/rain_v4_persona_graph.cypher"
OUT_JSON = ROOT / "artifacts/rain-v4-validation/kag_refresh.json"

# The labels of the unreleased v1/v2 graph that deploy/scripts/seed_neo4j.py loads from rain-neo4j-graph/*.cypher,
# plus the shared Platform upper-ontology nodes the v4.0.0 factory release pointed at. Unreleased nodes with any
# other label are never deleted unless --purge-unknown is given.
LEGACY_LABELS = {"KPI", "SourceField", "CachedQuestion", "SourceSystem", "Signal", "Concept", "Persona", "Platform",
                 "CascadeBranch", "CountyRegion", "CoverageGap", "Constant", "ClosureEvent"}

# ─── curated knowledge (what the code does not state in a parseable form) ──────────────────────────────────
# PRD seed persona key -> (UI contract key, UI persona id). The backend query id comes from PERSONA_IDS and the pack.
PERSONAS = [("GregoryHaskins", "ceo", "rain_ceo"), ("NaomiCastellanos", "cmo", "rain_cmo"),
            ("RajMalhotra", "cio", "rain_cio"), ("LaurenPike", "state", "rain_state"),
            ("TeresaLopez", "chw", "rain_chw"), ("BrandonKee", "access", "rain_access"),
            ("LindaGarcia", "linda", "rain_linda")]
BACKEND_HINT = {"LindaGarcia": "linda_garcia"}
PATIENT_VIEW = {"LindaGarcia": "/patient"}
PERSONA_GROUPS = {"LindaGarcia": ["LINDA", "PATIENTS"]}
# metrics_personas_v4.py: datasets lg_* (Linda)
DATASET_PERSONA = {"lg": "LindaGarcia"}

# Constants groups of the computed context -> the tables metrics_v4.py reads for them (synthetic unless qualified),
# from reading _Calc.frame/reference/cost/imaging/quality/campaign/scheduling/model/geography/assemble.
# A group that is not listed here is mapped by parsing the function that builds it (mapping="parsed").
GROUP_TABLES = {
    "CONTRACT": ["contract_benchmark", "data_source", "patient", "impactability_score", "claim", "quality_measure",
                 "quality_measure_result"],
    "GAP": ["claim", "claim_line", "patient", "utilization_benchmark", "condition", "hcc_reference",
            "impactability_score", "low_value_finding", "low_value_measure", "contract_benchmark"],
    "SEGMENTS": ["patient", "impactability_score", "claim"],
    "COHORT": ["patient", "impactability_score", "assumption"],
    "CODING": ["condition", "hcc_reference", "impactability_score", "patient", "contract_benchmark", "claim"],
    "LOW_VALUE": ["low_value_finding", "low_value_measure", "claim_line", "claim", "patient", "provider", "encounter"],
    "ED": ["claim", "patient", "utilization_benchmark"],
    "MEASURES": ["quality_measure", "quality_measure_result", "patient", "campaign_member", "ehr_order", "assumption"],
    "BP": ["quality_measure_result", "campaign_member", "assumption"],
    "FIT": ["campaign_member", "quality_measure_result", "assumption"],
    "MODEL": ["model_card", "model_feature", "impactability_score", "patient", "adt_event", "data_source",
              "sdoh_screening", "broadband_coverage", "match_review", "encounter", "condition", "quality_measure_result"],
    "STATE": ["grantee", "clinic_site", "attributed_member", "patient", "claim", "low_value_finding",
              "broadband_coverage", "zip_place", "assumption", "public_data.hpsa_primary_care"],
    "CARE": ["outreach_task", "provider"],
    "SITES": ["clinic_site", "provider", "patient", "claim", "claim_line", "low_value_finding"],
    "COUNTIES": ["public_data.county_boundaries", "public_data.cdc_places", "public_data.svi_county",
                 "public_data.hpsa_primary_care", "public_data.acs_county", "public_data.county_health_rankings",
                 "patient", "encounter", "claim", "claim_line", "condition", "quality_measure_result", "low_value_finding"],
    "NETWORKS": ["grantee", "clinic_site", "patient", "claim", "quality_measure_result", "low_value_finding"],
    "PMPM_TREND": ["claim", "patient", "contract_benchmark"],
    "WINNEMUCCA_TREND": ["claim_line", "claim", "low_value_finding", "provider", "encounter"],
    "LOCUMS": ["provider", "claim_line", "claim", "low_value_finding"],
    "LV_MEASURES": ["low_value_finding", "low_value_measure", "claim_line", "claim", "patient"],
    "OPTIONS": ["assumption", "patient", "broadband_coverage", "attributed_member", "low_value_finding"],
    "LOW_BB_PLACES": ["broadband_coverage", "zip_place"],
    "FRESHNESS": ["data_source"],
    "SITE_SOCIAL": ["sdoh_screening", "patient", "clinic_site"],
    "TERESA_SITES": ["outreach_task", "patient"],
    "ORG": ["grantee", "contract_benchmark"],
    "SCOPES": ["patient"],
    "LINDA": ["patient", "appointment", "slot", "schedule", "reminder_message", "contact_preference", "rpm_reading",
              "travel_time"],
    "campaignMembers": ["campaign_member", "risk_score", "standing_order", "observation", "remote_bp_reading",
                        "encounter", "claim", "care_gap", "condition", "sdoh_screening", "contact_preference",
                        "appointment", "slot", "outreach_task", "patient", "travel_time", "impactability_score"],
    "slots": ["slot", "schedule", "appointment", "provider", "travel_time"],
    "pendingBookings": ["outreach_task", "eligibility_check", "patient"],
    "reminders": ["appointment", "slot", "schedule", "reminder_message", "contact_preference", "provider", "patient"],
    "SUBGROUP": ["impactability_score", "patient", "condition", "zip_place"],
    "swaps": ["impactability_score", "model_card", "quality_measure_result", "condition", "patient"],
    "FEATURES": ["model_feature", "model_card"],
    "accessPoints": ["patient", "encounter", "travel_time"],
}
CONFIG_GROUPS = {"ILLUSTRATIVE", "PERSONAS"}          # configuration, not data
GROUP_FROM_GROUPS = {"BP": ["campaignMembers"], "CARE": ["campaignMembers", "reminders", "pendingBookings"],
                     "TASKS": ["PATIENTS"],
                     "TERESA_SITES": ["campaignMembers"]}
GROUP_TEXT = {
    "CONTRACT": "Q3 contract checkpoint: attributed members, actual vs expected PMPM, days left, quality gate",
    "GAP": "The PMPM gap split into coding, excess avoidable ED, low-value care and other",
    "SEGMENTS": "Impactability segments with member and spend shares", "COHORT": "Top-ranked outreach cohort, cost avoided",
    "CODING": "Coding recapture: high-need members with unrecaptured chronic conditions", "LOW_VALUE": "Low-value care spend and the Winnemucca imaging cluster",
    "ED": "Avoidable ED visits per 1,000 against the benchmark", "MEASURES": "The five quality gate measures: current, projected, target",
    "BP": "BP control campaign (CMS165)", "FIT": "FIT kit campaign gain (CMS130)", "MODEL": "Impactability model card and data health",
    "STATE": "State program view across networks and counties", "CARE": "Care team workload: calls, bookings, reminders",
    "SITES": "Network sites: members, PMPM, imaging rate, low-value spend", "COUNTIES": "County view with public data (PLACES, SVI, HPSA, ACS, CHR)",
    "NETWORKS": "The four networks in the RHTP program", "LINDA": "Linda Garcia's own visit, reminders and readings",
    "TASKS": "The patient's task briefing, built from her own record",
    "PATIENTS": "The patient persona's own record (Linda Garcia): next visit, reminders, readings, checks, coverage",
    "SCOPES": "Each persona's data scope (the patient: her own record only)",
}
# Data sources the UI lists without a table string -> the tables they feed (synthetic unless qualified).
SOURCE_TABLES = {"rain-benchmark": ["contract_benchmark"], "rain-library": ["low_value_measure", "low_value_finding"],
                 "rain-adt": ["adt_event"], "rain-costModel": ["claim", "claim_line", "contract_benchmark"],
                 "rain-impactability": ["impactability_score", "model_card", "model_feature"],
                 "rain-ecqmEngine": ["quality_measure", "quality_measure_result", "care_gap"],
                 "rain-synthea": ["patient", "encounter", "condition", "medication", "observation", "ehr_order"]}
# public_data tables no UI source names -> the UI source they belong to
PUBLIC_TABLE_SOURCE = {"zcta_county": "rain-zcta", "acs_variables": "rain-acs", "uds_state_national_cqm": "rain-uds"}
# planned-DDL source feed (System) -> the UI data source that provides it
FEED_SOURCE = {"synthea": "rain-synthea", "synthea_claims": "rain-claims", "synthetic_mco_eligibility": "rain-mco",
               "mock_270_271": "rain-ops", "contract_benchmark": "rain-benchmark", "cms_ecqm": "rain-ecqm",
               "lvc_library": "rain-library", "synthetic_calendars": "rain-ops", "synthetic_sms": "rain-ops",
               "synthetic_rpm": "rain-rpm", "simulated_rpm": "rain-rpm", "nppes": "rain-nppes", "hrsa_sites": "rain-hrsaSites",
               "cdc_places": "rain-places", "hrsa_hpsa": "rain-hpsa", "usda_rucc": "rain-rucc", "fcc_nbm": "rain-fcc",
               "derived_osrm": "rain-osm", "cms_geo_variation": "rain-geovar", "hie_adt": "rain-adt", "cms_pos": "rain-cmsPos",
               "hrsa_uds": "rain-uds", "census_acs": "rain-acs", "census_zcta": "rain-zcta", "cdc_svi": "rain-svi"}
EXTENSION_FEED = "rain_v4_synthetic_extension"
# Blocked public sources the UI does not list as cards (MANIFEST.md "How to unblock" has the detail).
BLOCKED_EXTRA = [
    ("vsac", "VSAC value sets (eCQM value-set expansions)", "NLM", "Needs a UMLS Metathesaurus licence (NLM UTS account)",
     "eCQM value sets"),
    ("cms-pos-file", "CMS Provider of Services file (official CMS download)", "CMS",
     "data.cms.gov refuses scripted downloads (HTTP 403); the HRSA republication is loaded instead", "CMS Geographic Variation, CMS POS file"),
    ("forhp-data-files", "HRSA FORHP data files (eligible ZIP codes, county and tract workbook)", "HRSA FORHP",
     "www.hrsa.gov refuses scripted downloads (HTTP 403); needs a browser download", "FORHP eligible ZIP codes"),
]


# ─── small helpers ──────────────────────────────────────────────────────────────────────────────────────────
def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.is_file() else None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def qual(t: str) -> str:
    return t if "." in t else f"synthetic.{t}"


def tkey(t: str) -> str:
    return f"table:{qual(t)}"


def pascal(name: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in name.split("_"))


def safe(v):
    """A Neo4j-storable property value: primitives and lists of primitives; anything else becomes JSON."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)) and all(x is None or isinstance(x, (bool, int, float, str)) for x in v):
        return [x for x in v if x is not None]
    return json.dumps(v, ensure_ascii=False, default=str, sort_keys=True)


def schema_tables(text: str) -> set[str]:
    """Every schema-qualified table a piece of SQL or Python names (synthetic.x, public_data.x, ui_v4.x)."""
    return {f"{s}.{t}" for s, t in re.findall(r"\b(synthetic|public_data|ui_v4)\.([a-z_][a-z0-9_]*)\b", text)}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Graph:
    """The release being built: nodes by key, relationships by (from, type, to)."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.rels: dict[tuple, dict] = {}

    def node(self, key: str, label: str, *extra_labels: str, **props) -> dict:
        n = self.nodes.get(key)
        if n is None:
            n = self.nodes[key] = {"key": key, "labels": [label, *extra_labels], "props": {}}
        for k, v in props.items():
            if v is not None:
                n["props"][k] = v
        return n

    def rel(self, frm: str, typ: str, to: str, **props):
        r = self.rels.setdefault((frm, typ, to), {})
        r.update({k: v for k, v in props.items() if v is not None})

    def drop_rels(self, pred):
        for k in [k for k in self.rels if pred(*k)]:
            del self.rels[k]


# ─── inputs ─────────────────────────────────────────────────────────────────────────────────────────────────
def pg_connect(admin: bool):
    import psycopg2
    user = os.getenv("PG_ADMIN_USER", "postgres") if admin else os.getenv("PG_USER", "rain_app")
    pw = os.getenv("PG_ADMIN_PASSWORD", "root") if admin else os.getenv("PG_PASSWORD", "rain_dev_pw")
    conn = psycopg2.connect(host=os.getenv("PG_HOST", "postgres"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user=user, password=pw)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def pg_inventory() -> dict:
    """Tables, columns (with types), primary keys, foreign keys and exact row counts of the three schemas."""
    from psycopg2 import sql
    conn = pg_connect(admin=True)
    cur = conn.cursor()
    cur.execute("""SELECT n.nspname, c.relname, obj_description(c.oid, 'pg_class') FROM pg_class c
                   JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p') ORDER BY 1, 2""", (list(SCHEMAS),))
    tables = {f"{s}.{t}": {"schema": s, "name": t, "comment": cmt, "columns": [], "pk": []} for s, t, cmt in cur.fetchall()}
    cur.execute("""SELECT n.nspname, c.relname, a.attname, a.attnum, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull,
                          col_description(c.oid, a.attnum)
                   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_attribute a ON a.attrelid = c.oid
                   WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
                   ORDER BY 1, 2, 4""", (list(SCHEMAS),))
    for s, t, col, pos, typ, nullable, cmt in cur.fetchall():
        tables[f"{s}.{t}"]["columns"].append({"name": col, "position": pos, "data_type": typ, "nullable": nullable,
                                               "comment": cmt})
    cur.execute("""SELECT n.nspname, c.relname, con.contype, con.conname,
                          ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(attnum, i)
                                JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum ORDER BY k.i),
                          n2.nspname, c2.relname,
                          ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(attnum, i)
                                JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum ORDER BY k.i)
                   FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace
                   LEFT JOIN pg_class c2 ON c2.oid = con.confrelid LEFT JOIN pg_namespace n2 ON n2.oid = c2.relnamespace
                   WHERE n.nspname = ANY(%s) AND con.contype IN ('p', 'f') ORDER BY 1, 2, 4""", (list(SCHEMAS),))
    fks = []
    for s, t, kind, name, cols, s2, t2, cols2 in cur.fetchall():
        if kind == "p":
            tables[f"{s}.{t}"]["pk"] = list(cols)
        else:
            fks.append({"name": name, "table": f"{s}.{t}", "columns": list(cols), "ref_table": f"{s2}.{t2}",
                        "ref_columns": list(cols2)})
    for full, t in tables.items():
        cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(t["schema"]), sql.Identifier(t["name"])))
        t["row_count"] = cur.fetchone()[0]
    conn.close()
    return {"tables": tables, "fks": fks}


def ui_templates() -> tuple[dict, str]:
    """The persona contract templates the API renders (ui_v4.dataset section 'templates'; the seed file as fallback)."""
    try:
        conn = pg_connect(admin=True)
        cur = conn.cursor()
        cur.execute("SELECT key, payload FROM ui_v4.dataset WHERE client_id = 'rain' AND section = 'templates'")
        rows = dict(cur.fetchall())
        conn.close()
        if rows.get("contracts"):
            return {"contracts": rows["contracts"], "personas": rows.get("personas", {})}, "ui_v4.dataset (templates)"
    except Exception as exc:  # noqa: BLE001
        print("  templates from Postgres failed:", type(exc).__name__, exc)
    d = json.loads(read(PATHS["templates"]) or "{}")
    return {"contracts": d.get("contracts", {}), "personas": d.get("personas", {})}, str(PATHS["templates"].relative_to(ROOT))


def ui_sections() -> tuple[dict, str, object]:
    """The computed UI context exactly as GET /api/v4/ui/data builds it (imported from rain-api)."""
    os.environ.setdefault("PG_HOST", "postgres")
    sys.path.insert(0, str(API))
    try:
        import ui_data_v4  # noqa: PLC0415
        sections, _, _, _ = ui_data_v4.load_sections("rain")
        return sections, "rain-api ui_data_v4.load_sections (computed now)", ui_data_v4
    except Exception as exc:  # noqa: BLE001
        print("  ui_data_v4.load_sections failed:", type(exc).__name__, exc)
    import urllib.request
    url = os.getenv("RAIN_API", "http://backend:8000") + "/api/v4/ui/data?clientId=rain"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())["sections"], url, None


def parse_ddl() -> dict:
    out = {}
    for m in re.finditer(r"--\s*source:\s*(\w+)\s*\nCREATE TABLE (\w+) \((.*?)\n\);", read(PATHS["ddl"]), re.S):
        cols = []
        for line in m.group(3).split("\n"):
            s = line.strip().rstrip(",")
            if s and not s.startswith("--") and not re.match(r"(PRIMARY|FOREIGN)\s+KEY|UNIQUE\s*\(|CONSTRAINT\s|CHECK\s*\(", s, re.I):
                cols.append(s.split()[0])
        out[m.group(2)] = {"source": m.group(1), "columns": cols}
    return out


def parse_public_derivations() -> dict:
    """synthetic table -> the public_data tables gen_load.py derives it from."""
    m = re.search(r'PUBLIC_SQL = r"""(.*?)"""', read(PATHS["gen_load"]), re.S)
    out = defaultdict(set)
    for stmt in (m.group(1).split(";") if m else []):
        tgt = re.search(r"(?:INSERT INTO|UPDATE)\s+synthetic\.(\w+)", stmt)
        if tgt:
            srcs = {t for t in schema_tables(stmt) if t.startswith("public_data.")}
            if srcs:
                out[tgt.group(1)] |= srcs
    return {k: sorted(v) for k, v in out.items()}


def parse_pack() -> list[dict]:
    text = read(PATHS["pack"])
    out = []
    for block in re.split(r"(?m)^-- @id ", text)[1:]:
        qid, _, rest = block.partition("\n")
        meta = dict(re.findall(r"(?m)^-- @(\w+) (.*)$", rest))
        sql_text = "\n".join(line for line in rest.splitlines() if not line.startswith("-- @"))
        sql_text = sql_text.split("\n-- ####")[0].strip()
        code = "\n".join(re.sub(r"--.*$", "", line) for line in sql_text.splitlines())
        # a catalog query (information_schema ... table_schema = 'x' ... FROM x.%I) reads every table of schema x
        scans = sorted(set(re.findall(r"table_schema\s*=\s*'(\w+)'", code))) if "information_schema" in code else []
        out.append({"id": qid.strip(), "persona": (meta.get("persona") or "").strip(), "data": (meta.get("data") or "").strip(),
                    "question": (meta.get("question") or "").strip(), "sql": sql_text, "tables": sorted(schema_tables(code)),
                    "schema_scans": scans})
    return out


def backend_persona_ids() -> list[str]:
    m = re.search(r"PERSONA_IDS\s*=\s*\((.*?)\)", read(PATHS["queries_api"]), re.S)
    return re.findall(r'"(\w+)"', m.group(1)) if m else []


def parse_flows() -> list[dict]:
    text = read(PATHS["flow"])
    doc = re.search(r'^"""(.*?)"""', text, re.S)
    desc = dict(re.findall(r"(?m)^  (\w+)\s{2,}(.+)$", doc.group(1))) if doc else {}
    helpers = {}
    for m in re.finditer(r"(?m)^def (_\w+)\((.*?)(?=^def |^@router|^class |\Z)", text, re.S):
        helpers[m.group(1)] = m.group(0)
    flows = []
    for m in re.finditer(r'(?m)^@router\.(post|get)\("/(\w+)"\)\s*\ndef (\w+)\((.*?)(?=^@router|\Z)', text, re.S):
        method, name, _, body = m.group(1), m.group(2), m.group(3), m.group(0)
        for h, hbody in helpers.items():
            if h not in ("_run", "_conn", "_j") and f"{h}(" in body:
                body += hbody
        writes = {f"synthetic.{t}" for t in re.findall(r'tx\.(?:insert|update)\("(\w+)"', body)}
        writes |= {f"synthetic.{t}" for t in re.findall(r"(?:INSERT INTO|UPDATE|DELETE FROM)\s+synthetic\.(\w+)", body)}
        if method == "post" and "_run(" in body:
            writes.add("synthetic.flow_event")          # _Tx logs every action with its undo list
        reads = {f"synthetic.{t}" for t in re.findall(r"(?:FROM|JOIN)\s+synthetic\.(\w+)", body)} - {"synthetic.flow_event"}
        flows.append({"name": name, "method": method.upper(), "path": f"/api/v4/flow/{name}",
                      "description": desc.get(name), "writes": sorted(writes), "reads": sorted(reads - writes),
                      "replays_undo": name == "reset"})
    return flows


def parse_metric_code() -> tuple[dict, dict, dict]:
    """Parse rain-api/metrics_v4.py and metrics_personas_v4.py.

    Returns (group -> tables read by the function that builds it, following the functions it calls;
    dataset -> groups it is built from; group -> module). Datasets with a computed key (DS[f"{prefix}_{name}"])
    are matched by the literal (key, prefix) pairs in the same function.
    """
    funcs = {}     # (module, function) -> body, tables, calls
    for path in (PATHS["metrics"], PATHS["metrics_personas"]):
        text = read(path)
        mod = path.relative_to(ROOT).as_posix()
        for m in re.finditer(r"(?m)^(\s*)def (\w+)\((.*?)(?=^\1def |^class |^def |\Z)", text, re.S):
            body = m.group(0)
            funcs[(mod, m.group(2))] = {"body": body, "module": mod, "tables": schema_tables(body),
                                        "calls": set(re.findall(r"(?:self\.)?\b(_?[a-z]\w*)\(", body[len(m.group(2)) + 5:]))}

    def resolve(mod, name):
        return (mod, name) if (mod, name) in funcs else next((k for k in funcs if k[1] == name), None)

    def reach(key, seen=None):
        seen = seen if seen is not None else set()
        if key is None or key in seen:
            return set()
        seen.add(key)
        out = set(funcs[key]["tables"])
        for c in funcs[key]["calls"]:
            out |= reach(resolve(key[0], c), seen)
        return out

    group_tables, group_module, ds_groups, dyn_prefix = {}, {}, {}, {}
    for fkey, f in funcs.items():
        body = f["body"]
        assigned = set(re.findall(r'(?:C|REC|GOV)\["(\w+)"\]\s*=', body)) | set(re.findall(r'^\s+"([A-Z][A-Z_]+)":', body, re.M))
        for key in assigned:
            group_tables.setdefault(key, set()).update(reach(fkey))
            group_module.setdefault(key, f["module"])
        if "DS[" not in body:
            continue
        alias = {}     # local name -> the groups it was built from (transitively: left = [m for m in members ...])
        for line in body.splitlines():
            rev = re.match(r"""\s+(?:C|REC|GOV)\[['"](\w+)['"]\]\s*=\s*([A-Za-z_]\w*)\s*$""", line)   # C["NAME"] = value
            if rev:
                alias[rev.group(2)] = alias.get(rev.group(2), set()) | {rev.group(1)}
                continue
            a = re.match(r"\s+([A-Za-z_][\w, ]*?)\s*=\s*([^=].*)$", line)
            if not a:
                continue
            names = [x.strip() for x in a.group(1).split(",")]
            if not all(re.fullmatch(r"[A-Za-z_]\w*", x) for x in names) or names[0] in ("DS", "C"):
                continue
            gs = set(re.findall(r"""(?:C|REC|GOV)\[['"](\w+)['"]\]""", a.group(2)))
            for name, ngs in list(alias.items()):
                if re.search(rf"\b{re.escape(name)}\b", a.group(2)):
                    gs |= ngs
            if gs:
                for x in names:
                    alias[x] = alias.get(x, set()) | gs
        chunks = re.split(r'(?m)^\s+DS\["(\w+)"\]\s*=', body)
        for i in range(1, len(chunks), 2):
            chunk = chunks[i + 1]
            groups = set(re.findall(r"""(?:C|REC|GOV)\[['"](\w+)['"]\]""", chunk))
            for name, gs in alias.items():
                if re.search(rf"\b{re.escape(name)}\b", chunk):
                    groups |= gs
            ds_groups.setdefault(chunks[i], set()).update(groups or assigned)   # else: what this function computes
        if re.search(r'DS\[f"\{', body):
            for _, prefix in re.findall(r'\("(\w+)",\s*"(\w+)"\)', body):
                dyn_prefix[prefix] = assigned
        for prefix in re.findall(r'DS\[f"([a-z]+)_\{', body):           # DS[f"lg_{name}"]: one persona's datasets
            dyn_prefix[prefix] = assigned
    for prefix, groups in dyn_prefix.items():
        ds_groups.setdefault(f"{prefix}_*", set()).update(groups)
    return ({k: sorted(v) for k, v in group_tables.items()}, {k: sorted(v) for k, v in ds_groups.items()}, group_module)


def parse_workbenches() -> list[dict]:
    text = read(PATHS["contract_ts"])
    m = re.search(r"export const WORKBENCHES[^=]*=\s*\{(.*?)\n\};", text, re.S)
    out = []
    for line in (m.group(1).splitlines() if m else []):
        f = dict(re.findall(r"(\w+): '((?:[^'\\]|\\.)*)'", line))
        if f.get("id"):
            out.append({k: v.replace("\\'", "'") for k, v in f.items()})
    return out


def parse_switcher() -> tuple[list[str], dict]:
    """(UI persona ids in the switcher, folder -> UI persona id)."""
    text = read(PATHS["client_manifest"])
    imports = dict(re.findall(r"import \{ (\w+) \} from '\./personas/(\w+)'", text))
    arr = re.search(r"personas:\s*\[(.*?)\]", text, re.S)
    listed = re.findall(r"\b(\w+Persona)\b", arr.group(1)) if arr else []
    folder_id = {}
    for d in sorted(PATHS["personas_dir"].glob("*/index.ts")):
        mid = re.search(r"\bid:\s*'(\w+)'", read(d))
        if mid:
            folder_id[d.parent.name] = mid.group(1)
    return [folder_id[imports[s]] for s in listed if s in imports and imports[s] in folder_id], folder_id


def parse_frontend_usage(group_names: set[str]) -> dict:
    """UI element (workbench id or page key) -> {'groups': [...], 'flows': [...], 'sources': bool}."""
    rec_text = read(PATHS["records_ts"])
    rec_fn = {}
    for m in re.finditer(r"((?:/\*\*(?:(?!\*/).)*\*/\s*)?)export (?:const|function) (\w+)(.*?)(?=(?:/\*\*(?:(?!\*/).)*\*/\s*)?export |\Z)",
                         rec_text, re.S):
        chunk = m.group(1) + m.group(3)
        keys = set(re.findall(r"records\.(\w+)", chunk)) | set(re.findall(r"'(?:records|governance)',\s*'(\w+)'", chunk))
        rec_fn[m.group(2)] = (keys, chunk)
    for _ in range(3):  # functions defined through other functions inherit their record keys
        for name, (keys, chunk) in rec_fn.items():
            for other, (okeys, _) in rec_fn.items():
                if other != name and re.search(rf"\b{other}\(", chunk):
                    keys |= okeys
    store_text = read(PATHS["store_ts"])
    store_fn = {}
    for m in re.finditer(r"export (?:const|function) (\w+)(.*?)(?=\nexport |\Z)", store_text, re.S):
        store_fn[m.group(1)] = sorted(set(re.findall(r"postFlow\('(\w+)'", m.group(2))))
    usage = {}
    for path in sorted(PATHS["components"].rglob("*.tsx")):
        text = read(path)
        rel = path.relative_to(PATHS["components"]).as_posix()
        if rel.startswith("workbenches/"):
            owner = "workbench:" + path.stem[0].lower() + path.stem[1:]
            if path.stem == "RainDataSources":
                owner = "workbench:dataSources"
        elif rel.startswith("patient/"):
            owner = "page:PatientView"
        elif rel.startswith("cards/"):
            owner = "page:AskCockpitAI"
        else:
            continue
        u = usage.setdefault(owner, {"groups": set(), "flows": set(), "sources": False, "files": set()})
        u["files"].add(rel)
        for names in re.findall(r"import \{([^}]*)\} from '@/data/rain/_shared/constants'", text):
            u["groups"] |= {n.strip() for n in names.split(",") if n.strip() in group_names}
        for names in re.findall(r"import \{([^}]*)\} from '@/data/rain/_shared/records'", text):
            for n in (x.strip() for x in names.split(",")):
                if n in group_names:
                    u["groups"].add(n)
                elif n in rec_fn:
                    u["groups"] |= {k for k in rec_fn[n][0] if k in group_names}
        for names in re.findall(r"import \{([^}]*)\} from '\.\./shell/store'", text):
            for n in (x.strip() for x in names.split(",")):
                u["flows"] |= set(store_fn.get(n, []))
        if re.search(r"import \{[^}]*\} from '@/data/rain/_shared/sources'", text):   # a value import, not `import type`
            u["sources"] = True
    return usage


def parse_loader() -> dict:
    """public_data table -> source file path (relative to .data/public)."""
    out = {}
    for t, f in re.findall(r'\("(\w+)",\s*PUB / "([^"]+)"', read(PATHS["loader"])):
        out.setdefault(t, []).append(f)
    return out


def parse_manifest() -> tuple[dict, dict]:
    """(file or folder -> inventory row, item -> how to unblock) from .data/public/MANIFEST.md."""
    text = read(PATHS["manifest"])
    rows, unblock = {}, {}
    section = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Folder") or line.startswith("| Item"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if section == "Inventory" and len(cells) >= 10:
            path = re.sub(r"`", "", cells[0]).split(" ")[0]
            rows[path] = {"source_name": cells[1], "publisher": cells[2], "url": cells[3], "release": cells[4],
                          "download_date": cells[5], "status": cells[9]}
        elif section == "How to unblock" and len(cells) >= 2:
            unblock[cells[0]] = cells[1]
    return rows, unblock


# ─── build ──────────────────────────────────────────────────────────────────────────────────────────────────
def build(inputs: dict) -> tuple[Graph, dict]:
    g = Graph()
    notes: dict = {"warnings": []}
    warn = notes["warnings"].append
    inv, ddl = inputs["pg"], inputs["ddl"]
    tables = inv["tables"]
    sections = inputs["sections"]

    # ---- PRD v0.4 seed ------------------------------------------------------------------------------------
    seed = load_module("rain_v4_prd_seed", PATHS["seed"])
    seed_nodes, seed_rels = seed.build_records()
    persona_ids = sorted(set(inputs["backend_ids"]) | {q["persona"] for q in inputs["pack"] if q["persona"]})
    templates = inputs["templates"]
    switcher, _ = inputs["switcher"]
    remap, persona_meta = {}, {}
    seed_names = {n["key"]: n["props"].get("name", "") for n in seed_nodes if "Persona" in n["labels"]}
    for prd_key, ui_key, ui_id in PERSONAS:
        hint = BACKEND_HINT.get(prd_key)
        backend = ui_id if ui_id in persona_ids else next((i for i in persona_ids if hint and hint in i), None)
        contract_key = ui_key if ui_key in templates["contracts"] else next(
            (k for k, p in templates["personas"].items()
             if norm((p.get("identity") or {}).get("name", "")) == norm(seed_names.get(f"persona:{prd_key}", ""))), None)
        kag_id = backend or ui_id
        remap[f"persona:{prd_key}"] = f"persona:{kag_id}"
        if ui_id in switcher:
            status = "switcher"
        elif prd_key in PATIENT_VIEW:
            status = "patient_view"
        else:
            status = "kag_only"
        persona_meta[f"persona:{kag_id}"] = dict(
            persona_id=kag_id, backend_persona_id=backend, ui_persona_id=ui_id, ui_contract_key=contract_key,
            ui_status=status, in_switcher=ui_id in switcher, ui_path=PATIENT_VIEW.get(prd_key) or (None if status == "kag_only" else "/"),
            prd_key=prd_key, has_ui_contract=contract_key is not None)
    wbs_ui = {w["id"]: w for w in inputs["workbenches"]}
    for n in seed_nodes:
        if "Workbench" in n["labels"]:
            wid = next((w["id"] for w in wbs_ui.values() if norm(w.get("title", "")) == norm(n["props"].get("name", ""))), None)
            if wid:
                remap[n["key"]] = f"workbench:{wid}"
            else:
                warn(f"seed workbench {n['key']} ({n['props'].get('name')}) is not in contract.ts WORKBENCHES")
    rk = lambda k: remap.get(k, k)  # noqa: E731
    for n in seed_nodes:
        labels = [lab for lab in n["labels"] if lab != "Enterprise"]
        props = {k: safe(v) for k, v in n["props"].items() if k not in ("enterprise_id", "release")}
        g.node(rk(n["key"]), labels[0], *labels[1:], **props)
    for r in seed_rels:
        g.rel(rk(r["from"]), r["type"], rk(r["to"]), **{k: safe(v) for k, v in (r.get("props") or {}).items()},
              origin="prd_seed")
    for key, meta in persona_meta.items():
        g.node(key, "Persona", **meta)

    # ---- upper ontology concepts, classes and properties (factory) --------------------------------------
    upper = {c["id"]: c for c in json.loads(read(PATHS["upper"]) or '{"concepts": []}').get("concepts", [])}
    factory = json.loads(read(PATHS["factory"]) or '{"nodes": [], "relationships": []}')
    for n in factory["nodes"]:
        labels = [lab for lab in n["labels"] if lab not in ("Enterprise", "Platform")]
        if labels[0] in ("Class", "Property"):
            props = {k: safe(v) for k, v in n["props"].items() if k not in ("enterprise_id", "release")}
            g.node(n["key"], labels[0], **props)
    class_by_table = {g.nodes[k]["props"].get("source_table"): k for k in g.nodes if k.startswith("class:")}
    for r in factory["relationships"]:
        if r["type"] in ("RELATES_TO", "HAS_PROPERTY", "ALIGNS_TO"):
            g.rel(r["from"], r["type"], r["to"], **{k: safe(v) for k, v in (r.get("props") or {}).items()}, origin="factory")
    for full, t in tables.items():
        if t["schema"] == "synthetic" and t["name"] not in class_by_table:
            ck = f"class:{pascal(t['name'])}"
            g.node(ck, "Class", name=pascal(t["name"]), source_table=t["name"], source_entity=t["name"],
                   provenance=["rain_v4_extension"], description="Extension table added by the v0.4 synthetic generator")
            class_by_table[t["name"]] = ck
    for tname, ck in class_by_table.items():
        if f"synthetic.{tname}" in tables:
            g.rel(ck, "MAPS_TO", tkey(tname), method="name")
        else:
            warn(f"class {ck} maps to synthetic.{tname}, which is not in Postgres")
    concept_keys ={to for (frm, typ, to) in g.rels if typ == "ALIGNS_TO" and to.startswith("concept:")}
    for ck in sorted(concept_keys):
        cid = ck.split(":", 1)[1]
        c = upper.get(cid, {})
        g.node(ck, "Concept", name=c.get("name", cid), upper_id=cid, parent=c.get("parent"), description=c.get("description"),
               ontology="platform/ontology/upper-ontology.v1.json")

    # ---- schemas, tables, columns, keys, source feeds ----------------------------------------------------
    derived = inputs["derived"]
    for s in SCHEMAS:
        n_t = sum(1 for t in tables.values() if t["schema"] == s)
        g.node(f"schema:{s}", "Schema", name=s, database="rain_v4", tables=n_t,
               rows=sum(t["row_count"] for t in tables.values() if t["schema"] == s))
    loader = inputs["loader"]
    man_rows, _ = inputs["manifest"]
    for full, t in tables.items():
        s, name = t["schema"], t["name"]
        planned = ddl.get(name) if s == "synthetic" else None
        ext_cols = [c["name"] for c in t["columns"] if planned and c["name"] not in planned["columns"]]
        props = dict(name=name, schema=s, qualified_name=full, row_count=t["row_count"], column_count=len(t["columns"]),
                     primary_key=t["pk"], comment=t["comment"], database="rain_v4")
        if s == "synthetic":
            props.update(planned_in_prd=planned is not None, extension_table=planned is None, extension_columns=ext_cols,
                         has_extension=planned is None or bool(ext_cols),
                         planned_columns_missing=[c for c in (planned or {}).get("columns", []) if c not in {x["name"] for x in t["columns"]}],
                         source_feed=planned["source"] if planned else EXTENSION_FEED,
                         origin="derived_from_public_data" if name in derived else
                                ("write_back_log" if name == "flow_event" else "generated"),
                         write_back=False)
        elif s == "public_data":
            files = loader.get(name, [])
            props.update(origin="public_download", source_files=files)
            mrow = next((man_rows[f] for f in files if f in man_rows), None)
            if mrow:
                props.update(source_name=mrow["source_name"], publisher=mrow["publisher"], source_release=mrow["release"],
                             download_date=mrow["download_date"], manifest_status=mrow["status"])
        else:
            props.update(origin="ui_config")
        g.node(tkey(full), "Table", **props)
        g.rel(tkey(full), "IN_SCHEMA", f"schema:{s}")
        for c in t["columns"]:
            ck = f"column:{full}.{c['name']}"
            g.node(ck, "Column", name=c["name"], table=full, position=c["position"], data_type=c["data_type"],
                   nullable=c["nullable"], primary_key=c["name"] in t["pk"], comment=c["comment"],
                   extension=c["name"] in ext_cols)
            g.rel(tkey(full), "HAS_COLUMN", ck)
        if s == "synthetic":
            feed = planned["source"] if planned else EXTENSION_FEED
            g.node(f"system:{feed}", "System", name=feed,
                   description="Rows generated by scripts/e2e/synth/gen_synthetic_v4.py for tables the planned DDL lacks"
                   if feed == EXTENSION_FEED else None)
            g.rel(tkey(full), "FED_BY", f"system:{feed}")
        for src in derived.get(name, []) if s == "synthetic" else []:
            g.rel(tkey(full), "DERIVED_FROM", tkey(src), via="scripts/e2e/synth/gen_load.py PUBLIC_SQL")
    for fk in inv["fks"]:
        for c1, c2 in zip(fk["columns"], fk["ref_columns"]):
            g.rel(f"column:{fk['table']}.{c1}", "REFERENCES", f"column:{fk['ref_table']}.{c2}", constraint=fk["name"])
    for feed, info in sorted({p["source"]: p for p in ddl.values()}.items()):
        g.node(f"system:{feed}", "System", name=feed)

    # ---- data sources (as the Data Sources workbench lists them, with live status) -----------------------
    ui_mod = inputs["ui_module"]
    pending = getattr(ui_mod, "PENDING_SOURCES", {}) if ui_mod else {}
    syn_sql = getattr(ui_mod, "SYNTHETIC_COUNT_SQL", {}) if ui_mod else {}
    man_rows, unblock = inputs["manifest"]
    srcs = sections.get("sources", {})
    covered = set()
    for group, kind in (("PUBLIC_SOURCES", "public"), ("SYNTHETIC_SOURCES", "synthetic"), ("ENGINES", "engine")):
        for s in srcs.get(group, []):
            sid = s["id"]
            tlist = []
            if s.get("table"):
                parts = [p.strip() for p in s["table"].split("+")]
                schema = parts[0].split(".")[0]
                tlist = [p if "." in p else f"{schema}.{p}" for p in parts]
            if sid in syn_sql:
                tlist += sorted(schema_tables(syn_sql[sid]))
            tlist += [qual(t) for t in SOURCE_TABLES.get(sid, [])]
            tlist = list(dict.fromkeys(tlist))
            existing = [t for t in tlist if t in tables]
            if sid in pending and pending[sid][0] not in tables:
                load_status, reason = "blocked", pending[sid][1]
            elif not existing and s.get("status") == "error":       # the UI marks a source it could not load
                load_status = "blocked"
                reason = re.sub(r"^Not loaded yet:\s*", "", s.get("freshness") or "") or "not loaded"
            elif sid == "rain-synthea":       # a public generator: its rows are the generated synthetic tables
                load_status, reason = "generated", None
            elif kind == "public":
                load_status = "loaded" if existing and all(tables[t]["row_count"] > 0 for t in existing) else "missing"
                reason = None
            else:
                load_status, reason = ("generated" if kind == "synthetic" else "computed"), None
            unblock_text = None
            if load_status == "blocked":
                unblock_text = next((v for k, v in unblock.items() if any(w in norm(k) for w in
                                     ({"rain-fcc": ["fcc"], "rain-geovar": ["geographicvariation"]}.get(sid, [norm(s['name'])])))), None)
            g.node(f"source:{sid}", "DataSource", source_id=sid, name=s.get("name"), kind=kind, ui_status=s.get("status"),
                   load_status=load_status, blocked_reason=reason, unblock=unblock_text, record_count=s.get("recordCount"),
                   live=s.get("live"), freshness=s.get("freshness"), used_for=s.get("usedFor"), provides=s.get("provides"),
                   tables=tlist, target_table=pending[sid][0] if load_status == "blocked" else None, in_ui=True)
            for t in existing:
                g.rel(f"source:{sid}", "LOADS" if t.startswith("public_data.") else "FEEDS", tkey(t))
                covered.add(t)
    for sid, name, publisher, reason, item in BLOCKED_EXTRA:
        g.node(f"source:{sid}", "DataSource", source_id=sid, name=name, kind="public", publisher=publisher, load_status="blocked",
               blocked_reason=reason, unblock=unblock.get(item), in_ui=False, record_count=0)
    by_folder = defaultdict(set)
    for t, files in loader.items():
        for f in files:
            by_folder[f.split("/")[0]].add(t)
    for full, t in tables.items():
        if t["schema"] != "public_data" or full in covered:
            continue
        sid = PUBLIC_TABLE_SOURCE.get(t["name"])
        if not sid:
            folder = next((f.split("/")[0] for f in loader.get(t["name"], [])), None)
            sid = next((k.split(":", 1)[1] for (k, typ, to) in g.rels if typ == "LOADS" and folder and
                        to.split(".")[-1] in by_folder.get(folder, set())), None)
        if sid and f"source:{sid}" in g.nodes:
            g.rel(f"source:{sid}", "LOADS", tkey(full), via="same source")
        else:
            mrow = next((man_rows[f] for f in loader.get(t["name"], []) if f in man_rows), {})
            sid = f"public-{t['name']}"
            g.node(f"source:{sid}", "DataSource", source_id=sid, name=mrow.get("source_name") or t["name"], kind="public",
                   publisher=mrow.get("publisher"), load_status="loaded" if t["row_count"] else "missing", in_ui=False,
                   record_count=t["row_count"], tables=[full])
            g.rel(f"source:{sid}", "LOADS", tkey(full))
    for feed, sid in FEED_SOURCE.items():
        if f"system:{feed}" in g.nodes and f"source:{sid}" in g.nodes:
            g.rel(f"system:{feed}", "PROVIDED_BY", f"source:{sid}")

    # ---- the computed context: metric groups, records, governance, datasets ------------------------------
    parsed_tables, ds_groups, group_module = inputs["metric_code"]
    group_kind = {}
    for sec, kind in (("constants", "constants"), ("records", "records"), ("governance", "governance")):
        for k in sections.get(sec, {}):
            group_kind[k] = "config" if k in CONFIG_GROUPS else kind
    for k, kind in sorted(group_kind.items()):
        mk = f"metricgroup:{k}"
        curated = GROUP_TABLES.get(k)
        tl = [] if kind == "config" else (curated if curated is not None else parsed_tables.get(k, []))
        val = sections.get(kind if kind != "config" else "constants", {}).get(k)
        size = len(val) if isinstance(val, (list, dict)) else None
        mapping = "config" if kind == "config" else "curated" if curated is not None else "parsed" if tl else \
                  "derived" if k in GROUP_FROM_GROUPS else "none"
        g.node(mk, "MetricGroup", name=k, kind=kind, section=kind if kind != "config" else "constants",
               description=GROUP_TEXT.get(k), mapping=mapping,
               items=size, computed_by=group_module.get(k, "rain-api/metrics_v4.py"), tables=[qual(t) for t in tl])
        for t in tl:
            if qual(t) in tables:
                g.rel(mk, "COMPUTED_FROM", tkey(t), mapping="curated" if curated is not None else "parsed")
            else:
                warn(f"metric group {k} names {qual(t)}, which is not in Postgres")
        for src in GROUP_FROM_GROUPS.get(k, []):
            if src in group_kind:
                g.rel(mk, "DERIVED_FROM", f"metricgroup:{src}")
    for k in sorted(sections.get("datasets", {})):
        v = sections["datasets"][k]
        caption = v.get("caption") or v.get("title") if isinstance(v, dict) else None
        dk = f"dataset:{k}"
        groups = ds_groups.get(k) or ds_groups.get(k.split("_")[0] + "_*", [])
        built_by = next((group_module[grp] for grp in groups if grp in group_module), "rain-api/metrics_v4.py")
        g.node(dk, "Dataset", name=k, caption=caption, built_by=built_by)
        for grp in groups:
            if grp in group_kind:
                g.rel(dk, "DERIVED_FROM", f"metricgroup:{grp}")
        owner = DATASET_PERSONA.get(k.split("_")[0])
        if owner:
            g.rel(remap[f"persona:{owner}"], "SEES", dk, via="persona datasets")

    # ---- personas: UI contracts, workbench access, what they see, their queries --------------------------
    for wid, w in wbs_ui.items():
        g.node(f"workbench:{wid}", "Workbench", ui_id=wid, name=g.nodes.get(f"workbench:{wid}", {}).get("props", {}).get("name") or w.get("title"),
               title=w.get("title"), path=w.get("path"), ui_priority=w.get("priority"), subtitle=w.get("subtitle"),
               in_ui=True, proposed=False, built=True)
    for k, n in g.nodes.items():
        if "Workbench" in n["labels"] and "in_ui" not in n["props"]:
            n["props"]["in_ui"] = False
    ui_personas = {m["ui_contract_key"]: k for k, m in persona_meta.items() if m["ui_contract_key"]}
    for ckey, pkey in ui_personas.items():
        contract = templates["contracts"].get(ckey, {})
        ident = (templates["personas"].get(ckey) or {}).get("identity", {})
        g.node(pkey, "Persona", ui_name=ident.get("name"), ui_role=ident.get("role"),
               ui_suggested_queries=[q for q in contract.get("queries", []) if isinstance(q, str)],
               ui_signals=len(contract.get("signals", [])), ui_kpis=len(contract.get("kpis", [])))
        if contract.get("workbenches"):
            g.drop_rels(lambda f, t, to, pkey=pkey: f == pkey and t == "USES")   # the UI contract is the access truth
            for wb in contract["workbenches"]:
                if f"workbench:{wb['id']}" not in g.nodes:
                    warn(f"{ckey} contract names workbench {wb['id']}, which is not in contract.ts WORKBENCHES")
                    continue
                g.rel(pkey, "USES", f"workbench:{wb['id']}", access=wb.get("access"), scope=wb.get("scope"),
                      origin="ui_contract")
        text = json.dumps(contract) + json.dumps(templates["personas"].get(ckey, {}))
        seen = set(re.findall(r"constants\.([A-Z_]+)", text)) | set(re.findall(r"(?:records|governance)\.(\w+)", text))
        for grp in sorted(seen & set(group_kind)):
            g.rel(pkey, "SEES", f"metricgroup:{grp}", via="ui_contract")
        for ds in sorted(set(re.findall(r'"(?:dataset|datasetId)": "(\w+)"', text)) | set(re.findall(r"datasets\.(\w+)", text))):
            if f"dataset:{ds}" in g.nodes:
                g.rel(pkey, "SEES", f"dataset:{ds}", via="ui_contract")
    for prd_key, groups in PERSONA_GROUPS.items():
        pkey = remap[f"persona:{prd_key}"]
        for grp in groups:
            if grp in group_kind:
                g.rel(pkey, "SEES", f"metricgroup:{grp}", via="persona metrics")
    by_backend = {m["persona_id"]: k for k, m in persona_meta.items()}
    for q in inputs["pack"]:
        qk = f"query:{q['id']}"
        missing = [t for t in q["tables"] if t not in tables]
        reads = list(dict.fromkeys(q["tables"] + sorted(t for t in tables if tables[t]["schema"] in q["schema_scans"])))
        g.node(qk, "Query", query_id=q["id"], persona_id=q["persona"], data=q["data"], question=q["question"], sql=q["sql"],
               tables=reads, missing_tables=missing, schema_scans=q["schema_scans"], api=f"/api/v4/queries/{q['id']}",
               pack="doc/queries/rain_v4_persona_queries.sql")
        if q["persona"] in by_backend:
            g.rel(by_backend[q["persona"]], "ASKS", qk, data=q["data"])
        else:
            warn(f"query {q['id']} names persona {q['persona']}, which no KAG persona carries")
        for t in reads:
            if t in tables:
                g.rel(qk, "READS", tkey(t), via="schema scan" if t not in q["tables"] else None)
    for key, meta in persona_meta.items():
        n = g.nodes[key]["props"]
        n["queries"] = sum(1 for (f, t, _) in g.rels if f == key and t == "ASKS")
        n["workbench_count"] = sum(1 for (f, t, _) in g.rels if f == key and t == "USES")

    # ---- write-back flows, and what triggers them in the UI ----------------------------------------------
    for fl in inputs["flows"]:
        fk = f"flow:{fl['name']}"
        g.node(fk, "Flow", name=fl["name"], method=fl["method"], path=fl["path"], description=fl["description"],
               writes=fl["writes"], reads=fl["reads"], replays_undo=fl["replays_undo"], module="rain-api/flow_v4.py")
        for t in fl["writes"]:
            if t in tables:
                g.rel(fk, "WRITES", tkey(t))
                g.nodes[tkey(t)]["props"]["write_back"] = True
        for t in fl["reads"]:
            if t in tables:
                g.rel(fk, "READS", tkey(t))
    usage = inputs["usage"]
    for owner, u in usage.items():
        if owner not in g.nodes:
            continue
        for grp in sorted(u["groups"]):
            g.rel(owner, "SHOWS", f"metricgroup:{grp}", via="frontend import")
        for fl in sorted(u["flows"]):
            if f"flow:{fl}" in g.nodes:
                g.rel(owner, "TRIGGERS", f"flow:{fl}")
        if u["sources"]:
            for k in [k for k in g.nodes if k.startswith("source:") and g.nodes[k]["props"].get("in_ui")]:
                g.rel(owner, "LISTS", k)
        g.nodes[owner]["props"]["ui_files"] = sorted(u["files"])

    # ---- the release itself ------------------------------------------------------------------------------
    labels = Counter(n["labels"][0] for n in g.nodes.values())
    g.node(f"release:{RELEASE}", "Release", name=RELEASE, enterprise=ENTERPRISE, built_at=inputs["built_at"],
           git_commit=inputs["git"], supersedes=["rain-v4.0.0"], personas=labels.get("Persona", 0),
           queries=labels.get("Query", 0), tables=labels.get("Table", 0), sources=json.dumps(inputs["sources_used"]),
           builder="scripts/e2e/kag_v4_refresh.py")
    # drop relationships whose endpoints are missing (reported)
    dangling = [(f, t, to) for (f, t, to) in g.rels if f not in g.nodes or to not in g.nodes]
    for k in dangling:
        warn(f"dropped dangling relationship {k[0]} -[{k[1]}]-> {k[2]}")
        del g.rels[k]
    notes["dangling"] = len(dangling)
    return g, notes


# ─── Neo4j ──────────────────────────────────────────────────────────────────────────────────────────────────
LABEL_RE, TYPE_RE = re.compile(r"^[A-Za-z]+$"), re.compile(r"^[A-Z][A-Z0-9_]*$")


def neo4j_driver():
    from neo4j import GraphDatabase
    uri, auth = os.getenv("NEO4J_URI", "bolt://neo4j:7687"), (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    try:   # an empty database warns about every property the queries name; those warnings are noise here
        return GraphDatabase.driver(uri, auth=auth, notifications_min_severity="OFF")
    except TypeError:
        return GraphDatabase.driver(uri, auth=auth)


def run(s, q, **kw):
    return [r.data() for r in s.run(q, **kw)]


def graph_state(s) -> dict:
    return {
        "nodes": run(s, "MATCH (n) RETURN count(n) AS c")[0]["c"],
        "relationships": run(s, "MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"],
        "by_release": {r["release"]: r["c"] for r in run(s, "MATCH (n) RETURN coalesce(n.release, '(none)') AS release, count(*) AS c")},
        "unreleased_by_labels": {":".join(sorted(r["l"])): r["c"] for r in
                                 run(s, "MATCH (n) WHERE n.release IS NULL RETURN labels(n) AS l, count(*) AS c")},
        "personas": {r["release"]: r["c"] for r in run(s, "MATCH (p:Persona) RETURN coalesce(p.release, '(none)') AS release, count(*) AS c")},
    }


def purge_legacy(s, purge_unknown: bool) -> dict:
    rows = run(s, "MATCH (n) WHERE n.release IS NULL RETURN labels(n) AS l, count(*) AS c")
    unknown = {":".join(r["l"]): r["c"] for r in rows if not set(r["l"]) <= LEGACY_LABELS}
    if unknown and not purge_unknown:
        raise SystemExit(f"unreleased nodes with labels outside the v1/v2 seed set: {unknown} (re-run with --purge-unknown)")
    rels = run(s, "MATCH (a)-[r]-(b) WHERE a.release IS NULL OR b.release IS NULL RETURN count(DISTINCT r) AS c")[0]["c"]
    total = sum(r["c"] for r in rows)
    while True:
        n = run(s, "MATCH (n) WHERE n.release IS NULL WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS c")[0]["c"]
        if not n:
            break
    return {"nodes": total, "relationships": rels, "by_labels": {":".join(sorted(r["l"])): r["c"] for r in rows}}


def purge_superseded(s) -> dict:
    rows = run(s, "MATCH (n) WHERE n.release IS NOT NULL AND n.release <> $r AND coalesce(n.enterprise_id, $e) = $e "
                  "RETURN n.release AS release, count(*) AS c", r=RELEASE, e=ENTERPRISE)
    rels = run(s, "MATCH (a)-[x]-(b) WHERE (a.release IS NOT NULL AND a.release <> $r AND coalesce(a.enterprise_id, $e) = $e) "
                  "OR (b.release IS NOT NULL AND b.release <> $r AND coalesce(b.enterprise_id, $e) = $e) "
                  "RETURN count(DISTINCT x) AS c", r=RELEASE, e=ENTERPRISE)[0]["c"]
    while True:
        n = run(s, "MATCH (n) WHERE n.release IS NOT NULL AND n.release <> $r AND coalesce(n.enterprise_id, $e) = $e "
                   "WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS c", r=RELEASE, e=ENTERPRISE)[0]["c"]
        if not n:
            break
    return {"by_release": {r["release"]: r["c"] for r in rows}, "relationships": rels}


def publish(s, g: Graph, run_id: str) -> dict:
    s.run("CREATE INDEX kag_enterprise_key IF NOT EXISTS FOR (n:Enterprise) ON (n.key, n.release)").consume()
    groups = defaultdict(list)
    for n in g.nodes.values():
        for lab in n["labels"]:
            if not LABEL_RE.match(lab):
                raise ValueError(f"bad label {lab}")
        props = {k: safe(v) for k, v in n["props"].items() if v is not None}
        props.update(key=n["key"], release=RELEASE, enterprise_id=ENTERPRISE, run_id=run_id)
        groups[tuple(n["labels"])].append({"key": n["key"], "props": props})
    for labels, rows in groups.items():
        lab = ":".join(("Enterprise", *labels))
        for i in range(0, len(rows), 500):
            s.run(f"UNWIND $rows AS r MERGE (n:{lab} {{key: r.key, release: $rel}}) SET n = r.props",
                  rows=rows[i:i + 500], rel=RELEASE).consume()
    by_type = defaultdict(list)
    for (frm, typ, to), props in g.rels.items():
        if not TYPE_RE.match(typ):
            raise ValueError(f"bad relationship type {typ}")
        p = {k: safe(v) for k, v in props.items() if v is not None}
        p.update(release=RELEASE, run_id=run_id)
        by_type[typ].append({"from": frm, "to": to, "props": p})
    for typ, rows in by_type.items():
        for i in range(0, len(rows), 1000):
            s.run(f"UNWIND $rows AS r MATCH (a:Enterprise {{key: r.from, release: $rel}}) "
                  f"MATCH (b:Enterprise {{key: r.to, release: $rel}}) MERGE (a)-[x:{typ}]->(b) SET x = r.props",
                  rows=rows[i:i + 1000], rel=RELEASE).consume()
    stale_rels = run(s, "MATCH (a {release: $rel})-[x]->(b {release: $rel}) WHERE coalesce(x.run_id, '') <> $run "
                        "DELETE x RETURN count(*) AS c", rel=RELEASE, run=run_id)[0]["c"]
    stale_nodes = run(s, "MATCH (n {release: $rel}) WHERE coalesce(n.run_id, '') <> $run DETACH DELETE n RETURN count(*) AS c",
                      rel=RELEASE, run=run_id)[0]["c"]
    return {"stale_nodes_removed": stale_nodes, "stale_relationships_removed": stale_rels}


# ─── validation ─────────────────────────────────────────────────────────────────────────────────────────────
def checks(n_personas: int, n_queries: int) -> list[tuple]:
    """(id, title, cypher, expectation): 'zero' = no rows, ('eq', rows) = exactly these rows, 'info' = shown only."""
    R = RELEASE
    return [
        ("K01", "One release in the database, and it is the current one",
         "MATCH (n) RETURN coalesce(n.release, '(none)') AS release, count(*) AS nodes ORDER BY release",
         ("single", R)),
        ("K02", "No node without a release (the v1/v2 seed graph is gone)",
         "MATCH (n) WHERE n.release IS NULL RETURN labels(n) AS labels, count(*) AS nodes", "zero"),
        ("K03", "No relationship outside the release",
         "MATCH (a)-[r]->(b) WHERE r.release IS NULL OR a.release <> r.release OR b.release <> r.release "
         "RETURN type(r) AS type, count(*) AS n", "zero"),
        ("K04", "No legacy label left (v1/v2 seed graph, Platform nodes, factory DataAssets)",
         "MATCH (n) WHERE any(l IN labels(n) WHERE l IN ['KPI','SourceField','CachedQuestion','SourceSystem','CascadeBranch',"
         "'CountyRegion','CoverageGap','Constant','ClosureEvent','Platform','DataAsset']) RETURN labels(n) AS labels, count(*) AS n",
         "zero"),
        ("K05", f"Exactly {n_personas} personas, each with a backend id and a UI persona id",
         f"MATCH (p:Persona {{release: '{R}'}}) RETURN count(p) AS personas, count(p.persona_id) AS with_kag_id, "
         "count(p.ui_persona_id) AS with_ui_id", ("eq", [{"personas": n_personas, "with_kag_id": n_personas, "with_ui_id": n_personas}])),
        ("K06", "Only the seven personas: every Persona is a PRD v0.4 persona of v0.3 origin, and no RetiredPersona node",
         f"MATCH (p) WHERE (p:Persona AND (p.release <> '{R}' OR p.prd_origin <> 'v0.3' OR p.prd_version <> 'v0.4')) "
         "OR p:RetiredPersona RETURN labels(p) AS labels, p.name AS persona, p.release AS release", "zero"),
        ("K07", "The persona roster with UI status, workbench access and pack queries",
         f"MATCH (p:Persona {{release: '{R}'}}) RETURN p.order AS order, p.name AS persona, p.persona_id AS kag_id, "
         "p.ui_persona_id AS ui_id, p.ui_status AS ui_status, COUNT { (p)-[:USES]->(:Workbench) } AS workbenches, "
         "COUNT { (p)-[:ASKS]->(:Query) } AS queries ORDER BY order", "info"),
        ("K08", "Every persona has pack queries",
         f"MATCH (p:Persona {{release: '{R}'}}) WHERE NOT (p)-[:ASKS]->(:Query) RETURN p.name AS persona, p.persona_id AS kag_id, "
         "p.backend_persona_id AS backend_id", "zero"),
        ("K09", "Every persona has workbenches (patients: the patient view page instead)",
         f"MATCH (p:Persona {{release: '{R}'}}) WHERE NOT (p)-[:USES]->(:Workbench) "
         "AND NOT (p.role = 'Patient' AND (p)-[:LANDS_ON]->(:Page {key: 'page:PatientView'})) "
         "RETURN p.name AS persona, p.ui_status AS ui_status, p.has_ui_contract AS has_ui_contract", "zero"),
        ("K10", f"Every pack query is in the graph ({n_queries} in doc/queries/rain_v4_persona_queries.sql)",
         f"MATCH (q:Query {{release: '{R}'}}) RETURN count(q) AS queries", ("eq", [{"queries": n_queries}])),
        ("K11", "Every query reads at least one existing Table node and names no missing table",
         f"MATCH (q:Query {{release: '{R}'}}) WHERE NOT (q)-[:READS]->(:Table) OR size(q.missing_tables) > 0 "
         "RETURN q.query_id AS query, q.tables AS tables, q.missing_tables AS missing", "zero"),
        ("K12", "Every query belongs to a persona",
         f"MATCH (q:Query {{release: '{R}'}}) WHERE NOT (:Persona)-[:ASKS]->(q) RETURN q.query_id AS query, q.persona_id AS persona",
         "zero"),
        ("K13", "Tables per schema with rows and columns",
         f"MATCH (t:Table {{release: '{R}'}}) RETURN t.schema AS schema, count(t) AS tables, sum(t.row_count) AS rows, "
         "sum(t.column_count) AS columns ORDER BY schema", "info"),
        ("K14", "Every column belongs to exactly one table; every foreign key points at a column of a table",
         f"MATCH (c:Column {{release: '{R}'}}) WHERE COUNT {{ (:Table)-[:HAS_COLUMN]->(c) }} <> 1 "
         "OR EXISTS { MATCH (c)-[:REFERENCES]->(d:Column) WHERE NOT (:Table)-[:HAS_COLUMN]->(d) } RETURN c.key AS column", "zero"),
        ("K15", "Every synthetic table has a source feed; every public_data table has a data source",
         f"MATCH (t:Table {{release: '{R}'}}) WHERE (t.schema = 'synthetic' AND NOT (t)-[:FED_BY]->(:System)) "
         "OR (t.schema = 'public_data' AND NOT (:DataSource)-[:LOADS]->(t)) RETURN t.qualified_name AS table", "zero"),
        ("K16", "Every class maps to a table",
         f"MATCH (c:Class {{release: '{R}'}}) WHERE NOT (c)-[:MAPS_TO]->(:Table) RETURN c.name AS class", "zero"),
        ("K17", "Every UI workbench is in the graph and used by at least one persona",
         f"MATCH (w:Workbench {{release: '{R}'}}) WHERE w.in_ui AND NOT (:Persona)-[:USES]->(w) RETURN w.name AS workbench", "zero"),
        ("K18", "Every computed metric group reads tables (directly or through the records it is built from)",
         f"MATCH (m:MetricGroup {{release: '{R}'}}) WHERE m.kind <> 'config' AND NOT (m)-[:COMPUTED_FROM]->(:Table) "
         "AND NOT (m)-[:DERIVED_FROM]->(:MetricGroup) RETURN m.name AS group, m.kind AS kind", "zero"),
        ("K19", "Every dataset is derived from at least one metric group",
         f"MATCH (d:Dataset {{release: '{R}'}}) WHERE NOT (d)-[:DERIVED_FROM]->(:MetricGroup) RETURN d.name AS dataset", "zero"),
        ("K20", "Every write-back flow (POST) writes at least one table",
         f"MATCH (f:Flow {{release: '{R}'}}) WHERE f.method = 'POST' AND NOT (f)-[:WRITES]->(:Table) RETURN f.name AS flow", "zero"),
        ("K21", "Every data source has a load status; blocked ones say why",
         f"MATCH (s:DataSource {{release: '{R}'}}) WHERE s.load_status IS NULL OR (s.load_status = 'blocked' AND s.blocked_reason IS NULL) "
         "OR s.load_status = 'missing' RETURN s.name AS source, s.load_status AS status", "zero"),
        ("K22", "Data sources by load status",
         f"MATCH (s:DataSource {{release: '{R}'}}) RETURN s.load_status AS status, count(*) AS sources, "
         "collect(s.name) AS names ORDER BY status", "info"),
        ("K23", "Nodes by label", f"MATCH (n {{release: '{R}'}}) RETURN labels(n)[1] AS label, count(*) AS nodes ORDER BY nodes DESC",
         "info"),
        ("K24", "Relationships by type",
         f"MATCH ({{release: '{R}'}})-[r]->() RETURN type(r) AS type, count(*) AS relationships ORDER BY relationships DESC", "info"),
    ]


def run_checks(s, n_personas, n_queries, pg_tables: dict) -> list[dict]:
    out = []
    for cid, title, q, expect in checks(n_personas, n_queries):
        rows = run(s, q)
        if expect == "zero":
            ok = not rows
        elif expect == "info":
            ok = None
        elif expect[0] == "single":
            ok = len(rows) == 1 and rows[0]["release"] == expect[1]
        else:
            ok = rows == expect[1]
        out.append({"id": cid, "title": title, "cypher": q, "ok": ok, "rows": rows})
    # checks against Postgres itself
    kag = {r["t"]: r["n"] for r in run(s, f"MATCH (t:Table {{release: '{RELEASE}'}}) RETURN t.qualified_name AS t, t.row_count AS n")}
    missing_in_pg = sorted(set(kag) - set(pg_tables))
    missing_in_kag = sorted(set(pg_tables) - set(kag))
    out.append({"id": "K25", "title": "Every Table node exists in Postgres rain_v4, and every table of the three schemas has a Table node",
                "cypher": f"MATCH (t:Table {{release: '{RELEASE}'}}) RETURN t.qualified_name  // compared with pg_class",
                "ok": not missing_in_pg and not missing_in_kag,
                "rows": [{"table_nodes": len(kag), "postgres_tables": len(pg_tables), "not_in_postgres": missing_in_pg,
                          "not_in_kag": missing_in_kag}]})
    drift = {t: {"kag": kag[t], "postgres": pg_tables[t]} for t in sorted(set(kag) & set(pg_tables)) if kag[t] != pg_tables[t]}
    out.append({"id": "K26", "title": "Row counts on the Table nodes match Postgres at validation time (write-back flows may move them)",
                "cypher": f"MATCH (t:Table {{release: '{RELEASE}'}}) RETURN t.qualified_name, t.row_count  // compared with count(*)",
                "ok": not drift, "rows": [{"tables_compared": len(set(kag) & set(pg_tables)), "different": drift}]})
    return out


def table_md(rows: list[dict], limit=40) -> str:
    if not rows:
        return "_no rows_"
    cols = list(rows[0].keys())
    fmt = lambda v: (", ".join(map(str, v)) if isinstance(v, list) else json.dumps(v) if isinstance(v, dict) else str(v)).replace("|", "\\|")  # noqa: E731
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(r.get(c)) for c in cols) + " |" for r in rows[:limit]]
    if len(rows) > limit:
        lines.append(f"\n_{len(rows) - limit} more rows_")
    return "\n".join(lines)


def write_check_doc(results, summary):
    passed = sum(1 for r in results if r["ok"] is True)
    failed = [r for r in results if r["ok"] is False]
    lines = [
        "# RAIN v0.4 knowledge graph (KAG): release check", "",
        f"Release **`{RELEASE}`** in Neo4j database `neo4j` of the compose project `rain4` "
        "(http://localhost:17477/browser/, bolt://localhost:17690). Written by `scripts/e2e/kag_v4_refresh.py` on "
        f"{summary['built_at']} (git {summary['git']}); re-run that script to rebuild the release and this file.", "",
        f"**{passed} of {sum(1 for r in results if r['ok'] is not None)} checks pass**"
        + (f"; failing: {', '.join(r['id'] for r in failed)}." if failed else "."), "",
        "## What the release holds", "",
        f"{summary['nodes']:,} nodes and {summary['relationships']:,} relationships, all with `release = '{RELEASE}'`, built from:", "",
    ]
    lines += [f"- {k}: {v}" for k, v in summary["sources_used"].items()]
    lines += ["", "Graph model (main paths):", "",
              "- `(:Persona)-[:USES {access, scope}]->(:Workbench)-[:READS]->(:Class)-[:MAPS_TO]->(:Table)`",
              "- `(:Persona)-[:ASKS]->(:Query)-[:READS]->(:Table)-[:HAS_COLUMN]->(:Column)-[:REFERENCES]->(:Column)`",
              "- `(:Persona)-[:SEES]->(:MetricGroup|Dataset)`, `(:Dataset)-[:DERIVED_FROM]->(:MetricGroup)-[:COMPUTED_FROM]->(:Table)`",
              "- `(:Workbench|Page)-[:SHOWS]->(:MetricGroup)`, `(:Workbench|Page)-[:TRIGGERS]->(:Flow)-[:WRITES|READS]->(:Table)`",
              "- `(:DataSource)-[:LOADS|FEEDS]->(:Table)-[:FED_BY]->(:System)-[:PROVIDED_BY]->(:DataSource)`, "
              "`(:Table)-[:DERIVED_FROM]->(:Table)` (synthetic reference tables built from public_data), `(:Table)-[:IN_SCHEMA]->(:Schema)`",
              "- PRD v0.4 seed: `Organization, County, Site, Contract, Checkpoint, QualityGate, Measure, Metric, Segment, UseCase, Page, "
              "Capability, Signal, Step, SuccessMetric` with the persona edges `WORKS_FOR, PARTICIPATES_IN, LANDS_ON, "
              "VIEWS, HAS_SIGNAL, OWNS_METRIC, REPORTS_TO`", ""]
    if summary.get("cleanup_log") is not None:
        lines += ["## What was deleted", "",
                  "Every run that deleted something is logged on the release node (`MATCH (r:Release) RETURN r.cleanup_log`).", ""]
        for e in summary["cleanup_log"] or [{"at": summary["built_at"], "run": "-", "legacy": {"nodes": 0, "relationships": 0, "by_labels": {}},
                                             "superseded": {"by_release": {}, "relationships": 0},
                                             "stale": {"stale_nodes_removed": 0, "stale_relationships_removed": 0}}]:
            lg, sp, st = e["legacy"], e["superseded"], e["stale"]
            lines += [f"- **{e['at']}** (run `{e['run']}`):",
                      f"  - unreleased v1/v2 seed graph and Platform upper-ontology nodes: {lg['nodes']} nodes, {lg['relationships']} "
                      f"relationships" + (f" ({', '.join(f'{k} {v}' for k, v in sorted(lg['by_labels'].items()))})" if lg["by_labels"] else ""),
                      f"  - superseded releases: " + (", ".join(f"`{k}` {v} nodes" for k, v in sp["by_release"].items()) or "none")
                      + f", {sp['relationships']} relationships",
                      f"  - stale content of `{RELEASE}` from an earlier run: {st['stale_nodes_removed']} nodes, "
                      f"{st['stale_relationships_removed']} relationships"]
        lines += ["", f"This run: before {summary['before']['nodes']:,} nodes / {summary['before']['relationships']:,} relationships "
                  f"({', '.join(f'{k} {v}' for k, v in summary['before']['by_release'].items())}); after {summary['after']['nodes']:,} / "
                  f"{summary['after']['relationships']:,} ({', '.join(f'{k} {v}' for k, v in summary['after']['by_release'].items())}).", ""]
    if summary["warnings"]:
        lines += ["## Build warnings", ""] + [f"- {w}" for w in summary["warnings"]] + [""]
    lines += ["## Checks", ""]
    for r in results:
        mark = "info" if r["ok"] is None else ("PASS" if r["ok"] else "FAIL")
        lines += [f"### {r['id']} {mark}: {r['title']}", "", "```cypher", r["cypher"], "```", "", table_md(r["rows"]), ""]
    OUT_CHECK.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_browser_pack():
    R = RELEASE
    q = [
        ("KAG-1", "The seven v0.4 personas: origin, scope, UI id and status, workbenches, pack queries",
         f"MATCH (p:Persona {{release: '{R}'}})\nRETURN p.order AS order, p.name AS name, p.role AS role, p.prd_origin AS prd_origin, "
         "p.data_scope AS data_scope,\n       p.persona_id AS kag_id, p.ui_persona_id AS ui_id, p.ui_status AS ui_status, "
         "p.workbench_count AS workbenches, p.queries AS queries\nORDER BY p.order;"),
        ("KAG-2", "Every persona with everything it links to (graph view)",
         f"MATCH (p:Persona {{release: '{R}'}})-[r]->(x)\nWHERE NOT x:Query\nRETURN p, r, x;"),
        ("KAG-3", "One persona's neighbourhood (swap the id: rain_ceo, rain_cmo, rain_cio, rain_state, rain_chw, rain_access,\n"
                  "//            patient_linda_garcia)",
         f"MATCH (p:Persona {{release: '{R}', persona_id: 'rain_ceo'}})-[r]-(x)\nRETURN p, r, x;"),
        ("KAG-4", "Priority signals per persona (PRD)",
         f"MATCH (p:Persona {{release: '{R}'}})-[:HAS_SIGNAL]->(s:Signal)\nRETURN p.name AS persona, s.name AS signal, "
         "s.severity AS severity, s.detail AS detail\nORDER BY p.order, s.severity;"),
        ("KAG-5", "The PRD's suggested questions and the UI's chat suggestions per persona",
         f"MATCH (p:Persona {{release: '{R}'}})\nRETURN p.name AS persona, coalesce(p.suggested_queries, []) AS prd_questions, "
         "coalesce(p.ui_suggested_queries, []) AS ui_questions\nORDER BY p.order;"),
        ("KAG-6", "Guided conversation steps per persona (PRD v0.3), in order",
         f"MATCH (p:Persona {{release: '{R}'}})-[:HAS_STEP]->(s:Step)\nRETURN p.name AS persona, s.step AS step, "
         "s.user_prompt AS user_prompt, s.visualization AS visualization\nORDER BY p.order, s.step;"),
        ("KAG-7", "What each persona's workbenches read: Persona -> Workbench -> Class -> Table",
         f"MATCH (p:Persona {{release: '{R}'}})-[u:USES]->(w:Workbench)-[:READS]->(c:Class)-[:MAPS_TO]->(t:Table)\n"
         "RETURN p.name AS persona, w.name AS workbench, u.access AS access, u.scope AS scope,\n"
         "       collect(DISTINCT c.name) AS classes, collect(DISTINCT t.qualified_name) AS tables\nORDER BY persona, workbench;"),
        ("KAG-8", "Same lineage as a graph (one persona; swap the id)",
         f"MATCH path = (p:Persona {{release: '{R}', persona_id: 'rain_cmo'}})-[:USES]->(:Workbench)-[:READS]->(:Class)-[:MAPS_TO]->(:Table)\n"
         "RETURN path;"),
        ("KAG-9", "The release without columns, queries and datasets (overview graph)",
         f"MATCH (n {{release: '{R}'}})\nWHERE NOT n:Column AND NOT n:Query AND NOT n:Dataset\n"
         f"OPTIONAL MATCH (n)-[r]->(m {{release: '{R}'}})\nWHERE NOT m:Column AND NOT m:Query AND NOT m:Dataset\nRETURN n, r, m;"),
        ("KAG-10", "Contract checkpoint the operator personas view",
         f"MATCH (p:Persona {{release: '{R}'}})-[:VIEWS]->(c:Checkpoint)\nRETURN c.name AS checkpoint, c.actual_pmpm AS actual_pmpm, "
         "c.expected_pmpm AS expected_pmpm, c.days_left AS days_left, collect(p.name) AS viewed_by;"),
        ("KAG-11", "Success metrics and the personas that own them (PRD v0.4 Section 10)",
         f"MATCH (p:Persona {{release: '{R}'}})-[:OWNS_METRIC]->(m:SuccessMetric)\nRETURN m.metric_id AS metric, m.name AS name, "
         "m.baseline AS baseline, m.target AS target, collect(p.name) AS owners\nORDER BY metric;"),
        ("KAG-12", "The workbenches (UI ids and paths) and who uses them with what access",
         f"MATCH (w:Workbench {{release: '{R}'}})\nOPTIONAL MATCH (p:Persona)-[u:USES]->(w)\n"
         "RETURN w.ui_id AS id, w.path AS path, w.name AS workbench, w.ui_priority AS priority,\n"
         "       collect(p.name + ' (' + u.access + coalesce(', ' + u.scope, '') + ')') AS used_by\nORDER BY id;"),
        ("KAG-13", "Each persona's pack queries and the tables they read",
         f"MATCH (p:Persona {{release: '{R}'}})-[:ASKS]->(q:Query)-[:READS]->(t:Table)\n"
         "RETURN p.order AS order, p.name AS persona, q.query_id AS query, q.data AS data, q.question AS question,\n"
         "       collect(t.qualified_name) AS tables\nORDER BY order, query;"),
        ("KAG-14", "Computed metric groups (rain-api/metrics_v4.py) and the tables they read",
         f"MATCH (m:MetricGroup {{release: '{R}'}})\nOPTIONAL MATCH (m)-[:COMPUTED_FROM]->(t:Table)\n"
         "OPTIONAL MATCH (m)-[:DERIVED_FROM]->(src:MetricGroup)\nRETURN m.kind AS kind, m.name AS group, m.description AS description,\n"
         "       collect(DISTINCT t.qualified_name) AS tables, collect(DISTINCT src.name) AS built_from\nORDER BY kind, group;"),
        ("KAG-15", "Datasets the UI renders: dataset -> metric groups -> tables, and who sees them",
         f"MATCH (d:Dataset {{release: '{R}'}})\nOPTIONAL MATCH (d)-[:DERIVED_FROM]->(m:MetricGroup)\n"
         "OPTIONAL MATCH (p:Persona)-[:SEES]->(d)\nRETURN d.name AS dataset, d.caption AS caption, collect(DISTINCT m.name) AS groups, "
         "collect(DISTINCT p.name) AS seen_by\nORDER BY dataset;"),
        ("KAG-16", "Write-back flows (/api/v4/flow/*): what they write and read, and which UI triggers them",
         f"MATCH (f:Flow {{release: '{R}'}})\nOPTIONAL MATCH (ui)-[:TRIGGERS]->(f)\n"
         "RETURN f.path AS endpoint, f.method AS method, f.description AS does, f.writes AS writes, f.reads AS reads,\n"
         "       collect(DISTINCT coalesce(ui.ui_id, ui.name)) AS triggered_from\nORDER BY endpoint;"),
        ("KAG-17", "Data sources with load status (blocked ones say why) and the tables they load",
         f"MATCH (s:DataSource {{release: '{R}'}})\nOPTIONAL MATCH (s)-[:LOADS|FEEDS]->(t:Table)\n"
         "RETURN s.kind AS kind, s.name AS source, s.load_status AS status, s.blocked_reason AS why_blocked, s.record_count AS records,\n"
         "       collect(t.qualified_name) AS tables\nORDER BY kind, status, source;"),
        ("KAG-18", "Table inventory: schema, rows, columns, PRD plan, extension flags, origin, source feed",
         f"MATCH (t:Table {{release: '{R}'}})\nRETURN t.schema AS schema, t.name AS table, t.row_count AS rows, t.column_count AS columns,\n"
         "       t.planned_in_prd AS planned, t.extension_table AS extension_table, t.extension_columns AS extension_columns,\n"
         "       t.origin AS origin, t.source_feed AS feed, t.write_back AS write_back\nORDER BY schema, table;"),
        ("KAG-19", "Foreign keys (column to column)",
         f"MATCH (a:Table {{release: '{R}'}})-[:HAS_COLUMN]->(c:Column)-[r:REFERENCES]->(d:Column)<-[:HAS_COLUMN]-(b:Table)\n"
         "RETURN a.qualified_name AS table, c.name AS column, b.qualified_name AS references, d.name AS ref_column, r.constraint AS constraint\n"
         "ORDER BY table, column;"),
        ("KAG-20", "Synthetic reference tables derived from public data",
         f"MATCH (s:Table {{release: '{R}'}})-[:DERIVED_FROM]->(p:Table)\nOPTIONAL MATCH (src:DataSource)-[:LOADS]->(p)\n"
         "RETURN s.qualified_name AS synthetic_table, collect(DISTINCT p.qualified_name) AS from_public, collect(DISTINCT src.name) AS sources;"),
        ("KAG-21", "Impact of a table: which queries, metric groups, flows and personas depend on it (swap the table)",
         f"MATCH (t:Table {{release: '{R}', qualified_name: 'synthetic.appointment'}})\n"
         "OPTIONAL MATCH (q:Query)-[:READS]->(t) OPTIONAL MATCH (pq:Persona)-[:ASKS]->(q)\n"
         "OPTIONAL MATCH (m:MetricGroup)-[:COMPUTED_FROM]->(t) OPTIONAL MATCH (pm:Persona)-[:SEES]->(m)\n"
         "OPTIONAL MATCH (f:Flow)-[:WRITES]->(t)\n"
         "RETURN t.qualified_name AS table, collect(DISTINCT q.query_id) AS queries, collect(DISTINCT m.name) AS metric_groups,\n"
         "       collect(DISTINCT f.name) AS written_by, collect(DISTINCT coalesce(pq.name, pm.name)) AS personas;"),
        ("KAG-22", "The release node (what it was built from)",
         f"MATCH (r:Release {{release: '{R}'}}) RETURN r.name AS release, r.built_at AS built_at, r.git_commit AS git, r.sources AS sources;"),
    ]
    head = ["// " + "=" * 101,
            "// RAIN v0.4 knowledge graph (KAG) - persona and lineage queries for Neo4j Browser",
            "// Open http://localhost:17477/browser/ , connect URL bolt://localhost:17690 , user neo4j / password, database neo4j.",
            f"// Release '{R}' is the only content of the database: the PRD v0.4 seed (7 personas, signals, steps, success",
            "// metrics), the UI workbenches with persona access, every table of rain_v4 (synthetic,",
            "// public_data, ui_v4) with columns, keys and row counts, the data sources with load status, the computed metric",
            "// groups and datasets, the persona query pack and the write-back flows.",
            "// Generated by scripts/e2e/kag_v4_refresh.py (checks: doc/queries/RAIN_v4_kag_check.md).",
            "// " + "=" * 101, ""]
    body = []
    for qid, title, cypher in q:
        body += [f"// @id {qid:6s} {title}", cypher, ""]
    OUT_PACK.write_text("\n".join(head + body), encoding="utf-8", newline="\n")


# ─── main ───────────────────────────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="build and report, write nothing")
    ap.add_argument("--keep-legacy", action="store_true", help="do not delete the unreleased v1/v2 graph or other releases")
    ap.add_argument("--purge-unknown", action="store_true", help="also delete unreleased nodes with unexpected labels")
    ap.add_argument("--no-docs", action="store_true", help="publish and check, but do not rewrite the doc/ and artifacts/ files")
    args = ap.parse_args()
    t0 = time.time()
    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    git = os.getenv("RAIN_GIT_COMMIT", "")
    if not git:
        try:
            git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                 timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            pass
    git = git or "unknown (set RAIN_GIT_COMMIT)"
    print(f"== RAIN v0.4 KAG refresh -> release {RELEASE}")
    pg = pg_inventory()
    print(f"  postgres rain_v4: {len(pg['tables'])} tables, {len(pg['fks'])} foreign keys")
    sections, sections_src, ui_mod = ui_sections()
    print(f"  computed UI context from {sections_src}: " + ", ".join(f"{k} {len(v)}" for k, v in sections.items() if isinstance(v, dict)))
    templates, templates_src = ui_templates()
    group_names = set(sections.get("constants", {})) | set(sections.get("records", {})) | set(sections.get("governance", {}))
    inputs = {
        "pg": pg, "sections": sections, "ui_module": ui_mod, "templates": templates, "ddl": parse_ddl(),
        "derived": parse_public_derivations(), "pack": parse_pack(), "backend_ids": backend_persona_ids(),
        "flows": parse_flows(), "metric_code": parse_metric_code(), "workbenches": parse_workbenches(),
        "switcher": parse_switcher(), "usage": parse_frontend_usage(group_names), "loader": parse_loader(),
        "manifest": parse_manifest(), "built_at": built_at, "git": git,
    }
    rel = lambda p: str(p.relative_to(ROOT)).replace("\\", "/")  # noqa: E731
    inputs["sources_used"] = {
        "PRD seed": f"{rel(PATHS['seed'])} (sha {sha(PATHS['seed'])})",
        "ontology": f"{rel(PATHS['factory'])} ({'present' if PATHS['factory'].is_file() else 'missing: classes from Postgres only'}) "
                    f"+ {rel(PATHS['upper'])}",
        "postgres": f"rain_v4 {', '.join(SCHEMAS)}: {len(pg['tables'])} tables, {len(pg['fks'])} foreign keys (pg_catalog, exact counts)",
        "planned DDL": f"{rel(PATHS['ddl'])}: {len(inputs['ddl'])} planned tables",
        "computed context": f"{sections_src}; templates from {templates_src}",
        "query pack": f"{rel(PATHS['pack'])}: {len(inputs['pack'])} queries; backend PERSONA_IDS {len(inputs['backend_ids'])}",
        "flows": f"{rel(PATHS['flow'])}: {len(inputs['flows'])} endpoints",
        "frontend": f"WORKBENCHES {len(inputs['workbenches'])}, switcher personas {len(inputs['switcher'][0])}",
        "public manifest": f"{rel(PATHS['manifest'])} ({'present' if PATHS['manifest'].is_file() else 'missing'})",
    }
    g, notes = build(inputs)
    labels = Counter(n["labels"][0] for n in g.nodes.values())
    types = Counter(t for (_, t, _) in g.rels)
    print(f"  built {len(g.nodes)} nodes, {len(g.rels)} relationships")
    print("  nodes:", dict(labels.most_common()))
    print("  relationships:", dict(types.most_common()))
    for w in notes["warnings"]:
        print("  WARNING:", w)
    summary = {"release": RELEASE, "built_at": built_at, "git": git, "nodes": len(g.nodes), "relationships": len(g.rels),
               "labels": dict(labels.most_common()), "types": dict(types.most_common()), "warnings": notes["warnings"],
               "sources_used": inputs["sources_used"]}
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    driver = neo4j_driver()
    db = os.getenv("NEO4J_DATABASE", "neo4j")
    run_id = uuid.uuid4().hex[:12]
    with driver.session(database=db) as s:
        before = graph_state(s)
        print("  before:", json.dumps(before))
        prev = run(s, "MATCH (r:Release {release: $rel}) RETURN r.cleanup_log AS log", rel=RELEASE)
        cleanup_log = json.loads(prev[0]["log"]) if prev and prev[0]["log"] else []
        legacy = {"nodes": 0, "relationships": 0, "by_labels": {}}
        if not args.keep_legacy:
            legacy = purge_legacy(s, args.purge_unknown)
            print(f"  deleted the unreleased v1/v2 graph: {legacy['nodes']} nodes, {legacy['relationships']} relationships")
        stale = publish(s, g, run_id)
        print(f"  published {RELEASE} (run {run_id}); removed from an earlier run: {stale}")
        superseded = {"by_release": {}, "relationships": 0}
        if not args.keep_legacy:
            superseded = purge_superseded(s)
            print(f"  deleted superseded releases: {superseded}")
        if legacy["nodes"] or superseded["by_release"] or stale["stale_nodes_removed"] or stale["stale_relationships_removed"]:
            cleanup_log.append({"at": built_at, "run": run_id, "legacy": legacy, "superseded": superseded, "stale": stale})
        # the deletion history survives re-runs on the release node (publish rewrites its other properties)
        s.run("MATCH (r:Release {release: $rel}) SET r.cleanup_log = $log", rel=RELEASE,
              log=json.dumps(cleanup_log, sort_keys=True)).consume()
        after = graph_state(s)
        print("  after:", json.dumps(after))
        summary.update(before=before, after=after, deleted={"legacy": legacy, "superseded": superseded, "stale": stale},
                       cleanup_log=cleanup_log, nodes=after["nodes"], relationships=after["relationships"])
        pg_counts = {k: v["row_count"] for k, v in pg_inventory()["tables"].items()}
        n_personas = len(PERSONAS)
        results = run_checks(s, n_personas, len(inputs["pack"]), pg_counts)
    driver.close()
    for r in results:
        print(f"  {r['id']} {'info' if r['ok'] is None else ('PASS' if r['ok'] else 'FAIL')}: {r['title']}"
              + ("" if r["ok"] is not False else f" -> {json.dumps(r['rows'], default=str)[:400]}"))
    summary["checks"] = [{k: r[k] for k in ("id", "title", "ok", "rows")} for r in results]
    if not args.no_docs:
        write_check_doc(results, summary)
        write_browser_pack()
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
        print(f"  wrote {OUT_CHECK.relative_to(ROOT)}, {OUT_PACK.relative_to(ROOT)}, {OUT_JSON.relative_to(ROOT)}")
    print(f"  done in {time.time() - t0:.1f}s")
    return 0 if all(r["ok"] is not False for r in results) else EXIT_CHECKS_FAILED


if __name__ == "__main__":
    sys.exit(main())
