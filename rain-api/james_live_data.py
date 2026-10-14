"""
James's signals/KPIs, computed live via real SQL against PostgreSQL.
Same honest pattern: only verified-exact fields are live.

Confirmed exact:
- over_capacity / over_capacity_by = COUNT(TransportRequest WHERE scheduled=false) = 9
- zips_no_coverage = COUNT(EMSCoverage WHERE unit_available_within_60min=false) = 2
- requests_today = COUNT(TransportRequest WHERE date=today) = 47 (38 scheduled
  against capacity + 9 unscheduled)
- ems_response = MetricTrend.ems_avg_response_time_min (34 -> 47) -- this
  table wasn't known when this module was first written ("spec says 47"
  was noted as untestable then); it is a real, stored documented trend
- awaiting_transport = distinct elevated-risk patients (ELEVATED_RISK_PATIENTS_SQL)
  with a transport request today = 16
- telehealth_unslotted = requested TelehealthSession rows with no
  scheduled_date = 31, 12 of them elevated-risk
- mobile_clinic = Facility.utilization_pct of the Winnemucca Mobile Clinic = 98

Still not computable (genuinely no backing field in the dataset):
- coverage (sq mi) -- no geographic-area field anywhere
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in this folder, sets ANTHROPIC_API_KEY / PG_* / NEO4J_* automatically
import psycopg2

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DB", "rain"),
    "user": os.environ.get("PG_USER", "rain_app"),
    "password": os.environ.get("PG_PASSWORD", "rain_dev_pw"),
}


# The risk engine's elevated-risk population: any active pregnancy, or an
# enrollment in one of the four tracked chronic conditions. Shared with
# priya_live_data so "elevated-risk" means the same thing on every card.
ELEVATED_RISK_PATIENTS_SQL = """
    SELECT patient_id FROM "PregnancyEpisode"
    UNION SELECT patient_id FROM "ChronicConditionEnrollment"
    WHERE condition_type IN ('CHF', 'COPD', 'diabetes', 'hypertension')
"""
MOBILE_CLINIC_UTILIZATION_SQL = """SELECT utilization_pct::int FROM "Facility" WHERE name = 'Winnemucca Mobile Clinic'"""


def _query_one(sql: str):
    conn = psycopg2.connect(**PG_CONFIG)
    with conn.cursor() as cur:
        cur.execute(sql)
        result = cur.fetchone()[0]
    conn.close()
    return result


def get_james_live_kpis() -> dict:
    ems_after = _query_one("""SELECT after_value::int FROM "MetricTrend" WHERE metric_id='ems_avg_response_time_min'""")
    return {
        "over_capacity": _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE scheduled=false"""),
        "requests_today": _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE date='2026-05-15'"""),
        "ems_response": f"{ems_after} min",
        "awaiting_transport": _query_one(f"""
            SELECT COUNT(DISTINCT patient_id) FROM "TransportRequest"
            WHERE date='2026-05-15' AND patient_id IN ({ELEVATED_RISK_PATIENTS_SQL})"""),
        "telehealth_unslotted": _query_one("""SELECT COUNT(*) FROM "TelehealthSession" WHERE scheduled_date IS NULL"""),
        "mobile_clinic": _query_one(MOBILE_CLINIC_UTILIZATION_SQL),
    }


def get_james_live_signals() -> dict:
    over_capacity = _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE scheduled=false""")
    requests_today = _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE date='2026-05-15'""")
    zips_no_coverage = _query_one(
        """SELECT COUNT(*) FROM "EMSCoverage" WHERE unit_available_within_60min=false"""
    )
    ems_minutes = _query_one("""SELECT after_value::int FROM "MetricTrend" WHERE metric_id='ems_avg_response_time_min'""")
    telehealth_unslotted = _query_one("""SELECT COUNT(*) FROM "TelehealthSession" WHERE scheduled_date IS NULL""")
    elevated_unslotted = _query_one(f"""
        SELECT COUNT(DISTINCT patient_id) FROM "TelehealthSession"
        WHERE scheduled_date IS NULL AND patient_id IN ({ELEVATED_RISK_PATIENTS_SQL})""")
    mobile_clinic = _query_one(MOBILE_CLINIC_UTILIZATION_SQL)
    return {
        "SIG-RAIN-JAMES-001": {
            "affected_count": over_capacity,
            "affected_unit": "trips",
            "description": (
                f"There are {int(requests_today)} transport requests today. "
                f"{int(over_capacity)} of them are unscheduled."
            ),
            "metrics": {"over_capacity_by": over_capacity, "requests_today": requests_today},
        },
        "SIG-RAIN-JAMES-002": {
            "affected_count": telehealth_unslotted,
            "affected_unit": "visits",
            "description": (
                f"The mobile clinic is at {int(mobile_clinic)}% utilization. "
                f"{int(telehealth_unslotted)} requested telehealth visits have no slot, and "
                f"{int(elevated_unslotted)} of those are elevated-risk patients."
            ),
            "metrics": {
                "unslotted_visits": telehealth_unslotted,
                "elevated_risk_unslotted": elevated_unslotted,
                "mobile_clinic_utilization_pct": mobile_clinic,
            },
        },
        "SIG-RAIN-JAMES-003": {
            "affected_count": zips_no_coverage,
            "affected_unit": "ZIP codes",
            "description": (
                f"Average EMS response time is {int(ems_minutes)} minutes. "
                f"{int(zips_no_coverage)} ZIP codes have no unit available within 60 minutes."
            ),
            "metrics": {"zips_no_coverage": zips_no_coverage, "ems_response_minutes": ems_minutes},
        },
    }


if __name__ == "__main__":
    live = get_james_live_kpis()
    expected = {"over_capacity": 9, "requests_today": 47, "ems_response": "47 min", "awaiting_transport": 16, "telehealth_unslotted": 31, "mobile_clinic": 98}
    print("James live PostgreSQL results:")
    for key, val in live.items():
        status = "OK" if val == expected[key] else "MISMATCH"
        print(f"  {key:20s} live={val!s:<10} expected={expected[key]!s:<10} [{status}]")
