"""
Live content for David's two Tier-1 static cards: the Data Health board
(connected sources + summary stats) and the Reconciliation Breakdown
(unresolved provider references by record type + crosswalk mismatches).

Both are read-only informational boards -- no route/hold gate, nothing to
approve. Every figure here is computed fresh from rain.db on each call;
nothing is cached or pre-written. See AS_OF for the dataset's fixed "today".

Key finding that drove this build: ProviderReferenceIssue holds BOTH
categories in one table, distinguished by status:
  - status='unresolved'  (source_table in encounter/order/pending_claim) -> 1,240 total
  - status='mismatched'  (source_table='panel_crosswalk')                -> 180 total
These two counts are exactly the figures already verified in
business_rules.py ("Provider crosswalk mismatch" / unresolved-references
rules), so this module and those rules can never disagree -- they read the
same rows.

The static card it replaces invented a 620/410/210 breakdown that happened
to sum to 1,240 but did not match any real category. The real breakdown is
Orders / Encounters / Pending claims, computed below.
"""

import os
import pg_compat as sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"

# Display labels for the real DataSourceFeed rows (source_name -> short label).
# Every key here must exist in DataSourceFeed; a feed with no mapping still
# displays under its raw source_name rather than being silently dropped.
SOURCE_LABELS = {
    "Clinical EHR": "Clinical EHR",
    "Maternal Health Registry": "Maternal Health Registry",
    "RPM Platform": "RPM Platform",
    "Claims & Encounters": "Claims",
    "Telehealth (Project ECHO Nevada)": "Telehealth",
    "EMS / Transport Dispatch": "EMS / Transport",
    "NEMT / Transportation Logs": "NEMT Logs",
    "SDOH Data": "SDOH Data",
    "Public Health Registries": "Public Health Reg.",
    "State HIE": "State HIE",
    "Enterprise Data Warehouse (GCP)": "Enterprise Data Warehouse",
    "New Rural Clinic EHR Connector": "New Rural Clinic EHR",
}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _status(conformance_pct, lag_status):
    """A source is red if it's delayed or badly out of conformance, yellow if
    it's on-time but below full conformance, green otherwise. This is a
    stated rule, not a fitted one -- anyone can re-derive it from the two
    underlying columns."""
    if lag_status == "delayed" or conformance_pct < 90:
        return "red"
    if conformance_pct < 97:
        return "yellow"
    return "green"


def get_data_health_board():
    conn = _conn()
    try:
        feeds = conn.execute(
            "SELECT source_name, fhir_conformance_pct, pipeline_freshness_hours, ingestion_lag_status FROM DataSourceFeed ORDER BY source_name"
        ).fetchall()
        sources = []
        for f in feeds:
            pct = float(f["fhir_conformance_pct"])
            lag = float(f["pipeline_freshness_hours"])
            status = _status(pct, f["ingestion_lag_status"])
            if status == "green":
                note = "Healthy"
            elif f["ingestion_lag_status"] == "delayed":
                note = f"Delayed {lag:g}h"
            else:
                note = f"{pct:g}% FHIR conformance"
            sources.append({"name": SOURCE_LABELS.get(f["source_name"], f["source_name"]), "status": status, "note": note})

        avg_conformance = sum(float(f["fhir_conformance_pct"]) for f in feeds) / len(feeds)
        avg_lag = sum(float(f["pipeline_freshness_hours"]) for f in feeds) / len(feeds)
        unresolved = conn.execute("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'").fetchone()[0]

        return {
            "as_of": AS_OF,
            "source_count": len(feeds),
            "sources": sources,
            "stats": [
                {"value": f"{avg_conformance:.0f}%", "label": "Avg FHIR conformance"},
                {"value": f"{avg_lag:.1f} hrs", "label": "Avg pipeline lag"},
                {"value": f"{unresolved:,}", "label": "Unresolved provider refs"},
            ],
        }
    finally:
        conn.close()


def get_reconciliation_breakdown():
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT source_table, COUNT(*) n FROM ProviderReferenceIssue WHERE status = 'unresolved' GROUP BY source_table"
        ).fetchall()
        label = {"order": "Orders", "encounter": "Encounters", "pending_claim": "Pending claims"}
        types = [{"label": label.get(r["source_table"], r["source_table"]), "count": r["n"]} for r in rows]
        types.sort(key=lambda t: -t["count"])
        total = sum(t["count"] for t in types)

        mismatches = conn.execute("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched'").fetchone()[0]
        deactivated = conn.execute(
            "SELECT provider_id, deactivation_date FROM Provider WHERE status = 'deactivated' ORDER BY deactivation_date LIMIT 1"
        ).fetchone()

        return {
            "as_of": AS_OF, "total": total, "types": types, "crosswalk_mismatches": mismatches,
            "deactivation_date": deactivated["deactivation_date"] if deactivated else None,
            "note": "Fixable with a claims-only active flag on the deactivated NPIs plus a panel crosswalk update.",
        }
    finally:
        conn.close()
