"""
Live content for Sarah's Risk-Tiered Outreach card.

The scoring (1 base point + medication gap>30d + lost provider + transport
barrier, on the same 17-patient CHF/COPD cohort as the Deterioration Board
and the verified "Risk ranked outreach list" rule in business_rules.py) is
identical to what already backs Sarah's Tier 1 action package -- so Tier 1
here is exactly the same 5 patients (PT-00127..131) with the same scores.

Checked against the static card it replaces:
  - Tier 1 count (5)               -> confirmed exact
  - "4 transport barriers" in Tier 1 note -> confirmed exact (4 of the 5
    have an SDOH transportation flag; matches the already-verified rule)
  - Tier 2 / Tier 3 counts (7 / 5)  -> WRONG. The real distribution, scored
    the same way, is 5 / 7 (score=2 -> 5 patients, score=1 -> 7 patients).
    The static card's Tier 2 and Tier 3 counts are swapped relative to
    what this scoring actually produces.
  - ">60% / 30-60% / <30%" probability bands -> UNSUPPORTED. No model in
    the dataset outputs a hospitalization probability; only a 1-4 risk-
    factor count exists. Replaced with the real "N of 4 factors" language.
  - "-45% Tier 1 modeled risk reduction" and "$1.0M annualized avoidable
    cost (208-cohort)" -> UNSUPPORTED. No risk-reduction model and no
    per-patient or per-cohort cost figure exists anywhere in the dataset
    for this group. Replaced with the real, already-verified avoidable-ED
    figures instead (100 -> 119 visits, +19%, 76 tied to a deactivated
    provider).

Every figure is computed fresh from rain.db on each call.
"""

import os
import pg_compat as sqlite3
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")
AS_OF = "2026-05-15"

SCORE_SQL = """
SELECT patient_id, 1 + med_gap + lost_provider + transport_barrier AS score FROM (
  SELECT w.patient_id,
  CASE WHEN EXISTS (SELECT 1 FROM MedicationFill m WHERE m.patient_id = w.patient_id AND julianday(?) - julianday(m.fill_date) > 30) THEN 1 ELSE 0 END AS med_gap,
  CASE WHEN EXISTS (SELECT 1 FROM ChronicConditionEnrollment e WHERE e.patient_id = w.patient_id AND e.assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated')) THEN 1 ELSE 0 END AS lost_provider,
  CASE WHEN EXISTS (SELECT 1 FROM SDOHFlag s WHERE s.patient_id = w.patient_id) THEN 1 ELSE 0 END AS transport_barrier
  FROM (SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN ('CHF','COPD')) w
) ORDER BY score DESC, patient_id
"""

TIER_META = {
    3: {"tier": "Tier 1", "color": "#DC2626", "action": "Same-day pharmacy + NEMT + telehealth < 48h"},   # score 3 or 4
    2: {"tier": "Tier 2", "color": "#D97706", "action": "Telehealth visit this week"},
    1: {"tier": "Tier 3", "color": "#64748B", "action": "Telehealth check-in"},
}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def get_risk_tiered_outreach():
    conn = _conn()
    try:
        scored = conn.execute(SCORE_SQL, (AS_OF,)).fetchall()
        buckets = {3: [], 2: [], 1: []}
        for r in scored:
            key = 3 if r["score"] >= 3 else r["score"]
            buckets[key].append(r["patient_id"])

        tier1_transport = conn.execute(
            "SELECT COUNT(*) FROM SDOHFlag WHERE flag_type = 'transportation' AND patient_id IN "
            f"({','.join('?' * len(buckets[3]))})", buckets[3]
        ).fetchone()[0] if buckets[3] else 0

        tiers = []
        for key in (3, 2, 1):
            ids = buckets[key]
            meta = TIER_META[key]
            scores_in_tier = {r["score"] for r in scored if r["patient_id"] in ids}
            factor_label = f"{min(scores_in_tier)}-{max(scores_in_tier)} of 4 factors" if len(scores_in_tier) > 1 else f"{next(iter(scores_in_tier), key)} of 4 factors"
            note = f"{tier1_transport} with a transportation barrier" if key == 3 else \
                   ("Worsening RPM, medication current" if key == 2 else "Early trend, single risk factor")
            tiers.append({"tier": meta["tier"], "count": len(ids), "patient_ids": ids, "factor_label": factor_label,
                          "note": note, "color": meta["color"], "action": meta["action"]})

        avoidable = conn.execute(
            "SELECT SUM(CASE WHEN date < '2026-03-01' THEN 1 ELSE 0 END) AS b, "
            "SUM(CASE WHEN date >= '2026-03-01' THEN 1 ELSE 0 END) AS a, "
            "SUM(CASE WHEN date >= '2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated') THEN 1 ELSE 0 END) AS t "
            "FROM ClaimEncounter WHERE avoidable_ed_flag = 'True' AND encounter_type != 'ED_delivery_or_BBA'"
        ).fetchone()
        avoidable_before, avoidable_total, avoidable_deactivated = avoidable["b"], avoidable["a"], avoidable["t"]

        return {
            "as_of": AS_OF, "total": len(scored), "tiers": tiers,
            "avoidable_ed": {"before": avoidable_before, "after": avoidable_total, "tied_to_deactivated": avoidable_deactivated,
                             "rise_pct": round(100 * (avoidable_total - avoidable_before) / avoidable_before) if avoidable_before else 0,
                             "pct_tied": round(100 * avoidable_deactivated / avoidable_total) if avoidable_total else 0},
            "note": "No probability model or cost-savings model exists in the dataset for this cohort; this shows risk-factor "
                    "counts and the real avoidable-ED figures instead of the invented probability bands, risk-reduction percentage, and dollar figure.",
        }
    finally:
        conn.close()
