"""The chat answers persona queries: typing a query's question (or its id) runs it on the backend.

POST /api/v4/ui/ask with a persona query's question returns a turn built from a live run of that query
(a data_table of rain_v4 rows) that satisfies the app's AiTurn and data_table schemas. Scripted chips
keep their recorded answers. Needs the rain_v4 database; skipped without it.
Run from rain-api/:  python -m pytest test_chat_queries_v4.py -q
"""
import json
from pathlib import Path

import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import persona_queries_v4 as pq
import ultra_v4_api

app = FastAPI()
app.include_router(ultra_v4_api.router, prefix="/api/v4/ui")
client = TestClient(app)

CATALOG = json.loads((Path(ultra_v4_api.FIXTURES_DIR) / "catalog.json").read_text(encoding="utf-8"))
TURN = jsonschema.validators.validator_for(CATALOG["response"]["schema"])(CATALOG["response"]["schema"])
TABLE_SCHEMA = next(c for c in CATALOG["components"] if c["type"] == "data_table")["props"]
TABLE = jsonschema.validators.validator_for(TABLE_SCHEMA)(TABLE_SCHEMA)
# Every persona's queries, asked in that persona's chat. The patient chats as rain_linda; the pack keeps her own
# id (pq.PERSONA_ALIASES).
APP_ID = {pack: app for app, pack in pq.PERSONA_ALIASES.items()}
QUERIES = sorted(pq._pack().values(), key=lambda q: q["id"])


def _db_ready() -> bool:
    try:
        with pq._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM synthetic.patient")
            return cur.fetchone()[0] > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="rain_v4 database not reachable")


def ask(persona: str, text: str):
    r = client.post("/api/v4/ui/ask", json={"clientId": "rain", "personaId": persona, "input": text})
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
    assert r.headers["X-RAIN-Data-Source"].startswith("postgres://rain_v4/")


@needs_db
@pytest.mark.parametrize("q", QUERIES, ids=lambda q: q["id"])
def test_typing_the_question_runs_the_query(q):
    assert_query_turn(ask(APP_ID.get(q["persona"], q["persona"]), q["question"]), q["id"])


@needs_db
def test_id_partial_and_reworded_questions():
    assert_query_turn(ask("rain_ceo", "CEO-P1"), "CEO-P1")
    assert_query_turn(ask("rain_ceo", "run cmo-p2 please"), "CMO-P2")
    assert_query_turn(ask("rain_ceo", "Profile of the six counties we serve"), "CEO-P1")
    assert_query_turn(ask("rain_ceo", "profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability"), "CEO-P1")
    assert_query_turn(ask("rain_state", "households without internet by county for broadband"), "STATE-P4")
    assert_query_turn(ask("rain_access", "ACCESS-P2"), "ACCESS-P2")
    assert_query_turn(ask("rain_chw", "which primary care practices are in our towns"), "CHW-P5")


def test_scripted_chips_keep_their_recorded_answers():
    assert ask("rain_ceo", "Where is the low-value care?").json()["id"] == "ceo_lvc"
    assert ask("rain_ceo", "Compare our sites on cost per member").json()["id"] == "ceo_sites"
    # a query whose question duplicates a scripted one: loosely typed → the scripted answer
    assert ask("rain_ceo", "Hi RAIN, compare our sites on cost per member please").json()["id"] == "ceo_sites"
    assert ask("rain_state", "Show me the county view").json()["id"] == "st_county"


def test_off_topic_still_gets_the_default_answer():
    assert ask("rain_ceo", "What is the weather in Reno tomorrow?").json()["id"] == "__default__"


# ─── Which pack query a chat input finds (no database: the pack file only) ─────────────────────────────

def _found(persona, text, level):
    q = pq.find_query(persona, text, level)
    return q["id"] if q else None


@pytest.mark.parametrize("patient", ["rain_linda", "patient_linda_garcia"])
def test_the_patient_finds_only_her_own_queries(patient):
    pack = pq._pack()
    # her own queries, by id and by question
    assert _found(patient, "GAR-S1", "exact") == "GAR-S1"
    assert _found(patient, pack["GAR-S3"]["question"], "exact") == "GAR-S3"
    # never an operator's: not by id, not by question, not loosely. The same words may find her OWN query.
    for qid in ("CEO-S1", "CHW-S2", "ACCESS-S2", "STATE-P1"):
        assert _found(patient, qid, "exact") is None, qid
        for text, level in ((pack[qid]["question"], "exact"), (pack[qid]["question"], "close"),
                            (pack[qid]["question"].lower().rstrip("?"), "fuzzy")):
            found = _found(patient, text, level)
            assert found is None or found.startswith("GAR-"), (qid, level, found)
    # how a patient types: first person, short
    assert (_found(patient, "show my visits", "close") or _found(patient, "show my visits", "fuzzy")) == "GAR-S1"


def test_only_the_seven_personas_have_queries():
    pack = pq._pack()
    assert {q["persona"] for q in pack.values()} == set(pq.PERSONA_IDS)
    for gone in ("HAR-S1", "BEL-S1", "HOL-S1", "BRK-S1", "OKA-S1", "ROS-S1", "HAN-S1"):
        assert gone not in pack
        assert _found("rain_ceo", gone, "exact") is None


# ─── The patient persona in the chat ───────────────────────────────────────────────────────────────────

def test_the_patient_answers_her_scripted_chips():
    assert ask("rain_linda", "When is my next visit?").json()["id"] == "lg_visit"
    assert ask("rain_linda", "how do i reach the clinic").json()["id"] == "lg_contact"


@needs_db
@pytest.mark.parametrize("persona,text", [("rain_linda", "CEO-S1"), ("rain_linda", "CHW-S1"), ("rain_linda", "ACCESS-S2"),
                                          ("rain_linda", "Who is on the BP campaign list?")])
def test_the_patient_never_gets_other_members_rows_in_the_chat(persona, text):
    turn = ask(persona, text).json()
    # the generic answer, or (for a query that exists) an answer that says why it is not run; never a table of rows
    assert turn["id"] == "__default__" or turn["id"].startswith("query:refused:"), (persona, text, turn["id"])
    assert not [c for c in turn["components"] if c["type"] == "data_table"], (persona, text)
    if turn["id"].startswith("query:refused:"):
        assert "not" in turn["text"] and turn["chips"], turn


@needs_db
def test_the_patients_answers_name_no_other_member():
    brief = client.get("/api/v4/ui/briefing", params={"clientId": "rain", "personaId": "rain_linda"}).json()
    texts = json.dumps(brief, ensure_ascii=False)
    for chip in brief["chips"]:
        texts += json.dumps(ask("rain_linda", chip).json(), ensure_ascii=False)
    assert "M-4" not in texts.replace("Linda Garcia", "")
