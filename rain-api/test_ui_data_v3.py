"""GET /api/v3/ui/data: the whole UI data set from Postgres, with live public figures and proof headers.

Needs the rain_v3 database with ui_v3.dataset loaded (deploy/scripts/load_ui_data.py); skipped otherwise.
Run from rain-api/:  python -m pytest test_ui_data_v3.py -q
"""
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ui_data_v3

app = FastAPI()
app.include_router(ui_data_v3.router, prefix="/api/v3/ui")
client = TestClient(app)


def _db_ready() -> bool:
    try:
        with ui_data_v3._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ui_v3.dataset WHERE client_id = 'rain'")
            return cur.fetchone()[0] > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="rain_v3.ui_v3.dataset not loaded")


@pytest.fixture(scope="module")
def response():
    return client.get("/api/v3/ui/data", params={"clientId": "rain"})


def test_serves_every_section_from_postgres(response):
    assert response.status_code == 200
    body = response.json()
    assert set(body["sections"]) >= {"contracts", "personas", "constants", "records", "governance", "geo",
                                     "sources", "capabilities", "datasets"}
    assert body["meta"]["database"]["table"] == "ui_v3.dataset"
    assert body["meta"]["database"]["rows"] == sum(len(v) for v in body["sections"].values())
    assert len(body["sections"]["records"]["campaignMembers"]) == 412
    assert set(body["sections"]["contracts"]) == {"ceo", "cmo", "cio", "state", "chw", "access"}


def test_proof_headers_and_checksum(response):
    h = response.headers
    assert h["X-RAIN-Data-Source"].startswith("postgres://rain_v3/ui_v3.dataset")
    assert h["X-RAIN-Request-Id"] and h["X-RAIN-Server"]
    assert h["X-RAIN-Data-Sha256"] == hashlib.sha256(response.content).hexdigest()
    assert h["Server-Timing"].startswith("db;dur=")


def test_county_public_fields_are_live_public_data(response):
    counties = {c["id"]: c for c in response.json()["sections"]["constants"]["COUNTIES"]}
    with ui_data_v3._conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT data_value FROM public_data.cdc_places WHERE locationid = 32033
                       AND measureid = 'BPHIGH' AND data_value_type = 'Crude prevalence' ORDER BY year DESC LIMIT 1""")
        white_pine_htn = cur.fetchone()[0]
        cur.execute("SELECT rpl_themes FROM public_data.svi_county WHERE fips = 32027")
        pershing_svi = cur.fetchone()[0]
    assert counties["whitePine"]["htnPct"] == round(white_pine_htn, 1)
    assert counties["pershing"]["svi"] == round(pershing_svi, 2)
    assert counties["elko"]["hpsa"] == "Part of county"      # HRSA: County Subdivision components
    assert counties["lander"]["hpsa"] == "Whole county"      # HRSA: Single County
    assert all(c.get("publicSources") for c in counties.values())


def test_live_source_counts(response):
    live = [s for s in response.json()["sections"]["sources"]["PUBLIC_SOURCES"] if s.get("live")]
    assert {s["id"] for s in live} == {"rain-places", "rain-svi", "rain-hpsa", "rain-rucc", "rain-zcta",
                                       "rain-hrsaSites", "rain-nppes"}
    assert all(s["recordCount"] > 0 and s["table"].startswith("public_data.") for s in live)


def test_unknown_client_is_404():
    assert client.get("/api/v3/ui/data", params={"clientId": "nobody"}).status_code == 404
