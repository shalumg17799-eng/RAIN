"""PRD v0.3 knowledge seed for the rain-v3 KAG.

The factory pipeline publishes the DATA ontology (Class/Table/Column/DataAsset/System).
This seed adds everything else the PRD (doc/prd/RAIN_Prototype_Spec_v2.docx) describes --
organizations, counties/sites, the Q3 contract checkpoint with its master metrics, the
quality gate and measures, impactability segments, both use cases, pages and workbenches
(wired to the ontology classes they read), the six Radiant AI capabilities, all seven
personas with their priority signals, and the guided conversation steps -- as
release-scoped Enterprise nodes (release rain-v3.0.0, provenance ["prd_seed"]).

Run AFTER the factory release is published into the rain-v3 database:

    .venv\\Scripts\\python.exe knowledge-gathering/seeds/rain_v3_prd_seed.py

Idempotent: neo4j-publish MERGEs on (key, enterprise_id, release). A clean re-publish of
the whole release still means deleting the release nodes first (MERGE never removes).
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RELEASE, ENTERPRISE, DB = "rain-v3.0.0", "rain", "rain-v3"
URI, USER, PASSWORD = "bolt://127.0.0.1:7687", "neo4j", "password"
PROV = ["prd_seed"]
SCHEMAS_SQL = ROOT / "doc/prd/RAIN_Prototype_Spec_v2_planned_schemas.sql"


def N(key, label, **props):
    return {"key": key, "labels": ["Enterprise", label], "props": {"provenance": PROV, **props}}


def R(frm, typ, to, **props):
    return {"from": frm, "type": typ, "to": to, "props": props}


def build_records():
    nodes, rels = [], []

    def add(node, *node_rels):
        nodes.append(node)
        rels.extend(node_rels)

    # ---- organizations, counties, sites --------------------------------------------------
    add(N("org:SierraBasinCommunityHealth", "Organization",
          name="Sierra Basin Community Health", kind="FQHC network", fictional=True,
          sites_total=7, description="Fictional rural FQHC network with seven sites across "
          "six Nevada counties; signed its first value-based contract in 2026."))
    add(N("org:HighDesertHealthPlan", "Organization",
          name="High Desert Health Plan", kind="Medicaid managed care plan", fictional=True))
    add(N("org:NevadaRHTPOutcomesAccelerator", "Organization",
          name="Rural Health Outcomes Accelerator", kind="state RHTP initiative", fictional=False,
          description="One of four Nevada RHTP initiatives (illustrative role within the "
          "Nevada Health Authority): expands value-based care and chronic disease models "
          "for rural providers."))

    counties = ["Elko", "Humboldt", "Lander", "Pershing", "WhitePine", "Churchill"]
    county_names = {"WhitePine": "White Pine"}
    for c in counties:
        add(N(f"county:{c}", "County", name=county_names.get(c, c), state="NV", rural=True),
            R(f"county:{c}", "ALIGNS_TO", "concept:Location"),
            R("org:SierraBasinCommunityHealth", "SERVES_COUNTY", f"county:{c}"),
            R("org:NevadaRHTPOutcomesAccelerator", "OVERSEES", f"county:{c}"))

    add(N("site:Winnemucca", "Site", name="Winnemucca",
          note="Low-value imaging cluster since the April locum rotation; 71% of the "
          "network's $162K low-value imaging."),
        R("site:Winnemucca", "IN_COUNTY", "county:Humboldt"),
        R("org:SierraBasinCommunityHealth", "OPERATES", "site:Winnemucca"),
        R("site:Winnemucca", "ALIGNS_TO", "concept:Location"))
    add(N("site:BattleMountain", "Site", name="Battle Mountain",
          note="Linda Garcia's town; the v1 prototype's story site."),
        R("site:BattleMountain", "IN_COUNTY", "county:Lander"),
        R("org:SierraBasinCommunityHealth", "OPERATES", "site:BattleMountain"),
        R("site:BattleMountain", "ALIGNS_TO", "concept:Location"))

    # ---- contract, checkpoint, quality gate, metrics, segments ---------------------------
    add(N("contract:SharedSavings2026", "Contract",
          name="2026 shared-savings agreement", members_attributed=9400,
          effective_date="2026-01-01",
          description="Sierra Basin's first value-based contract with High Desert Health "
          "Plan, covering 9,400 attributed Medicaid members after Nevada Medicaid moved "
          "its rural counties into managed care on January 1, 2026."),
        R("contract:SharedSavings2026", "ALIGNS_TO", "concept:Agreement"),
        R("org:SierraBasinCommunityHealth", "PARTY_TO", "contract:SharedSavings2026", role="provider"),
        R("org:HighDesertHealthPlan", "PARTY_TO", "contract:SharedSavings2026", role="payer"))

    add(N("checkpoint:Q3Reconciliation2026", "Checkpoint",
          name="Q3 2026 reconciliation", actual_pmpm=412.0, expected_pmpm=386.0,
          pct_above_expected=6.7, annualized_gap_usd=2900000, days_left=58,
          description="Actual cost $412 PMPM vs expected $386 (+6.7%, ~$2.9M/yr); quality "
          "gate at 2 of 5 with 58 days left. If the gate fails, no shared savings and a "
          "weak 2027 renegotiation position."),
        R("contract:SharedSavings2026", "HAS_CHECKPOINT", "checkpoint:Q3Reconciliation2026"),
        R("checkpoint:Q3Reconciliation2026", "ALIGNS_TO", "concept:Event"))

    add(N("gate:QualityGate2026", "QualityGate",
          name="2026 quality gate", rule="3 of 5 measures at target", met=2, required=3,
          total=5),
        R("contract:SharedSavings2026", "GOVERNED_BY", "gate:QualityGate2026"),
        R("gate:QualityGate2026", "ALIGNS_TO", "concept:Rule"))

    measures = [
        ("CMS2", "Depression screening", "74%", ">=70%", "met", False),
        ("CMS125", "Breast cancer screening", "52%", ">=50%", "met", False),
        ("CMS165", "Controlling high blood pressure", "58%", ">=65%", "not met", False),
        ("CMS122", "HbA1c poor control >9%", "34%", "<=30%", "not met", True),
        ("CMS130", "Colorectal cancer screening", "33%", ">=40%", "not met", False),
    ]
    for mid, name, current, target, status, lower_is_better in measures:
        add(N(f"measure:{mid}", "Measure", name=name, cms_id=mid, current=current,
              target=target, status=status, lower_is_better=lower_is_better),
            R("gate:QualityGate2026", "HAS_MEASURE", f"measure:{mid}"),
            R(f"measure:{mid}", "INSTANCE_OF", "class:QualityMeasure"),
            R(f"measure:{mid}", "ALIGNS_TO", "concept:Metric"))

    metrics = [
        ("AttributedMembers", "Attributed members", dict(value=9400, source="Synthetic MCO eligibility")),
        ("PmpmActualVsExpected", "Actual vs. expected PMPM",
         dict(actual=412.0, expected=386.0, pct_above=6.7, source="Synthetic claims + contract benchmark")),
        ("GapDecomposition", "Gap decomposition (PMPM)",
         dict(coding_gap_pmpm=12.0, avoidable_ed_pmpm=8.0, low_value_pmpm=5.5, other_pmpm=0.5,
              source="RAIN cost model")),
        ("HighNeedHighCostMembers", "High-need, high-cost members",
         dict(value=236, pct_of_members=2.5, pct_of_spend=41, source="Synthetic claims")),
        ("ImpactableCohort", "Impactable rising-risk cohort",
         dict(value=1180, pct_of_members=12.6, top_ranked=300, source="RAIN impactability score")),
        ("CodingRecaptureGap", "Risk-coding recapture gap",
         dict(value=73, pct_of_high_need=31, source="Synthetic EHR + claims")),
        ("LowValueCare", "Low-value care",
         dict(services=2140, annualized_usd=618000, measures=14, source="Low-value care measure library")),
        ("AvoidableEdVisits", "Avoidable ED visits per 1,000",
         dict(value=312, benchmark=251, source="Synthetic claims + CMS Geographic Variation")),
        ("QualityGateStatus", "Quality gate", dict(met=2, required=3, total=5,
                                                   source="eCQM logic on synthetic EHR")),
        ("DaysLeft", "Days left in contract year", dict(value=58, source="Contract calendar")),
    ]
    for key, name, props in metrics:
        add(N(f"metric:{key}", "Metric", name=name, **props),
            R("checkpoint:Q3Reconciliation2026", "REPORTS", f"metric:{key}"),
            R(f"metric:{key}", "ALIGNS_TO", "concept:Metric"))

    segments = [
        ("ImpactableRisingRisk", "Impactable / rising risk", "the high-value target",
         "Not yet high-cost, but trending toward it, with conditions or behaviors that "
         "respond to intervention.", "Ranked outreach, predicted cost avoided, hand-off to Use Case B"),
        ("HighNeedHighCost", "High-need, high-cost", "already expensive",
         "Segmented as ACOs do: multiple chronic conditions, medical plus behavioral "
         "health, frail or disabled (including dual eligibles), transitional care.",
         "Care plan intensity, cost versus expected, risk-coding recapture"),
        ("LowRiskStable", "Low risk, stable", "low intervention value",
         "Cost at or below expected, stable trend, gaps closed.", "Light-touch reminders only"),
    ]
    for key, name, tagline, definition, demo in segments:
        add(N(f"segment:{key}", "Segment", name=name, tagline=tagline, definition=definition,
              demo_shows=demo),
            R(f"segment:{key}", "SEGMENTED_BY", "class:ImpactabilityScore"),
            R(f"segment:{key}", "ALIGNS_TO", "concept:Person"))

    # ---- use cases, pages, workbenches, capabilities --------------------------------------
    add(N("usecase:A", "UseCase", name="Value-Based Care Insights", bucket="Data-Driven Insights",
          lead=True, question="Where is our cost of care above expected, which patients can "
          "we still change, and what care should we stop paying for?"),
        R("usecase:A", "ALIGNS_TO", "concept:Process"))
    add(N("usecase:B", "UseCase", name="Care Management Workflow",
          bucket="Care Management Workflows", lead=False,
          question="Who do I call today, what visit do they need, and how do I make sure "
          "the visit happens?"),
        R("usecase:B", "ALIGNS_TO", "concept:Process"),
        R("usecase:A", "HANDS_OFF_TO", "usecase:B",
          via="Approved ranked outreach worklist ('Assign outreach')"),
        R("usecase:B", "FEEDS_BACK_TO", "usecase:A",
          via="Visit results and home readings close care gaps and update the quality gate"))

    add(N("page:AskCockpitAI", "Page", name="Ask Cockpit.AI",
          description="Single front door for every operator persona. Use Case A personas "
          "get the insight briefing (signals, KPI tiles, guided conversation); Use Case B "
          "personas get a task briefing (today's queue). Workbench mode docks the Cockpit "
          "pane on the right."),
        R("page:AskCockpitAI", "SERVES", "usecase:A"),
        R("page:AskCockpitAI", "SERVES", "usecase:B"))
    add(N("page:PatientView", "Page", name="Patient view", route="/patient", channel="SMS",
          description="Phone-framed SMS thread (390px): reminders, C/R replies, telehealth "
          "link. Spanish by default with an English toggle. The patient does not use Cockpit."),
        R("page:PatientView", "SERVES", "usecase:B"))

    workbenches = [
        ("ValueInsights", "Value Insights", "A", "P1",
         "Cost vs. expected trend and gap waterfall, member segmentation pyramid, site "
         "comparison. Filters: county, site, payer, segment.",
         ["Claim", "ContractBenchmark", "AttributedMember", "ImpactabilityScore", "UtilizationBenchmark"]),
        ("QualityGateAndCampaigns", "Quality Gate and Campaigns", "A", "P1",
         "Five-measure tracker, member lists per gap, campaign builder with visit mode per "
         "member and standing orders.",
         ["QualityMeasure", "QualityMeasureResult", "CareGap", "Campaign", "CampaignMember", "EhrOrder"]),
        ("LowValueCare", "Low-Value Care", "A", "P2",
         "Measure library table, spend by measure, site and ordering provider, trend with annotations.",
         ["LowValueMeasure", "LowValueFinding", "Claim", "Provider", "ClinicSite"]),
        ("ModelGovernance", "Model Governance", "A", "P1",
         "Model card, subgroup check results, feature list, before and after comparison, sign-off.",
         ["ModelCard", "SubgroupCheck", "ImpactabilityScore"]),
        ("DataSources", "Data Sources", "A", "P2",
         "Every source with record count, freshness date, public or synthetic label.", []),
        ("CountyExplorer", "County Explorer", "A", "P1",
         "County map with layer toggles (PLACES, SVI, HPSA, broadband) and side-by-side "
         "county table; small cells suppressed.",
         ["CountyMetric", "ShortageArea", "BroadbandCoverage", "RuralClassification", "TravelTime"]),
        ("RHTPReporting", "RHTP Reporting", "A", "P2",
         "People served, services delivered and outcomes by county; export to PDF and CSV.",
         ["CountyMetric"]),
        ("Worklist", "Worklist", "B", "P1",
         "Ranked outreach list with reasons, patient summary drawer, contact log, campaign progress.",
         ["OutreachTask", "CampaignMember", "Patient", "Handoff"]),
        ("Scheduling", "Scheduling", "B", "P1",
         "Slot search by drive time and visit mode, eligibility check, booking.",
         ["Schedule", "Slot", "Appointment", "EligibilityCheck", "TravelTime", "ContactPreference"]),
        ("Reminders", "Reminders", "B", "P2",
         "Per-patient reminder plan and SMS log; R replies and no-reply tasks.",
         ["ReminderMessage", "ContactPreference", "Appointment"]),
    ]
    for key, name, uc, priority, shows, classes in workbenches:
        add(N(f"workbench:{key}", "Workbench", name=name, priority=priority, shows=shows),
            R(f"workbench:{key}", "SERVES", f"usecase:{uc}"),
            *[R(f"workbench:{key}", "READS", f"class:{c}") for c in classes])
    # Data Sources catalogs every source System the factory discovered (keys parsed from
    # the planned-schemas -- source: comments, which is where the System nodes come from).
    systems = sorted(set(re.findall(r"--\s*source:\s*([a-z0-9_]+)",
                                    SCHEMAS_SQL.read_text(encoding="utf-8"))))
    rels.extend(R("workbench:DataSources", "CATALOGS", f"system:{s}") for s in systems)

    capabilities = [
        ("ProactiveIntelligence", "Proactive Intelligence",
         "Surfaces the contract checkpoint before anyone asks: cost above expected, "
         "quality gate at risk, model blind spots."),
        ("ConvergedConversation", "Converged Conversation",
         "One conversation across claims, EHR, eligibility, social needs, public county "
         "data and the contract benchmark."),
        ("AnomalyDetection", "Anomaly Detection",
         "Finds outliers no single report shows: low-value imaging clustered at one site, "
         "a risk model ranking frontier patients too low."),
        ("PredictiveIntelligence", "Predictive Intelligence",
         "Projects cost avoided, quality gate outcomes and county impact under different "
         "interventions."),
        ("ServiceFrictionObservability", "Service / Friction Observability",
         "Shows where access breaks: drive time, no broadband, missed visits, unanswered "
         "reminders."),
        ("AutomatedAction", "Automated Action",
         "Produces worklists, campaigns, board and state briefs, and governance packets "
         "from the conversation."),
    ]
    for key, name, context in capabilities:
        add(N(f"capability:{key}", "Capability", name=name, context=context),
            R(f"capability:{key}", "SUPPORTS", "usecase:A"))

    # ---- personas --------------------------------------------------------------------------
    personas = [
        ("GregoryHaskins", "Gregory Haskins, MBA", "Chief Executive Officer", "A", 1,
         "org:SierraBasinCommunityHealth", "page:AskCockpitAI",
         "FQHC CEO focused on data-driven operations and sustainability",
         ["MCO contract reports", "claims", "finance", "RAIN cost model"],
         [("ValueInsights", "full"), ("QualityGateAndCampaigns", "view"),
          ("LowValueCare", "full"), ("DataSources", "view")],
         ["Why are we above expected cost?", "Which members drive the most spend?",
          "How close are we to the quality gate?", "Where is the low-value care?",
          "What happens if we do nothing?", "Compare our sites on cost per member",
          "Generate the board brief"],
         "the money"),
        ("NaomiCastellanos", "Dr. Naomi Castellanos",
         "Chief Medical Officer and Value-Based Care Quality Lead", "A", 2,
         "org:SierraBasinCommunityHealth", "page:AskCockpitAI",
         "FQHC CMO accountable for quality measures, provider practice and outcomes",
         ["EHR", "eCQM reports", "UDS reporting", "claims", "RAIN quality engine"],
         [("QualityGateAndCampaigns", "full"), ("LowValueCare", "full"), ("ValueInsights", "full"),
          ("ModelGovernance", "co-sign"), ("Worklist", "view")],
         ["How close are we to each quality target?", "Which patients are closest to BP control?",
          "Show low-value care by site", "Which providers order the most low-value imaging?",
          "Which members need coding recapture?", "Project our measures to December 31",
          "Draft a provider feedback note"],
         "the quality gate and wasted care"),
        ("RajMalhotra", "Raj Malhotra",
         "Chief Information Officer and Data and AI Governance Lead", "A", 4,
         "org:SierraBasinCommunityHealth", "page:AskCockpitAI",
         "FQHC CIO responsible for technology strategy, security, integration and responsible AI",
         ["EHR (FHIR R4)", "MCO claims feed", "HIE ADT feed", "RAIN data pipeline",
          "model card and subgroup check"],
         [("ModelGovernance", "full"), ("DataSources", "full")],
         ["Show the model card", "Did the risk model pass its subgroup check?",
          "How fresh is each data source?", "Which members are missing social needs screening?",
          "What public data feeds the county view?", "Show records that failed patient matching",
          "Generate the governance packet"],
         "the risk model missing the most isolated patients"),
        ("LaurenPike", "Dr. Lauren Pike",
         "Program Lead, Rural Health Outcomes Accelerator (illustrative)", "A", 5,
         "org:NevadaRHTPOutcomesAccelerator", "page:AskCockpitAI",
         "State program manager overseeing RHTP funds across many clinics and counties",
         ["RAIN state view (aggregated, de-identified)", "public county data", "grantee reports"],
         [("CountyExplorer", "full"), ("ValueInsights", "state scope"), ("RHTPReporting", "full")],
         ["Show county need side by side", "Which counties lost primary care visits after January?",
          "Compare participating networks on quality", "Where is low-value care concentrated?",
          "Where does broadband limit telehealth?",
          "Model funding options for the Outcomes Accelerator",
          "Generate the CMS progress summary"],
         "the same pattern across counties"),
        ("TeresaLopez", "Teresa Lopez, CHW", "Community Health Worker and Care Coordinator",
         "B", 3, "org:SierraBasinCommunityHealth", "page:AskCockpitAI",
         "Field-based coordinator following up with hard-to-reach patients",
         ["RAIN worklist", "phone", "EHR summary"],
         [("Worklist", "full"), ("Scheduling", "full")], None, "calls and visits"),
        ("BrandonKee", "Brandon Kee", "Patient Access Coordinator (scheduler)", "B", 3,
         "org:SierraBasinCommunityHealth", "page:AskCockpitAI",
         "Front desk and scheduling staff juggling phone, EHR and paper",
         ["RAIN scheduling", "EHR schedule", "eligibility check", "SMS reminders"],
         [("Scheduling", "full"), ("Reminders", "full")], None, "bookings and reminders"),
    ]
    for (key, name, role, uc, order, org, landing, archetype, systems_used, wbs,
         queries, angle) in personas:
        props = dict(name=name, role=role, archetype=archetype, order=order,
                     primary_systems=systems_used, fictional=True)
        if queries:
            props["suggested_queries"] = queries
        add(N(f"persona:{key}", "Persona", **props),
            R(f"persona:{key}", "ALIGNS_TO", "concept:Person"),
            R(f"persona:{key}", "WORKS_FOR", org),
            R(f"persona:{key}", "PARTICIPATES_IN", f"usecase:{uc}"),
            R(f"persona:{key}", "LANDS_ON", landing),
            R(f"persona:{key}", "VIEWS", "checkpoint:Q3Reconciliation2026", angle=angle),
            *[R(f"persona:{key}", "USES", f"workbench:{w}", access=a) for w, a in wbs])
    rels.append(R("persona:NaomiCastellanos", "REPORTS_TO", "persona:GregoryHaskins"))
    rels.append(R("persona:RajMalhotra", "REPORTS_TO", "persona:GregoryHaskins"))

    add(N("persona:LindaGarcia", "Persona", name="Linda Garcia", role="Patient", order=3,
          archetype="58-year-old Medicaid member in Battle Mountain with hypertension and "
          "type 2 diabetes", fictional=True, channel="SMS first, no app; voice call fallback",
          context="81-minute drive to her clinic, shared family phone, prefers Spanish, "
          "broadband at home; missed her last two visits because of the drive."),
        R("persona:LindaGarcia", "ALIGNS_TO", "concept:Person"),
        R("persona:LindaGarcia", "PARTICIPATES_IN", "usecase:B"),
        R("persona:LindaGarcia", "LANDS_ON", "page:PatientView"),
        R("persona:LindaGarcia", "ATTRIBUTED_TO", "org:SierraBasinCommunityHealth"),
        R("persona:LindaGarcia", "ENROLLED_WITH", "org:HighDesertHealthPlan"),
        R("persona:LindaGarcia", "RESIDES_IN", "site:BattleMountain"))

    # ---- priority signals -------------------------------------------------------------------
    signals = [
        ("GregoryHaskins", "CostAboveExpected", "Cost Running Above Expected", "CRITICAL",
         "Q3 reconciliation shows $412 PMPM against an expected $386 across 9,400 attributed "
         "members, 6.7 percent above expected, about $2.9M annualized. 236 high-need members "
         "(2.5 percent) account for 41 percent of spend.", "metric:PmpmActualVsExpected"),
        ("GregoryHaskins", "QualityGateAtRisk", "Quality Gate at Risk", "CRITICAL",
         "Shared savings require 3 of 5 quality measures at target. The network meets 2. "
         "Blood pressure control (CMS165) is 7 points short with 58 days left.",
         "metric:QualityGateStatus"),
        ("GregoryHaskins", "LowValueCareSpend", "Low-Value Care Spend", "WARNING",
         "2,140 services across 14 low-value care measures, $618K annualized. Imaging for "
         "uncomplicated low back pain is the largest single item.", "metric:LowValueCare"),
        ("NaomiCastellanos", "BpControlShort", "Blood Pressure Control Short of Target",
         "CRITICAL", "CMS165 is at 58 percent against a 65 percent target. About 180 more of "
         "the 2,250 hypertensive members need a controlled reading. 412 of them had a last "
         "reading within 10 points of control.", "measure:CMS165"),
        ("NaomiCastellanos", "LowValueImagingCluster", "Low-Value Imaging Cluster", "WARNING",
         "Imaging for uncomplicated low back pain accounts for $162K a year. 71 percent of "
         "it traces to one site, Winnemucca, since a locum provider rotation began in April.",
         "metric:LowValueCare"),
        ("NaomiCastellanos", "CodingRecaptureGap", "Risk-Coding Recapture Gap", "WARNING",
         "73 high-need members have chronic conditions documented in 2025 that have not "
         "been recaptured in 2026, understating expected cost by about 3.1 percent.",
         "metric:CodingRecaptureGap"),
        ("RajMalhotra", "ModelUnderRanksFrontier", "Risk Model Under-Ranks Frontier Patients",
         "CRITICAL", "The subgroup check shows the impactability score ranks members in "
         "frontier ZIP codes 18 percent lower than clinically similar members in town. 57 "
         "high-need frontier members are missing from the top 300.", "class:SubgroupCheck"),
        ("RajMalhotra", "ClaimsFeedLag", "Claims Feed Lag", "WARNING",
         "MCO claims arrive 45 days after service, so ED and low-value care signals trail "
         "reality by six weeks. The ADT feed is near real time and can fill the gap.",
         "class:Claim"),
        ("RajMalhotra", "SocialNeedsCoverage", "Social Needs Data Coverage", "WARNING",
         "Only 38 percent of members have a social needs screening on file, which limits "
         "transportation and housing signals in the risk model.", "class:SdohScreening"),
        ("LaurenPike", "PrimaryCareVisitsDown",
         "Primary Care Visits Down After Managed Care Transition", "CRITICAL",
         "Among members moved into managed care on January 1, primary care visits fell 14 "
         "percent in Lander and Pershing Counties, while avoidable ED use rose. Both are "
         "primary care shortage areas.", "metric:AvoidableEdVisits"),
        ("LaurenPike", "NetworkLowValueCare", "Low-Value Care Across Participating Networks",
         "WARNING", "Across four participating networks (18 sites), RAIN estimates $2.4M a "
         "year in low-value care, with the same imaging pattern at sites using locum "
         "coverage.", "metric:LowValueCare"),
        ("LaurenPike", "BroadbandLimitsTelehealth", "Telehealth Reach Limited by Broadband",
         "WARNING", "In six frontier ZIP codes, fewer than 40 percent of locations have "
         "broadband adequate for video visits, so telehealth recheck strategies need a "
         "phone or mobile clinic fallback.", "class:BroadbandCoverage"),
    ]
    for persona, key, title, severity, detail, refers_to in signals:
        add(N(f"signal:{persona}.{key}", "Signal", name=title, severity=severity, detail=detail),
            R(f"persona:{persona}", "HAS_SIGNAL", f"signal:{persona}.{key}"),
            R(f"signal:{persona}.{key}", "REFERS_TO", refers_to))

    # ---- guided conversation steps (Use Case A personas) ------------------------------------
    steps = [
        ("GregoryHaskins", 1, "ProactiveIntelligence", "(Initial greeting, no prompt)",
         "Flags the three signals: $412 vs $386 PMPM (+6.7%), quality gate at 2 of the "
         "needed 3 with 58 days left, $618K/yr in low-value care; most of the gap is "
         "explainable and part of it recoverable this year.",
         "Three signal cards. KPI tiles. PMPM actual-vs-expected trend line since January.",
         ["Claims", "MCO Eligibility", "Contract Benchmark", "eCQM Engine", "Low-Value Care Library"],
         None),
        ("GregoryHaskins", 2, "ConvergedConversation", "Break down the gap",
         "The $26 PMPM gap has four parts: $12 coding gap (73 high-need members not "
         "recaptured, expected cost understated ~3.1%), $8 excess avoidable ED (312 vs 251 "
         "per 1,000), $5.50 low-value care, $0.50 noise. Half is a documentation fix; most "
         "of the rest traces to ~1,180 changeable rising-risk members.",
         "Waterfall $386 to $412 with four labeled bars. Segment pyramid: 236 high-need, "
         "1,180 impactable, 7,984 stable, with share of spend.",
         ["Claims", "EHR (FHIR)", "MCO Eligibility", "Contract Benchmark",
          "CMS Medicare Geographic Variation"],
         ("ValueInsights", True)),
        ("GregoryHaskins", 3, "PredictiveIntelligence", "What can we still recover by December 31?",
         "Three moves: recapture coding for the 73 members (corrects benchmark to ~$398), "
         "get ~180 more hypertensive members controlled to pass the gate (home cuff "
         "readings count for CMS165; telehealth recheck for the 268 driving >1 hour), and "
         "start outreach to the top 300 impactable members (~$1.1M avoided over 12 months).",
         "Scenario panel: do nothing vs three moves. Bars for gap, quality gate, 12-month "
         "avoided cost. Timeline to December 31.",
         ["RAIN Cost Model", "eCQM Engine", "Impactability Score", "Travel Time (OpenStreetMap)",
          "Contract Benchmark"],
         None),
        ("GregoryHaskins", 4, "AutomatedAction", "Generate the board brief",
         "One-page board brief: the checkpoint, the four-part gap, the three moves with "
         "owners and dates, the 2027 renegotiation position. Two hand-offs for approval: "
         "top-300 outreach worklist to the care team, 73-member coding recapture list to "
         "Dr. Castellanos.",
         "Brief preview. Two hand-off cards with Approve buttons.",
         ["All Use Case A sources"], None),
        ("NaomiCastellanos", 1, "ProactiveIntelligence", "(Initial greeting, no prompt)",
         "Three quality signals: BP control at 58% needs 65% in 58 days; 412 hypertensive "
         "members within 10 points of control so the target is reachable; a low-value "
         "imaging cluster at Winnemucca; 73 members with coding to recapture.",
         "Quality gate tracker: five measures with current, target and status. Three signal cards.",
         ["EHR (FHIR)", "eCQM Engine", "Claims", "Low-Value Care Library"], None),
        ("NaomiCastellanos", 2, "AnomalyDetection", "What is happening at Winnemucca?",
         "Low back pain imaging averages 9% of eligible visits network-wide but jumped to "
         "27% at Winnemucca from April, matching the locum rotation; 71% of the $162K in "
         "low-value imaging. Three rotating clinicians show the same rate, suggesting a "
         "missing order set or protocol, not an individual outlier.",
         "Site comparison bar chart. Monthly Winnemucca trend with the April rotation "
         "marked. Top-5 low-value measures with dollars.",
         ["Claims", "EHR Orders", "Provider Directory (NPPES)", "Low-Value Care Library"], None),
        ("NaomiCastellanos", 3, "PredictiveIntelligence", "Which gaps can we close in 58 days?",
         "Blood pressure is the one to win: of the 412 near-control members, ~210 projected "
         "to reach control; 180 passes the gate. 268 drive over an hour, so telehealth "
         "recheck with a home cuff (counts for CMS165). Colorectal could gain ~4 points "
         "with mailed FIT kits; HbA1c will not move in 58 days, plan for Q1.",
         "Projection chart per measure. Intervention mix for the 412: in person vs "
         "telehealth with home cuff.",
         ["EHR", "Remote BP Readings", "Travel Time (OpenStreetMap)", "FCC Broadband",
          "eCQM Engine"], None),
        ("NaomiCastellanos", 4, "AutomatedAction", "Launch the BP campaign",
         "The BP campaign: 412 members ranked by likelihood of reaching control, a visit "
         "mode for each (144 in person, 268 telehealth with home cuff, 37 needing a cuff "
         "shipped), standing orders for review, and a Choosing Wisely feedback note for "
         "the Winnemucca clinicians. Approving sends the worklist to the care team.",
         "Campaign preview with counts by mode. Worklist hand-off card. Draft provider note.",
         ["EHR", "Care Plan Templates", "Low-Value Care Library"],
         ("QualityGateAndCampaigns", False)),
        ("RajMalhotra", 1, "ProactiveIntelligence", "(Initial greeting, no prompt)",
         "The impactability model failed its subgroup check: frontier-ZIP members ranked "
         "18% lower than similar members in town, 57 high-need frontier members missing "
         "from the top 300. Plus the 45-day claims lag and low social needs coverage.",
         "Model card summary with subgroup check status (red). Source freshness tiles.",
         ["Model Card", "Claims", "EHR", "HIE ADT", "USDA RUCC", "HRSA FORHP Rural Areas"], None),
        ("RajMalhotra", 2, "AnomalyDetection", "Show me the subgroup result",
         "The model uses past utilization as a main input. Frontier members have 31% fewer "
         "primary care visits because the median drive is 74 minutes and 190 have no "
         "broadband; fewer visits means fewer claims, which reads as lower risk. Same-"
         "condition comparisons rank the frontier group lower in every condition group: "
         "the documented cost-as-a-proxy bias.",
         "Paired bar chart by condition group, frontier vs town. Drive time vs visit count "
         "scatter. Frontier ZIP map (Census ZCTA, RUCC).",
         ["Model Card", "Claims", "EHR", "Travel Time (OpenStreetMap)", "FCC Broadband",
          "Census ZCTA"],
         ("ModelGovernance", False)),
        ("RajMalhotra", 3, "PredictiveIntelligence", "What changes if we fix it?",
         "Adding access-adjusted features (drive time, broadband, missed appointments, "
         "shortage-area status) brings the frontier gap from 18% to 3%, inside the release "
         "threshold. 57 members enter the top 300; 41 of them are in the BP measure "
         "denominator, so the fix also helps the quality gate. Accuracy holds steady.",
         "Before/after subgroup gap. Members entering and leaving the top 300 "
         "(de-identified). Impact on BP campaign count.",
         ["Model Card", "HRSA HPSA", "FCC Broadband", "Travel Time", "eCQM Engine"], None),
        ("RajMalhotra", 4, "AutomatedAction", "Generate the governance packet",
         "The governance packet: updated model card, subgroup results before and after, "
         "feature change log, sign-off page for Raj and Dr. Castellanos. Until signed, the "
         "care team sees the current ranking with a pending-fix banner. Also drafts a "
         "request for ADT-based ED alerts to beat the 45-day claims lag.",
         "Packet preview. Sign-off control. Banner preview as the care team will see it.",
         ["Model Card", "Data Quality Monitor", "HIE ADT"], None),
        ("LaurenPike", 1, "ProactiveIntelligence", "(Initial greeting, no prompt)",
         "Across the four participating networks: primary care visits dropped 14% in Lander "
         "and Pershing while avoidable ED rose; ~$2.4M/yr in low-value care across the "
         "networks; broadband limits telehealth in six frontier ZIP codes.",
         "County choropleth of avoidable ED per 1,000 with HPSA overlay. Three signal cards.",
         ["Aggregated Claims", "CDC PLACES", "HRSA HPSA", "USDA RUCC", "Census Boundaries"], None),
        ("LaurenPike", 2, "ConvergedConversation", "Show me the county view",
         "Each county side by side: PLACES prevalence, SVI vulnerability, HRSA shortage "
         "status, FCC broadband, and RAIN's aggregated cost, ED and quality measures. "
         "Lander and Pershing stand out. Cells under 11 members are suppressed.",
         "County comparison table with color scale. Map with layer toggles (PLACES, SVI, "
         "HPSA, broadband). Suppressed cells as dashes.",
         ["CDC PLACES", "CDC SVI", "HRSA HPSA", "FCC Broadband", "Census ACS",
          "Aggregated Claims"],
         ("CountyExplorer", False)),
        ("LaurenPike", 3, "PredictiveIntelligence",
         "Where should Outcomes Accelerator funds go first?",
         "Three options: A fund care coordinator capacity and telehealth recheck in Lander "
         "and Pershing (~12% avoidable-ED reduction there within a year); B a shared "
         "low-value care feedback program (~a third of the $2.4M); C mobile clinic days "
         "for the six low-broadband ZIPs. Recommend funding A and C together, run B as a "
         "no-cost data service.",
         "Option comparison table: reach, cost, projected outcome, time to impact, RHTP "
         "initiative alignment. Targeting map.",
         ["Aggregated Claims", "PLACES", "HPSA", "FCC Broadband", "RAIN Cost Model"], None),
        ("LaurenPike", 4, "AutomatedAction", "Generate the CMS progress summary",
         "An RHTP progress summary for the Outcomes Accelerator: people served, services "
         "delivered and outcome measures by county, every figure tied to its source, small "
         "cells suppressed, recommended funding options, county chart appendix. Exports to "
         "PDF or CSV.",
         "Summary preview with county appendix. Export buttons (PDF, CSV).",
         ["All aggregated sources"], None),
    ]
    for persona, num, capability, prompt, response, viz, sources, launch in steps:
        key = f"step:{persona}.{num}"
        step_rels = [R(f"persona:{persona}", "HAS_STEP", key, order=num),
                     R(key, "TAGGED_WITH", f"capability:{capability}")]
        if launch:
            wb, optional = launch
            step_rels.append(R(key, "LAUNCHES", f"workbench:{wb}", optional=optional))
        add(N(key, "Step", name=f"{persona} step {num}", step=num, user_prompt=prompt,
              ai_summary=response, visualization=viz, data_sources=sources), *step_rels)

    return nodes, rels


def _load_skill(name):
    p = ROOT / "knowledge-gathering" / "skills" / name / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
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
    pub, val = _load_skill("neo4j-publish"), _load_skill("neo4j-validate")
    pub._driver_factory = PinnedDriver
    val._driver_factory = PinnedDriver

    out = pub.run({"nodes": nodes, "relationships": rels, "release": RELEASE,
                   "enterprise": ENTERPRISE}, {"enterprise": ENTERPRISE})
    print("PUBLISHED into", DB, "->", out["published"], "statements:", out.get("statements"))
    print("by_label:", out["counts"]["by_label"])

    vout = val.run({"release": RELEASE, "enterprise": ENTERPRISE}, {"enterprise": ENTERPRISE})
    print("LIVE VALIDATION passed:", vout["passed"], "mode:", vout["mode"])
    for issue in vout.get("issues", []):
        print(" issue:", issue["severity"], issue["message"])


if __name__ == "__main__":
    main()
