"""
Live content for Sarah's CHF/COPD Deterioration Board (the last Tier-1 card).

The cohort (17 patients, 11 CHF/weight + 6 COPD/spo2) is exactly the
verified "CHF COPD worsening RPM deterioration" rule in business_rules.py --
`SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN
('CHF','COPD')` -- so this module and that rule can never disagree.

Checked against the static card it replaces:
  - "11 weight up / 6 SpO2 down"     -> confirmed exact (11 CHF, 6 COPD)
  - "5 lost their provider"          -> confirmed exact (5 of 17 assigned
                                         to a deactivated provider)
  - "9 with a 30-day med gap"        -> WRONG. The real count is 10 (also
                                         the figure behind the already-
                                         verified "10 of the 17 worsening
                                         patients have a medication gap"
                                         note in business_rules.py). Fixed
                                         here, not reproduced as 9.
  - the "silent (24d)" badge on one patient -> WRONG. Zero of the 17 are
                                         silent: every one transmitted an
                                         RPM reading dated 2026-05-15 (the
                                         same finding already documented in
                                         Sarah's Tier 1 action package). Not
                                         reproduced; included as a flag that
                                         is simply false for all 17 today,
                                         so it always renders empty rather
                                         than being silently removed from
                                         the data model.
  - fictional patient ids (P-3310 etc) -> replaced with the real PT-0012x ids
  - the sparkline shapes               -> now drawn from each patient's real
                                         RPM readings, downsampled to 6
                                         points for the same visual size as
                                         the original.

Every figure is computed fresh from rain.db on each call.
"""

import os
import pg_compat as sqlite3
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"
SILENT_DAYS = 24
MED_GAP_DAYS = 30


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _downsample(values, n=6):
    """Evenly spaced n-point sample of a longer series, keeping the first
    and last points -- for a compact sparkline that still reflects the
    real trend rather than a smoothed or invented shape."""
    if len(values) <= n:
        return values
    step = (len(values) - 1) / (n - 1)
    return [values[round(i * step)] for i in range(n)]


def get_deterioration_board():
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT patient_id, condition_type FROM RPMReading WHERE condition_type IN ('CHF','COPD') ORDER BY patient_id"
        ).fetchall()

        patients = []
        for r in rows:
            pid, cond = r["patient_id"], r["condition_type"]
            marker = "weight" if cond == "CHF" else "spo2"
            readings = [float(x["value"]) for x in conn.execute(
                "SELECT value FROM RPMReading WHERE patient_id = ? AND reading_type = ? ORDER BY timestamp", (pid, marker))]
            pts = _downsample(readings)

            fill = conn.execute("SELECT fill_date FROM MedicationFill WHERE patient_id = ? ORDER BY fill_date DESC LIMIT 1", (pid,)).fetchone()
            med_gap = bool(fill) and (date.fromisoformat(AS_OF) - date.fromisoformat(fill["fill_date"])).days > MED_GAP_DAYS

            enr = conn.execute("SELECT assigned_provider_id FROM ChronicConditionEnrollment WHERE patient_id = ? LIMIT 1", (pid,)).fetchone()
            reassigned = False
            if enr:
                prov = conn.execute("SELECT status FROM Provider WHERE provider_id = ?", (enr["assigned_provider_id"],)).fetchone()
                reassigned = bool(prov) and prov["status"] == "deactivated"

            transport = bool(conn.execute("SELECT 1 FROM SDOHFlag WHERE patient_id = ? AND flag_type = 'transportation'", (pid,)).fetchone())

            last_rpm = conn.execute("SELECT MAX(timestamp) FROM RPMReading WHERE patient_id = ?", (pid,)).fetchone()[0]
            last_claim = conn.execute("SELECT MAX(date) FROM ClaimEncounter WHERE patient_id = ?", (pid,)).fetchone()[0]
            gaps = [(date.fromisoformat(AS_OF) - date.fromisoformat(str(d)[:10])).days for d in (last_rpm, last_claim, fill["fill_date"] if fill else None) if d]
            silent = bool(gaps) and min(gaps) >= SILENT_DAYS

            patients.append({"id": pid, "cond": cond, "marker": marker, "pts": pts,
                             "med_gap": med_gap, "reassigned": reassigned, "transport": transport, "silent": silent})

        weight_up = sum(1 for p in patients if p["marker"] == "weight")
        spo2_down = sum(1 for p in patients if p["marker"] == "spo2")
        return {
            "as_of": AS_OF, "total": len(patients), "weight_up": weight_up, "spo2_down": spo2_down,
            "patients": patients,
            "med_gap_count": sum(p["med_gap"] for p in patients),
            "reassigned_count": sum(p["reassigned"] for p in patients),
            "transport_count": sum(p["transport"] for p in patients),
            "silent_count": sum(p["silent"] for p in patients),
        }
    finally:
        conn.close()
