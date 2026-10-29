"""Domain modelling (plan 5.1) and semantic mapping / enrichment extension (plan 5.4): extractor, normalizer,
domain-modelling-agent, semantic-mapper, domain-enrichment-agent with and without a domain model, Rain override."""
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
INP = {"prd": PRD, "schemas": ["loan_application", "member", "fair_lending_snapshot"]}
RICH_PRD = PRD + ("\nEach member has many loan applications. A loan application must reference exactly one member. "
                  "The member has a full_name, zip_code and joined_at. Risk Score is a numeric rating of default likelihood. "
                  "fair_lending_snapshot includes loan_application_id and approval_rate.")
SAMPLE_ENTITIES = {"loan_application", "member", "fair_lending_snapshot", "risk_score"}


def contract(name):
    return jsonschema.Draft202012Validator(json.loads((ROOT / "contracts" / name).read_text()))


def make():
    tmp = Path(tempfile.mkdtemp())
    store = Store(f"sqlite:///{tmp}/t.db")
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(ROOT / "agents", store, ROOT / "contracts"),
                   LocalExecutor(2), ArtifactStore(f"file://{tmp}/artifacts"), ROOT / "contracts")


@pytest.fixture(scope="module")
def reg():
    return SkillRegistry(settings.skills_dirs)


@pytest.fixture(scope="module")
def extraction(reg):
    return reg.get("schema-metadata-extractor").execute(INP)


@pytest.fixture(scope="module")
def domain_model(reg):
    draft = reg.get("domain-model-extractor").execute({"prd": RICH_PRD})
    return reg.get("domain-model-normalizer").execute({"domain_model": draft})


# ---- extractor ---------------------------------------------------------------------------------------
def test_extractor_finds_sample_entities_with_prd_evidence(reg):
    out = reg.get("domain-model-extractor").execute({"prd": PRD})
    ids = {e["id"] for e in out["entities"]}
    assert SAMPLE_ENTITIES <= ids
    assert "core_banking" not in ids and "compliance_dw" not in ids  # source systems are not entities
    for e in out["entities"]:
        assert e["evidence"] and all(ev["source"] == "prd" and ev["text"] in PRD for ev in e["evidence"])
    assert out["confidence"] == 1.0 and out["assumptions"] == []
    assert {"relationships", "constraints", "glossary"} <= set(out)


def test_extractor_attributes_relationships_constraints_glossary(reg):
    out = reg.get("domain-model-extractor").execute({"prd": RICH_PRD})
    ents = {e["id"]: e for e in out["entities"]}
    assert [a["name"] for a in ents["member"]["attributes"]] == ["full_name", "zip_code", "joined_at"]
    assert next(a for a in ents["member"]["attributes"] if a["name"] == "joined_at")["type"] == "timestamp"
    assert {a["name"] for a in ents["fair_lending_snapshot"]["attributes"]} == {"loan_application_id", "approval_rate"}
    assert "approval_rate" not in ents and "full_name" not in ents  # claimed attributes never become entities
    rels = {(r["from"], r["to"], r["type"], r["name"]) for r in out["relationships"]}
    assert ("member", "loan_application", "one-to-many", "has_many") in rels
    assert ("loan_application", "fair_lending_snapshot", "one-to-many", "foreign_key") in rels
    assert all(r["evidence"] for r in out["relationships"])
    assert [c["entity"] for c in out["constraints"]] == ["loan_application"] and "must" in out["constraints"][0]["rule"]
    assert out["glossary"] == [{"term": "Risk Score", "definition": "numeric rating of default likelihood"}]


def test_extractor_merges_requirements_existing_model_and_glossary(reg):
    existing = {"entities": [{"name": "Underwriter", "attributes": [{"name": "employee_id", "type": "integer"}],
                              "evidence": [{"source": "interview", "text": "underwriters approve loans"}]}],
                "relationships": [{"from": "underwriter", "to": "loan_application", "type": "one-to-many"}]}
    out = reg.get("domain-model-extractor").execute({"prd": PRD, "requirements": {"entities_mentioned": ["Branches"]},
                                                     "domain_model": existing, "glossary": {"APR": "annual percentage rate"}})
    ents = {e["id"]: e for e in out["entities"]}
    assert ents["underwriter"]["attributes"] == [{"name": "employee_id", "type": "integer"}]
    assert ents["underwriter"]["evidence"] == [{"source": "interview", "text": "underwriters approve loans"}]
    assert "branch" in ents and ents["branch"]["evidence"] == []  # requirement-only entity: no PRD sentence
    assert any("branch" in a for a in out["assumptions"]) and any("underwriter" in a for a in out["assumptions"])
    assert ("underwriter", "loan_application") in {(r["from"], r["to"]) for r in out["relationships"]}
    assert {"term": "APR", "definition": "annual percentage rate"} in out["glossary"]
    assert out["confidence"] < 1.0


def test_extractor_llm_refinement_and_degradation(reg, monkeypatch):
    from dif import llm
    sk = reg.get("domain-model-extractor")
    monkeypatch.setattr(llm, "complete", lambda p: pytest.fail("LLM must not be called with provider none"))
    sk.execute({"prd": PRD})

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    reply = json.dumps({"entities": [
        {"name": "Members", "description": "A credit union member", "attributes": [{"name": "fullName", "type": "string"}]},
        {"name": "Underwriter", "description": "Approves applications", "attributes": [{"name": "employee_id", "type": "integer"}],
         "relationships": [{"to": "Loan Application", "type": "one-to-many"}]},
        "garbage", {"name": 42}]})
    monkeypatch.setattr(llm, "complete", lambda p: "Sure:\n```json\n" + reply + "\n```")
    out = sk.execute({"prd": PRD})
    ents = {e["id"]: e for e in out["entities"]}
    assert "llm_error" not in out and SAMPLE_ENTITIES <= set(ents)
    assert ents["member"]["description"] == "A credit union member" and ents["member"]["attributes"] == [{"name": "full_name", "type": "string"}]
    assert ents["member"]["evidence"][0]["source"] == "prd"                        # PRD evidence is kept
    assert ents["underwriter"]["evidence"] == [{"source": "llm", "text": "Approves applications"}]
    assert ("underwriter", "loan_application", "one-to-many") in {(r["from"], r["to"], r["type"]) for r in out["relationships"]}
    assert out["confidence"] < 1.0  # the LLM-only entity has no PRD evidence

    def boom(p):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "complete", boom)
    out = sk.execute({"prd": PRD})
    assert out["llm_error"] == "down" and SAMPLE_ENTITIES <= {e["id"] for e in out["entities"]} and out["confidence"] == 1.0


# ---- normalizer --------------------------------------------------------------------------------------
def test_normalizer_dedupes_normalises_and_validates_contract(reg):
    messy = {"entities": [
        {"name": "Loan Applications", "attributes": [{"name": "Applied At", "type": "timestamp"}, "amount", {"name": "amount"}],
         "keys": ["ID"], "evidence": [{"source": "prd", "text": "x"}, {"source": "prd", "text": "x"}]},
        {"id": "loan_application", "attributes": [{"name": "status"}], "evidence": [{"source": "llm", "text": "y"}]},
        {"name": "members"},                                      # no evidence -> assumption
        "Risk Scores", {"nope": 1}],
        "relationships": [{"from": "Members", "to": "Loan Applications", "type": "has-lots"},
                          {"from": "member", "to": "ghost", "type": "one-to-many"},
                          {"from": "member", "to": "member", "type": "one-to-one"}],
        "constraints": ["Amount must be positive", {"entity": "Loan Applications", "rule": "status cannot be null"}, {"rule": ""}],
        "glossary": [{"term": "APR", "definition": "rate"}, {"term": "apr"}, {"definition": "no term"}]}
    out = reg.get("domain-model-normalizer").execute({"domain_model": messy})
    contract("domain-model.v1.json").validate(out)
    ents = {e["id"]: e for e in out["entities"]}
    assert set(ents) == {"loan_application", "member", "risk_score"}
    la = ents["loan_application"]
    assert la["name"] == "Loan Applications" and [a["name"] for a in la["attributes"]] == ["applied_at", "amount", "id", "status"]
    assert la["keys"] == ["id"] and la["evidence"] == [{"source": "prd", "text": "x"}, {"source": "llm", "text": "y"}]
    assert ents["member"]["evidence"] == [{"source": "assumption", "text": "'members' has no PRD evidence; kept as an assumption"}]
    assert out["relationships"] == [{"from": "member", "to": "loan_application", "type": "one-to-many", "name": None, "evidence": []}]
    assert len(out["assumptions"]) == 4 and any("ghost" in a for a in out["assumptions"])
    assert [c["entity"] for c in out["constraints"]] == [None, "loan_application"]
    assert out["glossary"] == [{"term": "APR", "definition": "rate"}]
    assert out["confidence"] == round(1 / 3, 2)
    assert reg.get("domain-model-normalizer").execute({"domain_model": out}) == out  # idempotent


def test_normalizer_is_idempotent_on_extractor_output(reg, domain_model):
    contract("domain-model.v1.json").validate(domain_model)
    assert reg.get("domain-model-normalizer").execute({"domain_model": domain_model}) == domain_model
    assert SAMPLE_ENTITIES <= {e["id"] for e in domain_model["entities"]} and domain_model["confidence"] == 1.0
    with pytest.raises(ValueError, match="'entities' list"):
        reg.get("domain-model-normalizer").execute({"domain_model": {"entities": "nope"}})


# ---- domain-modelling-agent --------------------------------------------------------------------------
def test_domain_modelling_agent_end_to_end():
    rt = make()
    run = rt.start("domain-modelling-agent", {"prd": RICH_PRD, "glossary": {"APR": "annual percentage rate"}})
    assert run["status"] == "succeeded", run["error"]
    assert run["state"]["acceptance"]["passed"]
    assert {c["name"] for c in run["state"]["acceptance"]["checks"]} == {"schema:domain-model.v1.json", "min_confidence", "output:entities"}
    contract("domain-model.v1.json").validate(run["output"])
    assert SAMPLE_ENTITIES <= {e["id"] for e in run["output"]["entities"]} and run["output"]["confidence"] == 1.0
    assert run["output"]["artifact_version"] == 1
    (art,) = rt.store.artifacts(kind="domain_model")
    assert art["run_id"] == run["id"] and {e["id"] for e in art["body"]["entities"]} >= SAMPLE_ENTITIES
    assert {"term": "APR", "definition": "annual percentage rate"} in art["body"]["glossary"]
    assert [e["event"] for e in rt.store.history(run["id"])].count("persisted") == 1
    assert rt.start("domain-modelling-agent", {"prd": RICH_PRD})["output"]["artifact_version"] == 2


def test_domain_modelling_agent_fails_acceptance_when_nothing_is_grounded():
    rt = make()
    run = rt.start("domain-modelling-agent", {"prd": "Nothing to see here.", "requirements": {"entities_mentioned": ["Widget"]}})
    assert run["status"] == "failed" and run["error"].startswith("acceptance failed")
    assert not run["state"]["acceptance"]["passed"] and run["output"]["confidence"] == 0.0


# ---- semantic-mapper ---------------------------------------------------------------------------------
def test_semantic_mapper_maps_sample_entities_and_lists_gaps(reg, extraction, domain_model):
    out = reg.get("semantic-mapper").execute({"domain_model": domain_model, "extraction": extraction, "prd": PRD})
    contract("semantic-mappings.v1.json").validate(out)
    ent = {m["entity"]: m for m in out["mappings"] if m["attribute"] is None}
    for e in ("loan_application", "member", "fair_lending_snapshot"):
        assert ent[e]["table"] == e and ent[e]["confidence"] >= 0.6 and ent[e]["method"] == "name" and ent[e]["evidence"]
    assert any("lineage" in ev for ev in ent["loan_application"]["evidence"])
    assert any("fk" in ev for ev in ent["fair_lending_snapshot"]["evidence"])   # loan_application_id supports the relationship
    cols = {(m["entity"], m["attribute"]): m["column"] for m in out["mappings"] if m["attribute"]}
    assert cols[("member", "full_name")] == "full_name" and cols[("fair_lending_snapshot", "approval_rate")] == "approval_rate"
    gaps = {(g["kind"], g["name"]) for g in out["gaps"]}
    assert ("unmapped_entity", "risk_score") in gaps and all(g["reason"] for g in out["gaps"])
    assert not any(k == "unmapped_table" for k, _ in gaps)
    assert out["confidence"] >= 0.6


def test_semantic_mapper_uses_attributes_synonyms_and_reports_unmapped_tables(reg):
    dm = {"entities": [{"id": "customer", "attributes": [{"name": "full_name"}, {"name": "zip_code"}, {"name": "joined_at"}], "evidence": []},
                       {"id": "credit_decision", "attributes": [{"name": "decided_at"}, {"name": "outcome"}, {"name": "reason_code"}], "evidence": []}]}
    ex = {"tables": ["dim_member", "decision_log", "zzz_widget"],
          "columns": {"dim_member": ["id", "full_name", "zip_code", "joined_at"],
                      "decision_log": ["id", "decided_at", "outcome", "reason_code"], "zzz_widget": ["id"]}}
    out = reg.get("semantic-mapper").execute({"domain_model": dm, "extraction": ex})
    contract("semantic-mappings.v1.json").validate(out)
    ent = {m["entity"]: m for m in out["mappings"] if m["attribute"] is None}
    assert ent["customer"]["table"] == "dim_member" and ent["customer"]["method"] == "name"          # synonym + prefix
    assert ent["credit_decision"]["table"] == "decision_log" and ent["credit_decision"]["method"] == "attribute"
    assert {(g["kind"], g["name"]) for g in out["gaps"]} == {("unmapped_table", "zzz_widget")}


def test_semantic_mapper_without_domain_model_is_valid_and_empty(reg, extraction):
    out = reg.get("semantic-mapper").execute({"extraction": extraction})
    contract("semantic-mappings.v1.json").validate(out)
    assert out["mappings"] == [] and out["confidence"] == 0.0
    assert {g["name"] for g in out["gaps"]} == set(extraction["tables"]) and {g["kind"] for g in out["gaps"]} == {"unmapped_table"}
    with pytest.raises(ValueError, match="needs 'tables'"):
        reg.get("semantic-mapper").execute({"extraction": {"nope": 1}})


def test_semantic_mapper_llm_refinement_and_degradation(reg, extraction, domain_model, monkeypatch):
    from dif import llm
    ex = {**extraction, "tables": extraction["tables"] + ["risk_rating"], "columns": {**extraction["columns"], "risk_rating": ["id", "band"]}}
    inp = {"domain_model": domain_model, "extraction": ex}
    monkeypatch.setattr(llm, "complete", lambda p: pytest.fail("LLM must not be called with provider none"))
    base = reg.get("semantic-mapper").execute(inp)
    assert ("unmapped_entity", "risk_score") in {(g["kind"], g["name"]) for g in base["gaps"]}

    calls = []
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", lambda p: calls.append(p) or json.dumps(
        [{"entity": "risk_score", "table": "risk_rating"}, {"entity": "compliance_dashboard", "table": "member"},  # member is taken
         {"entity": "loan_application", "table": "risk_rating"}, "junk"]))
    out = reg.get("semantic-mapper").execute(inp)
    contract("semantic-mappings.v1.json").validate(out)
    assert len(calls) == 1 and "risk_score" in calls[0] and "risk_rating" in calls[0] and "loan_application:" not in calls[0]
    ent = {m["entity"]: m for m in out["mappings"] if m["attribute"] is None}
    assert ent["risk_score"]["table"] == "risk_rating" and ent["risk_score"]["method"] == "llm" and ent["risk_score"]["confidence"] == 0.5
    assert ent["loan_application"]["table"] == "loan_application" and "compliance_dashboard" not in ent
    assert out["confidence"] > base["confidence"] and "llm_error" not in out

    def boom(p):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "complete", boom)
    out = reg.get("semantic-mapper").execute(inp)
    assert out["llm_error"] == "down" and {k: v for k, v in out.items() if k != "llm_error"} == base


# ---- domain-enricher with a domain model --------------------------------------------------------------
def test_enricher_uses_domain_model_entities_as_evidence(reg, extraction, domain_model):
    sk = reg.get("domain-enricher")
    without = sk.execute({"extraction": extraction, "prd": PRD})
    with_dm = sk.execute({"extraction": extraction, "prd": PRD, "domain_model": domain_model})
    for t in extraction["tables"]:
        assert without["tables"][t]["entity"] is None and with_dm["tables"][t]["entity"] == t
        assert with_dm["tables"][t]["score"] == without["tables"][t]["score"] + 2
        assert with_dm["tables"][t]["domain"] == without["tables"][t]["domain"]
        assert [e for e in with_dm["tables"][t]["evidence"] if e["source"] == "entity"] == [
            {"source": "entity", "entity": t, "keyword": next(e for e in with_dm["tables"][t]["evidence"] if e["source"] == "entity")["keyword"]}]
    # an entity only lifts the table it describes: member_contact scores 6 on its own (member + contact keywords), 8 with its entity
    ex = {**extraction, "tables": ["member_contact"], "columns": {"member_contact": ["id", "email"]}}
    dm = {"entities": [{"id": "member_contact", "name": "Member Contacts", "attributes": [{"name": "email"}],
                        "evidence": [{"source": "prd", "text": "Member contacts hold the profile email."}]}]}
    assert sk.execute({"extraction": ex, "min_score": 7})["unmapped"] == ["member_contact"]
    lifted = sk.execute({"extraction": ex, "domain_model": dm, "min_score": 7})
    assert lifted["unmapped"] == [] and lifted["tables"]["member_contact"]["score"] == 8 and lifted["tables"]["member_contact"]["entity"] == "member_contact"
    ghost = sk.execute({"extraction": ex, "domain_model": {"entities": [{"id": "ghost", "attributes": [], "evidence": []}]}, "min_score": 7})
    assert ghost["unmapped"] == ["member_contact"] and ghost["tables"]["member_contact"]["entity"] is None


# ---- domain-enrichment-agent ---------------------------------------------------------------------------
@pytest.mark.parametrize("with_model", [False, True])
def test_domain_enrichment_agent_with_and_without_domain_model(extraction, domain_model, with_model):
    rt = make()
    inp = {"extraction": {k: extraction[k] for k in ("tables", "columns", "keys", "lineage")}, "prd": PRD}
    if with_model:
        inp["domain_model"] = domain_model
    run = rt.start("domain-enrichment-agent", inp)
    assert run["status"] == "succeeded", run["error"]
    assert run["state"]["acceptance"]["passed"]
    out = run["output"]
    contract("domain-catalog.v1.json").validate(out)
    assert out["domain"] == "Lending" and out["unmapped"] == [] and out["artifact_version"] == 1
    assert out["semantic_mappings"]["gaps"] == out["gaps"]
    if with_model:
        assert {m["entity"] for m in out["semantic_mappings"]["mappings"]} >= {"loan_application", "member", "fair_lending_snapshot"}
        assert out["tables"]["member"]["entity"] == "member" and ("unmapped_entity", "risk_score") in {(g["kind"], g["name"]) for g in out["gaps"]}
    else:
        assert out["semantic_mappings"]["mappings"] == [] and {g["kind"] for g in out["gaps"]} == {"unmapped_table"}
        assert out["tables"]["member"]["entity"] is None
    assert [a["kind"] for a in rt.store.artifacts(run_id=run["id"])] == ["domain_catalog"]


def test_pipeline_output_still_has_no_domain_model_dependency():
    rt = make()
    run = rt.start("dif-pipeline-agent", INP)
    assert run["status"] == "succeeded", run["error"]
    assert run["output"]["domain_catalog"]["domains"] and run["output"]["unmapped"] == []


# ---- enterprise override ---------------------------------------------------------------------------------
def test_rain_override_is_used_only_for_rain(reg, extraction):
    assert reg.errors == {}
    assert reg.get("domain-enricher", enterprise="rain").enterprise == "rain"
    assert reg.get("domain-enricher", enterprise="nfcu").enterprise is None and reg.get("domain-enricher").enterprise is None
    rt = make()
    inp = {"extraction": {k: extraction[k] for k in ("tables", "columns", "lineage")}, "prd": PRD}
    rain = rt.start("domain-enrichment-agent", inp, enterprise="rain")
    assert rain["status"] == "succeeded", rain["error"]
    assert rain["output"]["domain_catalog"]["taxonomy_version"] == "rain-1"
    assert {t: m["domain"] for t, m in rain["output"]["tables"].items()} == {"loan_application": "Lending", "member": "Membership", "fair_lending_snapshot": "Compliance"}
    assert rt.store.artifacts(kind="domain_catalog", enterprise="rain")[0]["body"]["taxonomy_version"] == "rain-1"
    ev = next(e for e in rt.store.history(rain["id"]) if e["event"] == "step_started" and (e["detail"] or {}).get("step") == "enrich")
    assert ev["detail"]["enterprise_override"] == "rain"
    for ent in ("nfcu", None):
        other = rt.start("domain-enrichment-agent", inp, enterprise=ent)
        assert other["status"] == "succeeded", other["error"]
        assert other["output"]["domain_catalog"]["taxonomy_version"] == "1"
    # an explicit taxonomy still wins inside the override
    tax = {"version": "9", "domains": [{"name": "Banking", "capabilities": [{"name": "Credit", "keywords": ["loan", "application"]}]}]}
    custom = rt.start("domain-enrichment-agent", {**inp, "taxonomy": tax}, enterprise="rain")
    assert custom["output"]["domain_catalog"]["taxonomy_version"] == "9" and custom["output"]["tables"]["loan_application"]["domain"] == "Banking"
