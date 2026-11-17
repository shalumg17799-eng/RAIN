"""/api/v4/ui2: the new Ultra UI (frontend/ultra-rain-v2) on the v0.4 data, additive to /api/v4/ui.

Checks that the new UI's data is the v0.4 data plus only the documented extras, that /api/v4/ui does not see the
extras, that Linda's contract is filled from her computed record, and that every persona's briefing and scripted
chips answer. Needs the database (rain_v4 synthetic data, the v0.4 templates and the rain_ui2 rows from
deploy/scripts/load_ui2_data_v4.py); skipped otherwise.
Run from rain-api/:  python -m pytest test_ui2_v4.py -q
"""
import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ui2_v4
import ui_data_v4

app = FastAPI()
app.include_router(ui_data_v4.router, prefix="/api/v4/ui")
app.include_router(ui2_v4.router, prefix="/api/v4/ui2")
client = TestClient(app)

NEW_DATASETS = {"pmpm_trend", "winnemucca_trend", "quality_gate", "pc_trend", "banner_pending_fix", "banner_freshness"}
RETIRED = {"rain.pmpm_trend", "rain.quality_tracker", "rain.annotated_trend", "rain.pc_trend", "rain.banner_preview"}
OPERATORS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"]


def _db_ready() -> bool:
    try:
        with ui_data_v4._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ui_v4.dataset WHERE client_id = %s", (ui2_v4.OVERLAY_CLIENT_ID,))
            return cur.fetchone()[0] > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="rain_v4 or the rain_ui2 rows are not loaded")


@pytest.fixture(scope="module")
def both():
    v4 = client.get("/api/v4/ui/data", params={"clientId": "rain"})
    v2 = client.get("/api/v4/ui2/data", params={"clientId": "rain"})
    assert v4.status_code == 200 and v2.status_code == 200
    return v4.json()["sections"], v2.json(), v2.headers


def test_proof_headers_and_meta(both):
    _v4, body, headers = both
    for h in ("X-RAIN-Request-Id", "X-RAIN-Data-Sha256", "X-RAIN-Data-Source", "Server-Timing"):
        assert headers.get(h), h
    assert body["meta"]["ui"] == "ultra-rain-v2"
    assert body["meta"]["database"]["uiClientId"] == "rain_ui2"


def test_v4_ui_does_not_see_the_extras(both):
    v4, _body, _h = both
    assert "patient" not in v4["contracts"] and "linda" in v4["contracts"]
    assert "PATIENT_PERSONA_ID" not in v4["constants"] and "PC_TREND" not in v4["constants"]
    assert not NEW_DATASETS & set(v4["datasets"])
    assert v4["contracts"]["ceo"]["viz"]["v_gate"]["type"] == "rain.quality_tracker"
    assert len(v4["sources"]["SYNTHETIC_SOURCES"]) == v4["constants"]["MODEL"]["syntheticSources"]


def test_v2_is_v4_plus_only_the_documented_extras(both):
    v4, body, _h = both
    v2 = body["sections"]
    # untouched sections are identical
    for name in ("records", "governance", "geo", "capabilities", "client"):
        assert v2[name] == v4[name], name
    assert v2["sources"]["PUBLIC_SOURCES"] == v4["sources"]["PUBLIC_SOURCES"]
    assert v2["sources"]["ENGINES"] == v4["sources"]["ENGINES"]
    assert v2["sources"]["SYNTHETIC_SOURCES"][:len(v4["sources"]["SYNTHETIC_SOURCES"])] == v4["sources"]["SYNTHETIC_SOURCES"]
    assert {s["id"] for s in v2["sources"]["SYNTHETIC_SOURCES"][len(v4["sources"]["SYNTHETIC_SOURCES"]):]} == \
        {"rain-mobileClinic", "rain-rides", "rain-pharmacy", "rain-avs"}
    # datasets: every v0.4 dataset as computed, plus the six stacks
    assert {k: v for k, v in v2["datasets"].items() if k in v4["datasets"]} == v4["datasets"]
    assert set(v2["datasets"]) - set(v4["datasets"]) == NEW_DATASETS
    # constants: only the documented keys differ
    changed = {k for k in v4["constants"] if v2["constants"].get(k) != v4["constants"][k]}
    assert changed == {"PERSONAS", "LINDA", "MODEL"}, changed
    assert set(v2["constants"]) - set(v4["constants"]) == {"PATIENT_PERSONA_ID", "PC_TREND"}
    linda4, linda2 = v4["constants"]["LINDA"], v2["constants"]["LINDA"]
    assert all(linda2[k] == v for k, v in linda4.items() if k != "visit")
    assert {k: v for k, v in linda2["visit"].items() if k in linda4["visit"]} == linda4["visit"]
    model4 = copy.deepcopy(v4["constants"]["MODEL"])
    model4["syntheticSources"] = len(v2["sources"]["SYNTHETIC_SOURCES"])
    assert v2["constants"]["MODEL"] == model4


def test_contracts_carry_the_new_visuals(both):
    v4, body, _h = both
    v2 = body["sections"]
    assert set(v2["contracts"]) == {"ceo", "cmo", "cio", "state", "chw", "access", "patient"}
    expected = {("ceo", "v_gate"): "quality_gate", ("ceo", "v_pmpm_trend"): "pmpm_trend",
                ("cmo", "v_gate"): "quality_gate", ("cmo", "v_winnemucca_trend"): "winnemucca_trend",
                ("cio", "v_banner"): "banner_pending_fix", ("cio", "v_freshness_banner"): "banner_freshness",
                ("state", "v_trend"): "pc_trend"}
    for (p, viz), dataset in expected.items():
        assert v2["contracts"][p]["viz"][viz] == {"type": "stack", "props": {"dataset": dataset}}
    for p in ("ceo", "cmo", "cio", "state", "chw", "access"):
        c2, c4 = copy.deepcopy(v2["contracts"][p]), copy.deepcopy(v4["contracts"][p])
        for (q, viz) in expected:
            if q == p:
                c2["viz"].pop(viz), c4["viz"].pop(viz)
        if p == "cio":
            k2 = next(k for k in c2["kpis"] if k["id"] == "sources")
            m = v2["constants"]["MODEL"]
            assert k2["value"] == f"{m['publicSources']} public + {m['syntheticSources']} synthetic"
            k2["value"] = next(k for k in c4["kpis"] if k["id"] == "sources")["value"]
        assert c2 == c4, p


def test_patient_contract_is_filled_from_her_record(both):
    _v4, body, _h = both
    s = body["sections"]
    linda, patient = s["constants"]["LINDA"], s["contracts"]["patient"]
    assert set(patient) == {"signals", "kpis", "steps", "queries", "viz", "handoffs", "workbenches"}
    v = linda["visit"]
    assert patient["signals"][1]["when"]["en"] == f"{v['day']}, {v['date']}, {v['time']}"
    assert f"on {v['day']} at {v['time']}" in patient["steps"]["pt_keep"]["ai"]["en"]
    assert v["es"] in patient["steps"]["pt_visit"]["ai"]["es"]
    assert f"({linda['last']['sys']} over {linda['last']['dia']})" in patient["steps"]["pt_bp_result"]["ai"]["en"]
    assert "{{" not in str(patient)
    assert s["personas"]["patient"]["identity"]["name"] == linda["name"]


def test_every_persona_briefs_and_answers_its_chips():
    for pid in OPERATORS + ["rain_patient"]:
        ctx = client.get("/api/v4/ui2/context", params={"clientId": "rain", "personaId": pid})
        assert ctx.status_code == 200, pid
        assert [p["id"] for p in ctx.json()["personas"]] == OPERATORS + ["rain_patient"]
        b = client.get("/api/v4/ui2/briefing", params={"clientId": "rain", "personaId": pid})
        assert b.status_code == 200 and b.headers.get("X-RAIN-Turn"), pid
        for chip in b.json()["chips"]:
            r = client.post("/api/v4/ui2/ask", json={"clientId": "rain", "personaId": pid, "input": chip})
            assert r.status_code == 200, (pid, chip)
            turn = r.json()
            assert turn["id"] != "__default__", (pid, chip)
            types = {c["type"] for c in turn["components"]}
            assert not types & RETIRED, (pid, chip, types)


def test_patient_runs_her_own_ten_queries_and_only_hers():
    listed = client.get("/api/v4/ui2/queries", params={"personaId": "rain_patient"})
    assert listed.status_code == 200
    qs = listed.json()["queries"]
    assert sorted(q["id"] for q in qs) == [f"GAR-{d}{i}" for d in "PS" for i in range(1, 6)]
    assert {q["data"] for q in qs} == {"synthetic", "public"}
    for q in qs:
        r = client.post("/api/v4/ui2/ask", json={"clientId": "rain", "personaId": "rain_patient", "input": q["question"]})
        assert r.status_code == 200 and r.json()["id"] == f"query:{q['id']}", q
        schema = "public_data" if q["data"] == "public" else "synthetic"
        assert r.headers["X-RAIN-Data-Source"] == f"postgres://rain_v4/{schema} (query {q['id']})"
        assert r.json()["components"][0]["type"] == "data_table"
    # typed the way a patient asks, and by id
    for text, qid in (("Is my county a primary care shortage area?", "GAR-P4"), ("GAR-P2", "GAR-P2"),
                      ("how far is the nearest health center", "GAR-P1")):
        r = client.post("/api/v4/ui2/ask", json={"clientId": "rain", "personaId": "rain_patient", "input": text})
        assert r.json()["id"] == f"query:{qid}", text
    # someone else's query is refused, never run; her scripted chip still wins
    r = client.post("/api/v4/ui2/ask", json={"clientId": "rain", "personaId": "rain_patient", "input": "CEO-S1"})
    assert r.json()["id"] == "query:refused:CEO-S1" and r.json()["components"] == []
    r = client.post("/api/v4/ui2/ask", json={"clientId": "rain", "personaId": "rain_patient", "input": ui2_v4.WEEK_CHIP})
    assert r.json()["id"] == "pt_week"


def test_unknown_persona_and_client():
    assert client.get("/api/v4/ui2/briefing", params={"clientId": "rain", "personaId": "rain_linda"}).status_code == 404
    assert client.get("/api/v4/ui2/data", params={"clientId": "other"}).status_code == 404
