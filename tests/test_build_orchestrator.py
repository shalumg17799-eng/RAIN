"""End-to-end build-time factory: PRD -> knowledge package through dif-build-orchestrator, with and without gates."""
import importlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dif.artifacts.store import ArtifactStore
from dif.config import ROOT, settings
from dif.runtime.agents import AgentRegistry
from dif.runtime.engine import Runtime
from dif.runtime.executors import LocalExecutor
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry

PRD = (ROOT / "samples/prd.txt").read_text()
INP = {"prd": PRD, "schemas": ["loan_application", "member", "fair_lending_snapshot"], "rows_per_table": 10, "seed": 7}
KINDS = {"requirements", "domain_model", "normalized_metadata_graph", "validation_report", "domain_catalog", "lower_ontology",
         "data_assets", "ontology_alignment", "kag_release", "reconciliation", "knowledge_package"}


def make(tmp):
    store = Store(f"sqlite:///{tmp}/t.db")
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(settings.agents_dir, store, ROOT / "contracts"),
                   LocalExecutor(3), ArtifactStore(f"file://{tmp}/art"), ROOT / "contracts")


@pytest.fixture
def rt():
    return make(Path(tempfile.mkdtemp()))


def test_factory_end_to_end_without_gates(rt):
    run = rt.start("dif-build-orchestrator", {**INP, "auto_approve": True, "package_version": "1.0.0"}, by="alice", enterprise="rain")
    assert run["status"] == "succeeded", run["error"]
    out = run["output"]
    assert out["scenario"] == "uc2" and set(out["tables"]) == set(INP["schemas"])
    assert {e["id"] for e in out["entities"]} >= {"loan_application", "member", "fair_lending_snapshot"}
    assert len(out["ontology_classes"]) >= 3 and out["alignment"] and out["data_status"] == "synthetic"
    assert out["kag_published"] is False and out["kag_release"]  # no Neo4j configured
    assert out["readiness"] in ("ready", "partial") and out["package_version"] == "1.0.0"
    assert out["package_uri"].endswith("packages/rain/1.0.0") and any(f["uri"].endswith("manifest.yaml") for f in out["package_files"])
    kinds = {a["kind"] for a in rt.store.artifacts(enterprise="rain", include_body=False)}
    assert KINDS <= kinds, KINDS - kinds
    children = rt.store.list_runs(100, parent=run["id"])
    assert {c["agent"] for c in children} == {"domain-modelling-agent", "metadata-extraction-agent", "validation-agent", "domain-enrichment-agent",
                                              "lower-ontology-agent", "data-acquisition-agent", "upper-ontology-alignment-agent",
                                              "kag-builder-agent", "reconciliation-agent", "package-publisher-agent"}
    assert all(c["status"] == "succeeded" and c["enterprise_id"] == "rain" and c["created_by"] == "alice" for c in children)
    gates = [s for s in run["state"]["steps"] if s.startswith("gate_")]
    assert gates and all(run["state"]["steps"][g]["skipped"] for g in gates)
    manifest = rt.artifacts.get_json("packages/rain/1.0.0/provenance.json")
    assert manifest["artifact_ids"]["domain_model"] and manifest["agents"]["lower-ontology-agent"] == "1.0.0"
    assert run["state"]["acceptance"]["passed"]
    ev = [e["event"] for e in rt.store.history(run["id"])]
    assert ev.count("group_joined") == 2 and ev.count("sub_agent_started") == 10


def test_factory_pauses_at_each_gate_and_resumes_without_repeating_work(rt):
    run = rt.start("dif-build-orchestrator", INP, by="alice")
    for gate, keys in (("gate_1", {"entities", "tables", "validation"}), ("gate_2", {"classes", "extensions_proposed"}),
                       ("gate_3", {"readiness", "unresolved", "data_status"})):
        assert run["status"] == "awaiting_approval", run["error"]
        sid, rec = rt.store.pending_gate(run["id"])
        assert sid == gate and keys <= set(rec["payload"]) and not rec.get("delegated")
        children_before = len(rt.store.list_runs(100, parent=run["id"]))
        run = rt.approve(run["id"], "lead", f"ok {gate}", wait=True)
        assert len(rt.store.list_runs(100, parent=run["id"])) >= children_before  # finished children are reused, never re-run
    assert run["status"] == "succeeded", run["error"]
    assert run["output"]["package_version"] == "1.0.1"  # auto-numbered: no package published before for this (platform) scope
    children = rt.store.list_runs(100, parent=run["id"])
    assert len(children) == 10 and all(c["status"] == "succeeded" for c in children)
    ev = [e["event"] for e in rt.store.history(run["id"])]
    assert ev.count("approval_requested") == 3 and ev.count("approved") == 3 and ev.count("sub_agent_started") == 10


def test_rejecting_a_gate_ends_the_build(rt):
    run = rt.start("dif-build-orchestrator", INP)
    assert run["status"] == "awaiting_approval"
    out = rt.reject(run["id"], "lead", "model is wrong")
    assert out["status"] == "rejected" and "model is wrong" in out["error"]
    assert rt.execute(run["id"])["status"] == "rejected"


@pytest.fixture
def client(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp}/t.db")
    monkeypatch.setattr(settings, "artifact_store", f"file://{tmp}/art")
    monkeypatch.setattr(settings, "orchestrator", "local")
    monkeypatch.setattr(settings, "api_keys", "k-user:alice:user:rain,k-lead:lead:approver:rain,k-other:bob:user:nfcu,k-admin:root:admin")
    import dif.app
    importlib.reload(dif.app)
    return TestClient(dif.app.app)


def test_gates_through_the_api(client):
    user, lead, other, admin = ({"X-API-Key": k} for k in ("k-user", "k-lead", "k-other", "k-admin"))
    run = client.post("/agents/dif-build-orchestrator/runs?wait=true", json={"input": INP}, headers=user).json()
    assert run["status"] == "awaiting_approval" and run["enterprise_id"] == "rain"
    rid = run["id"]
    detail = client.get(f"/runs/{rid}", headers=user).json()
    assert detail["pending_approval"]["step"] == "gate_1" and "entities" in detail["pending_approval"]["payload"]
    assert [a["id"] for a in client.get("/approvals", headers=lead).json()] == [rid]
    assert client.get("/approvals", headers=other).json() == []           # other enterprise cannot see it
    assert client.get(f"/runs/{rid}", headers=other).status_code == 404
    assert client.post(f"/runs/{rid}/approve", json={}, headers=user).status_code == 403   # user role cannot approve
    assert client.post(f"/runs/{rid}/resume", headers=user).status_code == 409
    r = client.post(f"/runs/{rid}/approve?wait=true", json={"comment": "fine"}, headers=lead).json()
    assert r["status"] == "awaiting_approval"  # moved on to gate 2
    assert client.get(f"/runs/{rid}", headers=user).json()["pending_approval"]["step"] == "gate_2"
    r = client.post(f"/runs/{rid}/approve?wait=true", json={}, headers=admin).json()
    assert client.get(f"/runs/{rid}", headers=user).json()["pending_approval"]["step"] == "gate_3"
    r = client.post(f"/runs/{rid}/reject", json={"comment": "not now"}, headers=lead).json()
    assert r["status"] == "rejected"
    assert client.post(f"/runs/{rid}/approve", json={}, headers=lead).status_code == 409
    kids = client.get(f"/runs/{rid}/children", headers=user).json()
    assert len(kids) == 9 and all(k["status"] == "succeeded" for k in kids)   # everything before gate 3 completed
    arts = client.get("/artifacts?include_body=false&kind=lower_ontology", headers=user).json()
    assert arts and "body" not in arts[0]
    dl = client.get(f"/artifacts/{arts[0]['id']}/download", headers=user)
    assert dl.status_code == 200 and dl.headers["content-disposition"].startswith('attachment; filename="lower_ontology-v1.json"')
    assert client.get(f"/artifacts/{arts[0]['id']}", headers=other).status_code == 404
    ev = client.get(f"/runs/{rid}/history", headers=user).json()
    assert [e["event"] for e in ev].count("approved") == 2 and [e["event"] for e in ev].count("rejected") == 1
