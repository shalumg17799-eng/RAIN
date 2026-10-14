"""
Priya's NVHA Rural Health Access & Equity Brief -- the fifth and final RAIN
action package, sharing the same approval gate and audit log
(action_engine.py) as Sarah's, Maria's, David's, and James's.

Checked against the static card it replaces:
  - Section 1 ("Maternal care desert 31% -> 58% beyond 60 mi") -> This one
    IS backed by real stored data: MetricTrend holds
    metric_id='maternal_care_desert_pct' (before=31, after=58). BUT it
    measures a different population than the already-verified live
    snapshot rule ("Maternal care desert rate percentage", 30%, 38 of 126
    PregnancyEpisode rows at the coded desert distance of 115 miles) --
    MetricTrend's figure is
    "women of childbearing age beyond 60 miles," a broader population at
    a different distance threshold. Both are real; they are not the same
    measurement. Both are shown, labelled by what each actually counts,
    rather than picking one.
  - Section 2 ("avoidable-ED + continuity attribution... 64%") -> confirmed
    real (76 of 119, the same avoidable-hospitalizations model used
    throughout RAIN).
  - Section 3 (recommended interventions) -> reuses
    priya_intervention_comparison.py's real reach figures directly, so
    this brief and that card can never disagree.
  - Section 4 ("Projected 12-month outcomes") -> UNSUPPORTED. No
    projection or outcomes-forecasting model exists anywhere in the
    dataset (the same gap behind Maria's telehealth-scenario card).
    Dropped, not approximated.
  - Section 5 (measurement plan) -> a plan description, not a data claim;
    kept as authored planning text.

DRAFT-ONLY: routing records a person's approval through action_engine and
never executes or sends anything.
"""

import hashlib
import os
import pg_compat as sqlite3

import action_engine as engine
from action_engine import ActionInputError
from priya_intervention_comparison import get_intervention_comparison

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"
TYPES = ("situation", "evidence", "interventions", "measurement_plan")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def build_equity_brief(inputs=None, log_path=None):
    if inputs:
        raise ActionInputError("This package takes no inputs: every section is fully drafted from the data.")
    conn = _conn()
    try:
        trend = conn.execute(
            "SELECT before_value, after_value, before_date, after_date, note FROM MetricTrend WHERE metric_id = 'maternal_care_desert_pct'"
        ).fetchone()
        desert_total = conn.execute("SELECT COUNT(*) FROM PregnancyEpisode").fetchone()[0]
        desert_affected = conn.execute("SELECT COUNT(*) FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115").fetchone()[0]
        desert_pct = round(100 * desert_affected / desert_total) if desert_total else 0

        ed = conn.execute(
            "SELECT SUM(CASE WHEN date>='2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated') THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN date>='2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag='True' AND encounter_type != 'ED_delivery_or_BBA'"
        ).fetchone()
        ed_pct = round(100 * ed[0] / ed[1]) if ed[1] else 0

        interventions = get_intervention_comparison()["options"]
        package_id = "EQUITYBRIEF-%s-%s" % (AS_OF.replace("-", ""), hashlib.md5(f"{desert_pct}{ed[0]}{ed[1]}".encode()).hexdigest()[:6].upper())

        actions = [
            {"action_id": f"{package_id}:situation", "type": "situation", "patient_id": None, "status": "ready", "needs": [],
             "draft": {"documented_trend": {"before": int(trend["before_value"]), "after": int(trend["after_value"]),
                                            "before_date": trend["before_date"], "after_date": trend["after_date"], "scope": "women of childbearing age, >60mi from OB care"},
                       "live_snapshot": {"value": desert_pct, "affected": desert_affected, "total": desert_total, "scope": "active pregnancies, >100mi from delivery care", "as_of": AS_OF},
                       "message": f"Documented trend: {trend['before_value']}% \u2192 {trend['after_value']}% of women of childbearing age beyond 60mi from OB care "
                                  f"({trend['before_date']} \u2192 {trend['after_date']}). Live snapshot today: {desert_pct}% of active pregnancies ({desert_affected} of {desert_total}) "
                                  "are beyond 100mi from delivery care -- a narrower population at a different threshold, not the same measurement."}},
            {"action_id": f"{package_id}:evidence", "type": "evidence", "patient_id": None, "status": "ready", "needs": [],
             "draft": {"tied": ed[0], "total": ed[1], "tied_pct": ed_pct,
                       "message": f"{ed_pct}% of avoidable ED visits ({ed[0]} of {ed[1]}) are tied to a deactivated provider -- the same "
                                  "cross-system attribution behind Sarah's and David's verified figures."}},
            {"action_id": f"{package_id}:interventions", "type": "interventions", "patient_id": None, "status": "ready", "needs": [],
             "draft": {"options": interventions, "message": f"{sum(1 for o in interventions if o['recommended'])} of {len(interventions)} "
                      "intervention options are recommended, each with its real reach figure from the data."}},
            {"action_id": f"{package_id}:measurement_plan", "type": "measurement_plan", "patient_id": None, "status": "ready", "needs": [],
             "draft": {"message": "No outcomes-projection model exists in the dataset, so the static card's 'Projected 12-month outcomes' "
                      "section is not reproduced. Measurement plan: people served, services delivered, outcomes achieved (NVHA reporting format)."}},
        ]

        pkg = {"package_id": package_id, "persona": "priya", "kind": "equity_brief", "as_of": AS_OF, "actions": actions, "patients": [],
              "notes": ["The maternal-desert figure has two real, disagreeing sources in the dataset -- a documented trend (58%, a broader "
                       "population) and a live snapshot (30%, a narrower one) -- both shown rather than one picked silently.",
                       "The static card's 'Projected 12-month outcomes' section is dropped: no forecasting model exists anywhere in the dataset."]}
        engine.finalize(pkg, log_path, TYPES)
        pkg["display"] = {
            "title": "NVHA Rural Health Access & Equity Brief",
            "rows": [
                {"icon": "file", "label": "1. Situation", "status": "ready", "detail": actions[0]["draft"]["message"]},
                {"icon": "heart", "label": "2. Cross-system evidence", "status": "ready", "detail": actions[1]["draft"]["message"]},
                {"icon": "list", "label": "3. Recommended interventions", "status": "ready", "detail": actions[2]["draft"]["message"]},
                {"icon": "file", "label": "4. Measurement plan", "status": "ready", "detail": actions[3]["draft"]["message"]},
            ],
            "footer": "Draft only \u2014 routing records your approval; nothing is sent or executed.",
        }
        return pkg
    finally:
        conn.close()


def decide_equity_brief(decision, decided_by, inputs=None, note=None, log_path=None):
    return engine.decide(build_equity_brief, decision, decided_by, inputs, note, log_path)


def get_equity_brief_audit(log_path=None):
    return engine.audit(build_equity_brief, log_path)
