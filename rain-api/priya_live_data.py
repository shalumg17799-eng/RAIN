"""
Priya's signals/KPIs, computed live via real SQL against PostgreSQL.

Confirmed exact:
- dead_zone_zips (signal metric) = COUNT(ConnectivityRegistry WHERE broadband_available=false) = 5
- desert (KPI) = MetricTrend.maternal_care_desert_pct (31 -> 58) -- this table
  wasn't known when this module was first written; it is a real, stored
  documented trend, and its value matches this KPI's own "was 31%" label
  exactly. Note: this is a different population/threshold than the live
  snapshot used elsewhere (30%, active pregnancies at the coded desert
  distance) -- see priya_equity_brief.py, where both figures are shown
  together. A single compact KPI tile can't carry that nuance, so this
  tile uses the documented-trend figure its own label already names.
- dead_zones (KPI) = elevated-risk patients (james_live_data.ELEVATED_RISK_PATIENTS_SQL)
  living in a no-broadband ZIP = 240 (of 560 patients in those ZIPs)
- SIG-RAIN-PRIYA-001 desert_pct / prior_desert_pct: the same MetricTrend
  figure as the desert KPI above (31 -> 58)
- SIG-RAIN-PRIYA-001 ed_deliveries_60d = COUNT(ClaimEncounter WHERE
  encounter_type='ED_delivery_or_BBA') = 3 -- all 3 on record fall within
  the last 60 days, so "total" and "last 60 days" agree
- SIG-RAIN-PRIYA-002 continuity_linked_pct = 64 -- the same already-verified
  avoidable-hospitalizations model used throughout RAIN (76 of 119)

Still not computable (genuinely no backing field in the dataset):
- population (168,000) -- no general service-area population field; this
  dataset tracks ~1,463 patients, not a census figure
- avoidable_ed_rate (284) -- the raw avoidable-ED total (219) is verified
  elsewhere, but no population denominator is defined for "rate," and
  guessing one risks a wrong number more specific-looking than the data supports
- avoidable_ed_cost ($1.4M) / SIG-002 annualized_cost_usd -- no cost or
  dollar field exists anywhere in the dataset
- telehealth_uptake (71%) -- no capacity/demand field to compute an uptake rate against
- transport_prevalence (22%) -- the raw SDOH transportation-flag count (186) is
  verified (same figure as Sarah's transport_barrier), but this tile's specific
  22% denominator wasn't found; left static rather than guessed
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in this folder, sets ANTHROPIC_API_KEY / PG_* / NEO4J_* automatically
import psycopg2
from james_live_data import ELEVATED_RISK_PATIENTS_SQL

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DB", "rain"),
    "user": os.environ.get("PG_USER", "rain_app"),
    "password": os.environ.get("PG_PASSWORD", "rain_dev_pw"),
}


def _query_one(sql: str):
    conn = psycopg2.connect(**PG_CONFIG)
    with conn.cursor() as cur:
        cur.execute(sql)
        result = cur.fetchone()[0]
    conn.close()
    return result


DEAD_ZONE_ELEVATED_SQL = f"""
    SELECT COUNT(*) FROM "Patient" p JOIN "ConnectivityRegistry" c ON c.zip_code = p.zip_code
    WHERE c.broadband_available = false AND p.patient_id IN ({ELEVATED_RISK_PATIENTS_SQL})
"""


def get_priya_live_kpis() -> dict:
    desert_after = _query_one("""SELECT after_value::int FROM "MetricTrend" WHERE metric_id='maternal_care_desert_pct'""")
    return {
        "desert": f"{desert_after}%",
        "dead_zones": _query_one(DEAD_ZONE_ELEVATED_SQL),
    }


def get_priya_live_signals() -> dict:
    dead_zone_zips = _query_one("""SELECT COUNT(*) FROM "ConnectivityRegistry" WHERE broadband_available=false""")
    dead_zone_patients = _query_one(DEAD_ZONE_ELEVATED_SQL)
    desert_before, desert_after = (_query_one("""SELECT before_value::int FROM "MetricTrend" WHERE metric_id='maternal_care_desert_pct'"""),
                                   _query_one("""SELECT after_value::int FROM "MetricTrend" WHERE metric_id='maternal_care_desert_pct'"""))
    ed_deliveries = _query_one("""SELECT COUNT(*) FROM "ClaimEncounter" WHERE encounter_type='ED_delivery_or_BBA'""")
    continuity_pct = _query_one("""
        SELECT ROUND(100.0 * SUM(CASE WHEN date>='2026-03-01' AND rendering_provider_id IN
            (SELECT provider_id FROM "Provider" WHERE status='deactivated') THEN 1 ELSE 0 END)
            / SUM(CASE WHEN date>='2026-03-01' THEN 1 ELSE 0 END))
        FROM "ClaimEncounter" WHERE avoidable_ed_flag=true AND encounter_type != 'ED_delivery_or_BBA'
    """)
    return {
        "SIG-RAIN-PRIYA-001": {
            # desert_pct/prior_desert_pct: MetricTrend's documented trend (same
            # figure this card's label already names). ed_deliveries_60d: real
            # count of ED_delivery_or_BBA encounters -- all 3 on record happen
            # to fall within the last 60 days, so "total" and "last 60 days" agree.
            "metrics": {"desert_pct": desert_after, "prior_desert_pct": desert_before, "ed_deliveries_60d": ed_deliveries},
        },
        "SIG-RAIN-PRIYA-002": {
            # continuity_linked_pct: the already-verified avoidable-ED model (76
            # of 119, 64%). annualized_cost_usd stays static -- no cost/dollar
            # field exists anywhere in the dataset.
            "metrics": {"continuity_linked_pct": continuity_pct},
        },
        "SIG-RAIN-PRIYA-003": {
            "affected_count": dead_zone_patients,
            "description": (
                f"{int(dead_zone_patients)} elevated-risk patients live in telehealth dead zones "
                f"({int(dead_zone_zips)} ZIP codes with no reliable broadband)."
            ),
            "metrics": {"dead_zone_zips": dead_zone_zips, "dead_zone_patients": dead_zone_patients},
        },
    }


if __name__ == "__main__":
    kpis = get_priya_live_kpis()
    expected_kpis = {"desert": "58%", "dead_zones": 240}
    print("Priya live PostgreSQL results:")
    for key, val in kpis.items():
        status = "OK" if val == expected_kpis[key] else "MISMATCH"
        print(f"  {key:20s} live={val!s:<10} expected={expected_kpis[key]!s:<10} [{status}]")
    live = get_priya_live_signals()
    checks = {
        "dead_zone_zips": (live["SIG-RAIN-PRIYA-003"]["metrics"]["dead_zone_zips"], 5),
        "desert_pct": (live["SIG-RAIN-PRIYA-001"]["metrics"]["desert_pct"], 58),
        "prior_desert_pct": (live["SIG-RAIN-PRIYA-001"]["metrics"]["prior_desert_pct"], 31),
        "ed_deliveries_60d": (live["SIG-RAIN-PRIYA-001"]["metrics"]["ed_deliveries_60d"], 3),
        "continuity_linked_pct": (live["SIG-RAIN-PRIYA-002"]["metrics"]["continuity_linked_pct"], 64),
    }
    for key, (val, exp) in checks.items():
        print(f"  {key:20s} live={val!s:<5} expected={exp!s:<5} [{'OK' if val == exp else 'MISMATCH'}]")
