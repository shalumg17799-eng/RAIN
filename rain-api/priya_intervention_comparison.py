"""
Live content for Priya's RHTP-Aligned Intervention Options card.

Checked against the static card it replaces:
  - Option A reach ("84% of displaced cohort") -> UNSUPPORTED as written.
    The real, already-verified reach for mobile obstetric outreach is 48
    active pregnancies in a no-broadband ZIP (Priya Q6). 84% appears to be
    a recycled figure from the unrelated prenatal-completion rate, not a
    measured reach for this population.
  - Option B reach ("240 dead-zone patients") -> confirmed: 240 elevated-risk
    patients live in a no-broadband ZIP (priya_live_data.DEAD_ZONE_ELEVATED_SQL,
    the same figure as Priya's KPI tile).
  - Option C reach ("64% of avoidable ED") -> confirmed real (76 of 119,
    the already-verified avoidable-hospitalizations model).
  - Option C funding ("$1.0M avoided") -> UNSUPPORTED. No cost or dollar
    field exists anywhere in the dataset. Dropped, not approximated.
  - Funding program names (Flex Fund, RHOAP) -> these are the real named
    RHTP programs for Nevada and are kept as-is; they describe which
    funding category a real intervention could draw from, not a figure
    computed from rain.db.

Every numeric figure is computed fresh from rain.db on each call.
"""

import os
import pg_compat as sqlite3
from priya_live_data import DEAD_ZONE_ELEVATED_SQL

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def get_intervention_comparison():
    conn = _conn()
    try:
        mobile_reach = conn.execute(
            "SELECT COUNT(*) FROM PregnancyEpisode p JOIN Patient pt ON pt.patient_id = p.patient_id "
            "JOIN ConnectivityRegistry cr ON cr.zip_code = pt.zip_code WHERE cr.broadband_available = 'False'"
        ).fetchone()[0]
        no_broadband_total = conn.execute(
            "SELECT COUNT(*) FROM Patient pt JOIN ConnectivityRegistry cr ON cr.zip_code = pt.zip_code WHERE cr.broadband_available = 'False'"
        ).fetchone()[0]
        dead_zone_elevated = conn.execute(DEAD_ZONE_ELEVATED_SQL).fetchone()[0]

        ed = conn.execute(
            "SELECT SUM(CASE WHEN date>='2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated') THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN date>='2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag='True' AND encounter_type != 'ED_delivery_or_BBA'"
        ).fetchone()
        ed_pct = round(100 * ed[0] / ed[1]) if ed[1] else 0

        options = [
            {"id": "A", "name": "Mobile Obstetric Outreach", "reach": f"{mobile_reach} active pregnancies in a no-broadband ZIP",
             "timeline": "30 days", "funding": "Flex Fund", "priority": "Infrastructure", "recommended": True},
            {"id": "B", "name": "Telehealth Connectivity Bridge",
             "reach": f"{dead_zone_elevated} elevated-risk patients in the dead-zone ZIPs ({no_broadband_total} total in a no-broadband ZIP)",
             "timeline": "60 days", "funding": "RHOAP", "priority": "Value-based", "recommended": True},
            {"id": "C", "name": "Care Continuity Restoration", "reach": f"{ed_pct}% of avoidable ED ({ed[0]} of {ed[1]} visits)",
             "timeline": "90 days", "funding": "No cost figure in the dataset", "priority": "Cost & quality", "recommended": False},
        ]
        return {
            "options": options,
            "note": "Reach figures are computed from rain.db. Option A's and B's reach are corrected from the static card's "
                    "unsupported 84%; Option B's reach is the same elevated-risk dead-zone count as Priya's KPI tile; "
                    "Option C's '$1.0M avoided' is dropped -- "
                    "no cost or dollar field exists anywhere in the dataset. Flex Fund and RHOAP are the real named RHTP "
                    "funding programs, not figures computed from this data.",
        }
    finally:
        conn.close()
