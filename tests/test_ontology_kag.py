"""Lower ontology, upper-ontology alignment and KAG construction (PRD US-012..US-015, plan 4.3 / 5.5 / 5.6 / 5.8)."""
import json
import tempfile
from pathlib import Path

import jsonschema
import pytest

from dif.artifacts.store import ArtifactStore
from dif.config import ROOT, settings
from dif.runtime.agents import AgentRegistry, validate_agent
from dif.runtime.engine import Runtime
from dif.runtime.executors import LocalExecutor
from dif.runtime.store import Store
from dif.skills.registry import SkillRegistry

PRD = (ROOT / "samples/prd.txt").read_text()
SKILLS = SkillRegistry(settings.skills_dirs)
EXTRACTION = SKILLS.get("schema-metadata-extractor").execute({"prd": PRD, "schemas": ["loan_application", "member", "fair_lending_snapshot"]})
UPPER = json.loads((ROOT / "platform/ontology/upper-ontology.v1.json").read_text())


def ev(text):
    return [{"source": "prd", "text": text}]


DOMAIN_MODEL = {
    "entities": [
        {"id": "loan_application", "name": "Loan Application", "description": "A member's request for a loan product.",
         "attributes": [{"name": "id", "type": "integer"}, {"name": "member_id", "type": "integer"}, {"name": "product_type", "type": "string"},
                        {"name": "status"}, {"name": "amount", "type": "decimal"}, {"name": "applied_at", "type": "timestamp"}],
         "keys": ["id"], "evidence": ev("The dashboard shows loan applications and members.")},
        {"id": "member", "name": "Member", "description": "A credit union member.",
         "attributes": [{"name": "id"}, {"name": "full_name"}, {"name": "zip_code"}, {"name": "joined_at"}],
         "keys": ["id"], "evidence": ev("The dashboard shows loan applications and members.")},
        {"id": "fair_lending_snapshot", "name": "Fair Lending Snapshot", "description": "Periodic approval-rate snapshot for regulators.",
         "attributes": [{"name": "snapshot_id"}, {"name": "loan_application_id"}, {"name": "approval_rate"}, {"name": "snapshot_date"}],
         "keys": ["snapshot_id"], "evidence": ev("a fair lending snapshot for regulators")},
        {"id": "risk_score", "name": "Risk Score", "description": "Model-derived risk rating of an application.",
         "attributes": [{"name": "score", "type": "decimal"}, {"name": "scored_at"}, {"name": "loan_application_id"}],
         "keys": [], "evidence": ev("It also needs a risk_score entity that is not yet modelled.")},
    ],
    "relationships": [
        {"from": "loan_application", "to": "member", "type": "many_to_one", "name": "applicant", "evidence": ev("members apply")},
        {"from": "fair_lending_snapshot", "to": "loan_application", "type": "many_to_one"},
        {"from": "risk_score", "to": "loan_application", "type": "one_to_one", "name": "scores"},
    ],
}
SEMANTIC = {"mappings": [
    {"entity": "loan_application", "table": "loan_application", "confidence": 0.95, "method": "name"},
    {"entity": "member", "table": "member", "confidence": 0.95, "method": "name"},
    {"entity": "fair_lending_snapshot", "table": "fair_lending_snapshot", "confidence": 0.9, "method": "name"},
    {"entity": "member", "table": "member", "attribute": "full_name", "column": "full_name", "confidence": 0.9, "method": "name"},
], "gaps": [{"kind": "unmapped_entity", "name": "risk_score"}], "confidence": 0.9}
DATA_ASSETS = {"scenario": "uc1", "readiness_status": "synthetic", "assumptions": [], "gaps": [],
               "tables": [{"name": "loan_application", "synthetic": True, "status": "landed", "uri": "file:///x/loan_application.parquet"}]}


def contract(name):
    return json.loads((ROOT / "contracts" / name).read_text())


def valid(obj, schema):
    jsonschema.Draft202012Validator(contract(schema)).validate(obj)
    return True


def skill(name):
    return SKILLS.get(name)


def build(**over):
    return skill("lower-ontology-builder").execute({"domain_model": DOMAIN_MODEL, "semantic_mappings": SEMANTIC, "extraction": EXTRACTION, **over})


def make_runtime():
    tmp = Path(tempfile.mkdtemp())
    store = Store(f"sqlite:///{tmp}/t.db")
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(ROOT / "agents", store, ROOT / "contracts"),
                   LocalExecutor(2), ArtifactStore(f"file://{tmp}/artifacts"), ROOT / "contracts")


# ---- lower-ontology-builder ---------------------------------------------------------------------------
def test_builder_covers_entities_and_tables_and_is_contract_valid():
    onto = build()
    assert valid(onto, "ontology.v1.json")
    ids = {c["id"] for c in onto["classes"]}
    assert ids == {"LoanApplication", "Member", "FairLendingSnapshot", "RiskScore"}
    by_id = {c["id"]: c for c in onto["classes"]}
    assert by_id["LoanApplication"]["source"] == {"entity": "loan_application", "table": "loan_application"}
    assert by_id["RiskScore"]["source"]["table"] is None and by_id["RiskScore"]["evidence"]
    dp = {p["id"]: p["datatype"] for p in onto["data_properties"]}
    assert dp["LoanApplication.memberId"] == "xsd:integer" and dp["LoanApplication.appliedAt"] == "xsd:dateTime"
    assert dp["LoanApplication.amount"] == "xsd:decimal" and dp["Member.zipCode"] == "xsd:string" and dp["Member.fullName"] == "xsd:string"
    assert dp["FairLendingSnapshot.approvalRate"] == "xsd:decimal" and dp["RiskScore.loanApplicationId"] == "xsd:long"
    op = {p["id"]: p for p in onto["object_properties"]}
    assert op["LoanApplication.applicant"]["range"] == "Member" and op["LoanApplication.applicant"]["cardinality"] == "*..1"
    assert op["FairLendingSnapshot.hasLoanApplication"]["range"] == "LoanApplication"
    assert op["RiskScore.scores"]["cardinality"] == "1..1"
    assert {(p["domain"], p["range"]) for p in onto["object_properties"]} == {("LoanApplication", "Member"), ("FairLendingSnapshot", "LoanApplication"),
                                                                            ("RiskScore", "LoanApplication")}  # FK edges de-duplicated
    assert onto["coverage"] == {"entities_total": 4, "entities_covered": 4, "tables_total": 3, "tables_covered": 3}
    assert onto["validation"]["passed"] and onto["validation"]["score"] == 1.0
    assert {a["kind"] for a in onto["axioms"]} == {"key"} and any("LoanApplication is identified by id" == a["statement"] for a in onto["axioms"])


def test_builder_adds_classes_for_unmapped_tables_and_fk_object_properties():
    dm = {"entities": [DOMAIN_MODEL["entities"][1]], "relationships": []}  # only Member is modelled
    onto = skill("lower-ontology-builder").execute({"domain_model": dm, "extraction": EXTRACTION})
    assert valid(onto, "ontology.v1.json")
    by_id = {c["id"]: c for c in onto["classes"]}
    assert set(by_id) == {"Member", "LoanApplication", "FairLendingSnapshot"}
    assert by_id["Member"]["source"]["table"] == "member"  # bound by name without semantic mappings
    assert by_id["LoanApplication"]["source"] == {"entity": None, "table": "loan_application"}
    assert "loan_application sourced from core_banking" in by_id["LoanApplication"]["evidence"][0]
    assert {p["name"] for p in onto["data_properties"] if p["domain"] == "LoanApplication"} == {"id", "memberId", "productType", "status", "amount", "appliedAt"}
    fk = next(p for p in onto["object_properties"] if p["domain"] == "LoanApplication")
    assert fk["name"] == "member" and fk["range"] == "Member" and fk["cardinality"] == "*..1"
    assert onto["namespace"] == "https://dif.radiant.digital/ontology/enterprise#"
    assert onto["coverage"]["tables_covered"] == 3 and onto["validation"]["passed"]


def test_builder_llm_descriptions_refine_and_degrade(monkeypatch):
    from dif import llm
    dm = {"entities": [{"id": "member", "name": "Member", "attributes": [{"name": "id"}], "evidence": []}], "relationships": []}
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", lambda p: '{"Member": "A person who holds a share account."}')
    out = skill("lower-ontology-builder").execute({"domain_model": dm})
    assert out["classes"][0]["description"] == "A person who holds a share account." and out["classes"][0]["description_source"] == "llm"

    def boom(p): raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "complete", boom)
    out = skill("lower-ontology-builder").execute({"domain_model": dm})
    assert out["llm_error"] == "down" and out["classes"][0]["description"] is None and out["validation"]["passed"]


# ---- ontology-validator ---------------------------------------------------------------------------------
def test_validator_catches_dangling_range_and_duplicate_class():
    onto = build()
    onto["object_properties"].append({"id": "Member.owns", "name": "owns", "domain": "Member", "range": "Vehicle"})
    onto["classes"].append(dict(onto["classes"][1]))
    rep = skill("ontology-validator").execute({"ontology": onto, "domain_model": DOMAIN_MODEL})
    assert not rep["passed"] and rep["score"] < 1
    failed = {c["name"] for c in rep["checks"] if not c["passed"]}
    assert failed == {"unique_classes", "object_property_refs"}
    assert any("Vehicle" in i["message"] for i in rep["issues"]) and any(i["subject"] == "Member.owns" for i in rep["issues"])
    rep = skill("ontology-validator").execute({"ontology": {**build(), "classes": build()["classes"][:3]}, "domain_model": DOMAIN_MODEL})
    assert "entity_coverage" in {c["name"] for c in rep["checks"] if not c["passed"]}


def test_validator_checks_alignment_consistency():
    onto = build()
    alignment = {"upper_ontology_version": "1.0.0", "confidence": 0.5, "unaligned": [], "extensions_proposed": [],
                 "mappings": [{"class": "Member", "upper_concept": "Nobody", "relation": "exact", "confidence": 1}]}
    rep = skill("ontology-validator").execute({"ontology": onto, "alignment": alignment})
    failed = {c["name"] for c in rep["checks"] if not c["passed"]}
    assert failed == {"alignment_coverage", "alignment_concepts"}


# ---- upper-ontology-aligner -----------------------------------------------------------------------------
def test_aligner_maps_classes_and_proposes_extensions():
    onto = build()
    onto["classes"].append({"id": "Zorblax", "name": "Zorblax", "description": None, "source": {"entity": None, "table": "zorblax"}, "evidence": []})
    al = skill("upper-ontology-aligner").execute({"ontology": onto, "semantic_mappings": SEMANTIC, "domain_model": DOMAIN_MODEL})
    assert valid(al, "alignment.v1.json")
    m = {x["class"]: x for x in al["mappings"]}
    assert m["LoanApplication"]["upper_concept"] in ("Application", "Agreement")
    assert m["Member"]["upper_concept"] in ("Person", "Party")
    assert m["FairLendingSnapshot"]["upper_concept"] in ("Event", "Rule") and m["FairLendingSnapshot"]["confidence"] > 0.3
    assert m["RiskScore"]["upper_concept"] == "Metric" and m["RiskScore"]["relation"] == "narrower"
    assert all(x["evidence"] for x in al["mappings"]) and al["upper_ontology_version"] == "1.0.0"
    assert al["unaligned"] == ["Zorblax"] and al["extensions_proposed"][0]["classes"] == ["Zorblax"] and al["extensions_proposed"][0]["parent"] == "Thing"
    assert 0 < al["confidence"] <= 1 and al["validation"]["passed"]
    exact = skill("upper-ontology-aligner").execute({"ontology": {**onto, "classes": [{"id": "Account", "name": "Account", "source": {"table": "account"}}]}})
    assert exact["mappings"][0]["relation"] == "exact" and exact["mappings"][0]["upper_concept"] == "Account"
    rep = skill("ontology-validator").execute({"ontology": onto, "alignment": al, "upper_ontology": UPPER})
    assert rep["passed"]


def test_aligner_llm_refines_unaligned_and_degrades(monkeypatch):
    from dif import llm
    onto = {"name": "t", "version": "1.0.0", "namespace": "x#", "classes": [{"id": "Zorblax", "name": "Zorblax", "source": {"table": "zorblax"}}],
            "object_properties": [], "data_properties": [], "coverage": {}, "validation": {"passed": True}}
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm, "complete", lambda p: "Asset")
    al = skill("upper-ontology-aligner").execute({"ontology": onto})
    assert al["mappings"] == [{"class": "Zorblax", "upper_concept": "Asset", "confidence": 0.4, "relation": "related", "evidence": ["llm"], "method": "llm"}]
    assert al["unaligned"] == [] and al["extensions_proposed"] == []
    monkeypatch.setattr(llm, "complete", lambda p: "Spaceship")  # not an upper concept: rejected
    assert skill("upper-ontology-aligner").execute({"ontology": onto})["unaligned"] == ["Zorblax"]

    def boom(p): raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "complete", boom)
    al = skill("upper-ontology-aligner").execute({"ontology": onto})
    assert al["llm_error"] == "down" and al["unaligned"] == ["Zorblax"] and valid(al, "alignment.v1.json")


# ---- kag-model-mapper -----------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mapped():
    onto = build()
    al = skill("upper-ontology-aligner").execute({"ontology": onto})
    return skill("kag-model-mapper").execute({"ontology": onto, "alignment": al, "extraction": EXTRACTION, "semantic_mappings": SEMANTIC,
                                              "data_assets": DATA_ASSETS, "release": "rel-test", "artifact_versions": {"lower_ontology": 3}},
                                             {"enterprise": "ussfcu", "run_id": "r1"})


def test_mapper_records_and_counts(mapped):
    nodes = {n["key"]: n for n in mapped["nodes"]}
    assert mapped["release"] == "rel-test" and mapped["enterprise_id"] == "ussfcu"
    assert nodes["class:LoanApplication"]["labels"] == ["Enterprise", "Class"]
    assert nodes["class:LoanApplication"]["props"]["enterprise_id"] == "ussfcu" and nodes["class:LoanApplication"]["props"]["release"] == "rel-test"
    assert nodes["class:LoanApplication"]["props"]["provenance"] == ["lower_ontology", "ontology_alignment"]
    assert nodes["table:member"]["labels"] == ["Enterprise", "Table"] and "semantic_mappings" in nodes["table:member"]["props"]["provenance"]
    assert nodes["column:member.full_name"]["labels"] == ["Enterprise", "Column"] and nodes["system:core_banking"]["labels"] == ["Enterprise", "System"]
    assert nodes["asset:loan_application"]["labels"] == ["Enterprise", "DataAsset"]
    concept = nodes["concept:Metric"]
    assert concept["labels"] == ["Platform", "Concept"] and "release" not in concept["props"]
    assert all(set(n["props"]) >= {"enterprise_id", "release", "provenance"} for n in mapped["nodes"] if "Enterprise" in n["labels"])
    assert all(n["props"]["provenance"] for n in mapped["nodes"] if "Enterprise" in n["labels"])
    types = mapped["counts"]["by_type"]
    assert types["HAS_PROPERTY"] == len(build()["data_properties"]) and types["RELATES_TO"] == 3 and types["ALIGNS_TO"] == 4
    assert types["MAPS_TO"] == 3 and types["BACKED_BY"] == 1 and types["HAS_COLUMN"] == 14 and types["REFERENCES"] == 2 and types["DERIVED_FROM"] == 3
    maps = next(r for r in mapped["relationships"] if r["type"] == "MAPS_TO" and r["from"] == "class:Member")
    assert maps["to"] == "table:member" and maps["props"] == {"confidence": 0.95, "method": "name"}
    aligns = next(r for r in mapped["relationships"] if r["type"] == "ALIGNS_TO" and r["from"] == "class:RiskScore")
    assert aligns["to"] == "concept:Metric" and set(aligns["props"]) == {"relation", "confidence"}
    assert mapped["counts"]["nodes"] == len(mapped["nodes"]) and mapped["counts"]["relationships"] == len(mapped["relationships"])
    assert mapped["counts"]["by_label"]["Enterprise:Class"] == 4 and mapped["counts"]["by_label"]["Platform:Concept"] >= 3
    assert all(set(r) == {"type", "from", "to", "props"} for r in mapped["relationships"])
    assert {p["artifact_kind"]: p["artifact_version"] for p in mapped["provenance"]} == {
        "lower_ontology": 3, "ontology_alignment": None, "normalized_metadata_graph": None, "semantic_mappings": None, "data_assets": None}
    keys = {n["key"] for n in mapped["nodes"]}
    assert all(r["from"] in keys and r["to"] in keys for r in mapped["relationships"])  # no dangling relationship ends


def test_mapper_skips_assets_without_a_table_and_has_no_orphans(mapped):
    onto = build()
    al = skill("upper-ontology-aligner").execute({"ontology": onto})
    assets = {**DATA_ASSETS, "tables": [*DATA_ASSETS["tables"], {"name": "risk_score", "synthetic": True, "status": "schema_only"}]}
    out = skill("kag-model-mapper").execute({"ontology": onto, "alignment": al, "extraction": EXTRACTION, "semantic_mappings": SEMANTIC,
                                             "data_assets": assets, "release": "rel-x"}, {"enterprise": "ussfcu"})
    assert "asset:risk_score" not in {n["key"] for n in out["nodes"]}
    assert out["skipped_assets"] == [{"name": "risk_score", "status": "schema_only", "reason": "no table node in the graph"}]
    check = skill("neo4j-validate").execute({"release": "rel-x", "nodes": out["nodes"], "relationships": out["relationships"]}, {"dry_run": True})
    assert not [i for i in check["issues"] if "orphan" in i["message"]]
    assert mapped["skipped_assets"] == [] or all(a["name"] != "loan_application" for a in mapped["skipped_assets"])


# ---- neo4j-publish --------------------------------------------------------------------------------------
class FakeSession:
    def __init__(self, log, results=None):
        self.log, self.results = log, results or {}

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def run(self, cypher, **params):
        self.log.append((cypher, params))
        value = next((v for k, v in self.results.items() if k in cypher), 0)

        class R:
            def single(self_inner): return {"c": value}
        return R()


class FakeDriver:
    def __init__(self, log, results=None):
        self.log, self.results, self.closed = log, results, False

    def session(self): return FakeSession(self.log, self.results)
    def close(self): self.closed = True


def test_publish_merges_per_label_set_and_is_idempotent(mapped, monkeypatch):
    pub = skill("neo4j-publish")
    pub._load()
    g = pub._fn.__globals__
    monkeypatch.setattr(settings, "neo4j_uri", "bolt://fake:7687")
    log, drivers = [], []

    def factory(uri, user, password):
        assert uri == "bolt://fake:7687"
        d = FakeDriver(log)
        drivers.append(d)
        return d
    monkeypatch.setitem(g, "_driver_factory", factory)
    inp = {"nodes": mapped["nodes"], "relationships": mapped["relationships"], "release": "rel-test", "enterprise": "ussfcu", "batch_size": 5}
    out = pub.execute(inp, {"dry_run": False})
    assert out["published"] is True and out["dry_run"] is False and out["counts"] == mapped["counts"]
    cyphers = [c for c, _ in log]
    assert "UNWIND $rows AS r MERGE (n:Enterprise:Class {key: r.key, enterprise_id: r.enterprise_id, release: r.release}) SET n += r.props" in cyphers
    assert "UNWIND $rows AS r MERGE (n:Platform:Concept {key: r.key}) SET n += r.props" in cyphers
    assert any("MERGE (a)-[rel:ALIGNS_TO]->(b)" in c and "MATCH (a {key: r.from})" in c for c in cyphers)
    label_sets = {c.split("MERGE (n:")[1].split(" ")[0] for c in cyphers if "MERGE (n:" in c}
    assert label_sets == set(mapped["counts"]["by_label"])
    assert all(len(p["rows"]) <= 5 for _, p in log) and sum(len(p["rows"]) for c, p in log if "MERGE (n:" in c) == mapped["counts"]["nodes"]
    row = next(p["rows"][0] for c, p in log if "Enterprise:Class" in c)
    assert row["enterprise_id"] == "ussfcu" and row["release"] == "rel-test" and row["props"]["release"] == "rel-test"
    assert drivers[0].closed
    first = list(log)
    log.clear()
    assert pub.execute(inp, {"dry_run": False})["published"] is True
    assert log == first  # idempotent: identical MERGE statements on re-run


def test_publish_rejects_unsafe_labels(mapped, monkeypatch):
    monkeypatch.setattr(settings, "neo4j_uri", "")
    with pytest.raises(ValueError):
        skill("neo4j-publish").execute({"nodes": [{"key": "x", "labels": ["Enterprise", "Class) DETACH DELETE n //"], "props": {}}],
                                        "relationships": [], "release": "r"}, {})
    with pytest.raises(ValueError):
        skill("neo4j-publish").execute({"nodes": [], "relationships": [{"type": "drop all", "from": "a", "to": "b"}], "release": "r"}, {})


def test_publish_dry_run_and_unconfigured_do_not_connect(mapped, monkeypatch):
    pub = skill("neo4j-publish")
    pub._load()

    def boom(*a): raise AssertionError("must not connect")
    monkeypatch.setitem(pub._fn.__globals__, "_driver_factory", boom)
    monkeypatch.setattr(settings, "neo4j_uri", "")
    out = pub.execute({"nodes": mapped["nodes"], "relationships": mapped["relationships"], "release": "rel-test"}, {"dry_run": False})
    assert out["published"] is False and out["dry_run"] is False and "DIF_NEO4J_URI" in out["note"] and out["counts"] == mapped["counts"]
    monkeypatch.setattr(settings, "neo4j_uri", "bolt://fake:7687")
    out = pub.execute({"nodes": mapped["nodes"], "relationships": mapped["relationships"], "release": "rel-test"}, {"dry_run": True})
    assert out["published"] is False and out["dry_run"] is True and "dry run" in out["note"]


# ---- neo4j-validate -------------------------------------------------------------------------------------
def test_validate_in_memory_finds_orphan_and_missing_provenance(mapped, monkeypatch):
    monkeypatch.setattr(settings, "neo4j_uri", "")
    val = skill("neo4j-validate")
    good = val.execute({"release": "rel-test", "enterprise": "ussfcu", "nodes": mapped["nodes"], "relationships": mapped["relationships"]}, {})
    assert good["passed"] and good["mode"] == "memory" and {c["name"] for c in good["checks"]} == {
        "release_present", "orphan_nodes", "classes_aligned", "tables_mapped", "provenance_present"}
    nodes = mapped["nodes"] + [{"key": "class:Lonely", "labels": ["Enterprise", "Class"], "props": {"enterprise_id": "ussfcu", "release": "rel-test", "provenance": []}}]
    bad = val.execute({"release": "rel-test", "enterprise": "ussfcu", "nodes": nodes, "relationships": mapped["relationships"]}, {})
    assert not bad["passed"]
    by = {i["message"]: i for i in bad["issues"]}
    assert "1 orphan Enterprise node(s)" in by and by["1 orphan Enterprise node(s)"]["subjects"] == ["class:Lonely"]
    assert "1 Enterprise node(s) without provenance" in by
    assert next(i for i in bad["issues"] if "ALIGNS_TO" in i["message"])["severity"] == "warning"
    assert not val.execute({"release": "rel-test"}, {})["passed"]  # nothing to validate


def test_validate_with_driver_runs_scoped_cypher(monkeypatch):
    val = skill("neo4j-validate")
    val._load()
    log = []
    monkeypatch.setattr(settings, "neo4j_uri", "bolt://fake:7687")
    monkeypatch.setitem(val._fn.__globals__, "_driver_factory", lambda *a: FakeDriver(log, {"NOT (n)--()": 2, "MATCH (n:Enterprise {enterprise_id: $enterprise_id, release: $release}) RETURN": 10}))
    out = val.execute({"release": "rel-9", "enterprise": "ussfcu"}, {})
    assert out["mode"] == "graph" and not out["passed"]
    assert all(p == {"enterprise_id": "ussfcu", "release": "rel-9"} for _, p in log) and len(log) == 5
    assert [i["message"] for i in out["issues"]] == ["2 orphan Enterprise node(s)"]


# ---- platform-kag-seed ----------------------------------------------------------------------------------
def test_platform_seed_dry_run(monkeypatch):
    monkeypatch.setattr(settings, "neo4j_uri", "")
    out = skill("platform-kag-seed").execute({"skills": SKILLS.list()[:3], "agents": [{"name": "kag-builder-agent", "version": "1.0.0"}]}, {"dry_run": True})
    assert out["published"] is False and out["dry_run"] is True and out["release"] == "platform-1.0.0"
    by_label = out["counts"]["by_label"]
    assert by_label["Platform:Concept"] == len(UPPER["concepts"]) and by_label["Platform:Relation"] == len(UPPER["relations"])
    assert by_label["Platform:Skill"] == 3 and by_label["Platform:Agent"] == 1
    assert out["counts"]["by_type"]["SUBCLASS_OF"] == len([c for c in UPPER["concepts"] if c["parent"]])
    assert all("Platform" in n["labels"] for n in out["nodes"])


# ---- agents end to end ----------------------------------------------------------------------------------
def test_seed_agents_validate_against_layered_registry():
    rt = make_runtime()
    for name in ("lower-ontology-agent", "upper-ontology-alignment-agent", "kag-builder-agent"):
        validate_agent(rt.agents.get(name), rt.skills, rt.agents, ROOT / "contracts")


def test_ontology_and_kag_agents_end_to_end(monkeypatch):
    monkeypatch.setattr(settings, "neo4j_uri", "")
    rt = make_runtime()
    lo = rt.start("lower-ontology-agent", {"domain_model": DOMAIN_MODEL, "semantic_mappings": SEMANTIC, "extraction": EXTRACTION}, enterprise="ussfcu")
    assert lo["status"] == "succeeded", lo["error"]
    assert lo["state"]["acceptance"]["passed"] and lo["output"]["artifact_version"] == 1
    assert lo["output"]["validation"]["passed"] and lo["output"]["namespace"].endswith("/ussfcu#")
    onto = rt.store.artifacts()[0]
    assert onto["kind"] == "lower_ontology"
    ontology = {k: v for k, v in lo["output"].items() if k != "artifact_version"}
    assert valid(ontology, "ontology.v1.json")

    al = rt.start("upper-ontology-alignment-agent", {"ontology": ontology, "domain_model": DOMAIN_MODEL, "semantic_mappings": SEMANTIC}, enterprise="ussfcu")
    assert al["status"] == "succeeded", al["error"]
    assert al["state"]["acceptance"]["passed"] and al["output"]["validation"]["passed"] and al["output"]["unaligned"] == []
    alignment = {k: v for k, v in al["output"].items() if k != "artifact_version"}
    assert valid(alignment, "alignment.v1.json") and len(alignment["mappings"]) == 4

    kag = rt.start("kag-builder-agent", {"ontology": ontology, "alignment": alignment, "extraction": EXTRACTION, "semantic_mappings": SEMANTIC,
                                         "data_assets": DATA_ASSETS, "release": "rel-e2e"}, enterprise="ussfcu")
    assert kag["status"] == "succeeded", kag["error"]
    o = kag["output"]
    assert kag["state"]["acceptance"]["passed"] and o["published"] is False and o["dry_run"] is False and o["release"] == "rel-e2e"
    assert o["validation"]["passed"] and o["validation"]["mode"] == "memory" and o["counts"]["nodes"] > 20
    assert [p["artifact_kind"] for p in o["provenance"]][:2] == ["lower_ontology", "ontology_alignment"]
    assert valid({k: v for k, v in o.items() if k != "artifact_version"}, "kag-release.v1.json")
    assert {a["kind"] for a in rt.store.artifacts()} == {"lower_ontology", "ontology_alignment", "kag_release"}
    assert [e["event"] for e in rt.store.history(kag["id"])].count("acceptance_passed") == 1

    dry = rt.start("kag-builder-agent", {"ontology": ontology, "alignment": alignment, "release": "rel-dry"}, dry_run=True, enterprise="ussfcu")
    assert dry["status"] == "succeeded" and dry["output"]["dry_run"] is True and len(rt.store.artifacts()) == 3



def test_kag_builder_never_publishes_an_invalid_graph(monkeypatch):
    onto = build()
    al = skill("upper-ontology-aligner").execute({"ontology": onto})
    store = Store(f"sqlite:///{Path(tempfile.mkdtemp())}/t.db")
    rt = Runtime(store, SKILLS, AgentRegistry(ROOT / "agents", store, ROOT / "contracts"), LocalExecutor(1),
                 ArtifactStore(f"file://{tempfile.mkdtemp()}"), ROOT / "contracts")
    bad_ext = {**EXTRACTION, "tables": [*EXTRACTION["tables"], "lonely_table"]}  # a table with no columns/edges/mapping -> orphan node
    run = rt.start("kag-builder-agent", {"ontology": onto, "alignment": al, "extraction": bad_ext, "release": "rel-bad"})
    steps = run["state"]["steps"]
    assert run["status"] == "failed" and "precheck" in run["error"]
    assert steps["precheck"]["output"]["passed"] is False and steps["publish"]["skipped"] is True   # nothing was written
    good = rt.start("kag-builder-agent", {"ontology": onto, "alignment": al, "extraction": EXTRACTION, "release": "rel-ok"})
    assert good["status"] == "succeeded", good["error"]
    assert good["state"]["steps"]["precheck"]["output"]["passed"] is True and "skipped" not in good["state"]["steps"]["publish"]


# ---- platform KAG seed: registry-driven, agent, CLI ------------------------------------------------------
def make_rt():
    store = Store(f"sqlite:///{Path(tempfile.mkdtemp())}/t.db")
    return Runtime(store, SkillRegistry(settings.skills_dirs), AgentRegistry(ROOT / "agents", store, ROOT / "contracts"), LocalExecutor(1),
                   ArtifactStore(f"file://{tempfile.mkdtemp()}"), ROOT / "contracts")


def test_platform_seed_agent_uses_the_running_registry_and_the_whole_upper_ontology():
    rt = make_rt()
    run = rt.start("platform-kag-seed-agent", {}, by="system")
    assert run["status"] == "succeeded", run["error"]
    out = run["output"]
    assert out["release"] == f"platform-{UPPER['version']}" and out["published"] is False  # no Neo4j configured in tests
    by_label = out["counts"]["by_label"]
    assert by_label["Platform:Concept"] == len(UPPER["concepts"]) == 18 and by_label["Platform:Relation"] == len(UPPER["relations"])
    shared = [s for s in rt.skills.list() if not s.get("enterprise")]
    assert by_label["Platform:Skill"] == len(shared) and by_label["Platform:Agent"] == len([a for a in rt.agents.list() if a["enabled"]])
    assert by_label["Platform:Release"] == 1
    assert rt.store.artifacts("platform_kag_release")[0]["body"]["counts"]["nodes"] == out["counts"]["nodes"]


def test_platform_seed_ignores_enterprise_overrides_and_can_skip_the_registry():
    rt = make_rt()
    ctx = {"dry_run": True, "registry": {"skills": rt.skills, "agents": rt.agents}}
    out = rt.skills.get("platform-kag-seed").execute({}, ctx)
    skills = [n for n in out["nodes"] if "Skill" in n["labels"]]
    assert skills and all(n["props"]["name"] != "domain-enricher" or "rain" not in n["key"] for n in skills)
    assert len({n["key"] for n in skills}) == len(skills)                       # no duplicate keys from tenant overrides
    bare = rt.skills.get("platform-kag-seed").execute({"include_registry": False}, ctx)
    assert not [n for n in bare["nodes"] if "Skill" in n["labels"] or "Agent" in n["labels"]]


def test_seed_cli_exit_codes(monkeypatch, capsys):
    from dif import seed_platform
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{Path(tempfile.mkdtemp())}/cli.db")
    monkeypatch.setattr(settings, "artifact_store", f"file://{tempfile.mkdtemp()}")
    monkeypatch.setattr(settings, "neo4j_uri", "")
    assert seed_platform.main() == 0                                            # nothing to write is not an error
    assert '"published": false' in capsys.readouterr().out
    monkeypatch.setattr(settings, "neo4j_uri", "bolt://neo4j:7687")           # configured but the seed did not publish -> exit 1

    class Stub:
        def start(self, *a, **k):
            return {"status": "succeeded", "error": None, "output": {"release": "platform-1.0.0", "published": False, "counts": {"nodes": 1}}}
    monkeypatch.setattr("dif.runtime.factory.build_runtime", lambda *a, **k: Stub())
    assert seed_platform.main() == 1
    Stub.start = lambda self, *a, **k: {"status": "failed", "error": "boom", "output": None}
    assert seed_platform.main() == 1
    Stub.start = lambda self, *a, **k: {"status": "succeeded", "error": None, "output": {"release": "r", "published": True, "counts": {"nodes": 5}}}
    assert seed_platform.main() == 0
