"""The chat is computed from rows: change a source row in Postgres and the very next answer changes (no restart,
no files, nothing stored in ui_v4).

Edits synthetic.contract_benchmark (the CEO's gap answer text) and synthetic.low_value_measure (a table an
answer draws), asks through POST /api/v4/ui/ask, then restores each row. Needs the database. Run from rain-api/:  python -m pytest test_chat_v4_live.py -q
"""
import json
import os
import time

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ui_data_v4
import ultra_v4_api

app = FastAPI()
app.include_router(ultra_v4_api.router, prefix="/api/v4/ui")
client = TestClient(app)


def _sql(sql, args=()):
    conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user="postgres", password="root")
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone() if cur.description else None
    finally:
        conn.close()
        time.sleep(1.5)      # Postgres publishes the change counters the metrics cache watches about once a second


def _db_ready() -> bool:
    try:
        ui_data_v4.load_sections("rain")
        _sql("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="rain_v4 not reachable")


def ask(persona, text):
    r = client.post("/api/v4/ui/ask", json={"clientId": "rain", "personaId": persona, "input": text})
    assert r.status_code == 200, r.text
    return r


def test_answer_text_follows_the_rows():
    before = ask("rain_ceo", "Break down the gap").json()
    assert before["id"] == "ceo_gap"
    try:
        _sql("UPDATE synthetic.contract_benchmark SET expected_pmpm = expected_pmpm + 8 WHERE network_id = 'sbch'")
        after = ask("rain_ceo", "Break down the gap").json()
        assert after["id"] == "ceo_gap" and after["text"] != before["text"]
        gap_before = int(before["text"].split("$")[1].split()[0])
        assert f"${gap_before - 8} PMPM" in after["text"]
    finally:
        _sql("UPDATE synthetic.contract_benchmark SET expected_pmpm = expected_pmpm - 8 WHERE network_id = 'sbch'")
    assert ask("rain_ceo", "Break down the gap").json()["text"] == before["text"]


def test_answer_table_follows_the_rows():
    name = _sql("SELECT measure_name FROM synthetic.low_value_measure WHERE measure_id = 'LV01'")[0]
    try:
        _sql("UPDATE synthetic.low_value_measure SET measure_name = 'EDITED IN POSTGRES' WHERE measure_id = 'LV01'")
        turn = ask("rain_ceo", "Where is the low-value care?").json()
        assert turn["id"] == "ceo_lvc"
        assert "EDITED IN POSTGRES" in json.dumps(turn), "the answer did not draw the edited row"
    finally:
        _sql("UPDATE synthetic.low_value_measure SET measure_name = %s WHERE measure_id = 'LV01'", (name,))


def test_public_figures_in_answers_are_live():
    """The State persona's county context answer reads the live HRSA shortage-area status."""
    turn = ask("rain_state", "Humboldt County: what changed since January?").json()
    stats = {s["props"]["label"]: s["props"]["value"] for s in turn["components"][0]["props"]["children"]}
    sections, *_ = ui_data_v4.load_sections("rain")
    humboldt = next(c for c in sections["constants"]["COUNTIES"] if c["id"] == "humboldt")
    assert stats["Shortage area"] == humboldt["hpsa"]
