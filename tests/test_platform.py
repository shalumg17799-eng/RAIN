import tempfile
from pathlib import Path

from dif.config import ROOT, settings
from dif.evaluation.framework import evaluate
from dif.runtime.agents import AgentRegistry
from dif.runtime.engine import Runtime
from dif.runtime.executors import LocalExecutor
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry

PRD = (ROOT / "samples/prd.txt").read_text()
INP = {"prd": PRD, "schemas": ["loan_application", "member", "fair_lending_snapshot"]}


def make():
    db = Path(tempfile.mkdtemp()) / "t.db"
    store = Store(f"sqlite:///{db}")
    return Runtime(store, SkillRegistry(settings.skills_dir), AgentRegistry(ROOT / "agents", store, ROOT / "contracts"), LocalExecutor(2))


def test_registry_discovers_and_versions():
    r = SkillRegistry(settings.skills_dir)
    assert {s["name"] for s in r.list()} >= {"schema-metadata-extractor", "metadata-validator"}
    assert r.get("metadata-validator").version == "1.0.0"


def test_extraction_agent_end_to_end():
    run = make().start("metadata-extraction-agent", INP)
    assert run["status"] == "succeeded", run["error"]
    o = run["output"]
    assert set(o["tables"]) == {"loan_application", "member", "fair_lending_snapshot"}
    assert o["lineage"]["loan_application"] == "core_banking"
    assert o["lineage"]["fair_lending_snapshot"] == "compliance_dw"
    assert o["validation"]["valid"] and o["artifact_version"] == 1


def test_resume_skips_completed_steps_and_audit():
    rt = make()
    run = rt.start("metadata-extraction-agent", INP)
    st = run["state"]; st["steps"].pop("validate")
    rt.store.update_run(run["id"], status="failed", state=st)
    again = rt.resume(run["id"])
    assert again["status"] == "succeeded"
    ev = [e["event"] for e in rt.store.history(run["id"])]
    assert ev.count("step_started") == 3 and "resumed" in ev


def test_dry_run_does_not_persist():
    rt = make()
    run = rt.start("metadata-extraction-agent", INP, dry_run=True)
    assert run["status"] == "succeeded" and rt.store.artifacts() == []


def test_missing_input_fails_cleanly():
    run = make().start("metadata-extraction-agent", {"prd": "x"})
    assert run["status"] == "failed" and "schemas" in run["error"]


def test_evaluation_framework():
    rep = evaluate(make(), "metadata-extraction-agent", [{"input": INP, "expect": {"lineage": {"loan_application": "core_banking"}}},
                                                           {"input": INP, "expect": {"tables": ["nope"]}}])
    assert rep["pass_rate"] == 0.5 and rep["verdict"] == "FAIL" and rep["mean_confidence"] > 0.5
