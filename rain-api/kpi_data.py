"""
KPI tiles per persona, matching Charan's KpiCarousel schema
({id, label, value, unit, trend, severity, linked_query}). Every value is a
real number already computed and verified against the generated RAIN
dataset (see RAIN_Persona_Question_Answers.md).

`linked_query` is the real cached question that explains this specific
number -- same pattern SignalCard already uses with `chip_text`. This used
to live as a hardcoded lookup table inside the frontend JS; moved here so
the API is the single source of truth for what a tile click should ask,
not the client.
"""

RAIN_KPIS = {
    "maria": [
        {"id": "K01", "label": "Active Pregnancies in Service Area", "value": 126, "unit": "count", "trend": "stable", "severity": "info",
         "linked_query": "Generate a maternal access brief for the board"},
        {"id": "K02", "label": "Elevated-Risk Pregnancies", "value": 38, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Show me all elevated-risk pregnancies in the service area"},
        {"id": "K03", "label": "Prenatal Completion Rate", "value": 61, "unit": "percentage", "trend": "declining", "severity": "critical",
         "linked_query": "What is our prenatal completion rate trend"},
        {"id": "K04", "label": "Avg Distance to Delivering Hospital", "value": 115, "unit": "miles", "trend": "stable", "severity": "warning",
         "linked_query": "Show me all elevated-risk pregnancies in the service area"},
        {"id": "K05", "label": "Patients Without Scheduled Transport", "value": 22, "unit": "count", "trend": "worsening", "severity": "warning",
         "linked_query": "Which patients have no transport scheduled"},
    ],
    "sarah": [
        {"id": "K01", "label": "Chronic Disease Patients Monitored", "value": 1340, "unit": "count", "trend": "stable", "severity": "info",
         "linked_query": "Generate a risk-ranked outreach list"},
        {"id": "K02", "label": "Elevated-Risk Cohort (All Conditions)", "value": 208, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Show me chronic disease patients with worsening RPM readings"},
        {"id": "K03", "label": "CHF/COPD Patients With Worsening RPM", "value": 17, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Show me chronic disease patients with worsening RPM readings"},
        {"id": "K04", "label": "Diabetes Patients Without Recent A1c", "value": 112, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Show me diabetes patients overdue for an A1c"},
        {"id": "K05", "label": "Hypertension RPM Compliance", "value": 58, "unit": "percentage", "trend": "declining", "severity": "warning",
         "linked_query": "What is our RPM transmission compliance trend"},
    ],
    "james": [
        {"id": "K01", "label": "Transport Requests Today", "value": 73, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Show me today's transport queue and capacity"},
        {"id": "K02", "label": "Scheduled Against Capacity", "value": 64, "unit": "count", "trend": "stable", "severity": "info",
         "linked_query": "Show me today's transport queue and capacity"},
        {"id": "K03", "label": "Telehealth-Convertible Trips", "value": 13, "unit": "count", "trend": "stable", "severity": "info",
         "linked_query": "Which transports can be converted to telehealth"},
        {"id": "K04", "label": "Unscheduled Transport Requests", "value": 9, "unit": "count", "trend": "worsening", "severity": "warning",
         "linked_query": "Which elevated-risk patients are awaiting transport"},
        {"id": "K05", "label": "EMS Avg Response Time", "value": 47, "unit": "minutes", "trend": "declining", "severity": "warning",
         "linked_query": "Where are the EMS coverage holes right now"},
    ],
    "priya": [
        {"id": "K01", "label": "Maternal Care Desert Rate", "value": 30, "unit": "percentage", "trend": "worsening", "severity": "critical",
         "linked_query": "Map the maternal care desert before and after Battle Mountain"},
        {"id": "K02", "label": "Avoidable ED Events", "value": 219, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Where did avoidable ED utilization concentrate after the closure"},
        {"id": "K03", "label": "Elevated-Risk Patients in Dead Zones", "value": 574, "unit": "count", "trend": "stable", "severity": "warning",
         "linked_query": "Which elevated-risk patients are in telehealth dead zones"},
        {"id": "K04", "label": "Frontier ZIP Patient Population", "value": 576, "unit": "count", "trend": "stable", "severity": "info",
         "linked_query": "Compare outcomes in affected vs unaffected ZIP codes"},
    ],
    "david": [
        {"id": "K01", "label": "Unresolved Provider References", "value": 1240, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Which records have unresolved provider references"},
        {"id": "K02", "label": "Panel Crosswalk Mismatches", "value": 180, "unit": "count", "trend": "worsening", "severity": "critical",
         "linked_query": "Show me data quality across all connected sources"},
        {"id": "K03", "label": "Open Data Quality Events", "value": 4, "unit": "count", "trend": "stable", "severity": "warning",
         "linked_query": "Show me data quality across all connected sources"},
        {"id": "K04", "label": "Feeds Currently Delayed", "value": 2, "unit": "count", "trend": "stable", "severity": "warning",
         "linked_query": "Show me pipeline freshness and ingestion lag"},
    ],
}
