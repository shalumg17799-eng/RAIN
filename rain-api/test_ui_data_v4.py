"""GET /api/v4/ui/data: every number computed per request from rain_v4 rows, live public figures, proof headers.

No number is stored: ui_v4.dataset holds configuration and the persona templates only; metrics_v4 computes
constants/records/governance/datasets from rain_v4.synthetic and rain_v4.public_data. Needs the database
(the generator and deploy/scripts/load_ui_data_v4.py); skipped otherwise.
Run from rain-api/:  python -m pytest test_ui_data_v4.py -q
"""
import hashlib
import os
import time

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import metrics_v4
import ui_data_v4

app = FastAPI()
app.include_router(ui_data_v4.router, prefix="/api/v4/ui")
client = TestClient(app)


def _admin():
    return psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user="postgres", password="root")


def _one(sql, args=()):
    with ui_data_v4._conn() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()[0]


def _db_ready() -> bool:
    try:
        return _one("SELECT count(*) FROM ui_v4.dataset WHERE client_id = 'rain' AND section = 'templates'") > 0 \
            and _one("SELECT count(*) FROM synthetic.patient") > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="rain_v4 synthetic data or ui_v4 templates not loaded")


@pytest.fixture(scope="module")
def response():
    return client.get("/api/v4/ui/data", params={"clientId": "rain"})


def test_serves_every_section_computed_from_rows(response):
    assert response.status_code == 200
    body = response.json()
    assert set(body["sections"]) >= {"contracts", "personas", "constants", "records", "governance", "geo",
                                     "sources", "capabilities", "datasets"}
    db = body["meta"]["database"]
    assert db["computedFrom"] == ["synthetic", "public_data"] and db["configTable"] == "ui_v4.dataset"
    assert set(body["sections"]["contracts"]) == set(metrics_v4.CONFIG["personas"])
    assert set(body["sections"]["personas"]) == set(metrics_v4.CONFIG["personas"])
    rec = body["sections"]["records"]
    assert len(rec["campaignMembers"]) == _one("SELECT count(*) FROM synthetic.campaign_member WHERE campaign_id = 'BP2026'")
    assert "inboxItems" not in rec and "previsitSummaries" not in rec     # their workbenches were removed with their personas
    assert list(body["sections"]["constants"]["PERSONAS"].values()) == [
        "rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access", "rain_linda"]


def test_no_number_is_stored_in_ui_v4():
    with ui_data_v4._conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT section FROM ui_v4.dataset WHERE client_id = 'rain'")
        sections = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT payload::text FROM ui_v4.dataset WHERE client_id = 'rain' AND section = 'templates' AND key = 'contracts'")
        contracts = cur.fetchone()[0]
    assert not sections & {"constants", "records", "governance", "datasets", "contracts", "personas"}
    assert "{{ constants.CONTRACT.actualPmpm" in contracts.replace("{{constants", "{{ constants")


def test_contract_numbers_are_sql_over_the_rows(response):
    c = response.json()["sections"]["constants"]["CONTRACT"]
    members = _one("SELECT count(*) FROM synthetic.patient WHERE network_id = 'sbch'")
    spend = float(_one("""SELECT sum(c.allowed_amount) FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
                          WHERE p.network_id = 'sbch' AND c.service_date BETWEEN '2026-01-01' AND '2026-09-30'"""))
    expected = float(_one("SELECT expected_pmpm FROM synthetic.contract_benchmark WHERE network_id = 'sbch' AND contract_year = 2026"))
    assert c["members"] == members
    assert c["actualPmpm"] == round(spend / (members * 9))
    assert c["expectedPmpm"] == round(expected)
    kpis = {k["id"]: k for k in response.json()["sections"]["contracts"]["ceo"]["kpis"]}
    assert kpis["pmpm"]["value"] == f"${c['actualPmpm']} / ${c['expectedPmpm']}"


def test_proof_headers_and_checksum(response):
    h = response.headers
    assert h["X-RAIN-Data-Source"].startswith("postgres://rain_v4/synthetic + public_data")
    assert h["X-RAIN-Request-Id"] and h["X-RAIN-Server"]
    assert h["X-RAIN-Data-Sha256"] == hashlib.sha256(response.content).hexdigest()
    assert h["Server-Timing"].startswith("db;dur=")


def test_county_public_fields_are_live_public_data(response):
    counties = {c["id"]: c for c in response.json()["sections"]["constants"]["COUNTIES"]}
    white_pine_htn = _one("""SELECT data_value FROM public_data.cdc_places WHERE locationid = 32033
                             AND measureid = 'BPHIGH' AND data_value_type = 'Crude prevalence' ORDER BY year DESC LIMIT 1""")
    pershing_svi = _one("SELECT rpl_themes FROM public_data.svi_county WHERE fips = 32027")
    lander_bb = _one("SELECT pct_households_broadband FROM public_data.acs_county WHERE county_fips = 32015")
    assert counties["whitePine"]["htnPct"] == round(white_pine_htn, 1)
    assert counties["pershing"]["svi"] == round(pershing_svi, 2)
    assert counties["lander"]["broadbandPct"] == round(lander_bb)
    assert counties["elko"]["hpsa"] == "Part of county"      # HRSA: County Subdivision components
    assert counties["lander"]["hpsa"] == "Whole county"      # HRSA: Single County
    assert counties["lander"]["chr"]["preventableStays"] == round(
        _one("SELECT v005_rawvalue FROM public_data.county_health_rankings WHERE fipscode = 32015"))


def test_live_source_counts(response):
    live = [s for s in response.json()["sections"]["sources"]["PUBLIC_SOURCES"] if s.get("live")]
    assert {s["id"] for s in live} >= {"rain-places", "rain-svi", "rain-hpsa", "rain-rucc", "rain-zcta", "rain-chr",
                                       "rain-hrsaSites", "rain-nppes", "rain-acs", "rain-forhp", "rain-boundaries",
                                       "rain-cmsHospital", "rain-cmsPos", "rain-uds", "rain-ecqm", "rain-osm"}
    assert all(s["recordCount"] > 0 and s["table"].startswith("public_data.") for s in live)
    syn = [s for s in response.json()["sections"]["sources"]["SYNTHETIC_SOURCES"] if s.get("live")]
    assert syn and all(s["recordCount"] > 0 for s in syn)


def test_blocked_sources_say_so_instead_of_illustrative_counts(response):
    by_id = {s["id"]: s for s in response.json()["sections"]["sources"]["PUBLIC_SOURCES"]}
    for sid in ("rain-fcc", "rain-geovar"):
        assert by_id[sid]["recordCount"] == 0 and by_id[sid]["freshness"].startswith("Not loaded yet"), sid


def test_editing_a_source_row_changes_the_next_response():
    """Any writer (psql, pgAdmin, the flow): the cache sees the change and the numbers are recomputed."""
    def expected_now():
        c = client.get("/api/v4/ui/data", params={"clientId": "rain"}).json()["sections"]["constants"]["CONTRACT"]
        return c["expectedPmpm"], c["abovePct"]

    before = expected_now()
    conn = _admin()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE synthetic.contract_benchmark SET expected_pmpm = expected_pmpm + 8 WHERE network_id = 'sbch'")
        conn.close()
        time.sleep(1.5)
        after = expected_now()
        assert after[0] == before[0] + 8 and after[1] < before[1]
    finally:
        conn = _admin()
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE synthetic.contract_benchmark SET expected_pmpm = expected_pmpm - 8 WHERE network_id = 'sbch'")
        conn.close()
    time.sleep(1.5)
    assert expected_now() == before


def test_unknown_client_is_404():
    assert client.get("/api/v4/ui/data", params={"clientId": "nobody"}).status_code == 404
