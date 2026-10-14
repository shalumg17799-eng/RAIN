"""
The real Data Sources page content -- all 11 RAIN source systems with
their actual record counts and descriptions, pulled verbatim from
RAIN_Prototype_Spec_v1.docx's own Data Sources table (David Yazzie's
section). Not invented -- these are the spec's own canonical numbers.
"""

DATA_SOURCES_DETAIL = [
    {
        "name": "Clinical EHR (Critical Access Hospitals & RHCs)",
        "records": "2.1M",
        "description": "Encounters, problem lists, vitals, prenatal records, orders, and notes from participating rural critical access hospitals and rural health clinics. Primary source for clinical risk.",
        "status": "connected",
    },
    {
        "name": "Maternal Health Registry",
        "records": "18K",
        "description": "Pregnancy episodes, prenatal visit history, risk diagnoses, delivery outcomes, and obstetric service availability. Supports elevated-risk pregnancy stratification.",
        "status": "connected",
    },
    {
        "name": "RPM Platform (Remote Patient Monitoring)",
        "records": "640K",
        "description": "Home device readings for CHF, COPD, diabetes, and hypertension patients: weight, SpO2, blood glucose, blood pressure. Time-series source for deterioration detection.",
        "status": "connected",
    },
    {
        "name": "Claims & Encounters",
        "records": "8.4M",
        "description": "FFS and managed-care claims, pharmacy fills, and adjudication history. Utilization, medication adherence, and avoidable-ED analysis.",
        "status": "connected",
    },
    {
        "name": "Telehealth (Project ECHO Nevada)",
        "records": "210K",
        "description": "Virtual visit records, telehealth scheduling, provider mentorship sessions, and connectivity-based eligibility. UNR School of Medicine statewide telehealth initiative.",
        "status": "connected",
    },
    {
        "name": "EMS / Transport Dispatch",
        "records": "390K",
        "description": "Emergency medical services calls, response times, unit availability, and inter-facility transports across the frontier service area.",
        "status": "connected",
    },
    {
        "name": "NEMT / Transportation Logs",
        "records": "520K",
        "description": "Non-emergency medical transport trips, scheduling, corridor utilization, and transportation-barrier resolution for rural patients.",
        "status": "connected",
    },
    {
        "name": "SDOH Data",
        "records": "1.3M",
        "description": "Social determinants of health: transportation barriers, housing, food access, and broadband connectivity indicators linked to patients and ZIP codes.",
        "status": "connected",
    },
    {
        "name": "Public Health Registries",
        "records": "2.7M",
        "description": "Disease surveillance, immunization, maternal and child health, and chronic disease registries via DPBH OPHIE for frontier counties.",
        "status": "connected",
    },
    {
        "name": "State HIE",
        "records": "3.6M",
        "description": "Clinical data exchange: ADT notifications, lab results, and care summaries. HL7 FHIR-based interoperability with hospitals, labs, and health systems.",
        "status": "connected",
    },
    {
        "name": "Enterprise Data Warehouse (Medallion Lakehouse)",
        "records": "120M",
        "description": "Governed lakehouse on Google Cloud aggregating all RAIN domains. Bronze through Platinum medallion layers. Decision support, trend analysis, and NVHA reporting.",
        "status": "connected",
    },
]

# System-health strip -- David Yazzie's own KPI set, real numbers from the spec
DATA_SOURCES_HEALTH_KPIS = [
    {"id": "H01", "label": "Connected Data Sources", "value": 11, "unit": "count", "trend": "stable", "severity": "info"},
    {"id": "H02", "label": "Records Ingested (30-day)", "value": "9.2M", "unit": "count", "trend": "stable", "severity": "info"},
    {"id": "H03", "label": "FHIR Conformance Rate", "value": 94, "unit": "percentage", "trend": "stable", "severity": "warning"},
    {"id": "H04", "label": "Unresolved Provider References", "value": 1240, "unit": "count", "trend": "worsening", "severity": "critical"},
    {"id": "H05", "label": "RPM Transmission Completeness", "value": 78, "unit": "percentage", "trend": "declining", "severity": "critical"},
    {"id": "H06", "label": "Pipeline Freshness (Avg. Lag)", "value": "3.2 hrs", "unit": "count", "trend": "stable", "severity": "info"},
    {"id": "H07", "label": "Records in Quarantine (DQ)", "value": "14,800", "unit": "count", "trend": "worsening", "severity": "warning"},
]
