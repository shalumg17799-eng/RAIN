"""
Maria's priority maternal outreach package.

Built from the real dataset (rain.db) for the 14 third-trimester elevated-risk
patients (the same cohort as the verified "third-trimester within elevated-risk
cohort" rule). It drafts what the script promises:

  1. a ranked patient list, each patient with registry dx, last prenatal visit,
     distance, telehealth eligibility, transport, RPM and evidence
  2. telehealth referral drafts        (patients whose telehealth eligibility is "eligible")
  3. NEMT transport request drafts     (hybrid patients + every active pregnancy with no scheduled transport)
  4. a cross-team handoff              (pregnancy + chronic condition, to the chronic disease team)

Each patient's recommended intervention comes from their telehealth eligibility
label: eligible -> telehealth, hybrid -> telehealth with NEMT fallback,
dead-zone -> in-person coordination. Ranking is an explicit count of risk
factors met (of 5), not a model, so anyone can check it.

Where the data disagrees with itself or with the script, the package says so
instead of hiding it (for example, patients labelled telehealth-eligible whose
ZIP has no broadband on record).

DRAFT-ONLY: routing records a person's approval through action_engine and
never sends anything. Nothing here contacts an external system.
"""

import hashlib
import os
import pg_compat as sqlite3
from datetime import date

import action_engine as engine
from action_engine import ActionInputError

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rain.db")

AS_OF = "2026-05-15"                 # the dataset's "today" (same date the verified rules use)
MISSED_BEFORE = "2026-04-01"         # same cut-off as the verified "missed prenatal visit" rule
PERSONA = "maria"
FACTORS_TOTAL = 5
REFERRAL_PROGRAM = "Project ECHO Nevada"   # named in the spec; it is not in the dataset
CHRONIC_TEAM = "Chronic disease care team"
TYPES = ("telehealth_referral", "nemt_request", "chronic_handoff")

# Same cohort definition as the verified rule "Third-trimester within elevated-risk cohort"
COHORT_WHERE = "trimester = 3 AND distance_to_delivery_miles = 115"

SYSTEM = {"PregnancyEpisode": "Pregnancy Registry", "TelehealthSession": "Telehealth Platform", "ConnectivityRegistry": "Connectivity Registry",
          "TransportRequest": "NEMT Logs", "RPMReading": "RPM Platform", "ClaimEncounter": "Claims & Encounters",
          "ChronicConditionEnrollment": "Care Enrollment", "Provider": "Provider Registry"}

INTERVENTION = {"telehealth": "Telehealth", "hybrid_nemt": "Hybrid: telehealth with NEMT fallback", "in_person": "In-person coordination"}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _days(later, earlier):
    return (date.fromisoformat(str(later)[:10]) - date.fromisoformat(str(earlier)[:10])).days


def _intervention(labels):
    """eligible beats hybrid beats dead-zone (no patient in the cohort has mixed labels today)."""
    if not labels:
        return "in_person"
    return "telehealth" if "eligible" in labels else "hybrid_nemt" if "hybrid" in labels else "in_person"


def _patient(conn, pid):
    ep = conn.execute(
        "SELECT p.patient_id, p.risk_diagnoses, p.assigned_provider_id, p.delivering_facility_id, p.distance_to_delivery_miles, "
        "p.last_prenatal_visit_date, p.expected_delivery_date, f.name AS facility, pt.zip_code, pt.county "
        "FROM PregnancyEpisode p JOIN Patient pt ON pt.patient_id = p.patient_id LEFT JOIN Facility f ON f.facility_id = p.delivering_facility_id "
        "WHERE p.patient_id = ?", (pid,)).fetchone()
    labels = [r[0] for r in conn.execute("SELECT eligibility_status FROM TelehealthSession WHERE patient_id = ?", (pid,))]
    bb = conn.execute("SELECT broadband_available FROM ConnectivityRegistry WHERE zip_code = ?", (ep["zip_code"],)).fetchone()
    tr = conn.execute("SELECT COUNT(*) n, SUM(scheduled = 'True') sch FROM TransportRequest WHERE patient_id = ?", (pid,)).fetchone()
    rpm = conn.execute("SELECT reading_type, COUNT(*) n, MAX(timestamp) last_ts FROM RPMReading WHERE patient_id = ? GROUP BY reading_type", (pid,)).fetchall()
    claims = conn.execute("SELECT COUNT(*) n, MAX(date) last_date FROM ClaimEncounter WHERE patient_id = ?", (pid,)).fetchone()
    enr = [dict(r) for r in conn.execute("SELECT condition_type, assigned_provider_id, care_coordinator_id FROM ChronicConditionEnrollment WHERE patient_id = ? ORDER BY enrollment_id", (pid,))]
    for e in enr:
        pr = conn.execute("SELECT status, deactivation_date, reassigned_to_provider_id FROM Provider WHERE provider_id = ?", (e["assigned_provider_id"],)).fetchone()
        e["provider_status"] = pr["status"] if pr else None
        e["provider_deactivated"] = str(pr["deactivation_date"]) if pr and pr["deactivation_date"] else None
        e["reassigned_to"] = pr["reassigned_to_provider_id"] if pr else None
    return {
        "patient_id": pid, "dx": (ep["risk_diagnoses"] or "").strip(), "provider": ep["assigned_provider_id"],
        "facility_id": ep["delivering_facility_id"], "facility": ep["facility"], "distance": int(ep["distance_to_delivery_miles"]),
        "last_prenatal": str(ep["last_prenatal_visit_date"]), "edd": str(ep["expected_delivery_date"]), "zip": ep["zip_code"], "county": ep["county"],
        "labels": labels, "intervention": _intervention(labels), "broadband": None if bb is None else bool(bb["broadband_available"]),
        "transport": {"total": tr["n"], "scheduled": int(tr["sch"] or 0)},
        "rpm": [{"type": r["reading_type"], "readings": r["n"], "last": str(r["last_ts"])[:10]} for r in rpm],
        "claims": {"count": claims["n"], "last": str(claims["last_date"]) if claims["last_date"] else None}, "chronic": enr,
    }


def _factors(p):
    f = []
    if p["dx"]:
        f.append("registry high-risk diagnosis")
    if p["last_prenatal"] < MISSED_BEFORE:
        f.append("missed prenatal visit since the closure")
    if p["transport"]["scheduled"] == 0:
        f.append("no scheduled transport")
    if p["intervention"] != "telehealth":
        f.append("limited connectivity (hybrid or dead-zone)")
    if p["chronic"]:
        f.append("pregnancy and chronic condition compound")
    return f


def _summary_text(p):
    parts = [f"registry dx {p['dx'] or 'none on record'}",
             f"last prenatal visit {p['last_prenatal']} ({_days(AS_OF, p['last_prenatal'])} days ago{', missed since the closure' if p['last_prenatal'] < MISSED_BEFORE else ''})",
             f"{p['distance']} miles to {p['facility']}", f"telehealth eligibility: {', '.join(dict.fromkeys(p['labels'])) or 'no session on file'}",
             "transport: " + ("scheduled" if p["transport"]["scheduled"] else "none scheduled")]
    if p["rpm"]:
        parts.append("last " + ", ".join(f"{r['type']} reading {r['last']}" for r in p["rpm"]))
    if p["chronic"]:
        c = p["chronic"][0]
        parts.append(f"also enrolled: {c['condition_type']} (provider {c['assigned_provider_id']} {c['provider_status'] or 'unknown'})")
    return "Third trimester \u2014 " + "; ".join(parts) + "."


def _evidence(p):
    ev = [{"system": SYSTEM["PregnancyEpisode"], "table": "PregnancyEpisode", "as_of": p["last_prenatal"],
           "fact": f"registry dx {p['dx'] or 'none on record'}; expected delivery {p['edd']}; last prenatal visit {p['last_prenatal']} ({_days(AS_OF, p['last_prenatal'])} days ago)"},
          {"system": "Pregnancy Registry \u2014 distance", "table": "PregnancyEpisode.distance", "as_of": AS_OF,
           "fact": f"{p['distance']} miles to {p['facility']}"},
          {"system": SYSTEM["TelehealthSession"], "table": "TelehealthSession", "as_of": AS_OF,
           "fact": f"eligibility {', '.join(dict.fromkeys(p['labels'])) or 'no session on file'} \u2192 {INTERVENTION[p['intervention']].lower()}"}]
    if p["broadband"] is not None:
        ev.append({"system": SYSTEM["ConnectivityRegistry"], "table": "ConnectivityRegistry", "as_of": AS_OF,
                   "fact": f"ZIP {p['zip']}: {'broadband available' if p['broadband'] else 'no broadband on record'}"})
    tr = p["transport"]
    ev.append({"system": SYSTEM["TransportRequest"], "table": "TransportRequest", "as_of": AS_OF,
               "fact": "no transport request on file" if not tr["total"] else f"{tr['total']} on file ({tr['scheduled']} scheduled)"})
    ev.append({"system": SYSTEM["RPMReading"], "table": "RPMReading", "as_of": AS_OF,
               "fact": ("; ".join(f"{r['type']}: {r['readings']} readings, last {r['last']}" for r in p["rpm"])) if p["rpm"] else "no RPM readings on file"})
    ev.append({"system": SYSTEM["ClaimEncounter"], "table": "ClaimEncounter", "as_of": AS_OF,
               "fact": "no claims on file" if not p["claims"]["count"] else f"{p['claims']['count']} claim(s), last {p['claims']['last']}"})
    for c in p["chronic"]:
        ev.append({"system": SYSTEM["ChronicConditionEnrollment"], "table": "ChronicConditionEnrollment", "as_of": AS_OF,
                   "fact": f"{c['condition_type']}; coordinator {c['care_coordinator_id']}; provider {c['assigned_provider_id']} {c['provider_status'] or 'unknown'}"
                           + (f" {c['provider_deactivated']}" if c["provider_deactivated"] else "")})
    return ev


def build_maternal_package(inputs=None, log_path=None):
    if inputs:
        raise ActionInputError("This package takes no inputs: every action is fully drafted from the data.")
    conn = _conn()
    try:
        cohort_ids = [r[0] for r in conn.execute(f"SELECT patient_id FROM PregnancyEpisode WHERE {COHORT_WHERE} ORDER BY patient_id")]
        patients = [_patient(conn, pid) for pid in cohort_ids]
        for p in patients:
            p["factors"] = _factors(p)
            p["risk_score"] = len(p["factors"])
        patients.sort(key=lambda p: (-p["risk_score"], p["edd"], p["patient_id"]))       # most factors first; soonest due date breaks ties
        for i, p in enumerate(patients, 1):
            p["rank"], p["risk_factors_total"] = i, FACTORS_TOTAL
            p["care_summary"], p["evidence"] = _summary_text(p), _evidence(p)
            p["recommended_intervention"] = INTERVENTION[p["intervention"]]

        # every active pregnancy with no scheduled transport (all trimesters), plus the cohort's hybrid patients
        no_transport = {r[0] for r in conn.execute("SELECT patient_id FROM PregnancyEpisode WHERE patient_id NOT IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'True')")}
        by_id = {p["patient_id"]: p for p in patients}
        hybrid = {p["patient_id"] for p in patients if p["intervention"] == "hybrid_nemt"}
        nemt_ids = sorted(no_transport | hybrid)
        package_id = "MATERNAL-%s-%s" % (AS_OF.replace("-", ""), hashlib.md5(",".join(cohort_ids + nemt_ids).encode()).hexdigest()[:6].upper())

        actions, conflicts = [], 0
        for p in patients:                                                                    # 2. telehealth referrals
            if p["intervention"] != "telehealth":
                continue
            flags = []
            if p["broadband"] is False:
                conflicts += 1
                flags.append({"code": "connectivity_conflict", "message": f"Labelled telehealth-eligible, but ZIP {p['zip']} has no broadband on record. Confirm connectivity before scheduling."})
            actions.append({"action_id": f"{package_id}:{p['patient_id']}:telehealth_referral", "type": "telehealth_referral", "patient_id": p["patient_id"],
                            "status": "ready", "needs": [], "flags": flags,
                            "draft": {"to": REFERRAL_PROGRAM, "message": (f"Prenatal telehealth referral for {p['patient_id']}: third trimester, registry dx {p['dx'] or 'none on record'}, "
                                                                          f"expected delivery {p['edd']}, {p['distance']} miles from {p['facility']}."),
                                      "connectivity": {"zip": p["zip"], "broadband": p["broadband"]},
                                      "note": "The dataset holds no program slots; the receiving program confirms."}})

        for pid in nemt_ids:                                                                  # 3. NEMT requests
            row = by_id.get(pid) or _patient(conn, pid)
            reasons = (["hybrid connectivity \u2014 in-person fallback"] if pid in hybrid else []) + (["no scheduled transport"] if pid in no_transport else [])
            actions.append({"action_id": f"{package_id}:{pid}:nemt_request", "type": "nemt_request", "patient_id": pid, "status": "ready", "needs": [], "flags": [],
                            "draft": {"pickup_zip": row["zip"], "county": row["county"], "destination_facility": row["facility"], "reason": " + ".join(reasons),
                                      "in_ranked_list": pid in by_id, "for_visit": "next prenatal visit (no appointment dates in the dataset)"}})

        for p in patients:                                                                    # 4. cross-team handoff
            if not p["chronic"]:
                continue
            c = p["chronic"][0]
            actions.append({"action_id": f"{package_id}:{p['patient_id']}:chronic_handoff", "type": "chronic_handoff", "patient_id": p["patient_id"],
                            "status": "ready", "needs": [], "flags": [],
                            "draft": {"to": CHRONIC_TEAM, "coordinator": c["care_coordinator_id"], "conditions": [x["condition_type"] for x in p["chronic"]],
                                      "message": (f"{p['patient_id']} carries a third-trimester pregnancy (registry dx {p['dx'] or 'none on record'}, expected delivery {p['edd']}) "
                                                  f"and {', '.join(x['condition_type'] for x in p['chronic'])}. "
                                                  + (f"Provider {c['assigned_provider_id']} was deactivated {c['provider_deactivated']} (recorded reassignment {c['reassigned_to']})."
                                                     if c["provider_deactivated"] else f"Provider {c['assigned_provider_id']} is {c['provider_status'] or 'unknown'}."))}})

        pkg = {"package_id": package_id, "persona": PERSONA, "kind": "maternal_outreach", "as_of": AS_OF, "patients": patients, "actions": actions, "notes": []}
        pkg["summary"] = {"patients": len(patients), "interventions": {k: sum(p["intervention"] == k for p in patients) for k in INTERVENTION},
                          "connectivity_conflicts": conflicts, "nemt": {"hybrid": len(hybrid), "no_transport": len(no_transport), "total": len(nemt_ids)}}
        engine.finalize(pkg, log_path, TYPES)

        s, iv = pkg["summary"], pkg["summary"]["interventions"]
        lost = sum(1 for a in actions if a["type"] == "chronic_handoff" and by_id[a["patient_id"]]["chronic"][0]["provider_status"] == "deactivated")
        ct = s["chronic_handoff"]["total"]
        coord = next((by_id[a["patient_id"]]["chronic"][0]["care_coordinator_id"] for a in actions if a["type"] == "chronic_handoff"), None)
        st = lambda t: "routed" if s[t]["total"] and s[t]["routed"] == s[t]["total"] else f"{s[t]['ready']} of {s[t]['total']} ready"
        pkg["display"] = {
            "title": "Priority Maternal Outreach Package", "subject": f"{len(patients)} third-trimester patients",
            "rows": [
                {"icon": "list", "label": "Ranked patient list", "status": f"{len(patients)} patients",
                 "detail": f"{len(patients)} third-trimester patients ranked by risk factors met (of {FACTORS_TOTAL}) \u2014 registry dx, last prenatal visit, distance, telehealth eligibility, transport"},
                {"icon": "video", "label": f"Telehealth referrals ({s['telehealth_referral']['total']})", "status": st("telehealth_referral"),
                 "detail": f"Drafts to {REFERRAL_PROGRAM} for the telehealth-eligible patients" + (f" \u2014 {conflicts} need a broadband check" if conflicts else "")},
                {"icon": "bus", "label": f"NEMT transport requests ({s['nemt_request']['total']})", "status": st("nemt_request"),
                 "detail": f"{len(hybrid)} hybrid + {len(no_transport)} with no scheduled transport ({len(no_transport & set(by_id))} of those {len(no_transport)} are among the {len(patients)} ranked patients)"},
                {"icon": "users", "label": f"Cross-team handoff ({ct})", "status": st("chronic_handoff"),
                 "detail": f"{ct} compounding-risk cases to the {CHRONIC_TEAM.lower()}" + (f" ({coord})" if coord else "") + (f"; {lost} on a deactivated provider" if lost else "")}],
            "tiles": [{"n": iv["telehealth"], "label": "Telehealth"}, {"n": iv["hybrid_nemt"], "label": "Hybrid + NEMT"}, {"n": iv["in_person"], "label": "In-person"}],
            "footer": "Draft only \u2014 routing records your approval; nothing is sent to any program, dispatcher, clinic or care team. Every figure links to its source record."}

        with_claims = sum(1 for p in patients if p["claims"]["count"])
        with_rpm = sum(1 for p in patients if p["rpm"])
        if conflicts:
            pkg["notes"].append(f"{conflicts} of the {iv['telehealth']} telehealth-eligible patients live in a ZIP with no broadband on record: the eligibility label and the connectivity registry disagree.")
        pkg["notes"].append(f"Claims are on file for {with_claims} of the {len(patients)} patients and RPM readings for {with_rpm}, so the clinical history shown is mostly the pregnancy registry's prenatal visit dates.")
        inside = hybrid | (no_transport & set(by_id))
        pkg["notes"].append(f"{len(no_transport)} of all {conn.execute('SELECT COUNT(*) FROM PregnancyEpisode').fetchone()[0]} active pregnancies have no scheduled transport, and only "
                            f"{len(no_transport & set(by_id))} of them are among the {len(patients)} ranked patients: {len(nemt_ids) - len(inside)} of the {len(nemt_ids)} NEMT drafts are for patients outside the ranked list.")
        pkg["notes"].append(f"{REFERRAL_PROGRAM} is named in the spec; it is not in the dataset. The dataset also holds no appointment dates or program slots, so the receiving side confirms.")
        return pkg
    finally:
        conn.close()


def decide_maternal(decision, decided_by, inputs=None, note=None, log_path=None):
    return engine.decide(build_maternal_package, decision, decided_by, inputs, note, log_path)


def get_maternal_audit(log_path=None):
    return engine.audit(build_maternal_package, log_path)
