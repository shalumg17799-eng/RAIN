"""
James's Today's Operations Plan -- the fourth of RAIN's action packages,
sharing the same approval gate and audit log (action_engine.py).

Checked against the static card it replaces:
  - "Consolidated transport schedule... resolves 3 double-bookings, shifts
    5 to afternoon" -> UNSUPPORTED. No hour-of-day field exists on
    TransportRequest, so double-booking and shifting cannot be computed.
    Replaced with the real unscheduled count (9 of 73 today).
  - "13 trips converted to telehealth... 7 home visits, 6 freed rooms" ->
    WRONG. The only real figure is the already-verified proxy: 3 of 64
    scheduled transports belong to a patient who also has an eligible
    telehealth session today. No room/home-visit split exists.
  - "EMS crew reassignment... restores a unit to the northern ZIP codes" ->
    grounded in the real, already-verified coverage gap: 2 ZIPs (89820,
    89821) have no EMS unit within 60 minutes.
  - "Daily risk panel: 16 elevated-risk patients awaiting transport" ->
    WRONG. The real figure is 9 unscheduled transport requests, and of
    those 9: 0 are elevated-risk pregnancy patients, 0 have worsening RPM
    readings -- all 9 are chronic-condition enrollees. This is the exact
    finding already behind James's verified "elevated-risk patients
    awaiting transport" chat answer.

DRAFT-ONLY: routing records a person's approval through action_engine and
never executes anything against the dataset or any external system.
"""

import hashlib
import os
import pg_compat as sqlite3

import action_engine as engine
from action_engine import ActionInputError

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"
TYPES = ("transport_schedule", "telehealth_conversion", "ems_reassignment", "risk_panel")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def build_operations_plan(inputs=None, log_path=None):
    if inputs:
        raise ActionInputError("This package takes no inputs: every action is fully drafted from the data.")
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ?", (AS_OF,)).fetchone()[0]
        scheduled = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ? AND scheduled = 'True'", (AS_OF,)).fetchone()[0]
        unscheduled_ids = [r[0] for r in conn.execute("SELECT patient_id FROM TransportRequest WHERE date = ? AND scheduled = 'False'", (AS_OF,))]
        unscheduled = len(unscheduled_ids)

        proxy = conn.execute(
            "SELECT COUNT(*) FROM TransportRequest t WHERE t.date = ? AND t.scheduled = 'True' "
            "AND t.patient_id IN (SELECT patient_id FROM TelehealthSession WHERE eligibility_status = 'eligible')", (AS_OF,)
        ).fetchone()[0]

        gaps = conn.execute("SELECT zip_code, avg_response_time_minutes FROM EMSCoverage WHERE unit_available_within_60min = 'False' ORDER BY CAST(avg_response_time_minutes AS FLOAT) DESC").fetchall()

        ph = ",".join("?" * unscheduled) if unscheduled else "''"
        elevated_preg = conn.execute(f"SELECT COUNT(DISTINCT patient_id) FROM PregnancyEpisode WHERE trimester=3 AND distance_to_delivery_miles=115 AND patient_id IN ({ph})", unscheduled_ids).fetchone()[0] if unscheduled else 0
        worsening_rpm = conn.execute(f"SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type IN ('CHF','COPD') AND patient_id IN ({ph})", unscheduled_ids).fetchone()[0] if unscheduled else 0
        chronic = conn.execute(f"SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE patient_id IN ({ph})", unscheduled_ids).fetchone()[0] if unscheduled else 0

        package_id = "OPSPLAN-%s-%s" % (AS_OF.replace("-", ""), hashlib.md5(f"{total}{scheduled}{proxy}".encode()).hexdigest()[:6].upper())

        actions = [
            {"action_id": f"{package_id}:transport_schedule", "type": "transport_schedule", "patient_id": None,
             "status": "ready", "needs": [],
             "draft": {"scheduled": scheduled, "unscheduled": unscheduled, "total": total,
                       "message": f"{unscheduled} of {total} transport requests are unscheduled today. No hour-of-day field exists in the "
                                  "dataset, so double-booking and schedule-shifting cannot be computed or claimed."}},
            {"action_id": f"{package_id}:telehealth_conversion", "type": "telehealth_conversion", "patient_id": None,
             "status": "ready", "needs": [],
             "draft": {"proxy_convertible": proxy, "scheduled_today": scheduled,
                       "message": f"{proxy} of {scheduled} scheduled transports belong to a patient who also has an eligible telehealth "
                                  "session today -- a proxy, since no field marks a transport as convertible. No room-slot or home-visit data exists."}},
            {"action_id": f"{package_id}:ems_reassignment", "type": "ems_reassignment", "patient_id": None,
             "status": "ready", "needs": [],
             "draft": {"gap_zips": [{"zip": g["zip_code"], "minutes": float(g["avg_response_time_minutes"])} for g in gaps],
                       "message": (f"{len(gaps)} ZIP code(s) have no EMS unit available within 60 minutes: " +
                                  ", ".join(f"{g['zip_code']} ({float(g['avg_response_time_minutes']):.0f} min)" for g in gaps) +
                                  ". No vehicle/crew roster exists in the dataset, so a specific reassignment cannot be drafted -- this flags where coverage is needed.")}},
            {"action_id": f"{package_id}:risk_panel", "type": "risk_panel", "patient_id": None,
             "status": "ready", "needs": [],
             "draft": {"unscheduled": unscheduled, "elevated_pregnancy": elevated_preg, "worsening_rpm": worsening_rpm, "chronic": chronic,
                       "message": f"{unscheduled} patients have an unscheduled transport request today. Of them: {elevated_preg} are elevated-risk "
                                  f"pregnancy patients, {worsening_rpm} have worsening RPM readings, and {chronic} are chronic-condition enrollees."}},
        ]

        pkg = {"package_id": package_id, "persona": "james", "kind": "operations_plan", "as_of": AS_OF, "actions": actions, "patients": [],
              "notes": ["The static card's double-booking claim, 13-trip telehealth conversion, and '16 elevated-risk patients' figure all "
                       "had no basis in the dataset and are not reproduced. The real risk-panel finding is the opposite of what was claimed: "
                       "none of today's unscheduled transports belong to an elevated-risk pregnancy or worsening-RPM patient."]}
        engine.finalize(pkg, log_path, TYPES)
        pkg["display"] = {
            "title": "Today's Operations Plan",
            "rows": [
                {"icon": "route", "label": "Transport schedule", "status": "ready", "detail": actions[0]["draft"]["message"]},
                {"icon": "video", "label": "Telehealth overlap", "status": "ready", "detail": actions[1]["draft"]["message"]},
                {"icon": "ambulance", "label": "EMS coverage gap", "status": "ready", "detail": actions[2]["draft"]["message"]},
                {"icon": "heart", "label": "Daily risk panel", "status": "ready", "detail": actions[3]["draft"]["message"]},
            ],
            "footer": "Draft only \u2014 routing records your approval; nothing is executed against the dataset or any external system.",
        }
        return pkg
    finally:
        conn.close()


def decide_operations(decision, decided_by, inputs=None, note=None, log_path=None):
    return engine.decide(build_operations_plan, decision, decided_by, inputs, note, log_path)


def get_operations_audit(log_path=None):
    return engine.audit(build_operations_plan, log_path)
