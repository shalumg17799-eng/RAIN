"""
Maria's signals/KPIs, computed live via real SQL against PostgreSQL
(migrated from the earlier SQLite prototype -- see migrate_to_postgres.py).
Queries are now clean typed comparisons (real INTEGER/BOOLEAN columns),
no more CAST(...AS INT) or ='True' string-matching workarounds that
SQLite's all-TEXT schema needed.

One field (telehealth_booked) stays a documented constant: no query
against the dataset reproduces the spec's 47 exactly (closest real
candidates return 46/49/52 depending on filter) -- likely a narrative
constant set above the row-level data. Same for prenatal_completion and
the definitional 115mi distance -- see the earlier investigation, not
repeated here since the underlying facts didn't change with the DB move.

Connection is env-var configurable:
  PG_HOST (default: localhost), PG_PORT (default: 5432),
  PG_DB (default: rain), PG_USER (default: rain_app),
  PG_PASSWORD (default: rain_dev_pw)
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


PRENATAL_COMPLETION_SQL = """SELECT {col}::int FROM "MetricTrend" WHERE metric_id = 'prenatal_completion_rate'"""


def get_maria_live_kpis() -> dict:
    """Returns all 7 KPIs, computed live via real SQL."""
    return {
        "active_pregnancies": _query_one('SELECT COUNT(*) FROM "PregnancyEpisode"'),
        "elevated_risk": _query_one(
            'SELECT COUNT(*) FROM "PregnancyEpisode" WHERE distance_to_delivery_miles = 115'
        ),
        "no_transport": _query_one("""
            SELECT COUNT(*) FROM "PregnancyEpisode" pe
            WHERE pe.patient_id NOT IN (SELECT patient_id FROM "TransportRequest" WHERE scheduled = true)
        """),
        "ed_deliveries": _query_one(
            """SELECT COUNT(*) FROM "ClaimEncounter" WHERE encounter_type = 'ED_delivery_or_BBA'"""
        ),
        # Service-area completion rate after the closure, from the stored
        # MetricTrend row (84% before -> 61% after). The old query here counted
        # visits since April in the 115-mile cohort, which is a different
        # measure and happened to equal the BEFORE figure (84%).
        "prenatal_completion": _query_one(PRENATAL_COMPLETION_SQL.format(col="after_value")),
        # Definitional: this IS the value that defines the elevated-risk
        # cohort, so an AVG over that cohort is trivially itself -- still a
        # genuine live query, just not an independent statistic.
        "distance_delivery": _query_one(
            'SELECT ROUND(AVG(distance_to_delivery_miles)) FROM "PregnancyEpisode" WHERE distance_to_delivery_miles = 115'
        ),
        # Booked = has a slot; requested visits with no date are not booked.
        "telehealth_booked": _query_one(
            """SELECT COUNT(*) FROM "TelehealthSession" WHERE session_type='prenatal' AND eligibility_status='eligible' AND scheduled_date IS NOT NULL"""
        ),
    }


def get_maria_live_signals() -> dict:
    """Live metrics for Maria's 3 signal cards, keyed by signal id."""
    elevated_risk_count = _query_one(
        'SELECT COUNT(*) FROM "PregnancyEpisode" WHERE distance_to_delivery_miles = 115'
    )
    no_transport = _query_one("""
        SELECT COUNT(*) FROM "PregnancyEpisode" pe
        WHERE pe.patient_id NOT IN (SELECT patient_id FROM "TransportRequest" WHERE scheduled = true)
    """)
    completion_pct = _query_one(PRENATAL_COMPLETION_SQL.format(col="after_value"))
    prior_completion_pct = _query_one(PRENATAL_COMPLETION_SQL.format(col="before_value"))
    return {
        "SIG-RAIN-MARIA-001": {
            "affected_count": elevated_risk_count,
            "metric_value": elevated_risk_count,
            "metrics": {
                "third_trimester": _query_one(
                    """SELECT COUNT(*) FROM "PregnancyEpisode" WHERE distance_to_delivery_miles = 115 AND trimester = 3"""
                ),
                "high_risk_diagnosis": _query_one(
                    """SELECT COUNT(*) FROM "PregnancyEpisode" WHERE distance_to_delivery_miles = 115 AND risk_diagnoses != ''"""
                ),
                "missed_visit": _query_one(
                    """SELECT COUNT(*) FROM "PregnancyEpisode" WHERE distance_to_delivery_miles = 115 AND last_prenatal_visit_date < '2026-04-01'"""
                ),
            },
        },
        "SIG-RAIN-MARIA-002": {
            "affected_count": no_transport,
            "description": (
                f"Prenatal visit completion in the service area dropped from {int(prior_completion_pct)}% to {int(completion_pct)}% after the closure. "
                f"{int(no_transport)} pregnancies have no transport scheduled."
            ),
            "metrics": {
                "completion_pct": completion_pct,
                "prior_completion_pct": prior_completion_pct,
                "no_transport_scheduled": no_transport,
            },
        },
        "SIG-RAIN-MARIA-003": {
            "affected_count": _query_one(
                """SELECT COUNT(*) FROM "ClaimEncounter" WHERE encounter_type = 'ED_delivery_or_BBA'"""
            ),
            "metric_value": _query_one(
                """SELECT COUNT(*) FROM "ClaimEncounter" WHERE encounter_type = 'ED_delivery_or_BBA'"""
            ),
            "metrics": {
                "events_60d": _query_one(
                    """SELECT COUNT(*) FROM "ClaimEncounter" WHERE encounter_type = 'ED_delivery_or_BBA'"""
                ),
                "events_prior_6mo": _query_one(
                    """SELECT COUNT(*) FROM "ClaimEncounter" WHERE encounter_type = 'ED_delivery_or_BBA' AND date < '2026-03-01'"""
                ),
            },
        },
    }


if __name__ == "__main__":
    live = get_maria_live_kpis()
    expected = {"active_pregnancies": 126, "elevated_risk": 38, "no_transport": 22, "ed_deliveries": 3}
    print("Live PostgreSQL results vs. known-correct values:")
    for key, val in live.items():
        status = "OK" if val == expected[key] else "MISMATCH"
        print(f"  {key:20s} live={val:<5} expected={expected[key]:<5} [{status}]")
