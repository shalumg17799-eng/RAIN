"""
Live content for Maria's Telehealth Scenario Model card.

The patient-assignment breakdown (8 telehealth / 3 hybrid+NEMT / 3 in-person)
is exactly build_maternal_package()'s own intervention split, so this card
and Maria's action package can never disagree about who is assigned what.

The static card's top half was a fabricated 30-day FORECAST (Now/+10d/+20d/
+30d, two full projected trajectories). No forecasting mechanism exists
anywhere in the dataset -- there is no methodology, model, or even a second
historical data point to extrapolate from. That entire chart is dropped, not
approximated.

In its place: the dataset DOES hold one real, stored two-point trend for
this exact metric, in MetricTrend (metric_id='prenatal_completion_rate'):
before=84% (2026-01-30), after=61% (2026-05-15). This is a genuine
documented fact, not invented.

IMPORTANT, and disclosed in the response rather than picked silently: this
documented trend's "after" value (61%) does NOT match the live snapshot
computed directly from PregnancyEpisode.last_prenatal_visit_date for the
same cohort on the same date (84% -- the already-verified "Prenatal
completion rate current" rule in business_rules.py). Both are real, stored
facts that disagree with each other; this module reports both rather than
resolving the conflict on its own.
"""

import os
import pg_compat as sqlite3

from maria_action_package import build_maternal_package

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def get_telehealth_scenario():
    pkg = build_maternal_package()
    conn = _conn()
    try:
        trend = conn.execute(
            "SELECT before_value, after_value, before_date, after_date, note FROM MetricTrend WHERE metric_id = 'prenatal_completion_rate'"
        ).fetchone()
        live = conn.execute(
            "SELECT ROUND(100.0 * SUM(CASE WHEN last_prenatal_visit_date >= '2026-04-01' THEN 1 ELSE 0 END) / COUNT(*)) "
            "FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115"
        ).fetchone()[0]

        s = pkg["summary"]["interventions"]
        assignments = [
            {"label": "Telehealth", "count": s["telehealth"], "note": "Adequate broadband — virtual monitoring", "color": "#059669"},
            {"label": "Hybrid + NEMT", "count": s["hybrid_nemt"], "note": "Virtual + in-person fallback", "color": "#003366"},
            {"label": "In-person only", "count": s["in_person"], "note": "No broadband on record — highest priority", "color": "#DC2626"},
        ]

        return {
            "as_of": pkg["as_of"], "total": pkg["summary"]["patients"], "assignments": assignments,
            "documented_trend": {"before": int(trend["before_value"]), "after": int(trend["after_value"]),
                                 "before_date": trend["before_date"], "after_date": trend["after_date"], "source_note": trend["note"]},
            "live_snapshot": {"value": int(live), "as_of": pkg["as_of"]},
            "discrepancy": int(trend["after_value"]) != int(live),
            "note": ("No forecasting model exists in the dataset, so the projected 30-day trend line shown on the static card "
                    "(a smooth recovery to 88%) is not reproduced. What the dataset does hold: a documented before/after figure "
                    f"(84% \u2192 {int(trend['after_value'])}%, recorded as a stored trend) that does not match today's live snapshot "
                    f"computed directly from visit records ({int(live)}%). Both are shown; neither is hidden to make the other look right."),
        }
    finally:
        conn.close()
