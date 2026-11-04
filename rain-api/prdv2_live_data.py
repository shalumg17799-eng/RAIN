"""
Live KPI / signal values for the PRD v0.2 persona wave (kayla, denise,
samuel, linda, marcus), computed via real SQL against the synthetic schema
that migrate_to_postgres / the deploy loader filled from the v0.2 planned
schemas (doc/prd/RAIN_Platform_PRD_v0.2_planned_schemas.sql).

Same contract as the other *_live_data modules: each get_*_live_kpis()
returns {kpi_id: value} for the tiles that have an exact SQL match, and
each get_*_live_signals() returns {signal_id: {overlay fields}}. Errors
propagate to ultra_adapter, which falls back to the static values.

Only structural columns are queried (counts, flags, numeric scales) -- the
generator filled free-text columns with random words, so nothing here
depends on a text value except the shared status vocabulary
(active/pending/approved/closed/rejected).

Connection is env-var configurable: PG_HOST, PG_PORT, PG_DB, PG_USER,
PG_PASSWORD -- same defaults as data_api.py.
"""

import os

import psycopg2

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "127.0.0.1"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DB", "rain"),
    "user": os.environ.get("PG_USER", "rain_app"),
    "password": os.environ.get("PG_PASSWORD", "rain_dev_pw"),
}

# The generator wrote no_show_risk on an arbitrary 0..100000 float scale;
# the top quartile of that scale is what the reminder rules treat as "high".
HIGH_NO_SHOW_THRESHOLD = 70000


def _query_all(queries: dict) -> dict:
    """Run {key: sql} on one connection; every sql returns a single value."""
    conn = psycopg2.connect(**PG_CONFIG)
    out = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            for key, sql in queries.items():
                cur.execute(sql)
                out[key] = cur.fetchone()[0]
    finally:
        conn.close()
    return out


def get_rosa_live_kpis() -> dict:
    """First-person patient tiles, anchored to Rosa's own synthetic record
    (prdv2_personas.ROSA_PATIENT_ID) -- per-patient queries, not panel ones."""
    from prdv2_personas import ROSA_PATIENT_ID as PID
    live = _query_all({
        "upcoming_visits": f"SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{PID}'",
        "pending_confirm": f"SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{PID}' AND status = 'pending'",
        "reminders_received": f"SELECT COUNT(*) FROM synthetic.reminder_message WHERE patient_id = '{PID}'",
        "sms_consent_status": f"SELECT CASE WHEN BOOL_OR(consent_flag) THEN 'Yes' ELSE 'No' END FROM synthetic.contact_preference WHERE patient_id = '{PID}'",
        "coverage_status": f"SELECT INITCAP(MAX(coverage_status)) FROM synthetic.eligibility_check WHERE patient_id = '{PID}'",
        "telehealth_slots": "SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')",
    })
    return live


def get_rosa_live_signals() -> dict:
    from prdv2_personas import ROSA_PATIENT_ID as PID
    live = _query_all({
        "visits": f"SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{PID}'",
        "pending": f"SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{PID}' AND status = 'pending'",
        "slots": "SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')",
        "reminders": f"SELECT COUNT(*) FROM synthetic.reminder_message WHERE patient_id = '{PID}'",
        "replies": f"SELECT COUNT(*) FROM synthetic.reminder_message WHERE patient_id = '{PID}' AND delivery_status IN ('approved','closed')",
    })
    return {
        "SIG-RAIN-ROSA-001": {
            "affected_count": live["pending"],
            "metrics": {"visits_on_file": live["visits"], "pending": live["pending"]},
        },
        "SIG-RAIN-ROSA-002": {
            "affected_count": live["slots"],
            "metrics": {"open_telehealth_slots": live["slots"]},
        },
        "SIG-RAIN-ROSA-003": {
            "affected_count": live["reminders"],
            "metrics": {"reminders_sent": live["reminders"], "replies": live["replies"]},
        },
    }


def get_kayla_live_kpis() -> dict:
    return _query_all({
        "booked_visits": "SELECT COUNT(*) FROM synthetic.appointment",
        "high_no_show": f"SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= {HIGH_NO_SHOW_THRESHOLD}",
        "open_telehealth_slots": "SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')",
        "eligibility_active": "SELECT COUNT(*) FROM synthetic.eligibility_check WHERE coverage_status = 'active'",
        "reminders_sent": "SELECT COUNT(*) FROM synthetic.reminder_message",
        "sms_consent": "SELECT COUNT(*) FROM synthetic.contact_preference WHERE consent_flag",
    })


def get_kayla_live_signals() -> dict:
    live = get_kayla_live_kpis()
    checks_run = _query_all({"n": "SELECT COUNT(*) FROM synthetic.eligibility_check"})["n"]
    return {
        "SIG-RAIN-KAYLA-001": {
            "affected_count": live["high_no_show"],
            "metrics": {"booked_visits": live["booked_visits"], "high_risk": live["high_no_show"]},
        },
        "SIG-RAIN-KAYLA-002": {
            "affected_count": live["open_telehealth_slots"],
            "metrics": {"open_telehealth_slots": live["open_telehealth_slots"]},
        },
        "SIG-RAIN-KAYLA-003": {
            "affected_count": checks_run - live["eligibility_active"],
            "metrics": {"checks_run": checks_run, "active": live["eligibility_active"]},
        },
    }


def get_denise_live_kpis() -> dict:
    return _query_all({
        "open_tasks": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')",
        "high_risk": "SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7",
        "pending_replies": "SELECT COUNT(*) FROM synthetic.reminder_message WHERE delivery_status = 'pending'",
        "sdoh_screened": "SELECT COUNT(*) FROM synthetic.sdoh_screening",
        "tasks_closed": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status = 'closed'",
        "no_sms": "SELECT COUNT(*) FROM synthetic.contact_preference WHERE NOT COALESCE(consent_flag, false)",
    })


def get_denise_live_signals() -> dict:
    live = get_denise_live_kpis()
    return {
        "SIG-RAIN-DENISE-001": {
            "affected_count": live["open_tasks"],
            "metrics": {"open_tasks": live["open_tasks"], "high_risk_patients": live["high_risk"],
                        "closed_tasks": live["tasks_closed"]},
        },
        "SIG-RAIN-DENISE-002": {
            "affected_count": live["pending_replies"],
            "metrics": {"pending_replies": live["pending_replies"]},
        },
        "SIG-RAIN-DENISE-003": {
            "affected_count": live["no_sms"],
            "metrics": {"not_consented": live["no_sms"]},
        },
    }


def get_samuel_live_kpis() -> dict:
    live = _query_all({
        "panel_size": "SELECT COUNT(*) FROM synthetic.patient",
        "visits_week": "SELECT COUNT(*) FROM synthetic.encounter",
        "telehealth_pct": """SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE telehealth_flag)
                             / NULLIF(COUNT(*) FILTER (WHERE telehealth_flag IS NOT NULL), 0))
                             FROM synthetic.encounter""",
        "high_risk_panel": "SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7",
        "low_adherence": "SELECT COUNT(*) FROM synthetic.medication WHERE adherence_ratio < 0.8",
        "rpm_readings": "SELECT COUNT(*) FROM synthetic.rpm_reading",
    })
    live["telehealth_share"] = f"{int(live.pop('telehealth_pct'))}%"
    return live


def get_samuel_live_signals() -> dict:
    live = get_samuel_live_kpis()
    pct = int(str(live["telehealth_share"]).rstrip("%"))
    return {
        "SIG-RAIN-SAMUEL-001": {
            "affected_count": live["visits_week"],
            "metrics": {"visits": live["visits_week"], "telehealth_pct": pct},
        },
        "SIG-RAIN-SAMUEL-002": {
            "affected_count": live["high_risk_panel"],
            "metrics": {"high_risk": live["high_risk_panel"], "panel_size": live["panel_size"]},
        },
        "SIG-RAIN-SAMUEL-003": {
            "affected_count": live["low_adherence"],
            "metrics": {"low_adherence": live["low_adherence"]},
        },
    }


def get_linda_live_kpis() -> dict:
    live = _query_all({
        "high_risk": "SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7",
        "open_gaps": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')",
        "gaps_closed": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status = 'closed'",
        "ed_claims": "SELECT COUNT(*) FROM synthetic.claim WHERE ed_flag",
        "telehealth_pct": """SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE telehealth_flag)
                             / NULLIF(COUNT(*) FILTER (WHERE telehealth_flag IS NOT NULL), 0))
                             FROM synthetic.encounter""",
        "sdoh_coverage": "SELECT COUNT(*) FROM synthetic.sdoh_screening",
    })
    live["telehealth_share"] = f"{int(live.pop('telehealth_pct'))}%"
    return live


def get_linda_live_signals() -> dict:
    live = get_linda_live_kpis()
    return {
        "SIG-RAIN-LINDA-001": {
            "affected_count": live["high_risk"],
            "metrics": {"high_risk": live["high_risk"]},
        },
        "SIG-RAIN-LINDA-002": {
            "affected_count": live["open_gaps"],
            "metrics": {"closed": live["gaps_closed"], "open": live["open_gaps"]},
        },
        "SIG-RAIN-LINDA-003": {
            "affected_count": live["ed_claims"],
            "metrics": {"ed_claims": live["ed_claims"]},
        },
    }


def get_marcus_live_kpis() -> dict:
    return _query_all({
        "counties": "SELECT COUNT(DISTINCT county_fips) FROM synthetic.county_metric",
        "metric_records": "SELECT COUNT(*) FROM synthetic.county_metric",
        "unserved_broadband": "SELECT COUNT(*) FROM synthetic.broadband_coverage WHERE NOT COALESCE(served_flag, true)",
        "clinic_sites": "SELECT COUNT(*) FROM synthetic.clinic_site",
        "telehealth_sites": "SELECT COUNT(*) FROM synthetic.clinic_site WHERE telehealth_capable",
        "ed_claims": "SELECT COUNT(*) FROM synthetic.claim WHERE ed_flag",
    })


def get_marcus_live_signals() -> dict:
    live = get_marcus_live_kpis()
    return {
        "SIG-RAIN-MARCUS-001": {
            "affected_count": live["counties"],
            "metrics": {"counties": live["counties"], "metric_records": live["metric_records"]},
        },
        "SIG-RAIN-MARCUS-002": {
            "affected_count": live["unserved_broadband"],
            "metrics": {"unserved_areas": live["unserved_broadband"], "telehealth_sites": live["telehealth_sites"]},
        },
        "SIG-RAIN-MARCUS-003": {
            "affected_count": live["ed_claims"],
            "metrics": {"ed_claims": live["ed_claims"]},
        },
    }


PRDV2_LIVE_KPI_FUNCS = {
    "rosa": get_rosa_live_kpis,
    "kayla": get_kayla_live_kpis,
    "denise": get_denise_live_kpis,
    "samuel": get_samuel_live_kpis,
    "linda": get_linda_live_kpis,
    "marcus": get_marcus_live_kpis,
}

PRDV2_LIVE_SIGNAL_FUNCS = {
    "rosa": get_rosa_live_signals,
    "kayla": get_kayla_live_signals,
    "denise": get_denise_live_signals,
    "samuel": get_samuel_live_signals,
    "linda": get_linda_live_signals,
    "marcus": get_marcus_live_signals,
}
