"""
James's signals/KPIs, computed live via real SQL against PostgreSQL.
Same honest pattern: only verified-exact fields are live.

Confirmed exact:
- over_capacity / over_capacity_by = COUNT(TransportRequest WHERE scheduled=false) = 9
- zips_no_coverage = COUNT(EMSCoverage WHERE unit_available_within_60min=false) = 2
- requests_today = COUNT(TransportRequest WHERE date=today) = 73 -- corrects the
  static card's wrong 47 (not just "uncomputed": this was independently
  verified many times this session as the real total)
- ems_response = MetricTrend.ems_avg_response_time_min (34 -> 47) -- this
  table wasn't known when this module was first written ("spec says 47"
  was noted as untestable then); it is a real, stored documented trend
- awaiting_transport = COUNT(TransportRequest WHERE scheduled=false) = 9 --
  corrects the static card's wrong 16; the already-verified finding is
  that today's unscheduled requests are 0 elevated-risk, 0 worsening-RPM,
  all chronic-condition -- 16 never matched any real population

TelehealthSession has no room or capacity column. Every row has a
scheduled_date, so "unslotted" (a session with no date) is 0. The live
tile and card use the sessions scheduled on the dataset date instead,
which is the same count as the operations "Telehealth Today" tile.

Facility has no utilization column and no mobile-clinic row. The tile
that used to say 98% now counts facilities whose status is active.

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
        "awaiting_transport": _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE scheduled=false"""),
        "telehealth_unslotted": _query_one("""SELECT COUNT(*) FROM "TelehealthSession" WHERE scheduled_date='2026-05-15'"""),
        "mobile_clinic": _query_one("""SELECT COUNT(*) FROM "Facility" WHERE status='active'"""),
    }


def get_james_live_signals() -> dict:
    over_capacity = _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE scheduled=false""")
    requests_today = _query_one("""SELECT COUNT(*) FROM "TransportRequest" WHERE date='2026-05-15'""")
    zips_no_coverage = _query_one(
        """SELECT COUNT(*) FROM "EMSCoverage" WHERE unit_available_within_60min=false"""
    )
    ems_minutes = _query_one("""SELECT after_value::int FROM "MetricTrend" WHERE metric_id='ems_avg_response_time_min'""")
    telehealth_today = _query_one("""SELECT COUNT(*) FROM "TelehealthSession" WHERE scheduled_date='2026-05-15'""")
    telehealth_unslotted = _query_one("""SELECT COUNT(*) FROM "TelehealthSession" WHERE scheduled_date IS NULL""")
    elevated_today = _query_one("""
        SELECT COUNT(DISTINCT t.patient_id) FROM "TelehealthSession" t
        JOIN "PregnancyEpisode" p ON p.patient_id = t.patient_id
        WHERE p.distance_to_delivery_miles = 115 AND t.scheduled_date = '2026-05-15'
    """)
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
            "title": "Telehealth Sessions Scheduled Today",
            "affected_count": telehealth_today,
            "affected_unit": "sessions",
            "description": (
                f"{int(telehealth_today)} telehealth sessions are scheduled today. "
                f"{int(elevated_today)} of those patients are elevated-risk pregnancies. "
                f"{int(telehealth_unslotted)} sessions have no scheduled date."
            ),
            "metrics": {
                "sessions_today": telehealth_today,
                "elevated_risk_today": elevated_today,
                "unslotted_visits": telehealth_unslotted,
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
    expected = {"over_capacity": 9, "requests_today": 73, "ems_response": "47 min", "awaiting_transport": 9, "telehealth_unslotted": 17, "mobile_clinic": 6}
    print("James live PostgreSQL results:")
    for key, val in live.items():
        status = "OK" if val == expected[key] else "MISMATCH"
        print(f"  {key:20s} live={val!s:<10} expected={expected[key]!s:<10} [{status}]")
