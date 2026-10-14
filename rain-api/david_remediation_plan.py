"""
David's Data Remediation Plan -- the third of RAIN's action packages
(alongside Sarah's Tier 1 package and Maria's maternal outreach package),
sharing the same approval gate and audit log (action_engine.py).

Checked against the static card it replaces:
  - Fix 1 (provider reconciliation, "1,240 records resolve") -> confirmed
    real and unchanged.
  - Fix 2 ("RPM completeness 78% -> ~95%") -> start point confirmed: 78% of
    all RPM readings in the monitoring window were received (the same
    definition as David's KPI tile). No buffering model exists in the
    dataset, so no "~95%" outcome can be projected; this shows the real
    current state and the real weakest ZIPs instead.
  - Fix 3 ("clears null-location + bad codes") -> no null-location or
    malformed-code field exists anywhere in ClaimEncounter. The one real
    fact behind this fix is the weakest FHIR feed (New Rural Clinic EHR
    Connector, 88% conformance, the already-verified worst feed) -- shown
    instead of the unverifiable "clears X and Y" claim.

DRAFT-ONLY, like the other two action packages: routing records a person's
approval through action_engine and never executes anything against the
dataset or any external system.
"""

import hashlib
import os
import pg_compat as sqlite3

import action_engine as engine
from action_engine import ActionInputError

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"
TYPES = ("provider_reconciliation", "rpm_completeness", "fhir_mapping")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def build_remediation_plan(inputs=None, log_path=None):
    if inputs:
        raise ActionInputError("This package takes no inputs: every action is fully drafted from the data.")
    conn = _conn()
    try:
        unresolved = conn.execute("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'").fetchone()[0]
        mismatched = conn.execute("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched'").fetchone()[0]

        rpm_rows = conn.execute("SELECT transmission_status, COUNT(*) FROM RPMReading GROUP BY 1").fetchall()
        rpm_total = sum(n for _, n in rpm_rows)
        rpm_received = next((n for s, n in rpm_rows if s == "received"), 0)
        rpm_pct = round(100 * rpm_received / rpm_total) if rpm_total else 0
        weakest_zips = conn.execute(
            "SELECT p.zip_code, ROUND(100.0 * SUM(r.transmission_status='received') / COUNT(*)) pct "
            "FROM RPMReading r JOIN Patient p ON p.patient_id = r.patient_id "
            "GROUP BY p.zip_code ORDER BY pct ASC LIMIT 3"
        ).fetchall()

        weakest_feed = conn.execute("SELECT source_name, fhir_conformance_pct FROM DataSourceFeed ORDER BY CAST(fhir_conformance_pct AS FLOAT) ASC LIMIT 1").fetchone()
        weakest_feed_pct = int(float(weakest_feed["fhir_conformance_pct"]))  # Postgres returns a Decimal (e.g. 88.0) for this numeric column; int() keeps display consistent with the whole-number percentages used everywhere else in the app

        package_id = "REMEDIATION-%s-%s" % (AS_OF.replace("-", ""), hashlib.md5(f"{unresolved}{mismatched}{rpm_total}".encode()).hexdigest()[:6].upper())

        actions = [
            {"action_id": f"{package_id}:provider_reconciliation", "type": "provider_reconciliation", "patient_id": None,
             "status": "ready", "needs": [], "effort": "1 ingestion cycle", "risk": "Low", "recommended": True,
             "draft": {"action": "Apply a claims-only active flag to the deactivated provider NPIs and update the panel crosswalk",
                       "resolves": unresolved, "crosswalk_fixes": mismatched,
                       "message": f"Apply a claims-only active flag to PRV-001/PRV-002 so the {unresolved:,} unresolved provider "
                                  f"references resolve, and update the panel crosswalk for the {mismatched} mismatched records."}},
            {"action_id": f"{package_id}:rpm_completeness", "type": "rpm_completeness", "patient_id": None,
             "status": "ready", "needs": [], "effort": "Next window", "risk": "Low", "recommended": False,
             "draft": {"action": "Enable store-and-forward buffering for the frontier device fleet", "current_pct": rpm_pct,
                       "weakest_zips": [{"zip": z, "pct": p} for z, p in weakest_zips],
                       "message": f"RPM completeness is {rpm_pct}% today ({rpm_received:,} of {rpm_total:,} readings received), "
                                  f"weakest in ZIPs {', '.join(z for z, _ in weakest_zips)}. No projection model exists for the outcome of buffering; "
                                  "this records the real current state, not a forecast."}},
            {"action_id": f"{package_id}:fhir_mapping", "type": "fhir_mapping", "patient_id": None,
             "status": "ready", "needs": [], "effort": "Next window", "risk": "Low", "recommended": False,
             "draft": {"action": "Add a mapping rule for the new rural clinic EHR connector", "weakest_feed": weakest_feed["source_name"],
                       "weakest_pct": weakest_feed_pct,
                       "message": f"{weakest_feed['source_name']} is the weakest feed at {weakest_feed_pct}% FHIR conformance. "
                                  "No null-location or malformed-code field exists in the dataset to size that part of the claim directly."}},
        ]

        pkg = {"package_id": package_id, "persona": "david", "kind": "remediation_plan", "as_of": AS_OF, "actions": actions, "patients": [],
              "notes": [f"RPM completeness is {rpm_pct}% across all device readings in the monitoring window; "
                       "no outcome can be projected because no buffering model exists in the dataset.",
                       "The FHIR-mapping fix is tied to the real weakest feed (New Rural Clinic EHR Connector, 88%) rather than the "
                       "unverifiable 'clears null-location + bad codes' claim on the static card."]}
        engine.finalize(pkg, log_path, TYPES)
        pkg["display"] = {
            "title": "Data Remediation Plan",
            "rows": [
                {"icon": "route" if a["recommended"] else "file", "label": f"{i + 1}. {a['draft']['action']}" + (" — Execute first" if a["recommended"] else ""),
                 "status": "ready" if a["status"] == "ready" else "routed" if a["routed"] else a["status"],
                 "detail": f"Effort: {a['effort']} \u00b7 Risk: {a['risk']} \u00b7 {a['draft']['message']}"}
                for i, a in enumerate(actions)
            ],
            "footer": "Draft only \u2014 routing records your approval; nothing is executed against the dataset or any external system.",
        }
        return pkg
    finally:
        conn.close()


def decide_remediation(decision, decided_by, inputs=None, note=None, log_path=None):
    return engine.decide(build_remediation_plan, decision, decided_by, inputs, note, log_path)


def get_remediation_audit(log_path=None):
    return engine.audit(build_remediation_plan, log_path)
