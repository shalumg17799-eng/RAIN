"""The write-back flow (/api/v4/flow): each action changes rows, the next UI data shows it, /reset undoes all.
Needs the rain_v4 database. Run from rain-api/:  python -m pytest test_flow_v4.py -q
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import flow_v4
import ui_data_v4

app = FastAPI()
app.include_router(flow_v4.router, prefix="/api/v4/flow")
app.include_router(ui_data_v4.router, prefix="/api/v4/ui")
client = TestClient(app)


def _db_ready() -> bool:
    try:
        with flow_v4._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM synthetic.flow_event")
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="rain_v4 synthetic.flow_event not reachable")


def ui():
    return client.get("/api/v4/ui/data", params={"clientId": "rain"}).json()["sections"]


def post(action, body):
    r = client.post(f"/api/v4/flow/{action}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(autouse=True)
def clean():
    client.post("/api/v4/flow/reset")
    yield
    client.post("/api/v4/flow/reset")


def test_reading_closes_the_gap_and_counts_as_controlled():
    s = ui()
    linda = s["constants"]["LINDA"]
    sys_, dia = map(int, linda["reading"].split("/"))
    res = post("reading", {"memberId": linda["memberId"], "systolic": sys_, "diastolic": dia})
    assert res["result"]["controlled"] and res["result"]["gapsClosed"]
    after = ui()
    assert after["constants"]["CARE"]["controlled"] == s["constants"]["CARE"]["controlled"] + 1
    assert after["constants"]["LINDA"]["readingRecorded"] is True


def test_booking_writes_the_visit_reminders_and_closes_the_task():
    s = ui()
    b = next(x for x in s["records"]["pendingBookings"] if x["memberId"] != s["constants"]["LINDA"]["memberId"])
    slot = next(x for x in s["records"]["slots"] if x.get("status") == "open")
    res = post("book", {"memberId": b["memberId"], "slotId": slot["id"], "by": "Brandon Kee"})["result"]
    assert res["reminders"] and res["appointment"].startswith("APT-F")
    after = ui()
    assert len(after["records"]["pendingBookings"]) == len(s["records"]["pendingBookings"]) - 1
    assert any(r["memberId"] == b["memberId"] for r in after["records"]["reminders"])
    assert slot["id"] not in {x["id"] for x in after["records"]["slots"] if x.get("status") == "open"}
    assert client.post("/api/v4/flow/book", json={"memberId": "M-40107", "slotId": slot["id"]}).status_code == 409


def test_reply_c_confirms_and_reset_restores_everything():
    s = ui()
    r = next(x for x in s["records"]["reminders"] if x["status"] == "No reply yet")
    post("reply", {"memberId": r["memberId"], "reply": "C"})
    after = ui()
    assert next(x for x in after["records"]["reminders"] if x["memberId"] == r["memberId"])["status"] == "Confirmed"
    undone = client.post("/api/v4/flow/reset").json()
    assert undone["eventsUndone"] == 1
    back = ui()
    assert next(x for x in back["records"]["reminders"] if x["memberId"] == r["memberId"])["status"] == "No reply yet"
    assert back["constants"]["CARE"] == s["constants"]["CARE"]


def test_bad_input_is_refused():
    assert client.post("/api/v4/flow/reply", json={"memberId": "M-40107", "reply": "X"}).status_code == 422
    assert client.post("/api/v4/flow/reading", json={"memberId": "M-40107", "systolic": 20, "diastolic": 10}).status_code == 422
    assert client.post("/api/v4/flow/contact", json={"memberId": "M-40107", "outcome": "Maybe"}).status_code == 422
    assert client.post("/api/v4/flow/book", json={"memberId": "NOPE", "slotId": "S2"}).status_code == 404
