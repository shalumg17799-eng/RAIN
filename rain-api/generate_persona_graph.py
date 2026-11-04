"""
Generates Cypher that loads the actual application-layer content (persona
signals, KPIs, the cascade diagram, the county risk map) into Neo4j,
linked to the ontology graph that already exists there.

Pulls every value directly from the real, already-built Python modules
(signal_data.py, ultra_adapter.py, rural_health_data.py) -- nothing here
is retyped by hand, so this can't drift from what the API actually serves.

New graph model, layered on top of the existing Concept/SourceField/
SourceSystem/MAPS_TO/BELONGS_TO structure:

  (:Persona {id, name, role})
  (:Signal {id, title, severity, affected_count})
  (:KPI {id, label, value})
  (:Persona)-[:HAS_SIGNAL]->(:Signal)
  (:Persona)-[:HAS_KPI]->(:KPI)
  (:Signal)-[:REPRESENTS]->(:Concept)
  (:KPI)-[:REPRESENTS]->(:Concept)
  (:Signal)-[:COMPUTED_FROM]->(:SourceSystem)   -- ONLY for the fields
  (:KPI)-[:COMPUTED_FROM]->(:SourceSystem)         proven live via real
                                                     SQL today; everything
                                                     else has no such edge,
                                                     honestly reflecting
                                                     that it's still a
                                                     static value.
  (:CascadeBranch {id, label, metric})
  (:CountyRegion {name, risk})

This is what actually closes RK's feedback: the graph now knows not just
"what fields back Risk Signal in general" but "which specific persona's
specific signal card is backed by which real table, right now."
"""

from signal_data import RAIN_SIGNALS
from ultra_adapter import ULTRA_KPI_DATA
from rural_health_data import CASCADE_ROOT, CASCADE_BRANCHES, COUNTY_RISK_SUMMARY
from prdv2_personas import PRDV2_SIGNALS, PRDV2_ULTRA_KPIS

PERSONA_INFO = {
    "maria": {"name": "Dr. Maria Delgado-Reyes", "role": "Rural Health Medical Director"},
    "sarah": {"name": "Sarah Whitehorse, RN", "role": "Chronic Disease Care Coordinator"},
    "james": {"name": "James Tomley", "role": "Operations Lead"},
    "priya": {"name": "Dr. Priya Nair", "role": "Population Health Analyst"},
    "david": {"name": "David Yazzie", "role": "Data & Interoperability Lead"},
    # PRD v0.2 wave (doc/prd/RAIN_Platform_PRD_v0.2.docx section 2)
    "kayla": {"name": "Kayla Brooks", "role": "Clinic Scheduler / Front Desk"},
    "denise": {"name": "Denise Holloway", "role": "Community Health Worker / Care Coordinator"},
    "samuel": {"name": "Dr. Samuel Okafor", "role": "Rural Primary Care Provider"},
    "linda": {"name": "Dr. Linda Hargrove", "role": "Quality / Population Health Director"},
    "marcus": {"name": "Marcus Bell", "role": "State RHTP Program Manager"},
    "rosa": {"name": "Rosa Martínez", "role": "Rural Patient"},
}

ALL_SIGNALS = {**RAIN_SIGNALS, **PRDV2_SIGNALS}
ALL_KPIS = {**ULTRA_KPI_DATA, **PRDV2_ULTRA_KPIS}

# Which upper-ontology concept each signal/KPI represents. Judgment calls,
# made explicit here rather than left implicit -- reasonable first pass,
# not claimed to be the only valid mapping.
CONCEPT_MAP = {
    # Maria
    "active_pregnancies": "C-CONSTITUENT", "elevated_risk": "C-EPISODE",
    "no_transport": "C-ACCESS-BARRIER", "ed_deliveries": "C-RISK-SIGNAL",
    "SIG-RAIN-MARIA-001": "C-EPISODE", "SIG-RAIN-MARIA-002": "C-ACCESS-BARRIER",
    "SIG-RAIN-MARIA-003": "C-RISK-SIGNAL",
    # Sarah
    "monitored": "C-EPISODE", "overdue_a1c": "C-RISK-SIGNAL",
    "transport_barrier": "C-ACCESS-BARRIER", "worsening_rpm": "C-RISK-SIGNAL",
    "SIG-RAIN-SARAH-001": "C-RISK-SIGNAL", "SIG-RAIN-SARAH-002": "C-EPISODE",
    "SIG-RAIN-SARAH-003": "C-RISK-SIGNAL",
    # James
    "over_capacity": "C-ACCESS-BARRIER",
    "SIG-RAIN-JAMES-001": "C-ACCESS-BARRIER", "SIG-RAIN-JAMES-002": "C-ACCESS-BARRIER",
    "SIG-RAIN-JAMES-003": "C-ACCESS-BARRIER",
    # Priya
    "SIG-RAIN-PRIYA-001": "C-ACCESS-BARRIER", "SIG-RAIN-PRIYA-002": "C-RISK-SIGNAL",
    "SIG-RAIN-PRIYA-003": "C-ACCESS-BARRIER",
    # David
    "unresolved_refs": "C-PROVIDER",
    "SIG-RAIN-DAVID-001": "C-PROVIDER", "SIG-RAIN-DAVID-002": "C-RISK-SIGNAL",
    "SIG-RAIN-DAVID-003": "C-PROVIDER",
    # --- PRD v0.2 wave. Same kind of judgment calls as above; 'Metric' and
    # 'Location' are upper-ontology concepts whose concept_id equals the name.
    # Kayla (UC-01 smart scheduling)
    "SIG-RAIN-KAYLA-001": "C-RISK-SIGNAL", "SIG-RAIN-KAYLA-002": "C-ACCESS-BARRIER",
    "SIG-RAIN-KAYLA-003": "C-ACCESS-BARRIER",
    "booked_visits": "C-EPISODE", "high_no_show": "C-RISK-SIGNAL",
    "open_telehealth_slots": "C-ACCESS-BARRIER", "eligibility_active": "C-CONSTITUENT",
    "reminders_sent": "C-CONSTITUENT", "sms_consent": "C-REGULATORY-TEST",
    # Denise (CHW outreach / escalation)
    "SIG-RAIN-DENISE-001": "C-ACCESS-BARRIER", "SIG-RAIN-DENISE-002": "C-RISK-SIGNAL",
    "SIG-RAIN-DENISE-003": "C-ACCESS-BARRIER",
    "open_tasks": "C-ACCESS-BARRIER", "high_risk": "C-RISK-SIGNAL",
    "pending_replies": "C-RISK-SIGNAL", "sdoh_screened": "C-CONSTITUENT",
    "tasks_closed": "C-EPISODE", "no_sms": "C-ACCESS-BARRIER",
    # Samuel (provider panel)
    "SIG-RAIN-SAMUEL-001": "C-EPISODE", "SIG-RAIN-SAMUEL-002": "C-RISK-SIGNAL",
    "SIG-RAIN-SAMUEL-003": "C-RISK-SIGNAL",
    "panel_size": "C-CONSTITUENT", "visits_week": "C-EPISODE",
    "telehealth_share": "C-ACCESS-BARRIER", "high_risk_panel": "C-RISK-SIGNAL",
    "low_adherence": "C-RISK-SIGNAL", "rpm_readings": "C-EPISODE",
    # Linda (UC-02 quality / population health)
    "SIG-RAIN-LINDA-001": "C-RISK-SIGNAL", "SIG-RAIN-LINDA-002": "C-EPISODE",
    "SIG-RAIN-LINDA-003": "C-RISK-SIGNAL",
    "open_gaps": "C-EPISODE", "gaps_closed": "C-EPISODE",
    "ed_claims": "C-RISK-SIGNAL", "sdoh_coverage": "C-CONSTITUENT",
    # Marcus (state RHTP benchmarks)
    "SIG-RAIN-MARCUS-001": "Metric", "SIG-RAIN-MARCUS-002": "C-ACCESS-BARRIER",
    "SIG-RAIN-MARCUS-003": "C-RISK-SIGNAL",
    "counties": "Location", "metric_records": "Metric",
    "unserved_broadband": "C-ACCESS-BARRIER", "clinic_sites": "Location",
    "telehealth_sites": "C-ACCESS-BARRIER",
    # Rosa (rural patient, first-person UC-01)
    "SIG-RAIN-ROSA-001": "C-CONSTITUENT", "SIG-RAIN-ROSA-002": "C-ACCESS-BARRIER",
    "SIG-RAIN-ROSA-003": "C-RISK-SIGNAL",
    "upcoming_visits": "C-EPISODE", "pending_confirm": "C-RISK-SIGNAL",
    "reminders_received": "C-CONSTITUENT", "sms_consent_status": "C-REGULATORY-TEST",
    "coverage_status": "C-CONSTITUENT", "telehealth_slots": "C-ACCESS-BARRIER",
}

# Only the fields VERIFIED live via real SQL today (see maria/sarah/james/
# priya/david_live_data.py) get a COMPUTED_FROM edge. Everything else
# genuinely doesn't have one -- that's the honest point of this edge.
COMPUTED_FROM_MAP = {
    "active_pregnancies": "PregnancyEpisode", "elevated_risk": "PregnancyEpisode",
    "no_transport": "TransportRequest", "ed_deliveries": "ClaimEncounter",
    "prenatal_completion": "PregnancyEpisode", "distance_delivery": "PregnancyEpisode",
    "telehealth_booked": "TelehealthSession",
    "SIG-RAIN-MARIA-001": "PregnancyEpisode", "SIG-RAIN-MARIA-002": "TransportRequest",
    "SIG-RAIN-MARIA-003": "ClaimEncounter",
    "monitored": "ChronicConditionEnrollment", "overdue_a1c": "ChronicConditionEnrollment",
    "transport_barrier": "SDOHFlag", "worsening_rpm": "RPMReading",
    "med_nonadherence": "MedicationFill", "rpm_compliance": "RPMReading",
    "SIG-RAIN-SARAH-001": "RPMReading", "SIG-RAIN-SARAH-002": "ChronicConditionEnrollment",
    "SIG-RAIN-SARAH-003": "RPMReading",
    "over_capacity": "TransportRequest",
    "SIG-RAIN-JAMES-001": "TransportRequest", "SIG-RAIN-JAMES-003": "EMSCoverage",
    "SIG-RAIN-PRIYA-003": "ConnectivityRegistry",
    "unresolved_refs": "ProviderReferenceIssue", "SIG-RAIN-DAVID-001": "ProviderReferenceIssue",
    # --- PRD v0.2 wave: every id below is live-SQL backed by prdv2_live_data.py
    # against the synthetic schema, so every one gets a COMPUTED_FROM edge to
    # the primary table its query reads ('synthetic.<table>' names them apart
    # from the public-schema systems above).
    "SIG-RAIN-KAYLA-001": "synthetic.appointment", "SIG-RAIN-KAYLA-002": "synthetic.slot",
    "SIG-RAIN-KAYLA-003": "synthetic.eligibility_check",
    "booked_visits": "synthetic.appointment", "high_no_show": "synthetic.appointment",
    "open_telehealth_slots": "synthetic.slot", "eligibility_active": "synthetic.eligibility_check",
    "reminders_sent": "synthetic.reminder_message", "sms_consent": "synthetic.contact_preference",
    "SIG-RAIN-DENISE-001": "synthetic.outreach_task", "SIG-RAIN-DENISE-002": "synthetic.reminder_message",
    "SIG-RAIN-DENISE-003": "synthetic.contact_preference",
    "open_tasks": "synthetic.outreach_task", "high_risk": "synthetic.risk_score",
    "pending_replies": "synthetic.reminder_message", "sdoh_screened": "synthetic.sdoh_screening",
    "tasks_closed": "synthetic.outreach_task", "no_sms": "synthetic.contact_preference",
    "SIG-RAIN-SAMUEL-001": "synthetic.encounter", "SIG-RAIN-SAMUEL-002": "synthetic.risk_score",
    "SIG-RAIN-SAMUEL-003": "synthetic.medication",
    "panel_size": "synthetic.patient", "visits_week": "synthetic.encounter",
    "telehealth_share": "synthetic.encounter", "high_risk_panel": "synthetic.risk_score",
    "low_adherence": "synthetic.medication", "rpm_readings": "synthetic.rpm_reading",
    "SIG-RAIN-LINDA-001": "synthetic.risk_score", "SIG-RAIN-LINDA-002": "synthetic.outreach_task",
    "SIG-RAIN-LINDA-003": "synthetic.claim",
    "open_gaps": "synthetic.outreach_task", "gaps_closed": "synthetic.outreach_task",
    "ed_claims": "synthetic.claim", "sdoh_coverage": "synthetic.sdoh_screening",
    "SIG-RAIN-MARCUS-001": "synthetic.county_metric", "SIG-RAIN-MARCUS-002": "synthetic.broadband_coverage",
    "SIG-RAIN-MARCUS-003": "synthetic.claim",
    "counties": "synthetic.county_metric", "metric_records": "synthetic.county_metric",
    "unserved_broadband": "synthetic.broadband_coverage", "clinic_sites": "synthetic.clinic_site",
    "telehealth_sites": "synthetic.clinic_site",
    "SIG-RAIN-ROSA-001": "synthetic.appointment", "SIG-RAIN-ROSA-002": "synthetic.slot",
    "SIG-RAIN-ROSA-003": "synthetic.reminder_message",
    "upcoming_visits": "synthetic.appointment", "pending_confirm": "synthetic.appointment",
    "reminders_received": "synthetic.reminder_message", "sms_consent_status": "synthetic.contact_preference",
    "coverage_status": "synthetic.eligibility_check", "telehealth_slots": "synthetic.slot",
}

# Everything else, across all 5 personas, is genuinely not row-computable --
# geographic facts (service area sq mi, population served), narrative
# percentages, or figures no tested SQL formula reproduces. Rather than
# leave these with NO graph relationship (ambiguous -- looks like an
# oversight, not a decision), every one gets an explicit DOCUMENTED_AS
# edge to a single shared Constant node. This is what makes the graph's
# coverage genuinely complete: every signal and KPI has SOME real
# relationship, honestly stating whether it's live or a fixed value.
CONSTANT_REASON = "No live SQL query reproduces this value; documented as a fixed reference value, not computed."

# Systems used above that aren't in the graph yet from the original
# ontology-mapping skill run -- legitimate new coverage, not invented.
# The synthetic.* entries are the v0.2 planned-schema tables the PRD
# publish already registered as Table nodes; here they also become
# SourceSystem nodes so COMPUTED_FROM provenance can point at them.
NEW_SYSTEMS = {"TransportRequest", "EMSCoverage", "ProviderReferenceIssue"} | {
    s for s in COMPUTED_FROM_MAP.values() if s.startswith("synthetic.")
}


def esc(s):
    if s is None:
        return ""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def build():
    out = []

    out.append("// --- New SourceSystem coverage (tables used by today's live-SQL work, not in the original ontology test) ---")
    for sys_name in sorted(NEW_SYSTEMS):
        out.append(f"MERGE (:SourceSystem {{name: '{esc(sys_name)}'}});")

    out.append("\n// --- Shared Constant node for genuinely non-computable fields ---")
    out.append(f"MERGE (:Constant {{reason: '{esc(CONSTANT_REASON)}'}});")

    out.append("\n// --- Persona nodes ---")
    # MERGE on id only: the graph's existing persona nodes carry richer
    # role strings (and HAS_CACHED_QUESTION / SERVES edges) from earlier
    # loads -- matching on all properties would fork a duplicate node.
    for pid, info in PERSONA_INFO.items():
        out.append(
            f"MERGE (p:Persona {{id: '{pid}'}}) "
            f"ON CREATE SET p.name = '{esc(info['name'])}', p.role = '{esc(info['role'])}';"
        )

    out.append("\n// --- Signal nodes + HAS_SIGNAL + REPRESENTS + (COMPUTED_FROM or, honestly, DOCUMENTED_AS) ---")
    for pid, signals in ALL_SIGNALS.items():
        for sig in signals:
            sid, title, sev, count = sig["id"], esc(sig["title"]), sig["severity"], sig.get("affected_count")
            # MERGE can't match on a null property value -- create the
            # node on its unique id only, then SET the rest. When count
            # is None, affected_count is simply left off the node instead
            # of being set to a literal null.
            out.append(f"MERGE (s:Signal {{id: '{sid}'}}) SET s.title = '{title}', s.severity = '{sev}'{f', s.affected_count = {count}' if count is not None else ''};")
            out.append(f"MATCH (p:Persona {{id: '{pid}'}}), (s:Signal {{id: '{sid}'}}) MERGE (p)-[:HAS_SIGNAL]->(s);")
            concept = CONCEPT_MAP.get(sid)
            if concept:
                out.append(f"MATCH (s:Signal {{id: '{sid}'}}), (c:Concept {{concept_id: '{concept}'}}) MERGE (s)-[:REPRESENTS]->(c);")
            system = COMPUTED_FROM_MAP.get(sid)
            if system:
                out.append(f"MATCH (s:Signal {{id: '{sid}'}}), (sys:SourceSystem {{name: '{esc(system)}'}}) MERGE (s)-[:COMPUTED_FROM]->(sys);")
            else:
                out.append(f"MATCH (s:Signal {{id: '{sid}'}}), (k:Constant) MERGE (s)-[:DOCUMENTED_AS]->(k);")

    out.append("\n// --- KPI nodes + HAS_KPI + REPRESENTS + (COMPUTED_FROM or, honestly, DOCUMENTED_AS) ---")
    for pid, kpis in ALL_KPIS.items():
        for kpi in kpis:
            kid, label, value = kpi["id"], esc(kpi["label"]), esc(kpi["value"])
            out.append(f"MERGE (:KPI {{id: '{pid}_{kid}', label: '{label}', value: '{value}'}});")
            out.append(f"MATCH (p:Persona {{id: '{pid}'}}), (k:KPI {{id: '{pid}_{kid}'}}) MERGE (p)-[:HAS_KPI]->(k);")
            concept = CONCEPT_MAP.get(kid)
            if concept:
                out.append(f"MATCH (k:KPI {{id: '{pid}_{kid}'}}), (c:Concept {{concept_id: '{concept}'}}) MERGE (k)-[:REPRESENTS]->(c);")
            system = COMPUTED_FROM_MAP.get(kid)
            if system:
                out.append(f"MATCH (k:KPI {{id: '{pid}_{kid}'}}), (sys:SourceSystem {{name: '{esc(system)}'}}) MERGE (k)-[:COMPUTED_FROM]->(sys);")
            else:
                out.append(f"MATCH (k:KPI {{id: '{pid}_{kid}'}}), (const:Constant) MERGE (k)-[:DOCUMENTED_AS]->(const);")

    out.append("\n// --- Cascade root event + branches (one closure -> five branches, a real tree) ---")
    out.append(
        f"MERGE (r:ClosureEvent {{title: '{esc(CASCADE_ROOT['title'])}', date: '{CASCADE_ROOT['date']}'}}) "
        f"SET r.description = '{esc(CASCADE_ROOT['description'])}';"
    )
    # Content-based judgment calls, same as CONCEPT_MAP -- explicit here,
    # not claimed to be the only valid mapping.
    BRANCH_CONCEPT = {
        "maternal-access": "C-ACCESS-BARRIER", "chronic-continuity": "C-EPISODE",
        "ed-utilization": "C-RISK-SIGNAL", "transport-strain": "C-ACCESS-BARRIER",
        "telehealth-equity": "C-ACCESS-BARRIER",
    }
    BRANCH_PERSONA = {
        "maternal-access": "maria", "chronic-continuity": "sarah",
        "ed-utilization": "priya", "transport-strain": "james",
        "telehealth-equity": "priya",
    }
    for b in CASCADE_BRANCHES:
        bid = b["id"]
        out.append(
            f"MERGE (b:CascadeBranch {{id: '{bid}'}}) SET b.label = '{esc(b['label'])}', b.metric = '{esc(b['metric'])}';"
        )
        out.append(
            f"MATCH (b:CascadeBranch {{id: '{bid}'}}), (r:ClosureEvent {{title: '{esc(CASCADE_ROOT['title'])}'}}) "
            f"MERGE (b)-[:CAUSED_BY]->(r);"
        )
        concept = BRANCH_CONCEPT.get(bid)
        if concept:
            out.append(f"MATCH (b:CascadeBranch {{id: '{bid}'}}), (c:Concept {{concept_id: '{concept}'}}) MERGE (b)-[:REPRESENTS]->(c);")
        persona = BRANCH_PERSONA.get(bid)
        if persona:
            out.append(f"MATCH (b:CascadeBranch {{id: '{bid}'}}), (p:Persona {{id: '{persona}'}}) MERGE (b)-[:AFFECTS]->(p);")

    out.append("\n// --- County risk regions, linked to the real Patient table (Patient.county genuinely matches these names) ---")
    for r in COUNTY_RISK_SUMMARY["regions"]:
        name = esc(r["name"])
        out.append(f"MERGE (cr:CountyRegion {{name: '{name}'}}) SET cr.risk = '{esc(r['risk'])}';")
        out.append(f"MATCH (cr:CountyRegion {{name: '{name}'}}), (c:Concept {{concept_id: 'C-ACCESS-BARRIER'}}) MERGE (cr)-[:REPRESENTS]->(c);")
        out.append(f"MATCH (cr:CountyRegion {{name: '{name}'}}), (sys:SourceSystem {{name: 'Patient'}}) MERGE (cr)-[:AFFECTS]->(sys);")

    return "\n".join(out)


if __name__ == "__main__":
    cypher = build()
    # utf-8 explicitly: persona names carry accents (Martínez), and the
    # docker seeder (deploy/scripts/seed_neo4j.py) reads this file as utf-8
    with open("build_persona_graph.cypher", "w", encoding="utf-8") as f:
        f.write(cypher)
    n_statements = cypher.count(";")
    print(f"Wrote build_persona_graph.cypher: {n_statements} statements")
