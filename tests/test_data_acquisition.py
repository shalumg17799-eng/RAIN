"""data-acquisition-agent (plan 5.7): scenario routing, provisional schema, seeded synthetic data, Bronze-lite landing,
profiling and the data-assets readiness report - without Databricks."""
import csv
import hashlib
import importlib.util
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

PRD = (ROOT / "samples/prd.txt").read_text()
SCHEMAS = ["loan_application", "member", "fair_lending_snapshot"]
SKILLS = SkillRegistry(settings.skills_dirs)
CONTRACT = json.loads((ROOT / "contracts/data-assets.v1.json").read_text())
CTX = {"run_id": "r1", "dry_run": False, "enterprise": None, "artifacts": None}
DOMAIN_MODEL = {
    "entities": [
        {"id": "loan_application", "name": "Loan Application", "keys": ["id"], "evidence": [],
         "attributes": [{"name": "amount"}, {"name": "status", "type": "string", "required": True}, {"name": "applied_at"},
                        {"name": "is_joint"}, {"name": "applicant_count"}, {"name": "purpose"}]},
        {"id": "member", "name": "Member", "keys": ["id"], "evidence": [],
         "attributes": [{"name": "full_name", "required": True}, {"name": "email"}, {"name": "zip_code"}]},
    ],
    "relationships": [{"from": "member", "to": "loan_application", "type": "one-to-many", "name": "applies"}],
}


def skill(name, inp, ctx=None):
    return SKILLS.get(name).execute(inp, ctx or CTX)


@pytest.fixture(scope="module")
def extraction():
    return skill("schema-metadata-extractor", {"prd": PRD, "schemas": SCHEMAS})


@pytest.fixture
def tmp():
    return Path(tempfile.mkdtemp())


def make(tmp):
    store = Store(f"sqlite:///{tmp}/t.db")
    return Runtime(store, SKILLS, AgentRegistry(ROOT / "agents", store, ROOT / "contracts"), LocalExecutor(2),
                   ArtifactStore(f"file://{tmp}/artifacts"), ROOT / "contracts")


def parse_ddl():
    spec = importlib.util.spec_from_file_location("sme", settings.skills_dir / "schema-metadata-extractor/scripts/run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_ddl


# ---- scenario-router ---------------------------------------------------------------------------------
def test_router_decisions(extraction):
    assert skill("scenario-router", {})["scenario"] == "uc1"
    r = skill("scenario-router", {"extraction": extraction})
    assert r["scenario"] == "uc2" and r["has_schema"] and not r["has_sources"] and r["method"] == "inferred"
    assert skill("scenario-router", {"schemas": ["member"]})["scenario"] == "uc2"
    r = skill("scenario-router", {"extraction": extraction, "schema_calls": [{"server": "oracle-mcp", "tool": "get_ddl"}]})
    assert r["scenario"] == "uc3" and r["has_sources"]
    assert skill("scenario-router", {"sources": [{"type": "mcp", "server": "db"}]})["scenario"] == "uc3"
    assert skill("scenario-router", {"sources": [{"type": "file"}]})["scenario"] == "uc1"
    r = skill("scenario-router", {"scenario": "uc1", "extraction": extraction})  # explicit wins
    assert r["scenario"] == "uc1" and r["method"] == "explicit" and any("forced" in a for a in r["assumptions"])
    assert skill("scenario-router", {"requirements": {"scenario": "uc3"}})["method"] == "requirements"
    with pytest.raises(ValueError):
        skill("scenario-router", {"scenario": "uc9"})


# ---- provisional-schema-generator --------------------------------------------------------------------
def test_provisional_schema_from_domain_model():
    out = skill("provisional-schema-generator", {"domain_model": DOMAIN_MODEL})
    tables = {t["name"]: t for t in out["tables"]}
    assert set(tables) == {"loan_application", "member"} and all(t["source"] == "synthetic" for t in tables.values())
    la = {c["name"]: c for c in tables["loan_application"]["columns"]}
    assert la["id"]["primary_key"] and la["id"]["type"] == "BIGINT"
    assert la["amount"]["type"] == "NUMERIC(12,2)" and la["applied_at"]["type"] == "TIMESTAMP"
    assert la["is_joint"]["type"] == "BOOLEAN" and la["applicant_count"]["type"] == "INTEGER"
    assert la["status"]["type"] == "VARCHAR(100)" and la["status"]["nullable"] is False
    assert la["purpose"]["type"] == "VARCHAR(100)"
    assert la["member_id"]["references"] == "member.id" and la["member_id"]["type"] == "BIGINT"  # from the relationship
    assert out["ddl"].count("-- source: synthetic") == 2 and "REFERENCES member(id)" in out["ddl"]
    assert any("purpose" in a for a in out["assumptions"])
    parsed = {t["name"]: t for t in parse_ddl()(out["ddl"])}  # round-trips through the metadata extractor's parser
    assert parsed["loan_application"]["source"] == "synthetic"
    assert next(c for c in parsed["loan_application"]["columns"] if c["name"] == "member_id")["references"] == "member.id"


def test_provisional_schema_many_to_one_and_junction():
    dm = {"entities": [{"id": "Order", "name": "Order", "attributes": [{"name": "total"}], "evidence": []},
                       {"id": "Customer", "name": "Customer", "attributes": [{"name": "name"}], "evidence": []},
                       {"id": "Tag", "name": "Tag", "attributes": [{"name": "label"}], "evidence": []}],
          "relationships": [{"from": "Order", "to": "Customer", "type": "many-to-one"},
                            {"from": "Order", "to": "Tag", "type": "many_to_many"}]}
    out = skill("provisional-schema-generator", {"domain_model": dm})
    t = {x["name"]: {c["name"]: c for c in x["columns"]} for x in out["tables"]}
    assert t["order"]["customer_id"]["references"] == "customer.id" and "order_id" not in t["customer"]
    assert set(t["order_tag"]) == {"id", "order_id", "tag_id"}


# ---- synthetic-data-generator ------------------------------------------------------------------------
def test_generator_is_deterministic_and_keeps_fk_integrity():
    tables = skill("provisional-schema-generator", {"domain_model": DOMAIN_MODEL})["tables"]
    a = skill("synthetic-data-generator", {"tables": tables, "rows_per_table": 30, "seed": 7, "overrides": {"member": 10}})
    b = skill("synthetic-data-generator", {"tables": tables, "rows_per_table": 30, "seed": 7, "overrides": {"member": 10}})
    c = skill("synthetic-data-generator", {"tables": tables, "rows_per_table": 30, "seed": 8, "overrides": {"member": 10}})
    assert a == b and a["synthetic"] is True and a["seed"] == 7
    assert a["tables"] != c["tables"]
    assert a["order"] == ["member", "loan_application"]  # referenced table first
    assert a["row_counts"] == {"member": 10, "loan_application": 30}
    rows = {t["name"]: t["rows"] for t in a["tables"]}
    ids = {r["id"] for r in rows["member"]}
    assert ids == set(range(1, 11)) and all(r["member_id"] in ids for r in rows["loan_application"])
    la = rows["loan_application"][0]
    assert isinstance(la["amount"], float) and isinstance(la["is_joint"], bool) and "@" in rows["member"][0]["email"]
    assert la["status"] in ("active", "pending", "approved", "rejected", "closed")


def test_generator_accepts_extraction_and_selects_by_scenario(extraction):
    out = skill("synthetic-data-generator", {"extraction": extraction, "rows_per_table": 12})
    assert out["order"].index("member") < out["order"].index("loan_application") < out["order"].index("fair_lending_snapshot")
    rows = {t["name"]: t["rows"] for t in out["tables"]}
    assert all(len(r) == 12 for r in rows.values())
    assert {r["member_id"] for r in rows["loan_application"]} <= {r["id"] for r in rows["member"]}
    assert isinstance(rows["loan_application"][0]["amount"], float)  # type taken from the metadata graph (numeric)
    assert rows["fair_lending_snapshot"][0]["snapshot_id"] == 1
    prov = skill("provisional-schema-generator", {"domain_model": DOMAIN_MODEL})["tables"]
    uc1 = skill("synthetic-data-generator", {"scenario": "uc1", "tables_from_schema": extraction, "tables_provisional": prov})
    uc2 = skill("synthetic-data-generator", {"scenario": "uc2", "tables_from_schema": extraction, "tables_provisional": prov})
    assert "fair_lending_snapshot" not in uc1["row_counts"] and "fair_lending_snapshot" in uc2["row_counts"]
    only = skill("synthetic-data-generator", {"scenario": "uc2", "tables_from_schema": None, "tables_provisional": prov})
    assert set(only["row_counts"]) == {"loan_application", "member"}
    with pytest.raises(ValueError):
        skill("synthetic-data-generator", {"scenario": "uc2"})


def test_generator_breaks_cycles_with_a_note():
    tables = [{"name": "a", "columns": [{"name": "id", "type": "bigint", "primary_key": True, "nullable": False},
                                        {"name": "b_id", "type": "bigint", "nullable": True, "references": "b.id"}]},
              {"name": "b", "columns": [{"name": "id", "type": "bigint", "primary_key": True, "nullable": False},
                                        {"name": "a_id", "type": "bigint", "nullable": True, "references": "a.id"}]}]
    out = skill("synthetic-data-generator", {"tables": tables, "rows_per_table": 5})
    assert out["row_counts"] == {"a": 5, "b": 5} and any("cycle" in n for n in out["notes"])


# ---- data-landing ------------------------------------------------------------------------------------
GEN = {"tables": [{"name": "member", "columns": ["id", "full_name", "active"],
                   "rows": [{"id": 1, "full_name": "Ada", "active": True}, {"id": 2, "full_name": None, "active": False}]}]}


def test_landing_writes_csv_and_manifest(tmp):
    store = ArtifactStore(f"file://{tmp}")
    ctx = {"run_id": "run-1", "dry_run": False, "enterprise": "rain", "artifacts": store}
    out = skill("data-landing", {**GEN, "synthetic": True, "source": "synthetic-data-generator"}, ctx)
    assert out["written"] is True and out["landing_uri"] == f"file://{tmp}/landing/rain/run-1"
    f = out["files"][0]
    assert f["uri"] == f"file://{tmp}/landing/rain/run-1/member.csv" and f["rows"] == 2 and f["format"] == "csv"
    assert f["schema_hash"] == hashlib.sha256(b"id,full_name,active").hexdigest()
    p = tmp / "landing/rain/run-1/member.csv"
    assert p.exists() and p.stat().st_size == f["bytes"]
    rows = list(csv.DictReader(p.open()))
    assert rows == [{"id": "1", "full_name": "Ada", "active": "true"}, {"id": "2", "full_name": "", "active": "false"}]
    manifest = json.loads((tmp / "landing/rain/run-1/_manifest.json").read_text())
    assert manifest["synthetic"] is True and manifest["run_id"] == "run-1" and manifest["files"][0]["table"] == "member"


def test_landing_dry_run_and_no_store_write_nothing(tmp):
    store = ArtifactStore(f"file://{tmp}")
    out = skill("data-landing", GEN, {"run_id": "r2", "dry_run": True, "enterprise": None, "artifacts": store})
    assert out["written"] is False and out["files"][0]["uri"] == f"file://{tmp}/landing/platform/r2/member.csv"
    assert not (tmp / "landing").exists()
    out = skill("data-landing", GEN, {"run_id": "r3", "dry_run": False, "enterprise": None, "artifacts": None})
    assert out["written"] is False and out["files"][0]["uri"] == "file://landing/platform/r3/member.csv"


def test_landing_parquet_falls_back_to_csv_without_pyarrow(tmp):
    out = skill("data-landing", {**GEN, "format": "parquet"}, {"run_id": "r4", "dry_run": False, "artifacts": ArtifactStore(f"file://{tmp}")})
    try:
        import pyarrow  # noqa: F401
        assert out["format"] == "parquet" and "note" not in out
    except ImportError:
        assert out["format"] == "csv" and "pyarrow" in out["note"] and (tmp / "landing/platform/r4/member.csv").exists()


# ---- data-profiler -----------------------------------------------------------------------------------
def test_profiler_on_rows_and_on_landed_files(tmp):
    rows = [{"id": 1, "amount": 10.5, "status": "a"}, {"id": 2, "amount": None, "status": "b"},
            {"id": 3, "amount": 3, "status": "a"}, {"id": 4, "amount": "", "status": None}]
    p = skill("data-profiler", {"tables": [{"name": "t", "rows": rows}]})
    assert p["tables_profiled"] == ["t"] and p["profiles"]["t"]["rows"] == 4
    cols = p["profiles"]["t"]["columns"]
    assert cols["amount"] == {"null_rate": 0.5, "distinct": 2, "min": 3, "max": 10.5, "sample": [10.5, 3]}
    assert cols["status"]["null_rate"] == 0.25 and cols["status"]["distinct"] == 2 and cols["status"]["min"] == "a"
    assert cols["id"]["null_rate"] == 0.0 and cols["id"]["min"] == 1 and cols["id"]["max"] == 4
    store = ArtifactStore(f"file://{tmp}")
    ctx = {"run_id": "r1", "dry_run": False, "enterprise": None, "artifacts": store}
    landed = skill("data-landing", {"tables": [{"name": "t", "columns": ["id", "amount", "status"], "rows": rows}]}, ctx)
    q = skill("data-profiler", {"files": [{"table": landed["files"][0]["table"], "uri": landed["files"][0]["uri"]}]}, ctx)
    assert q["profiles"]["t"]["source"] == "file" and q["profiles"]["t"]["columns"]["amount"]["null_rate"] == 0.5
    assert q["profiles"]["t"]["columns"]["amount"]["max"] == 10.5 and q["profiles"]["t"]["columns"]["id"]["distinct"] == 4
    bad = skill("data-profiler", {"files": [{"table": "x", "uri": f"file://{tmp}/nope.csv"}]}, ctx)
    assert bad["profiles"]["x"]["rows"] is None and "error" in bad["profiles"]["x"]
    with pytest.raises(ValueError):
        skill("data-profiler", {})


# ---- data-readiness-report ---------------------------------------------------------------------------
def test_readiness_report_statuses_are_contract_valid(tmp, extraction):
    schema_only = skill("data-readiness-report", {"scenario": "uc2", "extraction": extraction, "assumptions": [["a"], None, "b"]})
    jsonschema.validate(schema_only, CONTRACT)
    assert schema_only["readiness_status"] == "schema_only" and schema_only["assumptions"] == ["a", "b"]
    assert {t["status"] for t in schema_only["tables"]} == {"schema_only"} and len(schema_only["gaps"]) == 3
    by = {t["name"]: t for t in schema_only["tables"]}
    assert by["loan_application"]["source"] == "core_banking" and by["member"]["schema_hash"] and by["member"]["uri"] is None

    ctx = {"run_id": "r1", "dry_run": False, "enterprise": None, "artifacts": ArtifactStore(f"file://{tmp}")}
    gen = skill("synthetic-data-generator", {"extraction": extraction, "rows_per_table": 5})
    landed = skill("data-landing", {"tables": gen["tables"], "synthetic": True}, ctx)
    profiles = skill("data-profiler", {"tables": gen["tables"]})
    full = skill("data-readiness-report", {"scenario": "uc2", "extraction": extraction, "landed": landed, "profiles": profiles})
    jsonschema.validate(full, CONTRACT)
    assert full["readiness_status"] == "synthetic" and full["gaps"] == [] and full["landing_uri"] == landed["landing_uri"]
    t = {x["name"]: x for x in full["tables"]}
    assert t["member"]["status"] == "landed" and t["member"]["synthetic"] and t["member"]["rows"] == 5
    assert t["member"]["source"] == "crm" and t["member"]["profile"]["rows"] == 5 and t["member"]["uri"].endswith("member.csv")

    unresolved = {"tables": ["ghost"], "columns": {"ghost": []}, "lineage": {}, "unresolved_schemas": ["ghost"]}
    missing = skill("data-readiness-report", {"scenario": "uc3", "extraction": unresolved})
    jsonschema.validate(missing, CONTRACT)
    assert missing["tables"][0]["status"] == "missing" and missing["summary"]["missing"] == 1
    with pytest.raises(ValueError):
        skill("data-readiness-report", {"scenario": "uc4"})


# ---- agent end to end --------------------------------------------------------------------------------
def _assert_persisted(rt, run, tmp):
    assert run["status"] == "succeeded", run["error"]
    assert run["state"]["acceptance"]["passed"] is True
    arts = rt.store.artifacts(kind="data_assets", run_id=run["id"])
    assert len(arts) == 1 and run["output"]["artifact_version"] == arts[0]["version"]
    jsonschema.validate(arts[0]["body"], CONTRACT)
    landing = tmp / "artifacts/landing/platform" / run["id"]
    assert (landing / "_manifest.json").exists()
    for t in run["output"]["tables"]:
        assert t["status"] == "landed" and t["synthetic"] is True and (landing / f"{t['name']}.csv").exists()
        assert t["profile"]["rows"] == t["rows"]
    return landing


def test_agent_uc2_from_extraction(tmp, extraction):
    rt = make(tmp)
    run = rt.start("data-acquisition-agent", {"extraction": extraction, "rows_per_table": 20})
    landing = _assert_persisted(rt, run, tmp)
    o = run["output"]
    assert o["scenario"] == "uc2" and o["readiness_status"] == "synthetic" and o["gaps"] == []
    assert {t["name"] for t in o["tables"]} == set(SCHEMAS) and o["provisional_schema"] is None
    assert o["landing_uri"] == f"file://{tmp}/artifacts/landing/platform/{run['id']}"
    assert {t["name"]: t["source"] for t in o["tables"]}["loan_application"] == "core_banking"
    assert run["state"]["steps"]["provisional"]["skipped"] is True
    members = {r["id"] for r in csv.DictReader((landing / "member.csv").open())}
    assert len(members) == 20 and all(r["member_id"] in members for r in csv.DictReader((landing / "loan_application.csv").open()))


def test_agent_uc1_from_domain_model(tmp):
    rt = make(tmp)
    run = rt.start("data-acquisition-agent", {"domain_model": DOMAIN_MODEL, "rows_per_table": 15, "seed": 3})
    landing = _assert_persisted(rt, run, tmp)
    o = run["output"]
    assert o["scenario"] == "uc1" and o["readiness_status"] == "synthetic"
    assert {t["name"] for t in o["tables"]} == {"loan_application", "member"}
    assert all(t["source"] == "synthetic" for t in o["tables"])
    assert "CREATE TABLE loan_application" in o["provisional_schema"]["ddl"]
    assert any("domain model" in a for a in o["assumptions"])
    members = {r["id"] for r in csv.DictReader((landing / "member.csv").open())}
    assert all(r["member_id"] in members for r in csv.DictReader((landing / "loan_application.csv").open()))


def test_agent_uc3_label_with_mcp_sources(tmp, extraction):
    rt = make(tmp)
    run = rt.start("data-acquisition-agent", {"extraction": extraction, "schema_calls": [{"server": "oracle-mcp", "tool": "get_ddl"}],
                                              "rows_per_table": 5})
    _assert_persisted(rt, run, tmp)
    assert run["output"]["scenario"] == "uc3" and run["output"]["readiness_status"] == "synthetic"


def test_agent_dry_run_lands_nothing_and_reports_schema_only(tmp, extraction):
    rt = make(tmp)
    run = rt.start("data-acquisition-agent", {"extraction": extraction, "rows_per_table": 5}, dry_run=True)
    assert run["status"] == "succeeded", run["error"]
    o = run["output"]
    assert o["readiness_status"] == "schema_only" and {t["status"] for t in o["tables"]} == {"schema_only"}
    assert len(o["gaps"]) == 3 and rt.store.artifacts() == [] and not (tmp / "artifacts/landing").exists()
