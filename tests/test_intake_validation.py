"""PRD intake, acceptance-check, llm-judge, ddl-source-reader, source-discovery and the validation-agent (plan section 5)."""
import json
import tempfile
from pathlib import Path

import jsonschema
import pytest

from dif import llm, mcp_client
from dif.artifacts.store import ArtifactStore
from dif.config import ROOT, settings
from dif.runtime.agents import AgentRegistry
from dif.runtime.engine import Runtime
from dif.runtime.executors import LocalExecutor
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry

PRD = (ROOT / "samples/prd.txt").read_text()
DDL = {p.stem: p.read_text() for p in (ROOT / "samples/schemas").glob("*.sql")}
TABLES = {"loan_application", "member", "fair_lending_snapshot"}
RUBRIC = ["title is present", "entities_mentioned lists the business entities", "Every use case has a name"]
REG = SkillRegistry(settings.skills_dirs)


def skill(name, inp):
    return REG.get(name).execute(inp, {"run_id": "t", "dry_run": False})


def valid(contract, obj):
    jsonschema.Draft202012Validator(json.loads((ROOT / "contracts" / contract).read_text())).validate(obj)


def make():
    tmp = Path(tempfile.mkdtemp())
    store = Store(f"sqlite:///{tmp}/t.db")
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(ROOT / "agents", store, ROOT / "contracts"),
                   LocalExecutor(2), ArtifactStore(f"file://{tmp}/artifacts"), ROOT / "contracts")


def mcp_ok(server, tool, arguments=None, servers=None):
    return {"text": DDL[arguments["path"].split("/")[-1].removesuffix(".sql")], "structured": None, "is_error": False}


def llm_on(monkeypatch, reply):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", lambda p: reply)


def llm_boom(monkeypatch):
    def boom(p):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", boom)


# ---- prd-intake --------------------------------------------------------------------------------------
def test_prd_intake_baseline_and_contract():
    out = skill("prd-intake", {"prd": PRD})
    valid("requirements.v1.json", out)
    assert out["title"] == "USSFCU Compliance Dashboard PRD" and out["scenario"] == "uc1" and "uc1" in out["assumptions"][0]
    assert {"loan_application", "fair_lending_snapshot", "risk_score"} <= set(out["entities_mentioned"])
    assert not {"core_banking", "compliance_dw"} & set(out["entities_mentioned"])  # systems are not entities
    uc = out["use_cases"][0]
    assert uc["id"] == "uc-1" and "regulator" in uc["actors"] and "fair_lending_snapshot" in uc["entities"]
    assert out["policies"] and out["evidence"]["loan_application"] and out["method"] == "rules" and out["summary"]
    assert any(k["name"] == "risk_score" for k in out["kpis"])


def test_prd_intake_detects_scenarios():
    uc2 = skill("prd-intake", {"prd": PRD, "schemas": sorted(TABLES)})
    assert uc2["scenario"] == "uc2" and TABLES <= set(uc2["entities_mentioned"])
    assert any("risk_score" in a for a in uc2["assumptions"]) and {s["type"] for s in uc2["sources_declared"]} == {"catalog"}
    ddl = skill("prd-intake", {"prd": PRD, "schemas": list(DDL.values())})
    assert ddl["scenario"] == "uc2" and "member" in ddl["entities_mentioned"] and ddl["sources_declared"][0]["type"] == "ddl-inline"
    uc3 = skill("prd-intake", {"prd": PRD, "schemas": sorted(TABLES), "sources": [{"name": "bb", "type": "mcp-bitbucket"}]})
    assert uc3["scenario"] == "uc3" and "bb" in uc3["scenario_reason"] and uc3["sources_declared"][0] == {"name": "bb", "type": "mcp-bitbucket"}
    assert skill("prd-intake", {"prd": PRD, "schema_calls": [{"server": "atlassian", "tool": "getBitbucketFile"}]})["scenario"] == "uc3"
    for o in (uc2, ddl, uc3):
        valid("requirements.v1.json", o)


def test_prd_intake_merges_existing_and_llm_refines_then_degrades(monkeypatch):
    out = skill("prd-intake", {"prd": PRD, "requirements": {"entities_mentioned": ["branch"], "kpis": [{"name": "approval rate", "definition": None}]}})
    assert "branch" in out["entities_mentioned"] and any(k["name"] == "approval rate" for k in out["kpis"])
    llm_on(monkeypatch, json.dumps({"use_cases": [{"name": "Fair lending review", "entities": ["fair_lending_snapshot", "examiner"], "kpis": ["approval rate"]}],
                                    "kpis": [{"name": "approval rate", "definition": "approved / decided"}]}))
    out = skill("prd-intake", {"prd": PRD})
    assert out["method"] == "rules+llm" and {"examiner", "risk_score"} <= set(out["entities_mentioned"])
    assert any(u["id"] == "uc-llm-1" for u in out["use_cases"]) and any(k["definition"] == "approved / decided" for k in out["kpis"])
    valid("requirements.v1.json", out)
    llm_boom(monkeypatch)
    out = skill("prd-intake", {"prd": PRD})
    assert out["llm_error"] == "down" and out["method"] == "rules" and out["use_cases"]  # baseline still produced


# ---- acceptance-check --------------------------------------------------------------------------------
def test_acceptance_check_passes_and_fails():
    subject = {"passed": True, "score": 0.9, "checks": [{"name": "a", "passed": True}], "findings": [], "refs": [{"to": "a"}, {"to": "zzz"}]}
    ok = skill("acceptance-check", {"subject": subject, "contract": "validation-report.v1.json", "thresholds": {"$.score": 0.8},
                                    "required_keys": ["checks"], "cross_refs": [{"from": "$.refs[0].to", "in": "$.checks[*].name"}]})
    valid("validation-report.v1.json", ok)
    assert ok["passed"] and ok["score"] == 1.0 and ok["judge"] is None and not ok["findings"]
    assert {c["name"] for c in ok["checks"]} == {"subject:non_empty", "schema:validation-report.v1.json", "threshold:$.score",
                                                 "key:checks", "cross_ref:$.refs[0].to->$.checks[*].name"}
    bad = skill("acceptance-check", {"subject": {**subject, "score": "high"}, "contract": "validation-report.v1.json",
                                     "thresholds": {"$.score": 0.95, "$.missing": 1}, "required_keys": ["judge"],
                                     "cross_refs": [{"from": "$.refs[*].to", "in": "$.checks[*].name"}]})
    valid("validation-report.v1.json", bad)
    assert not bad["passed"] and bad["score"] == round(1 / 6, 3) and len(bad["findings"]) == 5
    assert any("zzz" in f["message"] for f in bad["findings"]) and all(f["severity"] == "error" for f in bad["findings"])
    assert not skill("acceptance-check", {"subject": {"x": 1}, "contract": "nope.v1.json"})["passed"]
    none = skill("acceptance-check", {"subject": {"x": 1}})
    assert none["passed"] and none["findings"][0]["severity"] == "info"


# ---- llm-judge ---------------------------------------------------------------------------------------
def test_llm_judge_heuristic_and_llm_paths(monkeypatch):
    subject = skill("prd-intake", {"prd": PRD})
    h = skill("llm-judge", {"subject": subject, "rubric": RUBRIC})
    assert h["method"] == "heuristic" and h["passed"] and h["score"] == 1.0 and "llm_error" not in h
    assert h["findings"][0]["severity"] == "info" and h["findings"][0]["message"].startswith("LLM unavailable")
    miss = skill("llm-judge", {"subject": subject, "rubric": "title is present\nnot_there must be filled"})
    assert miss["score"] == round(2 / 3, 3) and miss["passed"] and any("not_there" in f["message"] for f in miss["findings"])
    assert skill("llm-judge", {"subject": {"a": 1}, "rubric": ["Every item is good"]})["score"] == 0.5
    assert not skill("llm-judge", {"subject": {}, "rubric": RUBRIC})["passed"]
    llm_on(monkeypatch, '{"passed": true, "score": 1.7, "findings": [{"severity": "bogus", "message": "fine"}]}')
    j = skill("llm-judge", {"subject": subject, "rubric": RUBRIC, "context": "stage: intake"})
    assert j == {"passed": True, "score": 1.0, "findings": [{"severity": "info", "message": "fine"}], "method": "llm", "threshold": 0.6}
    llm_on(monkeypatch, '{"passed": true, "score": 0.5, "findings": []}')
    assert not skill("llm-judge", {"subject": subject, "rubric": RUBRIC})["passed"]
    assert skill("llm-judge", {"subject": subject, "rubric": RUBRIC, "threshold": 0.4})["passed"]
    llm_boom(monkeypatch)
    d = skill("llm-judge", {"subject": subject, "rubric": RUBRIC})
    assert d["method"] == "heuristic" and d["llm_error"] == "down" and d["passed"]


# ---- ddl-source-reader -------------------------------------------------------------------------------
def test_ddl_source_reader_catalog_and_mcp(monkeypatch):
    cat = skill("ddl-source-reader", {"paths": ["*.sql"]})
    assert {d["name"] for d in cat["ddl"]} == TABLES and {d["source"] for d in cat["ddl"]} == {"catalog"} and len(cat["texts"]) == 3
    part = skill("ddl-source-reader", {"paths": ["member", "nope.sql", "../prd.txt"]})
    assert [d["name"] for d in part["ddl"]] == ["member"] and len(part["errors"]) == 2

    def flaky(server, tool, arguments=None, servers=None):
        if arguments.get("path") == "db/broken.sql":
            raise mcp_client.McpError("boom")
        return mcp_ok(server, tool, arguments)
    monkeypatch.setattr(mcp_client, "call_tool", flaky)
    calls = [{"server": "bb", "tool": "getBitbucketFile", "arguments": {"path": "db/member.sql"}},
             {"server": "bb", "tool": "getBitbucketFile", "arguments": {"path": "db/broken.sql"}}]
    out = skill("ddl-source-reader", {"calls": calls, "ddl_texts": [DDL["loan_application"]]})
    assert [(d["name"], d["source"]) for d in out["ddl"]] == [("db/member.sql", "mcp:bb"), ("inline-1", "inline")]
    assert out["errors"] == [{"call": "bb.getBitbucketFile", "error": "boom"}]
    with pytest.raises(ValueError, match="no DDL"):
        skill("ddl-source-reader", {"calls": calls[1:]})
    with pytest.raises(ValueError):
        skill("ddl-source-reader", {})


# ---- source-discovery --------------------------------------------------------------------------------
def test_source_discovery_mixed_statuses(monkeypatch):
    def flaky(server, tool, arguments=None, servers=None):
        if server == "down":
            raise mcp_client.McpError("unknown MCP server 'down'")
        return mcp_ok(server, tool, arguments)
    monkeypatch.setattr(mcp_client, "call_tool", flaky)
    call = {"tool": "getBitbucketFile", "arguments": {"path": "db/member.sql"}}
    out = skill("source-discovery", {"sources": [
        {"name": "bb", "type": "mcp-bitbucket", "server": "bb", "calls": [call]},
        {"name": "dead", "type": "mcp-bitbucket", "server": "down", "calls": [call]},
        {"name": "half", "type": "mcp-bitbucket"},
        {"name": "cat", "type": "catalog", "paths": ["*.sql"]},
        {"name": "inline", "type": "ddl-inline", "ddl": DDL["member"]},
        {"name": "nothing", "type": "none"},
        {"name": "odd", "type": "ftp"}]})
    valid("source-inventory.v1.json", out)
    assert [s["status"] for s in out["sources"]] == ["reachable", "unreachable", "not_configured", "reachable", "inline", "not_configured", "not_configured"]
    assert out["summary"] == {"reachable": 3, "total": 7, "files": 5}
    bb, inline = out["sources"][0], out["sources"][4]
    assert bb["files"][0]["path"] == "db/member.sql" and bb["files"][0]["hash"] == inline["files"][0]["hash"]
    assert bb["files"][0]["bytes"] == len(DDL["member"].encode()) and len(bb["files"][0]["hash"]) == 64
    assert "down" in out["sources"][1]["error"] and "ftp" in out["sources"][6]["error"]


# ---- validation-agent --------------------------------------------------------------------------------
def test_validation_agent_end_to_end():
    rt = make()
    subject = skill("prd-intake", {"prd": PRD})
    run = rt.start("validation-agent", {"subject": subject, "contract": "requirements.v1.json", "rubric": RUBRIC,
                                        "thresholds": {}, "required_keys": ["title", "use_cases"]})
    assert run["status"] == "succeeded", run["error"]
    o = run["output"]
    valid("validation-report.v1.json", o)
    assert o["passed"] and o["score"] == 1.0 and o["judge"]["method"] == "heuristic" and o["artifact_version"] == 1
    assert {c["name"] for c in o["checks"]} >= {"schema:requirements.v1.json", "key:title", "key:use_cases"}
    assert any(f["message"].startswith("LLM unavailable") for f in o["findings"])
    assert run["state"]["acceptance"]["passed"]
    arts = rt.store.artifacts(kind="validation_report", run_id=run["id"])
    assert len(arts) == 1 and arts[0]["body"]["passed"] is True and arts[0]["version"] == 1
    # judge switched off and a failing subject: the report fails, the run (and its acceptance) still succeeds
    bad = rt.start("validation-agent", {"subject": {"title": "x"}, "contract": "requirements.v1.json", "rubric": RUBRIC, "skip_judge": True})
    assert bad["status"] == "succeeded", bad["error"]
    assert not bad["output"]["passed"] and bad["output"]["judge"] is None and bad["output"]["score"] == 0.5
    assert bad["output"]["artifact_version"] == 2 and bad["state"]["acceptance"]["passed"]
