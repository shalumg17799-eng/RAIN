"""The chat is data-driven: change the data in Postgres and the very next answer changes (no restart, no files).

Edits contracts.ceo (an answer's text) and datasets.lv_top5 (a table the CMO's answer draws) in
rain_v3.ui_v3.dataset, asks through POST /api/v3/ui/ask, then restores both. Needs the database.
Run from rain-api/:  python -m pytest test_chat_v3_live.py -q
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg2.extras import Json

import ui_data_v3
import ultra_v3_api

app = FastAPI()
app.include_router(ultra_v3_api.router, prefix="/api/v3/ui")
client = TestClient(app)
ADMIN = dict(user="postgres", password="root")


def _admin():
    import os
    import psycopg2
    return psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V3", "rain_v3"), **ADMIN)


def _db_ready() -> bool:
    try:
        ui_data_v3.load_sections("rain")
        with _admin():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="rain_v3.ui_v3.dataset not reachable")


def _get(section, key):
    with _admin() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload FROM ui_v3.dataset WHERE client_id='rain' AND section=%s AND key=%s", (section, key))
        return cur.fetchone()[0]


def _put(section, key, payload):
    with _admin() as conn, conn.cursor() as cur:
        cur.execute("UPDATE ui_v3.dataset SET payload=%s WHERE client_id='rain' AND section=%s AND key=%s",
                    (Json(payload), section, key))


def ask(persona, text):
    r = client.post("/api/v3/ui/ask", json={"clientId": "rain", "personaId": persona, "input": text})
    assert r.status_code == 200, r.text
    return r


def test_answer_text_follows_the_contract_in_the_database():
    original = _get("contracts", "ceo")
    try:
        edited = json.loads(json.dumps(original))
        edited["steps"]["ceo_gap"]["ai"] = "EDITED IN POSTGRES: the gap answer now comes from the database."
        _put("contracts", "ceo", edited)
        r = ask("rain_ceo", "Break down the gap")
        assert r.json()["id"] == "ceo_gap"
        assert r.json()["text"] == "EDITED IN POSTGRES: the gap answer now comes from the database."
        assert r.headers["X-RAIN-Data-Source"].startswith("postgres://rain_v3/ui_v3.dataset (contracts.ceo")
    finally:
        _put("contracts", "ceo", original)
    assert ask("rain_ceo", "Break down the gap").json()["text"].startswith("The $26 PMPM gap")


def test_answer_table_follows_the_dataset_in_the_database():
    original = _get("datasets", "lv_top5")
    try:
        edited = json.loads(json.dumps(original))
        edited["rows"][0]["measure"] = "EDITED IN POSTGRES"
        _put("datasets", "lv_top5", edited)
        turn = ask("rain_ceo", "Where is the low-value care?").json()
        assert turn["id"] == "ceo_lvc"
        assert "EDITED IN POSTGRES" in json.dumps(turn), "the answer did not draw the edited dataset"
    finally:
        _put("datasets", "lv_top5", original)


def test_public_figures_in_answers_are_live():
    """The State persona's county context answer reads the live HRSA shortage-area status."""
    turn = ask("rain_state", "Humboldt County: what changed since January?").json()
    stats = {s["props"]["label"]: s["props"]["value"] for s in turn["components"][0]["props"]["children"]}
    sections, *_ = ui_data_v3.load_sections("rain")
    humboldt = next(c for c in sections["constants"]["COUNTIES"] if c["id"] == "humboldt")
    assert stats["Shortage area"] == humboldt["hpsa"] == "Whole county"   # recorded fixture said "Part of county"
