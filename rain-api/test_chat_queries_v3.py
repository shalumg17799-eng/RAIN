"""The chat answers persona queries: typing a query's question (or its id) runs it on the backend.

POST /api/v3/ui/ask with a persona query's question returns a turn built from a live run of that query
(a data_table of rain_v3 rows) that satisfies the app's AiTurn and data_table schemas. Scripted chips
keep their recorded answers. Needs the rain_v3 database; skipped without it.
Run from rain-api/:  python -m pytest test_chat_queries_v3.py -q
"""
import json
from pathlib import Path

import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import persona_queries_v3 as pq
import ultra_v3_api

app = FastAPI()
app.include_router(ultra_v3_api.router, prefix="/api/v3/ui")
client = TestClient(app)

CATALOG = json.loads((Path(ultra_v3_api.FIXTURES_DIR) / "catalog.json").read_text(encoding="utf-8"))
TURN = jsonschema.validators.validator_for(CATALOG["response"]["schema"])(CATALOG["response"]["schema"])
TABLE_SCHEMA = next(c for c in CATALOG["components"] if c["type"] == "data_table")["props"]
TABLE = jsonschema.validators.validator_for(TABLE_SCHEMA)(TABLE_SCHEMA)
QUERIES = sorted(pq._pack().values(), key=lambda q: q["id"])


def _db_ready() -> bool:
    try:
        with pq._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM synthetic.patient")
            return cur.fetchone()[0] > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="rain_v3 database not reachable")


def ask(persona: str, text: str):
    r = client.post("/api/v3/ui/ask", json={"clientId": "rain", "personaId": persona, "input": text})
    assert r.status_code == 200, r.text
    return r


def assert_query_turn(r, query_id: str):
    turn = r.json()
    assert turn["id"] == f"query:{query_id}"
    assert not list(TURN.iter_errors(turn)), [e.message for e in TURN.iter_errors(turn)]
    table = turn["components"][0]
    assert table["type"] == "data_table"
    assert not list(TABLE.iter_errors(table["props"])), [e.message for e in TABLE.iter_errors(table["props"])]
    assert table["props"]["rows"], "no rows"
    assert r.headers["X-RAIN-Turn"] == f"query:{query_id}"
    assert r.headers["X-RAIN-Data-Source"].startswith("postgres://rain_v3/")


@needs_db
@pytest.mark.parametrize("q", QUERIES, ids=lambda q: q["id"])
def test_typing_the_question_runs_the_query(q):
    assert_query_turn(ask(q["persona"], q["question"]), q["id"])


@needs_db
def test_id_partial_and_reworded_questions():
    assert_query_turn(ask("rain_ceo", "CEO-P1"), "CEO-P1")
    assert_query_turn(ask("rain_ceo", "run cmo-p2 please"), "CMO-P2")
    assert_query_turn(ask("rain_ceo", "Profile of the six counties we serve"), "CEO-P1")
    assert_query_turn(ask("rain_ceo", "profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability"), "CEO-P1")
    assert_query_turn(ask("rain_state", "households without internet by county for broadband"), "STATE-P4")


def test_scripted_chips_keep_their_recorded_answers():
    assert ask("rain_ceo", "Where is the low-value care?").json()["id"] == "ceo_lvc"
    assert ask("rain_ceo", "Compare our sites on cost per member").json()["id"] == "ceo_sites"
    # a query whose question duplicates a scripted one: loosely typed → the scripted answer
    assert ask("rain_ceo", "Hi RAIN, compare our sites on cost per member please").json()["id"] == "ceo_sites"
    assert ask("rain_state", "Show me the county view").json()["id"] == "st_county"


def test_off_topic_still_gets_the_default_answer():
    assert ask("rain_ceo", "What is the weather in Reno tomorrow?").json()["id"] == "__default__"
