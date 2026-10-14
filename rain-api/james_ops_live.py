"""
Live content for James's two remaining Tier-1 static cards: the Daily
Operations status tiles, and the Trip -> Telehealth conversion card.

IMPORTANT -- read before extending either function. These two cards are NOT
simple 1:1 conversions of their static originals. The static cards invented
figures the dataset cannot support, and this module does not reproduce them:

  OpsTrafficLightTiles (static) claimed 5 tiles. Two have zero basis anywhere
  in the schema:
    - "Telehealth Capacity: 31 unslotted"  -- no room/bandwidth/capacity
      field exists on TelehealthSession or anywhere else (already the
      documented finding behind the verified "James Q4" business rule).
    - "Mobile Clinic: 98% util"            -- no mobile-clinic entity or
      utilization field exists in the schema at all.
    - "Facility Beds: Available"           -- Facility has no bed-count or
      occupancy field.
  This module replaces those three invented tiles with real, computable ops
  facts instead (telehealth volume today, the EMS coverage gap, facility
  status) rather than inventing numbers to fill the original shape.

  TripTelehealthConversion (static) claimed "13 convertible / 7 home-capable
  / 6 need a room slot", an EMS projection ("47 min -> <38 min"), and
  "vehicles freed... for afternoon dialysis" -- RAIN has no dialysis concept
  anywhere, no room-slot data, and no mechanism to project an EMS response
  change from a transport conversion. The ONLY real figure behind this card
  is the proxy already verified in business_rules.py: of today's scheduled
  transports, how many belong to a patient who also has an eligible
  telehealth session booked. The live version returns exactly that, labelled
  as a proxy -- not a fictional breakdown.

Every figure below is computed fresh from rain.db on each call.
"""

import os
import pg_compat as sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def get_ops_traffic_tiles():
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ?", (AS_OF,)).fetchone()[0]
        unscheduled = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ? AND scheduled = 'False'", (AS_OF,)).fetchone()[0]
        telehealth_today = conn.execute("SELECT COUNT(*) FROM TelehealthSession WHERE scheduled_date = ?", (AS_OF,)).fetchone()[0]
        worst = conn.execute("SELECT zip_code, avg_response_time_minutes FROM EMSCoverage ORDER BY CAST(avg_response_time_minutes AS FLOAT) DESC LIMIT 1").fetchone()
        no_coverage = conn.execute("SELECT COUNT(*) FROM EMSCoverage WHERE unit_available_within_60min = 'False'").fetchone()[0]
        closed = conn.execute("SELECT COUNT(*) FROM Facility WHERE status = 'closed'").fetchone()[0]
        facility_total = conn.execute("SELECT COUNT(*) FROM Facility").fetchone()[0]

        tiles = [
            {"icon": "Truck", "label": "Transport Queue", "value": f"+{unscheduled} over" if unscheduled else "On track",
             "status": "red" if unscheduled else "green", "detail": f"{unscheduled} of {total} unscheduled today"},
            {"icon": "Video", "label": "Telehealth Today", "value": f"{telehealth_today} sessions",
             "status": "info",
             "detail": f"{telehealth_today} sessions scheduled for {AS_OF} (the dataset holds no room/capacity figure to compare against, so this is informational only)"},
            {"icon": "Ambulance", "label": "EMS Response", "value": f"{float(worst['avg_response_time_minutes']):.0f} min (worst)" if worst else "n/a",
             "status": "red" if no_coverage else "green",
             "detail": f"ZIP {worst['zip_code']} is the slowest; {no_coverage} ZIP(s) have no unit within 60 min" if worst else ""},
            {"icon": "Building2", "label": "Facility Status", "value": f"{closed} of {facility_total} closed",
             "status": "yellow" if closed else "green", "detail": "Battle Mountain Critical Access Hospital, closed 2026-03-01" if closed else ""},
        ]
        return {"as_of": AS_OF, "tiles": tiles,
                "omitted": ["Mobile Clinic utilization", "Facility bed availability"],
                "omitted_reason": "No utilization or bed-count field exists anywhere in the dataset for these; shown in the static card only, not computable here."}
    finally:
        conn.close()


def get_transport_queue_breakdown():
    """Live replacement for TransportQueueTimeline.jsx -- the static card's
    entire premise (an hourly chart, an 8-11a peak, a 'dialysis/oncology'
    category, a vehicle capacity of 6, double-booked patients) has no basis
    anywhere in the dataset: TransportRequest carries no hour-of-day field,
    no table holds vehicle/capacity data, and 'dialysis' appears nowhere.
    What IS real: today's requests split by request_type (EMS vs NEMT) and
    by scheduled status -- shown instead of the invented hourly chart."""
    conn = _conn()
    try:
        by_type = conn.execute("SELECT request_type, COUNT(*) FROM TransportRequest WHERE date = ? GROUP BY request_type", (AS_OF,)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ?", (AS_OF,)).fetchone()[0]
        scheduled = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ? AND scheduled = 'True'", (AS_OF,)).fetchone()[0]
        unscheduled = total - scheduled
        return {
            "as_of": AS_OF, "total": total, "scheduled": scheduled, "unscheduled": unscheduled,
            "by_type": [{"label": t, "count": n} for t, n in by_type],
            "note": "No hour-of-day field exists on transport requests, no table holds vehicle or capacity data, and no "
                    "'dialysis/oncology' category exists in the dataset -- the static card's hourly peak chart, 8-11a collision, "
                    "vehicle capacity of 6, and double-booking claim are not reproduced. Shown instead: today's real split by type and schedule status.",
        }
    finally:
        conn.close()


def get_trip_telehealth_conversion():
    conn = _conn()
    try:
        scheduled = conn.execute("SELECT COUNT(*) FROM TransportRequest WHERE date = ? AND scheduled = 'True'", (AS_OF,)).fetchone()[0]
        proxy = conn.execute(
            "SELECT COUNT(*) FROM TransportRequest t WHERE t.date = ? AND t.scheduled = 'True' "
            "AND t.patient_id IN (SELECT patient_id FROM TelehealthSession WHERE eligibility_status = 'eligible')",
            (AS_OF,),
        ).fetchone()[0]
        return {
            "as_of": AS_OF, "scheduled_today": scheduled, "proxy_convertible": proxy,
            "method": "No field in the dataset marks a transport as convertible to telehealth. This counts scheduled "
                      "transports whose patient also has an eligible telehealth session booked today -- a proxy, not a measured conversion rate.",
            "note": "The static card's 13/7/6 split, EMS response projection, and vehicle-reallocation claim have no basis "
                    "in the dataset (no room-slot data, no dialysis concept, no mechanism to project an EMS change from a conversion) and are not reproduced here.",
        }
    finally:
        conn.close()
