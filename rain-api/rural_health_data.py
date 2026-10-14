"""
The Battle Mountain closure cascade -- Priya Nair's Step 2 "Cascade
diagram" content from the spec, structured as real data instead of just
narrative text. Every number here is the same one already verified
elsewhere in this project (KPI tiles, signal cards, the SQL-backed data).
"""

CASCADE_ROOT = {
    "title": "Battle Mountain closure",
    "date": "2026-03-01",
    "description": "The labor and delivery unit at Battle Mountain Critical Access Hospital suspended obstetric services due to staffing loss. The nearest delivering hospital is now 115 miles away.",
}

CASCADE_BRANCHES = [
    {
        "id": "maternal-access",
        "label": "Maternal access",
        "metric": "58% of women >60 mi from OB",
        "sub": "was 31% · prenatal 84% → 61%",
    },
    {
        "id": "chronic-continuity",
        "label": "Chronic continuity",
        "metric": "64% of avoidable ED from affected panels",
        "sub": "providers reassigned to cover OB gap",
    },
    {
        "id": "ed-utilization",
        "label": "ED utilization",
        "metric": "+19% avoidable ED visits",
        "sub": "$1.4M annualized avoidable cost",
    },
    {
        "id": "transport-strain",
        "label": "Transport strain",
        "metric": "+210% long-distance transport demand",
        "sub": "same corridor as dialysis/oncology",
    },
    {
        "id": "telehealth-equity",
        "label": "Telehealth equity",
        "metric": "240 elevated-risk in dead zones",
        "sub": "no virtual fallback in 5 frontier ZIPs",
    },
]

# Exact content already live in NevadaCountyChoropleth.jsx -- the stylized
# SVG shape/paths stay in the component (decorative geometry, not data);
# only this semantic content moves to the backend.
COUNTY_RISK_SUMMARY = {
    "population_served": "168K",
    "avoidable_ed_rate_per_1000": 284,
    "regions": [
        {"name": "Humboldt", "risk": "critical"},
        {"name": "Pershing", "risk": "high"},
        {"name": "Lander", "risk": "warning"},
    ],
    "legend": [
        {"label": "Critical access risk", "risk": "critical"},
        {"label": "High", "risk": "high"},
        {"label": "Warning", "risk": "warning"},
    ],
}

# Real Nevada county-level aggregates, computed directly from rain.db
# (Patient/PregnancyEpisode/ClaimEncounter/SDOHFlag joined on county).
# FIPS ids are the real, verified US Census codes for these counties --
# used to color the actual county boundaries fetched from
# cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json, not invented shapes.
COUNTY_ACCESS_DATA = [
    {"fips": "32013", "name": "Humboldt", "total_patients": 480, "elevated_risk_pregnancies": 16, "avoidable_ed": 88, "sdoh_transport_flags": 57},
    {"fips": "32015", "name": "Lander", "total_patients": 494, "elevated_risk_pregnancies": 12, "avoidable_ed": 72, "sdoh_transport_flags": 57},
    {"fips": "32027", "name": "Pershing", "total_patients": 489, "elevated_risk_pregnancies": 10, "avoidable_ed": 62, "sdoh_transport_flags": 72},
]
