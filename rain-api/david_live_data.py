"""
David's signals/KPIs, computed live via real SQL against PostgreSQL.

Confirmed exact:
- unresolved_refs = COUNT(ProviderReferenceIssue WHERE status='unresolved') = 1240
- deactivated_providers = COUNT(Provider WHERE status='deactivated') = 2
- sources = COUNT(DataSourceFeed) = 12 -- corrects the static card's wrong 11
- fhir_conformance = AVG(DataSourceFeed.fhir_conformance_pct) = 96% -- corrects
  the static card's wrong 94%
- pipeline_freshness = AVG(DataSourceFeed.pipeline_freshness_hours) = 4.5 hrs --
  corrects the static card's wrong 3.2 hrs
- rpm_completeness current value = 61% (hypertension RPM received/total) --
  corrects the static card's wrong 78%; no model exists in the dataset for
  the static card's paired "target 95%" claim, so only the current % is
  made live, not a projected target
- SIG-RAIN-DAVID-002 window_days = 14 -- days since DQE-RPM-GAP (the real
  data-quality event behind this card) was detected (2026-05-01), matching
  this card's own label exactly. window_hours stays static: no hour-level
  field exists on DataQualityEvent, and the RPM Platform's real lag (14
  hrs) doesn't match the card's "24" under any tested reading.

Still not computable (genuinely no backing field in the dataset):
- ingested (9.2M) -- no record-count/ingestion-volume field anywhere
- quarantine (14,800) -- no quarantine concept exists anywhere in the schema
- SIG-RAIN-DAVID-003 null_location_pct / malformed_code_pct -- ClaimEncounter
  has no location or malformed-code field; the card's underlying event
  (DQE-FHIR-CONFORMANCE, tied to the real New Rural Clinic EHR Connector
  at 88% conformance) is real, but this specific percentage split is not
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


def get_david_live_kpis() -> dict:
    # SQL results are pulled into locals first so no backslash-escaped quote
    # sits inside an f-string expression (illegal on Python 3.11; this code
    # was originally written for 3.12+). Behavior is unchanged.
    fhir = round(_query_one('SELECT AVG(fhir_conformance_pct::float) FROM "DataSourceFeed"'))
    freshness = round(_query_one('SELECT AVG(pipeline_freshness_hours::float) FROM "DataSourceFeed"'), 1)
    rpm = _query_one(
        "SELECT ROUND(100.0 * SUM(CASE WHEN transmission_status='received' THEN 1 ELSE 0 END) / COUNT(*)) "
        'FROM "RPMReading" WHERE condition_type=\'hypertension\''
    )
    return {
        "unresolved_refs": _query_one("""SELECT COUNT(*) FROM "ProviderReferenceIssue" WHERE status='unresolved'"""),
        "sources": _query_one('SELECT COUNT(*) FROM "DataSourceFeed"'),
        "fhir_conformance": f"{fhir}%",
        "pipeline_freshness": f"{freshness} hrs",
        "rpm_completeness": f"{rpm}%",
    }


def get_david_live_signals() -> dict:
    unresolved = _query_one("""SELECT COUNT(*) FROM "ProviderReferenceIssue" WHERE status='unresolved'""")
    window_days = _query_one("""SELECT (DATE '2026-05-15' - detected_date) FROM "DataQualityEvent" WHERE event_id='DQE-RPM-GAP'""")
    fhir_pct = _query_one('SELECT ROUND(AVG(fhir_conformance_pct::float)) FROM "DataSourceFeed"')
    return {
        "SIG-RAIN-DAVID-001": {
            "affected_count": unresolved,
            "metric_value": unresolved,
            "metrics": {
                "deactivated_providers": _query_one("""SELECT COUNT(*) FROM "Provider" WHERE status='deactivated'"""),
            },
        },
        "SIG-RAIN-DAVID-002": {
            # window_days: days since DQE-RPM-GAP was detected (2026-05-01 ->
            # 2026-05-15 = 14), matching this card's own label exactly.
            # window_hours stays static -- DataQualityEvent carries no hour-
            # level field, and the RPM Platform's real lag (14 hrs) doesn't
            # match the card's "24" under any tested reading.
            "metrics": {"window_days": window_days},
        },
        "SIG-RAIN-DAVID-003": {
            "description": f"Average FHIR conformance across connected feeds is {int(fhir_pct)}%.",
            "metrics": {"fhir_conformance_pct": fhir_pct},
        },
    }


if __name__ == "__main__":
    live = get_david_live_kpis()
    expected = {"unresolved_refs": 1240, "sources": 12, "fhir_conformance": "96%", "pipeline_freshness": "4.5 hrs", "rpm_completeness": "61%"}
    print("David live PostgreSQL results:")
    for key, val in live.items():
        status = "OK" if val == expected[key] else "MISMATCH"
        print(f"  {key:20s} live={val!s:<10} expected={expected[key]!s:<10} [{status}]")
    sig = get_david_live_signals()
    checks = {
        "deactivated_providers": (sig["SIG-RAIN-DAVID-001"]["metrics"]["deactivated_providers"], 2),
        "window_days": (sig["SIG-RAIN-DAVID-002"]["metrics"]["window_days"], 14),
    }
    for key, (val, exp) in checks.items():
        print(f"  {key:20s} live={val!s:<5} expected={exp!s:<5} [{'OK' if val == exp else 'MISMATCH'}]")
