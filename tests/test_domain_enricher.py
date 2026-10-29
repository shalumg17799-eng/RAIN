import importlib
import tempfile
from pathlib import Path

import pytest

from dif.config import ROOT, settings
from dif.skills.registry import SkillError, SkillRegistry
from test_platform import INP


@pytest.fixture(scope="module")
def reg():
    return SkillRegistry(settings.skills_dir)


@pytest.fixture(scope="module")
def extraction(reg):
    return reg.get("schema-metadata-extractor").execute(INP)


def enrich(reg, extraction, **kw):
    return reg.get("domain-enricher").execute({"extraction": extraction, **kw})


def test_sample_tables_map_to_expected_domain_and_capability(reg, extraction):
    out = enrich(reg, extraction)
    got = {t: (m["domain"], m["capability"]) for t, m in out["tables"].items()}
    assert got == {"loan_application": ("Lending", "Loan Origination"),
                   "member": ("Membership", "Member Management"),
                   "fair_lending_snapshot": ("Compliance", "Fair Lending Monitoring")}
    assert out["unmapped"] == [] and out["confidence"] > 0.8
    assert (out["domain"], out["capability"]) == ("Lending", "Loan Origination")  # first of equally weighted mappings
    for m in out["tables"].values():
        assert 0 < m["confidence"] <= 1 and m["evidence"] and m["method"] == "rules"


def test_domain_catalog_groups_tables_by_domain_and_capability(reg, extraction):
    cat = enrich(reg, extraction)["domain_catalog"]
    flat = {(d["name"], c["name"]): c["tables"] for d in cat["domains"] for c in d["capabilities"]}
    assert flat[("Lending", "Loan Origination")] == ["loan_application"]
    assert flat[("Compliance", "Fair Lending Monitoring")] == ["fair_lending_snapshot"]
    assert cat["taxonomy_version"] == "1"


def test_unrecognised_table_is_reported_unmapped_not_dropped(reg, extraction):
    ex = {**extraction, "tables": extraction["tables"] + ["zzz_widget"], "columns": {**extraction["columns"], "zzz_widget": ["id", "color"]}}
    out = enrich(reg, ex)
    assert out["unmapped"] == ["zzz_widget"]
    assert out["tables"]["zzz_widget"]["confidence"] == 0.0 and out["tables"]["zzz_widget"]["domain"] is None
    assert out["confidence"] < enrich(reg, extraction)["confidence"]  # unmapped tables pull the overall score down


def test_custom_inline_taxonomy_overrides_default(reg, extraction):
    tax = {"version": "9", "domains": [{"name": "Banking", "capabilities": [{"name": "Credit", "keywords": ["loan", "application"]}]}]}
    out = enrich(reg, extraction, taxonomy=tax)
    assert out["tables"]["loan_application"]["domain"] == "Banking"
    assert out["tables"]["member"]["domain"] is None and "member" in out["unmapped"]
    assert out["domain_catalog"]["taxonomy_version"] == "9"


def test_prd_sentences_add_evidence(reg, extraction):
    out = enrich(reg, extraction, prd="The loan_application table holds each underwriting decision.")
    assert any(e["source"] == "prd" for e in out["tables"]["loan_application"]["evidence"])


def test_bad_inputs_fail_clearly(reg, extraction):
    with pytest.raises(SkillError, match="missing required input"):
        reg.get("domain-enricher").execute({})
    with pytest.raises(ValueError, match="needs 'tables'"):
        enrich(reg, {"nope": 1})
    with pytest.raises(ValueError, match="unknown taxonomy"):
        enrich(reg, extraction, taxonomy="does-not-exist")
    with pytest.raises(ValueError, match="invalid taxonomy name"):
        enrich(reg, extraction, taxonomy="../../etc/passwd")
    with pytest.raises(ValueError, match="non-empty 'domains'"):
        enrich(reg, extraction, taxonomy={"domains": []})


def test_llm_fallback_only_for_unmapped_tables_and_only_valid_answers(reg, extraction, monkeypatch):
    from dif import llm
    ex = {**extraction, "tables": extraction["tables"] + ["zzz_widget"], "columns": {**extraction["columns"], "zzz_widget": ["id"]}}
    calls = []
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", lambda p: calls.append(p) or "Risk / Credit Risk")
    out = enrich(reg, ex)
    assert len(calls) == 1 and "zzz_widget" in calls[0]                    # asked once, for the unmapped table only
    assert out["tables"]["zzz_widget"]["method"] == "llm" and out["tables"]["zzz_widget"]["confidence"] == 0.4
    assert out["tables"]["loan_application"]["method"] == "rules" and out["unmapped"] == []

    monkeypatch.setattr(llm, "complete", lambda p: "Made Up / Nonsense")   # invented answers are rejected
    assert enrich(reg, ex)["unmapped"] == ["zzz_widget"]
    assert enrich(reg, ex, use_llm=False)["unmapped"] == ["zzz_widget"]


def test_llm_failure_degrades_to_rule_based_result(reg, extraction, monkeypatch):
    from dif import llm
    ex = {**extraction, "tables": extraction["tables"] + ["zzz_widget"], "columns": {**extraction["columns"], "zzz_widget": []}}

    def boom(p):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", boom)
    out = enrich(reg, ex)
    assert out["llm_error"] == "down" and out["unmapped"] == ["zzz_widget"] and out["tables"]["member"]["domain"] == "Membership"


def test_no_llm_call_when_provider_is_none(reg, extraction, monkeypatch):
    from dif import llm
    monkeypatch.setattr(llm, "complete", lambda p: pytest.fail("LLM must not be called"))
    ex = {**extraction, "tables": extraction["tables"] + ["zzz_widget"], "columns": {**extraction["columns"], "zzz_widget": []}}
    assert enrich(reg, ex)["unmapped"] == ["zzz_widget"]  # default provider is "none"


def test_skill_is_discovered_and_listed_by_api(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{Path(tempfile.mkdtemp())}/d.db")
    monkeypatch.setattr(settings, "api_keys", "")
    import dif.app
    importlib.reload(dif.app)
    skills = {s["name"]: s for s in TestClient(dif.app.app).get("/skills").json()}
    assert skills["domain-enricher"]["version"] == "1.0.0"
    assert skills["domain-enricher"]["validation"]["required_input"] == ["extraction"]
