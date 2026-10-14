"""
Live content for Maria's Maternal Risk Stratification card.

Reuses build_maternal_package() (maria_action_package.py) for the cohort,
ranking, and risk factors, so this card and Maria's live action package can
never disagree about who is ranked where or why.

Checked against the static card it replaces:
  - dx breakdown (4 preeclampsia / 3 gestational DM / 2 prior preterm, 9
    total) -> confirmed exact
  - "6 have a missed visit since March 1" -> confirmed exact
  - per-patient "miles" (109-132, varying)  -> WRONG. Every one of the 14
    patients has the same distance_to_delivery_miles (115) -- it is the
    field that defines this cohort. Not reproduced as a varying number.
  - "composite risk score" (94/91/88/85/82/79) -> UNSUPPORTED. No scoring
    model in the dataset produces numbers like these. Replaced with the
    real 0-5 risk-factor count already used to rank Maria's action
    package (same _factors() logic, same ranking).
  - 3 compounding-risk patients with BP sparklines -> PARTIALLY WRONG. 3
    patients do carry both a pregnancy and a chronic condition (2
    hypertension, 1 diabetes), but only the 2 hypertension patients have
    any RPM blood-pressure readings on file -- the diabetes patient has
    no RPM readings of any kind. Shown as 2 real trends plus one patient
    explicitly marked as having no RPM data, not three invented trends.

Every figure is computed fresh from rain.db on each call.
"""

import os
import pg_compat as sqlite3

from maria_action_package import build_maternal_package

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")

DX_LABELS = {"preeclampsia": "Preeclampsia", "gestational diabetes": "Gestational DM", "prior preterm birth": "Prior preterm"}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _downsample(values, n=6):
    if len(values) <= n:
        return values
    step = (len(values) - 1) / (n - 1)
    return [values[round(i * step)] for i in range(n)]


def get_maternal_risk_stratification():
    pkg = build_maternal_package()          # the ranked 14-patient cohort, shared with the action package
    conn = _conn()
    try:
        dx_counts = {}
        rows = []
        bp_series = []
        for p in pkg["patients"]:
            dx = p["dx"]
            label = DX_LABELS.get(dx, dx.title() if dx else None)
            if label:
                dx_counts[label] = dx_counts.get(label, 0) + 1

            compound = None
            readings = conn.execute("SELECT value FROM RPMReading WHERE patient_id = ? AND reading_type = 'BP' ORDER BY timestamp", (p["patient_id"],)).fetchall()
            if p["chronic"]:
                cond = p["chronic"][0]["condition_type"]
                compound = "HTN" if cond == "hypertension" else "T2DM" if cond == "diabetes" else cond
                if readings:
                    bp_series.append({"id": p["patient_id"], "pts": _downsample([float(r[0]) for r in readings])})

            rows.append({
                "id": p["patient_id"], "zip": p["zip"], "dx": label, "miles": p["distance"],
                "score": p["risk_score"], "score_max": p["risk_factors_total"],
                "missed": "missed prenatal visit since the closure" in p["factors"],
                "compound": compound, "has_rpm": bool(readings),
            })

        no_rpm_compounding = [r["id"] for r in rows if r["compound"] and not r["has_rpm"]]
        return {
            "as_of": pkg["as_of"], "total": len(rows), "patients": rows,
            "dx_breakdown": [{"label": k, "count": v} for k, v in sorted(dx_counts.items(), key=lambda kv: -kv[1])],
            "dx_total": sum(dx_counts.values()),
            "missed_total": sum(r["missed"] for r in rows),
            "distance_miles": rows[0]["miles"] if rows else None,
            "bp_series": bp_series,
            "no_rpm_compounding": no_rpm_compounding,
            "note": (f"All {len(rows)} patients are the same {rows[0]['miles']}mi from delivery care -- that distance defines this cohort, "
                    "not a per-patient variable. Risk score is a 0-5 count of real factors (diagnosis, missed visit, no transport, "
                    "limited connectivity, a chronic condition), not a modeled probability."),
        }
    finally:
        conn.close()
