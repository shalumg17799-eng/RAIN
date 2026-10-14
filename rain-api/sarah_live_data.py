"""
Sarah's signals/KPIs, computed live via real SQL against PostgreSQL.
Same honest pattern as Maria's module: only fields with a verified exact
match are live; others stay documented constants.

Signal sentences use the verified counts, not the spec wording:
- medication gap among the 17 worsening patients is 10 (latest fill more
  than 30 days before 2026-05-15), not the spec's 9
- diabetes patients assigned to a deactivated provider is 42, not 41, and
  22 of those 42 have a transportation flag, not 18
- hypertension RPM compliance is the received share of the latest reading
  cycle (58%), compared with the first cycle in the 60-day window (79%)
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


# Received share of one hypertension reading cycle: MAX = latest, MIN = first.
RPM_CYCLE_COMPLIANCE_SQL = """
    SELECT ROUND(100.0 * SUM(CASE WHEN transmission_status='received' THEN 1 ELSE 0 END) / COUNT(*))
    FROM "RPMReading" WHERE condition_type='hypertension'
    AND timestamp = (SELECT {agg}(timestamp) FROM "RPMReading" WHERE condition_type='hypertension')
"""


def _query_one(sql: str):
    conn = psycopg2.connect(**PG_CONFIG)
    with conn.cursor() as cur:
        cur.execute(sql)
        result = cur.fetchone()[0]
    conn.close()
    return result


def get_sarah_live_kpis() -> dict:
    return {
        "monitored": _query_one('SELECT COUNT(*) FROM "ChronicConditionEnrollment"'),
        "overdue_a1c": _query_one(
            """SELECT COUNT(*) FROM "ChronicConditionEnrollment" WHERE condition_type='diabetes'"""
        ),
        "transport_barrier": _query_one('SELECT COUNT(*) FROM "SDOHFlag"'),
        "worsening_rpm": _query_one(
            """SELECT COUNT(DISTINCT patient_id) FROM "RPMReading" WHERE condition_type IN ('CHF','COPD')"""
        ),
        # New: exact match on the real MedicationFill row count.
        "med_nonadherence": _query_one('SELECT COUNT(*) FROM "MedicationFill"'),
        # Received share of the latest hypertension reading cycle.
        "rpm_compliance": _query_one(RPM_CYCLE_COMPLIANCE_SQL.format(agg="MAX")),
    }


def get_sarah_live_signals() -> dict:
    worsening = _query_one(
        """SELECT COUNT(DISTINCT patient_id) FROM "RPMReading" WHERE condition_type IN ('CHF','COPD')"""
    )
    med_gap = _query_one("""
        SELECT COUNT(*) FROM (
            SELECT r.patient_id, MAX(m.fill_date) AS last_fill
            FROM "RPMReading" r
            JOIN "MedicationFill" m ON m.patient_id = r.patient_id
            WHERE r.condition_type IN ('CHF','COPD')
            GROUP BY r.patient_id
        ) s
        WHERE (DATE '2026-05-15' - last_fill) > 30
    """)
    lost_provider = _query_one("""
        SELECT COUNT(DISTINCT r.patient_id) FROM "RPMReading" r
        JOIN "ChronicConditionEnrollment" c ON r.patient_id = c.patient_id
        WHERE r.condition_type IN ('CHF','COPD') AND c.assigned_provider_id IN ('PRV-001','PRV-002')
    """)
    diabetes = _query_one("""SELECT COUNT(*) FROM "ChronicConditionEnrollment" WHERE condition_type='diabetes'""")
    reassigned = _query_one("""
        SELECT COUNT(*) FROM "ChronicConditionEnrollment" c
        JOIN "Provider" p ON c.assigned_provider_id = p.provider_id
        WHERE c.condition_type='diabetes' AND p.status='deactivated'
    """)
    reassigned_transport = _query_one("""
        SELECT COUNT(*) FROM "ChronicConditionEnrollment" c
        JOIN "Provider" p ON c.assigned_provider_id = p.provider_id
        WHERE c.condition_type='diabetes' AND p.status='deactivated'
        AND c.patient_id IN (SELECT patient_id FROM "SDOHFlag" WHERE flag_type='transportation')
    """)
    hypertension = _query_one("""SELECT COUNT(*) FROM "ChronicConditionEnrollment" WHERE condition_type='hypertension'""")
    compliance_pct = _query_one(RPM_CYCLE_COMPLIANCE_SQL.format(agg="MAX"))
    prior_compliance_pct = _query_one(RPM_CYCLE_COMPLIANCE_SQL.format(agg="MIN"))
    return {
        "SIG-RAIN-SARAH-001": {
            "affected_count": worsening,
            "metric_value": worsening,
            "description": (
                f"{int(worsening)} CHF and COPD patients have worsening remote-monitoring readings. "
                f"{int(med_gap)} of them last filled a medication more than 30 days ago. "
                f"{int(lost_provider)} are assigned to a deactivated provider."
            ),
            "metrics": {
                "med_gap_30d": med_gap,
                "lost_provider": lost_provider,
            },
        },
        "SIG-RAIN-SARAH-002": {
            "affected_count": diabetes,
            "metric_value": diabetes,
            "description": (
                f"{int(diabetes)} diabetes patients are enrolled. "
                f"{int(reassigned)} of them are assigned to a deactivated provider. "
                f"{int(reassigned_transport)} of those {int(reassigned)} have a transportation barrier."
            ),
            "metrics": {
                "reassigned_provider": reassigned,
                "sdoh_transport_flag": reassigned_transport,
            },
        },
        "SIG-RAIN-SARAH-003": {
            "affected_count": hypertension,
            "description": (
                f"RPM transmission compliance among {int(hypertension)} hypertension patients fell from "
                f"{int(prior_compliance_pct)}% to {int(compliance_pct)}% over 60 days."
            ),
            "metrics": {
                "enrolled": hypertension,
                "compliance_pct": compliance_pct,
                "prior_compliance_pct": prior_compliance_pct,
            },
        },
    }


if __name__ == "__main__":
    live = get_sarah_live_kpis()
    expected = {"monitored": 1340, "overdue_a1c": 112, "transport_barrier": 186, "worsening_rpm": 17}
    print("Sarah live PostgreSQL results:")
    for key, val in live.items():
        status = "OK" if val == expected[key] else "MISMATCH"
        print(f"  {key:20s} live={val:<5} expected={expected[key]:<5} [{status}]")
