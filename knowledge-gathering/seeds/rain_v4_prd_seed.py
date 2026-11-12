"""PRD v0.4 knowledge seed for the rain-v4.0.0 KAG release.

The factory publishes the DATA ontology (Class/Table/Column/DataAsset/System) from the v0.4
factory extract and planned schemas. This seed adds the rest of PRD v0.4
(doc/prd/RAIN_Platform_PRD_v0.4.docx): it reuses every record of the v0.3 seed (organizations,
counties and sites, the Q3 contract checkpoint, quality gate, measures, segments, use cases,
pages, workbenches, capabilities, the v0.3 personas, signals and guided steps) and adds:

- the roster properties of the seven personas (origin, data scope, build status, switcher order);
- the new READS edges of the workbenches;
- the 17 success metrics with their owner personas.

The v0.4 roster is the seven v0.3 personas only (Haskins, Castellanos, Malhotra, Pike, Lopez, Kee,
Linda Garcia). The v0.2 personas and Hannah Lee were removed from the KAG and the UI on 2026-11-10,
and no retired persona is kept in the graph.

Every node is release-scoped (rain-v4.0.0, provenance ["prd_seed"]). Neo4j Community has a
single user database, so the default target is database `neo4j`; override with NEO4J_URI,
NEO4J_DATABASE and NEO4J_PASSWORD.
"""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RELEASE, ENTERPRISE = "rain-v4.0.0", "rain"
URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:17690")
DB = os.getenv("NEO4J_DATABASE", "neo4j")
USER, PASSWORD = "neo4j", os.getenv("NEO4J_PASSWORD", "password")
SCHEMAS_SQL = ROOT / "doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql"

_spec = importlib.util.spec_from_file_location("rain_v3_prd_seed", Path(__file__).with_name("rain_v3_prd_seed.py"))
v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v3)
v3.SCHEMAS_SQL = SCHEMAS_SQL  # the Data Sources workbench catalogs the v0.4 source systems
N, R = v3.N, v3.R

# The persona switcher order (operators, then the patient).
ORDER = ["GregoryHaskins", "NaomiCastellanos", "RajMalhotra", "LaurenPike", "TeresaLopez", "BrandonKee",
         "LindaGarcia"]
# Origin, data scope and build status of every persona.
ROSTER = {
    "GregoryHaskins": ("v0.3", "Network", "MVP"), "NaomiCastellanos": ("v0.3", "Network", "MVP"),
    "RajMalhotra": ("v0.3", "Network, all sources", "MVP"), "LaurenPike": ("v0.3", "State, aggregate", "MVP"),
    "TeresaLopez": ("v0.3", "Assigned patients", "MVP"), "BrandonKee": ("v0.3", "Network schedule", "MVP"),
    "LindaGarcia": ("v0.3", "Self", "MVP"),
}


def build_records():
    nodes, rels = v3.build_records()
    by_key = {n["key"]: n for n in nodes}

    def add(node, *node_rels):
        nodes.append(node)
        by_key[node["key"]] = node
        rels.extend(node_rels)

    # ---- v0.4 framing of the use cases -----------------------------------------------------
    by_key["usecase:A"]["props"].update(
        name="Value-Based Care and Population Health Insights",
        question="Where does cost of care run above the contract benchmark, which members can the "
                 "network still change, which services are low-value, and where does county need "
                 "concentrate?", absorbs="v0.2 UC-02 rural population health insights; v0.3 Use Case A")
    by_key["usecase:B"]["props"].update(
        name="Care Management, Smart Scheduling and Reminders",
        question="Who should the care team call today, which visit does each patient need, and how "
                 "does the team make sure the visit happens?",
        absorbs="v0.2 UC-01 smart scheduling and pattern-based reminders; v0.3 Use Case B")

    # ---- organizations ---------------------------------------------------------------------
    add(N("org:NevadaRHTPProgram", "Organization", name="Nevada RHTP program", kind="state program",
          fictional=False, description="Nevada's Rural Health Transformation Program; the Outcomes "
          "Accelerator is one of its four initiatives (illustrative roles)."),
        R("org:NevadaRHTPOutcomesAccelerator", "PART_OF", "org:NevadaRHTPProgram"))

    # ---- workbenches: what the existing ones also read -----------------------------------------
    extra_reads = {"RHTPReporting": ["RhtpReport", "Grantee"], "DataSources": ["DataSource"],
                   "CountyExplorer": ["SocialVulnerability", "PopulationProfile", "Facility", "ZipCounty"],
                   "Worklist": ["RiskScore"], "Reminders": ["NoShowRate"],
                   "QualityGateAndCampaigns": ["StandingOrder", "QualityBenchmark"],
                   "ModelGovernance": ["RiskScore"], "ValueInsights": ["AdtEvent"]}
    for wb, classes in extra_reads.items():
        rels.extend(R(f"workbench:{wb}", "READS", f"class:{c}") for c in classes)

    # ---- roster properties on every persona (origin, scope, status, switcher order) ----------
    for i, key in enumerate(ORDER, start=1):
        origin, scope, status = ROSTER[key]
        by_key[f"persona:{key}"]["props"].update(order=i, prd_origin=origin, data_scope=scope,
                                                 build_status=status, prd_version="v0.4")
    by_key["persona:RajMalhotra"]["props"]["owns_rule"] = "BR-08 model card and subgroup check"

    # ---- success metrics (PRD v0.4 Section 10) ------------------------------------------------
    metrics = [
        ("M01", "No-show rate for scheduled visits", "B", "Measure at pilot start", "25% relative reduction", ["BrandonKee"]),
        ("M02", "Reminder confirmation rate", "B", "Measure at pilot start", "70% of reminded visits confirmed", ["BrandonKee"]),
        ("M03", "Share of eligible visits done by telehealth", "B", "Measure at pilot start", "+15 percentage points", ["BrandonKee"]),
        ("M04", "Days to third-next-available appointment", "B", "Measure at pilot start", "20% reduction", ["BrandonKee"]),
        ("M05", "High-risk patients with outreach completed in 30 days", "A, B", "0 (no worklist today)", "60%", ["TeresaLopez"]),
        ("M06", "Care-gap closure rate (contract measure set)", "A", "Measure at pilot start", "+10 percentage points", ["NaomiCastellanos"]),
        ("M07", "Avoidable ED visits per 1,000 members", "A", "312 (benchmark 251)", "10% reduction", ["GregoryHaskins"]),
        ("M08", "Out-of-range remote readings acted on within 24 hours", "A", "None today", "90%", []),
        ("M09", "Weekly active staff users over licensed staff users", "Both", "None", "75%", ["RajMalhotra"]),
        ("M10", "Time to onboard a new clinic", "Both", "None", "Under 30 days", ["RajMalhotra"]),
        ("M11", "Cost above expected per member per month", "A", "+6.7% ($412 against $386)", "About 3.5% after coding recapture", ["GregoryHaskins"]),
        ("M12", "Contract quality measures at target", "A", "2 of 5", "3 of 5 by contract year end", ["NaomiCastellanos"]),
        ("M13", "Blood pressure control (CMS165)", "A", "58%", "65%", ["NaomiCastellanos"]),
        ("M14", "Coding recapture for high-need members", "A", "73 open", "All 73 reviewed by December 31", ["NaomiCastellanos"]),
        ("M15", "Cost avoided by top 300 impactable outreach", "A", "$0", "$1.1M over 12 months (estimate)", ["GregoryHaskins"]),
        ("M16", "Frontier-ZIP rank gap in the impactability model", "A", "18% lower; 57 missing from the top 300", "Under the BR-08 threshold", ["RajMalhotra"]),
        ("M17", "Low-value care spend", "A", "$618K a year, 2,140 services", "To set with Dr. Castellanos", ["NaomiCastellanos"]),
    ]
    for mid, name, uc, baseline, target, owners in metrics:
        add(N(f"successmetric:{mid}", "SuccessMetric", name=name, metric_id=mid.replace("M", "M-"),
              use_case=uc, baseline=baseline, target=target),
            R(f"successmetric:{mid}", "ALIGNS_TO", "concept:Metric"),
            *[R(f"persona:{o}", "OWNS_METRIC", f"successmetric:{mid}") for o in owners])

    return nodes, rels


def main():
    # The v0.4 KAG is published by scripts/e2e/kag_v4_refresh.py (release rain-v4.1.0), which imports
    # build_records() from this file; publishing the seed on its own would bring back release rain-v4.0.0.
    if os.getenv("RAIN_KAG_ALLOW_V400") != "1":
        sys.exit("Publish the v0.4 KAG with scripts/e2e/kag_v4_refresh.py (it uses this seed). "
                 "Set RAIN_KAG_ALLOW_V400=1 to publish the seed alone as rain-v4.0.0.")
    from neo4j import GraphDatabase

    from dif.config import settings

    class PinnedDriver:
        def __init__(self, uri, user, password):
            self._d = GraphDatabase.driver(uri, auth=(user, password))

        def session(self, **kw):
            kw.setdefault("database", DB)
            return self._d.session(**kw)

        def close(self):
            self._d.close()

    nodes, rels = build_records()
    print(f"seed records: {len(nodes)} nodes, {len(rels)} relationships")
    settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password = URI, USER, PASSWORD
    pub, val = v3._load_skill("neo4j-publish"), v3._load_skill("neo4j-validate")
    pub._driver_factory = PinnedDriver
    val._driver_factory = PinnedDriver
    out = pub.run({"nodes": nodes, "relationships": rels, "release": RELEASE, "enterprise": ENTERPRISE},
                  {"enterprise": ENTERPRISE})
    print("PUBLISHED into", URI, DB, "->", out["published"], "statements:", out.get("statements"))
    print("by_label:", out["counts"]["by_label"])
    vout = val.run({"release": RELEASE, "enterprise": ENTERPRISE}, {"enterprise": ENTERPRISE})
    print("LIVE VALIDATION passed:", vout["passed"], "mode:", vout["mode"])
    for issue in vout.get("issues", []):
        print(" issue:", issue["severity"], issue["message"])


if __name__ == "__main__":
    main()
