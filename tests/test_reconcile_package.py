import json
import tempfile
from pathlib import Path

import jsonschema
import pytest

from dif.artifacts.store import ArtifactStore
from dif.config import ROOT, settings
from dif.runtime.agents import AgentRegistry
from dif.runtime.engine import Runtime
from dif.runtime.executors import LocalExecutor
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry

SM = {"mappings": [{"entity": "loan_application", "table": "loan_application", "attribute": None, "column": None, "confidence": 0.9, "method": "name", "evidence": []},
                   {"entity": "member", "table": "member", "attribute": None, "column": None, "confidence": 0.8, "method": "name", "evidence": []},
                   {"entity": "risk_score", "table": "fair_lending_snapshot", "attribute": None, "column": None, "confidence": 0.2, "method": "name", "evidence": []}],
      "gaps": [{"kind": "unmapped_table", "name": "audit_log", "reason": "no entity"}], "confidence": 0.63}
DA = {"scenario": "uc2", "readiness_status": "synthetic", "assumptions": [], "gaps": [],
      "tables": [{"name": "loan_application", "synthetic": True, "status": "landed", "source": "core_banking"},
                 {"name": "member", "synthetic": True, "status": "landed"}, {"name": "fair_lending_snapshot", "synthetic": True, "status": "landed"}]}
REQ = {"title": "PRD", "use_cases": [], "entities_mentioned": [], "scenario": "uc2",
       "kpis": [{"name": "loan approval rate", "definition": "approved loan applications over total"}, {"name": "churn", "definition": "members leaving"}, {"name": "nps", "definition": None}]}


def schema(name):
    return json.load(open(ROOT / "contracts" / name))


def make(tmp):
    store = Store(f"sqlite:///{tmp}/t.db")
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(ROOT / "agents", store, ROOT / "contracts"),
                   LocalExecutor(2), ArtifactStore(f"file://{tmp}/art"), ROOT / "contracts")


@pytest.fixture
def rt():
    return make(Path(tempfile.mkdtemp()))


def test_reconciler_resolves_mapped_concepts_and_lists_gaps_and_kpis(rt):
    out = rt.skills.get("reconciler").execute({"semantic_mappings": SM, "data_assets": DA, "requirements": REQ,
                                               "alignment": {"unaligned": ["RiskScore"]}, "kag_release": {"published": False, "validation": {"passed": True}}})
    jsonschema.validate(out, schema("reconciliation.v1.json"))
    assert {r["concept"] for r in out["resolved"]} == {"loan_application", "member"}
    kinds = {u["kind"] for u in out["unresolved"]}
    assert kinds == {"low_confidence_mapping", "unmapped_table", "unaligned_class", "kpi_unresolvable"}
    kpi = {k["name"]: k for k in out["kpis"]}
    assert kpi["loan approval rate"]["resolvable"] and kpi["loan approval rate"]["depends_on"] == ["loan_application"]
    assert kpi["churn"]["resolvable"] and not kpi["nps"]["resolvable"]
    assert out["readiness"] == "blocked" and 0 < out["score"] < 0.5 and "not published" in out["explanation"]


def test_reconciler_ready_when_everything_lines_up(rt):
    sm = {"mappings": SM["mappings"][:2], "gaps": [], "confidence": 0.85}
    out = rt.skills.get("reconciler").execute({"semantic_mappings": sm, "data_assets": DA})
    assert out["readiness"] == "ready" and out["score"] == 1.0 and out["unresolved"] == []
    assert any("synthetic" in f for f in out["findings"])
    out = rt.skills.get("reconciler").execute({"semantic_mappings": sm, "data_assets": {**DA, "tables": DA["tables"][:1]}})
    assert [u["kind"] for u in out["unresolved"]] == ["no_data"] and out["readiness"] == "partial"


def test_reconciler_llm_explanation_and_degradation(rt, monkeypatch):
    from dif import llm
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", lambda p: "Map risk_score to a table.")
    out = rt.skills.get("reconciler").execute({"semantic_mappings": SM})
    assert out["explanation"].endswith("Map risk_score to a table.")

    def boom(p):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "complete", boom)
    out = rt.skills.get("reconciler").execute({"semantic_mappings": SM})
    assert out["llm_error"] == "down" and out["unresolved"]


def test_reconciliation_agent_end_to_end(rt):
    run = rt.start("reconciliation-agent", {"semantic_mappings": SM, "data_assets": DA, "requirements": REQ}, enterprise="rain")
    assert run["status"] == "succeeded", run["error"]
    assert run["state"]["acceptance"]["passed"] and rt.store.artifacts("reconciliation", "rain")[0]["body"]["readiness"]


def test_package_assembler_builds_files_with_checksums(rt):
    rec = rt.skills.get("reconciler").execute({"semantic_mappings": SM, "data_assets": DA})
    out = rt.skills.get("package-assembler").execute(
        {"package_version": "1.0.0", "requirements": REQ, "semantic_mappings": SM, "data_assets": DA, "reconciliation": rec,
         "domain_model": {"entities": [], "relationships": [], "constraints": [{"rule": "amount > 0"}], "assumptions": ["a1"]},
         "artifact_ids": {"semantic_mappings": 3}, "agent_versions": {"x": "1.0.0"}}, {"enterprise": "rain", "run_id": "r1"})
    paths = {f["path"] for f in out["files"]}
    assert {"manifest.yaml", "requirements.json", "semantic-mappings.json", "data-assets.json", "reconciliation.json",
            "business-rules.json", "unresolved-gaps.json", "quality-report.json", "provenance.json", "domain-model.json"} <= paths
    assert "ontology/lower-ontology.json" not in paths  # absent inputs are not fabricated
    rules = json.loads(next(f["content"] for f in out["files"] if f["path"] == "business-rules.json"))
    assert rules["constraints"] == [{"rule": "amount > 0"}]
    gaps = json.loads(next(f["content"] for f in out["files"] if f["path"] == "unresolved-gaps.json"))
    assert gaps["assumptions"] == ["a1"] and gaps["mapping_gaps"] == SM["gaps"]
    m = out["manifest"]
    assert m["enterprise_id"] == "rain" and m["artifacts"] == {"semantic_mappings": 3} and m["versions"]["agents"] == {"x": "1.0.0"}
    assert all(len(f["sha256"]) == 64 and f["bytes"] > 0 for f in m["files"]) and m["data_status"] == "synthetic"


def test_package_store_writes_immutable_release(rt):
    pkg = rt.skills.get("package-assembler").execute({"package_version": "2.0.0"}, {"enterprise": "rain"})
    ctx = {"enterprise": "rain", "artifacts": rt.artifacts, "dry_run": False}
    out = rt.skills.get("package-store").execute({"package": pkg}, ctx)
    jsonschema.validate(out["manifest"], schema("manifest.v1.json"))
    assert out["written"] and out["uri"].endswith("packages/rain/2.0.0")
    assert rt.artifacts.exists("packages/rain/2.0.0/manifest.yaml") and rt.artifacts.exists("packages/rain/2.0.0/provenance.json")
    with pytest.raises(ValueError, match="immutable"):
        rt.skills.get("package-store").execute({"package": pkg}, ctx)
    assert rt.skills.get("package-store").execute({"package": pkg, "overwrite": True}, ctx)["written"]
    dry = rt.skills.get("package-store").execute({"package": pkg}, {**ctx, "dry_run": True})
    assert dry["written"] is False and dry["manifest"]["files"][0]["uri"].startswith("file://")


def test_package_publisher_agent_end_to_end_records_versions_from_child_runs(rt):
    rec = rt.start("reconciliation-agent", {"semantic_mappings": SM, "data_assets": DA}, enterprise="rain")
    run = rt.start("package-publisher-agent", {"package_version": "1.0.0", "semantic_mappings": SM, "data_assets": DA,
                                               "reconciliation": rec["output"], "artifact_ids": {"reconciliation": 1}}, by="alice", enterprise="rain")
    assert run["status"] == "succeeded", run["error"]
    out = run["output"]
    jsonschema.validate(out, schema("manifest.v1.json"))
    assert out["written"] and out["readiness"] == "partial" and out["versions"]["agents"]["package-publisher-agent"] == "1.0.0"
    assert out["versions"]["skills"]["package-assembler"] == "1.0.0"
    art = rt.store.artifacts("knowledge_package", "rain")[0]
    assert art["body"]["package_version"] == "1.0.0" and rt.artifacts.get_json("packages/rain/1.0.0/provenance.json")["run_id"] == run["id"]
    again = rt.start("package-publisher-agent", {"package_version": "1.0.0", "semantic_mappings": SM}, enterprise="rain")
    assert again["status"] == "failed" and "immutable" in again["error"]
