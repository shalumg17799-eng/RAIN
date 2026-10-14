"""
Live content for David's Downstream Impact Map card.

Checked against the static card it replaces (and against the scripted chat
text it was drawn from):
  - "Maternal: 6 high-risk prenatal patients lost attribution" -> WRONG.
    Zero PregnancyEpisode rows have an assigned_provider_id pointing at a
    deactivated provider -- every one was already reassigned (the same
    finding behind the already-verified David Q5 answer). The real figure
    is 0, not 6.
  - "Chronic disease: 41 diabetes + 5 CHF/COPD continuity flags dropped"
    -> UNDERCOUNTED. The real breakdown is CHF 5 (correct), diabetes 42
    (not 41), and hypertension 2 -- entirely missing from the static
    card. Real total: 49, matching the already-verified "Lost provider
    continuity" rule; the static card's 41+5=46 misses 3 patients.
  - "Population health: 64% continuity-loss ED attribution" -> CONFIRMED
    real (76 of 119 avoidable ED visits, the already-verified model).
  - "86% now -> 99% within one ingestion cycle" cohort-completeness bar
    -> UNSUPPORTED. No completeness-percentage field exists on
    DataQualityEvent or anywhere else. Dropped, not approximated.

Every figure is computed fresh from rain.db on each call.
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


def get_downstream_impact():
    conn = _conn()
    try:
        unresolved = conn.execute("SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'").fetchone()[0]

        maternal_affected = conn.execute(
            "SELECT COUNT(*) FROM PregnancyEpisode WHERE assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated')"
        ).fetchone()[0]

        chronic_rows = conn.execute(
            "SELECT condition_type, COUNT(*) FROM ChronicConditionEnrollment "
            "WHERE assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated') GROUP BY condition_type"
        ).fetchall()
        chronic_by_condition = {r[0]: r[1] for r in chronic_rows}
        chronic_total = sum(chronic_by_condition.values())

        ed = conn.execute(
            "SELECT SUM(CASE WHEN date >= '2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated') THEN 1 ELSE 0 END) t, "
            "SUM(CASE WHEN date >= '2026-03-01' THEN 1 ELSE 0 END) a "
            "FROM ClaimEncounter WHERE avoidable_ed_flag = 'True' AND encounter_type != 'ED_delivery_or_BBA'"
        ).fetchone()
        ed_pct = round(100 * ed["t"] / ed["a"]) if ed["a"] else 0

        engines = [
            {"label": "Maternal risk engine", "owner": "Dr. Delgado-Reyes",
             "detail": "0 prenatal patients currently lost attribution -- all pregnancy episodes on a deactivated provider were already reassigned" if maternal_affected == 0
             else f"{maternal_affected} high-risk prenatal patients have lost provider attribution"},
            {"label": "Chronic disease engine", "owner": "Sarah Whitehorse",
             "detail": f"{chronic_by_condition.get('diabetes', 0)} diabetes + {chronic_by_condition.get('CHF', 0)} CHF + "
                       f"{chronic_by_condition.get('hypertension', 0)} hypertension patients have a continuity flag dropped ({chronic_total} total)"},
            {"label": "Population health engine", "owner": "Dr. Nair",
             "detail": f"{ed_pct}% of avoidable ED attribution ({ed['t']} of {ed['a']} visits) depends on this same provider linkage"},
        ]

        return {
            "as_of": AS_OF, "unresolved_refs": unresolved, "engines": engines,
            "maternal_affected": maternal_affected, "chronic_affected": chronic_total, "chronic_by_condition": chronic_by_condition,
            "note": "No completeness-percentage field exists in the dataset, so the static card's '86% now \u2192 99% within one "
                    "ingestion cycle' bar is not reproduced. The maternal risk engine figure is corrected from the scripted 6 to the "
                    "real 0 (every affected pregnancy episode was already reassigned), and the chronic breakdown now includes the "
                    "2 hypertension patients the static card omitted.",
        }
    finally:
        conn.close()
