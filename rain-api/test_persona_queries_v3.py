"""GET /api/v3/queries: every persona's synthetic and public data queries run and return rows.

Needs the rain_v3 database (synthetic + public_data schemas); the run tests are skipped without it.
Run from rain-api/:  python -m pytest test_persona_queries_v3.py -q
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import persona_queries_v3 as pq

app = FastAPI()
app.include_router(pq.router, prefix="/api/v3/queries")
client = TestClient(app)
IDS = sorted(pq._pack())


def _db_ready() -> bool:
    try:
        with pq._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM synthetic.patient")
            return cur.fetchone()[0] > 0
    except Exception:
        return False


def test_pack_has_five_synthetic_and_five_public_per_persona():
    body = client.get("/api/v3/queries").json()
    assert body["count"] == 60
    for persona in pq.PERSONA_IDS:
        mine = client.get("/api/v3/queries", params={"persona": persona}).json()["queries"]
        assert sum(q["data"] == "synthetic" for q in mine) == 5, persona
        assert sum(q["data"] == "public" for q in mine) == 5, persona
        assert all(q["url"] == f"/api/v3/queries/{q['id']}" and q["question"] for q in mine)


def test_unknown_persona_and_query_are_404():
    assert client.get("/api/v3/queries", params={"persona": "nobody"}).status_code == 404
    assert client.get("/api/v3/queries/NOPE-1").status_code == 404


@pytest.mark.skipif(not _db_ready(), reason="rain_v3 database not reachable")
@pytest.mark.parametrize("query_id", IDS)
def test_query_runs_and_returns_rows(query_id):
    r = client.get(f"/api/v3/queries/{query_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rowCount"] > 0 and len(body["rows"]) == body["rowCount"]
    assert r.headers["X-RAIN-Query-Id"] == query_id
    schema = "synthetic" if body["data"] == "synthetic" else "public_data"
    assert r.headers["X-RAIN-Data-Source"] == f"postgres://rain_v3/{schema}"
    assert schema in body["sql"]
