"""Coordinator, queues, workers, portal and runtime sign-in, with a stand-in agent (no model calls)."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from factory import apppack, coordinator, workqueue

PRD = b"# Demo PRD\n\nPersona: Ana, analyst.\n\nKPI: Active accounts | 120\n"


@pytest.fixture()
def packs(tmp_path, monkeypatch):
    """Isolated apppacks folder and a fake agent that just records which stages ran."""
    monkeypatch.setattr(apppack, "APPPACKS_DIR", tmp_path)
    monkeypatch.setattr(workqueue, "APPPACKS_DIR", tmp_path)
    monkeypatch.delenv("FACTORY_QUEUE_CONNECTION", raising=False)
    ran = []

    def fake_agent(spec, ctx, task, client=None):
        ran.append(ctx.mode or spec.name)
        return {"agent": spec.name, "status": "ok", "summary": f"{spec.name} done", "usage": {"turns": 1}}

    monkeypatch.setattr(coordinator, "run_agent", fake_agent)
    prd = tmp_path / "prd.md"
    prd.write_bytes(PRD)
    return tmp_path, prd, ran


def drain(ran_before=0, limit=20):
    for _ in range(limit):
        if not any(workqueue.work_once(a) for a in workqueue.AGENT_NAMES):
            return


def test_queue_flow_runs_every_agent_and_stops_at_gate_c(packs):
    _, prd, ran = packs
    coordinator.start("demo", str(prd), None, 0.95, 2, ["A", "B"])
    s = coordinator.advance("demo", dispatch=workqueue.enqueue)
    assert s["status"] == "queued requirements"
    drain()
    state = apppack.AppPack("demo").read_json("run.json")
    assert ran == ["requirements", "data", "knowledge", "app", "verify"]
    assert state["stage"] == "gate:C" and state["status"] == "waiting for gate C"
    coordinator.approve("demo", "C", "reviewer")
    coordinator.advance("demo", dispatch=workqueue.enqueue)
    drain()
    state = apppack.AppPack("demo").read_json("run.json")
    assert ran[-1] == "release" and state["stage"] == "done"
    assert state["gates"]["C"]["by"] == "reviewer"


def test_gate_a_waits_for_a_person_unless_configured(packs):
    _, prd, ran = packs
    coordinator.start("manual", str(prd), None, 0.95, 2, [])
    coordinator.advance("manual", dispatch=workqueue.enqueue)
    drain()
    assert apppack.AppPack("manual").read_json("run.json")["status"] == "waiting for gate A"
    assert ran == ["requirements"]


def test_blocked_stage_is_kept_and_retried(packs, monkeypatch):
    _, prd, ran = packs
    calls = {"n": 0}

    def flaky(spec, ctx, task, client=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("usage limit reached")
        return {"status": "ok", "summary": "ok", "usage": {}}

    monkeypatch.setattr(coordinator, "run_agent", flaky)
    coordinator.start("flaky", str(prd), None, 0.95, 2, ["A", "B"])
    coordinator.advance("flaky", dispatch=workqueue.enqueue)
    drain()
    s = apppack.AppPack("flaky").read_json("run.json")
    assert s["status"] == "blocked at requirements" and "usage limit" in s["history"][-1]["summary"]
    coordinator.retry("flaky", "ops")
    coordinator.advance("flaky", dispatch=workqueue.enqueue)
    drain()
    assert apppack.AppPack("flaky").read_json("run.json")["stage"] == "gate:C"


def test_portal_start_view_and_approve(packs):
    from factory.portal import server
    tmp, _, ran = packs
    server.APPPACKS_DIR = tmp
    client = TestClient(server.create_portal(start_workers=False))
    r = client.post("/api/runs", data={"app_id": "portal_demo", "auto_ab": "true"},
                    files={"prd": ("prd.md", PRD, "text/markdown"),
                           "data": ("accounts.csv", b"id,active\n1,true\n", "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued requirements"
    assert (tmp / "_uploads/portal_demo/data/accounts.csv").is_file()
    assert client.post("/api/runs", data={"app_id": "portal_demo"}, files={"prd": ("p.md", PRD)}).status_code == 409
    assert client.post("/api/runs", data={"app_id": "Bad Id"}, files={"prd": ("p.md", PRD)}).status_code == 400
    drain()
    detail = client.get("/api/runs/portal_demo").json()
    assert detail["state"]["stage"] == "gate:C"
    assert client.get("/api/runs/portal_demo/file", params={"path": "run.json"}).status_code == 200
    assert client.get("/api/runs/portal_demo/file", params={"path": "../../etc/passwd"}).status_code == 403
    assert client.post("/api/runs/portal_demo/gates/A/approve").status_code == 409
    r = client.post("/api/runs/portal_demo/gates/C/approve", headers={"X-MS-CLIENT-PRINCIPAL-NAME": "ana@contoso.com"})
    assert r.status_code == 200
    drain()
    state = client.get("/api/runs/portal_demo").json()["state"]
    assert state["stage"] == "done" and state["gates"]["C"]["by"] == "ana@contoso.com"
    assert client.post("/api/runs/portal_demo/retry").status_code == 409


def _principal(groups):
    claims = [{"typ": "groups", "val": g} for g in groups]
    return base64.b64encode(json.dumps({"auth_typ": "aad", "claims": claims}).encode()).decode()


def test_runtime_sign_in_maps_groups_to_personas(packs, monkeypatch):
    from factory.runtime_app.server import create_app
    pack = apppack.AppPack("signed")
    pack.write_yaml("manifest.yaml", {
        "app": {"id": "signed", "name": "Signed", "domain": "d", "description": "d"},
        "personas": [{"id": "ana", "name": "Ana", "role": "analyst"}, {"id": "bo", "name": "Bo", "role": "ops"}]})
    pack.write_json("ui.json", {"title": "Signed", "personas": [{"id": "ana", "kpis": [], "signals": []},
                                                                {"id": "bo", "kpis": [], "signals": []}]})
    pack.path("access.yaml").write_text("ana: [grp-analysts]\nbo: [grp-ops]\n", encoding="utf-8")
    monkeypatch.setenv("FACTORY_AUTH", "entra")
    client = TestClient(create_app("signed", enable_ask=False))
    assert client.get("/api/app").status_code == 401
    h = {"X-MS-CLIENT-PRINCIPAL": _principal(["grp-analysts"])}
    assert [p["id"] for p in client.get("/api/app", headers=h).json()["personas"]] == ["ana"]
    assert client.get("/api/personas/ana/dashboard", headers=h).status_code == 200
    assert client.get("/api/personas/bo/dashboard", headers=h).status_code == 403
    monkeypatch.setenv("FACTORY_AUTH", "none")
    assert len(client.get("/api/app").json()["personas"]) == 2
