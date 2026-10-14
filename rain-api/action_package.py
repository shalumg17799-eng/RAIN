"""
Tier 1 action package -- the transactional half of RAIN.

For Sarah's five highest-risk patients this assembles the actions a care
coordinator would review: a care summary with its evidence chain, a pharmacy
outreach, an NEMT transport request, a visit + re-panel request, and a
community-health-worker home visit.

Everything is built from the Postgres dataset. The Tier 1 patients come
from the SAME query as Sarah's "risk-ranked outreach list" rule in
business_rules.py, so this package and that answer can never disagree.

What this module does NOT do: contact anyone. There is no code path here that
reaches a pharmacy, dispatcher, clinic or community health worker. "Route"
records a person's approval (who, when, exactly what) in an audit log and marks
those actions as routed -- delivery is always "simulated". Wiring real
delivery would be a separate, deliberate change.

Where the dataset cannot supply something an action needs, the action says so
("needs input") instead of inventing a value:
  - pharmacy of record   (fill records carry no pharmacy)
  - the silent patient   (the data-quality event has a count of 1, no patient id)
  - a fitting re-panel   (when the recorded reassignment target's specialty does
                          not fit the patient's condition)
The coordinator supplies these through `inputs`; every input is validated
against the data before an action can become routable.
"""

import hashlib
import json
import re
import threading
from datetime import date, datetime, timedelta, timezone

import pg_compat
from action_engine import log_conn, log_scope

AS_OF = "2026-05-15"          # the dataset's "today" (same date the verified rules use)
VISIT_WINDOW_DAYS = 2         # "visit within 48 hours"
SILENT_DAYS = 24              # "no contact in 24 days"
DELIVERY = "simulated"        # nothing in this module contacts an external system
PERSONA = "sarah"
TIER1_RULE_TERM = "Risk ranked outreach list chronic patients"

# Table -> the source-system name a coordinator recognizes
SYSTEM = {
    "RPMReading": "RPM Platform",
    "MedicationFill": "Pharmacy Claims",
    "ClaimEncounter": "Claims & Encounters",
    "SDOHFlag": "SDOH Data",
    "Provider": "Provider Registry",
    "ConnectivityRegistry": "Connectivity Registry",
    "TransportRequest": "NEMT Logs",
    "TelehealthSession": "Telehealth Platform",
}

# Which specialties can take over a patient with this condition
_FIT = {"CHF": ("cardio", "family", "internal"), "COPD": ("pulmon", "family", "internal")}
_DEFAULT_FIT = ("family", "internal")

_LOCK = threading.Lock()


class ActionInputError(ValueError):
    """A caller-supplied value is missing or invalid (the API returns 400)."""


# ---------------------------------------------------------------- data access

def _conn():
    c = pg_compat.connect()
    c.row_factory = pg_compat.Row
    return c


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "t")


def _days(later, earlier):
    return (date.fromisoformat(str(later)[:10]) - date.fromisoformat(str(earlier)[:10])).days


def _fits(condition, specialty):
    s = (specialty or "").lower()
    return any(k in s for k in _FIT.get(condition, _DEFAULT_FIT))


def _provider(conn, provider_id):
    row = conn.execute(
        "SELECT p.provider_id, p.name, p.specialty, p.status, p.deactivation_date, p.reassigned_to_provider_id, "
        "p.facility_id, f.name AS facility_name, f.county AS facility_county "
        "FROM Provider p LEFT JOIN Facility f ON f.facility_id = p.facility_id WHERE p.provider_id = ?",
        (provider_id,)).fetchone()
    return dict(row) if row else None


def _fitting_active_providers(conn, condition):
    rows = conn.execute(
        "SELECT p.provider_id, p.specialty, f.name AS facility_name, f.county AS facility_county "
        "FROM Provider p LEFT JOIN Facility f ON f.facility_id = p.facility_id "
        "WHERE p.status = 'active' ORDER BY p.provider_id").fetchall()
    return [dict(r) for r in rows if _fits(condition, r["specialty"])]


def _tier1_rows(conn):
    """The Tier 1 patients: exactly the rows Sarah's risk-ranked outreach rule returns."""
    from business_rules import BREAKDOWN_RULES
    rule = next(r for r in BREAKDOWN_RULES if r["term"] == TIER1_RULE_TERM)
    return [(r[0], int(r[1])) for r in conn.execute(rule["group_by_sql"]).fetchall()]


def _patient_facts(conn, pid):
    """Everything the summary and actions need for one patient, straight from the tables."""
    weights = [(r["timestamp"][:10], float(r["value"])) for r in conn.execute(
        "SELECT value, timestamp FROM RPMReading WHERE patient_id = ? AND reading_type = 'weight' ORDER BY timestamp", (pid,))]
    rpm_all = conn.execute(
        "SELECT COUNT(*) n, SUM(transmission_status = 'received') rec, MAX(timestamp) last_ts FROM RPMReading WHERE patient_id = ?", (pid,)).fetchone()
    fill = conn.execute(
        "SELECT fill_date, medication_type, days_supply FROM MedicationFill WHERE patient_id = ? ORDER BY fill_date DESC LIMIT 1", (pid,)).fetchone()
    claim = conn.execute(
        "SELECT date, encounter_type FROM ClaimEncounter WHERE patient_id = ? ORDER BY date DESC LIMIT 1", (pid,)).fetchone()
    sdoh = [dict(r) for r in conn.execute("SELECT flag_type, zip_code FROM SDOHFlag WHERE patient_id = ?", (pid,))]
    enr = conn.execute(
        "SELECT condition_type, assigned_provider_id, care_coordinator_id FROM ChronicConditionEnrollment WHERE patient_id = ? ORDER BY enrollment_id LIMIT 1", (pid,)).fetchone()
    pat = conn.execute("SELECT zip_code, county, connectivity_status FROM Patient WHERE patient_id = ?", (pid,)).fetchone()
    bb = conn.execute("SELECT broadband_available FROM ConnectivityRegistry WHERE zip_code = ?", (pat["zip_code"],)).fetchone() if pat else None
    tr = conn.execute("SELECT COUNT(*) n, SUM(scheduled = 'True') sch FROM TransportRequest WHERE patient_id = ?", (pid,)).fetchone()
    th = conn.execute("SELECT COUNT(*) n FROM TelehealthSession WHERE patient_id = ?", (pid,)).fetchone()

    facts = {"condition": enr["condition_type"] if enr else None,
             "coordinator": enr["care_coordinator_id"] if enr else None,
             "assigned_provider_id": enr["assigned_provider_id"] if enr else None,
             "zip": pat["zip_code"] if pat else None, "county": pat["county"] if pat else None,
             "broadband": None if bb is None else _as_bool(bb["broadband_available"]),
             "sdoh": sdoh, "transport_barrier": any(s["flag_type"] == "transportation" for s in sdoh),
             "transport_requests": {"total": tr["n"], "scheduled": int(tr["sch"] or 0)},
             "telehealth_sessions": th["n"]}

    if weights:
        (t0, w0), (t1, w1) = weights[0], weights[-1]
        facts["rpm"] = {"first": w0, "last": w1, "delta": round(w1 - w0, 1), "from": t0, "to": t1,
                        "span_days": _days(t1, t0), "readings": rpm_all["n"], "received": int(rpm_all["rec"] or 0),
                        "last_reading": rpm_all["last_ts"][:10], "days_since_reading": _days(AS_OF, rpm_all["last_ts"])}
    else:
        facts["rpm"] = None
    if fill:
        supply = int(fill["days_supply"])
        end = (date.fromisoformat(fill["fill_date"]) + timedelta(days=supply)).isoformat()
        facts["medication"] = {"type": fill["medication_type"], "last_fill": fill["fill_date"], "days_supply": supply,
                               "supply_ended": end, "days_since_fill": _days(AS_OF, fill["fill_date"]),
                               "days_past_supply": max(0, _days(AS_OF, end))}
    else:
        facts["medication"] = None
    facts["last_contact"] = ({"date": claim["date"], "type": claim["encounter_type"].replace("_", " "),
                              "days_ago": _days(AS_OF, claim["date"])} if claim else None)

    # days since ANY recorded contact (RPM transmission, claim, pharmacy fill)
    gaps = [g for g in (facts["rpm"] and facts["rpm"]["days_since_reading"],
                        facts["last_contact"] and facts["last_contact"]["days_ago"],
                        facts["medication"] and facts["medication"]["days_since_fill"]) if g is not None]
    facts["days_since_any_contact"] = min(gaps) if gaps else None
    return facts


# ------------------------------------------------------------------ inputs

def _validate_inputs(conn, inputs, patients):
    """Normalise and validate coordinator input against the data. Raises ActionInputError."""
    out = {"pharmacy_of_record": {}, "repanel_to": {}, "chw_patient_id": None}
    if not inputs:
        return out
    if not isinstance(inputs, dict):
        raise ActionInputError("inputs must be an object")
    unknown = set(inputs) - set(out)
    if unknown:
        raise ActionInputError(f"unknown input(s): {', '.join(sorted(unknown))}")
    pids = {p["patient_id"] for p in patients}

    for pid, name in (inputs.get("pharmacy_of_record") or {}).items():
        if pid not in pids:
            raise ActionInputError(f"{pid} is not in this package")
        name = (name or "").strip()
        if not name:
            continue                      # blank = not supplied
        if len(name) > 100 or not name.isprintable():
            raise ActionInputError(f"pharmacy name for {pid} must be 1-100 printable characters")
        out["pharmacy_of_record"][pid] = name

    for pid, prov in (inputs.get("repanel_to") or {}).items():
        if pid not in pids:
            raise ActionInputError(f"{pid} is not in this package")
        prov = (prov or "").strip()
        if not prov:
            continue
        cond = next(p["condition"] for p in patients if p["patient_id"] == pid)
        rec = _provider(conn, prov)
        if not rec or rec["status"] != "active":
            raise ActionInputError(f"{prov} is not an active provider")
        if not _fits(cond, rec["specialty"]):
            options = ", ".join(f"{p['provider_id']} ({p['specialty']})" for p in _fitting_active_providers(conn, cond))
            raise ActionInputError(f"{prov} ({rec['specialty']}) is not a fitting choice for a {cond} patient; fitting active providers: {options}")
        out["repanel_to"][pid] = prov

    chw = (inputs.get("chw_patient_id") or "").strip()
    if chw:
        if not re.fullmatch(r"PT-\d{5}", chw) or not conn.execute("SELECT 1 FROM Patient WHERE patient_id = ?", (chw,)).fetchone():
            raise ActionInputError(f"{chw} is not a patient in the dataset")
        out["chw_patient_id"] = chw
    return out


# ---------------------------------------------------------------- the package

def _care_summary(p):
    f = p["facts"]
    parts = []
    if f["rpm"]:
        r = f["rpm"]
        parts.append(f"weight {r['first']:.1f} \u2192 {r['last']:.1f} lb over {r['span_days']} days ({r['delta']:+.1f})")
    if f["medication"]:
        m = f["medication"]
        parts.append(f"last {m['type']} medication fill {m['last_fill']} ({m['days_supply']}-day supply), {m['days_since_fill']} days ago")
    if f["last_contact"]:
        c = f["last_contact"]
        parts.append(f"last clinical contact: {c['type']} claim {c['date']}, {c['days_ago']} days ago")
    barriers = [x["flag_type"] for x in f["sdoh"]]
    parts.append("SDOH barrier: " + (", ".join(barriers) if barriers else "none on file"))
    prov = p["provider"]
    if prov:
        a, t = prov["assigned"], prov["recorded_target"]
        line = f"provider {a['provider_id']} {a['status']}" + (f" {a['deactivation_date']}" if a["deactivation_date"] else "")
        parts.append(line + (f", recorded reassignment {t['provider_id']} ({t['specialty']})" if t else ""))
    return f"{f['condition'] or 'Chronic condition'} \u2014 " + "; ".join(parts) + "."


def _evidence(p):
    f, ev = p["facts"], []
    if f["rpm"]:
        r = f["rpm"]
        ev.append({"system": SYSTEM["RPMReading"], "table": "RPMReading", "as_of": r["to"],
                   "fact": f"weight {r['first']:.1f} \u2192 {r['last']:.1f} lb, {r['from']} to {r['to']} ({r['readings']} readings, {r['received']} received)"})
    if f["medication"]:
        m = f["medication"]
        ev.append({"system": SYSTEM["MedicationFill"], "table": "MedicationFill", "as_of": m["last_fill"],
                   "fact": f"last fill {m['last_fill']}, {m['days_supply']}-day supply ended {m['supply_ended']}; {m['days_since_fill']} days since fill"})
    if f["last_contact"]:
        c = f["last_contact"]
        ev.append({"system": SYSTEM["ClaimEncounter"], "table": "ClaimEncounter", "as_of": c["date"],
                   "fact": f"last encounter: {c['type']} on {c['date']} ({c['days_ago']} days ago)"})
    ev.append({"system": SYSTEM["SDOHFlag"], "table": "SDOHFlag", "as_of": AS_OF,
               "fact": ("transportation barrier (ZIP %s)" % f["sdoh"][0]["zip_code"]) if f["transport_barrier"] else "no transportation barrier on file"})
    prov = p["provider"]
    if prov:
        a, t = prov["assigned"], prov["recorded_target"]
        tgt = f"; recorded reassignment {t['provider_id']} ({t['specialty']}, {t['facility_name']})" if t else ""
        ev.append({"system": SYSTEM["Provider"], "table": "Provider", "as_of": a["deactivation_date"] or AS_OF,
                   "fact": f"{a['provider_id']} {a['status']} {a['deactivation_date'] or ''}{tgt}".replace("  ", " ")})
    if f["broadband"] is not None:
        ev.append({"system": SYSTEM["ConnectivityRegistry"], "table": "ConnectivityRegistry", "as_of": AS_OF,
                   "fact": f"ZIP {f['zip']}: {'broadband available' if f['broadband'] else 'no broadband'}"})
    tr = f["transport_requests"]
    ev.append({"system": SYSTEM["TransportRequest"], "table": "TransportRequest", "as_of": AS_OF,
               "fact": "no transport request on file" if not tr["total"] else f"{tr['total']} on file ({tr['scheduled']} scheduled)"})
    ev.append({"system": SYSTEM["TelehealthSession"], "table": "TelehealthSession", "as_of": AS_OF,
               "fact": "no telehealth session on file" if not f["telehealth_sessions"] else f"{f['telehealth_sessions']} session(s) on file"})
    return ev


def _routed_snapshots(package_id, log_path=None):
    scope = log_scope(log_path)
    with _LOCK:
        lc = log_conn()
        try:
            rows = lc.execute(
                "SELECT action_id, routed_at, routed_by, draft_json FROM routed_actions WHERE package_id = ? AND scope = ?",
                (package_id, scope),
            ).fetchall()
            last = lc.execute(
                "SELECT decision, decided_by, decided_at FROM decisions WHERE package_id = ? AND scope = ? ORDER BY id DESC LIMIT 1",
                (package_id, scope),
            ).fetchone()
        finally:
            lc.close()
    return ({r[0]: {"routed_at": r[1], "routed_by": r[2], "draft": json.loads(r[3])} for r in rows},
            {"decision": last[0], "decided_by": last[1], "decided_at": last[2]} if last else None)


def build_tier1_package(inputs=None, log_path=None):
    conn = _conn()
    try:
        tier = _tier1_rows(conn)
        package_id = "TIER1-%s-%s" % (AS_OF.replace("-", ""), hashlib.md5(",".join(pid for pid, _ in tier).encode()).hexdigest()[:6].upper())

        patients = []
        for pid, score in tier:
            facts = _patient_facts(conn, pid)
            assigned = _provider(conn, facts["assigned_provider_id"]) if facts["assigned_provider_id"] else None
            target = _provider(conn, assigned["reassigned_to_provider_id"]) if assigned and assigned["reassigned_to_provider_id"] else None
            patients.append({"patient_id": pid, "condition": facts["condition"], "risk_score": score, "risk_factors_total": 4,
                             "facts": facts, "provider": {"assigned": assigned, "recorded_target": target} if assigned else None})
        ov = _validate_inputs(conn, inputs, patients)

        actions, notes = [], []
        for p in patients:
            pid, f, cond = p["patient_id"], p["facts"], p["condition"]
            p["care_summary"] = _care_summary(p)
            p["evidence"] = _evidence(p)

            # which provider will take the patient: coordinator's choice, else the recorded reassignment
            recorded = p["provider"]["recorded_target"] if p["provider"] else None
            chosen = _provider(conn, ov["repanel_to"][pid]) if pid in ov["repanel_to"] else recorded
            fits = bool(chosen) and _fits(cond, chosen["specialty"])
            p["repanel"] = {"from": p["provider"]["assigned"]["provider_id"] if p["provider"] else None,
                            "to": chosen["provider_id"] if chosen else None,
                            "to_specialty": chosen["specialty"] if chosen else None,
                            "to_facility": chosen["facility_name"] if chosen else None,
                            "to_county": chosen["facility_county"] if chosen else None,
                            "source": "coordinator" if pid in ov["repanel_to"] else "Provider.reassigned_to_provider_id",
                            "fits_condition": fits}
            need_repanel = [] if fits else [{
                "field": "repanel_to", "label": "Confirm a fitting provider",
                "why": (f"Recorded target {recorded['provider_id']} is {recorded['specialty']}; the patient has {cond}." if recorded and not fits
                        else "No reassignment target is recorded."),
                "options": [{"provider_id": o["provider_id"], "label": f"{o['provider_id']} \u2014 {o['specialty']}, {o['facility_name']}"}
                            for o in _fitting_active_providers(conn, cond)]}]

            in_person = not f["broadband"]          # unknown connectivity is treated as not connected
            modality = "in_person_via_nemt" if in_person else "telehealth"
            by = (date.fromisoformat(AS_OF) + timedelta(days=VISIT_WINDOW_DAYS)).isoformat()

            # 1. pharmacy outreach -- the dataset has no pharmacy of record
            med = f["medication"]
            pharm = ov["pharmacy_of_record"].get(pid)
            actions.append({
                "action_id": f"{package_id}:{pid}:pharmacy_outreach", "type": "pharmacy_outreach", "patient_id": pid,
                "status": "ready" if pharm else "needs_input",
                "needs": [] if pharm else [{"field": "pharmacy_of_record", "label": "Pharmacy of record",
                                            "why": "Not in the dataset \u2014 fill records carry no pharmacy."}],
                "draft": {"to": pharm, "medication_type": med and med["type"],
                          "message": (f"Patient {pid} has not refilled their {med['type']} {cond} medication since {med['last_fill']} "
                                      f"({med['days_supply']}-day supply, {med['days_since_fill']} days ago). Please contact the patient to arrange a refill.") if med else None}})

            # 2. NEMT -- only for a transportation barrier; destination follows the chosen provider
            if f["transport_barrier"]:
                actions.append({
                    "action_id": f"{package_id}:{pid}:nemt_request", "type": "nemt_request", "patient_id": pid,
                    "status": "ready" if fits else "needs_input", "needs": need_repanel,
                    "draft": {"pickup_zip": f["zip"], "county": f["county"],
                              "destination_facility": chosen["facility_name"] if fits else None,
                              "for_visit_by": by, "reason": "in-person visit (no broadband at home)" if in_person else "visit support"}})

            # 3. visit + re-panel -- telehealth only where the patient can actually connect
            actions.append({
                "action_id": f"{package_id}:{pid}:visit_and_repanel", "type": "visit_and_repanel", "patient_id": pid,
                "status": "ready" if fits else "needs_input", "needs": need_repanel,
                "draft": {"modality": modality, "requested_by": by, "repanel": p["repanel"],
                          "connectivity": {"zip": f["zip"], "broadband": f["broadband"]},
                          "note": "The dataset holds no provider schedules; the receiving clinic confirms the slot."}})

        # 4. CHW home visit -- the silent patient is not identifiable from the data
        chw_pid = ov["chw_patient_id"]
        chw = {"action_id": f"{package_id}:chw_home_visit", "type": "chw_home_visit", "patient_id": chw_pid,
               "status": "ready" if chw_pid else "needs_input", "flags": [],
               "needs": [] if chw_pid else [{"field": "chw_patient_id", "label": "Patient to visit",
                                             "why": "The data-quality event reports 1 patient with no contact in 24 days but carries no patient id."}],
               "draft": {"patient_id": chw_pid, "task": "Home visit to re-establish contact and assess in person.",
                         "reason": f"no recorded contact of any kind in {SILENT_DAYS} days"}}
        if chw_pid:
            cf = _patient_facts(conn, chw_pid)
            chw["draft"]["evidence"] = {"days_since_any_contact": cf["days_since_any_contact"], "rpm": cf["rpm"], "last_contact": cf["last_contact"], "medication": cf["medication"]}
            if cf["days_since_any_contact"] is not None and cf["days_since_any_contact"] < SILENT_DAYS:
                chw["flags"].append({"code": "not_silent", "message": f"{chw_pid} has a recorded contact {cf['days_since_any_contact']} days ago \u2014 fewer than {SILENT_DAYS}. Verify before dispatching."})
        actions.append(chw)

        # ---- package-level observations, computed from the data above
        n = len(patients)
        dead = [p["patient_id"] for p in patients if p["facts"]["broadband"] is False]
        if dead:
            conn_ok = [p["patient_id"] for p in patients if p["facts"]["broadband"] is not False]
            notes.append(f"{len(dead)} of {n} patients live in a ZIP with no broadband, so their visits are drafted as in-person visits linked to an NEMT trip; "
                         f"telehealth is drafted for {', '.join(conn_ok) if conn_ok else 'none'}.")
        bad = [p for p in patients if not p["repanel"]["fits_condition"]]
        if bad:
            t = bad[0]["provider"]["recorded_target"]
            notes.append(f"The recorded re-panel target {t['provider_id']} is {t['specialty']}, which does not fit {bad[0]['condition']}: "
                         f"{len(bad)} patient(s) need a provider choice before their visit and transport can be routed.")
        far = [p for p in patients if p["repanel"]["to_county"] and p["repanel"]["to_county"] != p["facts"]["county"]]
        if far:
            notes.append(f"{len(far)} patient(s) would be seen outside their own county; the dataset has no travel distances, so 'nearest provider' cannot be computed.")
        notes.append("The dataset has no pharmacy records, provider schedules or care-plan templates; those inputs are marked rather than invented.")
        if not chw_pid:
            gap = conn.execute(
                "SELECT MAX(?::date - last_ts) FROM "
                "(SELECT MAX(timestamp)::date AS last_ts FROM RPMReading "
                "WHERE condition_type IN ('CHF','COPD') GROUP BY patient_id) s",
                (AS_OF,),
            ).fetchone()[0]
            if gap is not None and gap < SILENT_DAYS:
                recent = f"dated {AS_OF}" if int(gap) == 0 else f"within the last {int(gap)} day(s)"
                notes.append(f"No CHF/COPD patient matches the silent-patient description: every one has an RPM reading {recent}. "
                             "The CHW visit stays unassigned until a patient is chosen.")
            else:
                notes.append("The CHW visit stays unassigned until a patient is chosen; the data-quality event does not identify who is silent.")

        # ---- fold in what has already been routed (from the audit log)
        snaps, last = _routed_snapshots(package_id, log_path)
        for a in actions:
            s = snaps.get(a["action_id"])
            a["routed"] = bool(s)
            a["routed_at"] = s["routed_at"] if s else None
            if s:
                a["status"], a["draft"], a["needs"] = "routed", s["draft"], []
        routed_n = sum(a["routed"] for a in actions)
        state = ("routed" if routed_n == len(actions) else "partially_routed" if routed_n
                 else "held" if last and last["decision"] == "hold" else "draft")

        def _count(t):
            xs = [a for a in actions if a["type"] == t]
            return {"total": len(xs), "ready": sum(a["status"] == "ready" for a in xs),
                    "needs_input": sum(a["status"] == "needs_input" for a in xs), "routed": sum(a["routed"] for a in xs)}
        summary = {"patients": n, "care_summary": {"total": n}, "pharmacy_outreach": _count("pharmacy_outreach"),
                   "nemt_request": _count("nemt_request"), "visit_and_repanel": _count("visit_and_repanel"), "chw_home_visit": _count("chw_home_visit"),
                   "actions_total": len(actions), "ready_total": sum(a["status"] == "ready" for a in actions), "routed_total": routed_n}
        summary["visit_and_repanel"].update({
            "telehealth": sum(a["draft"]["modality"] == "telehealth" for a in actions if a["type"] == "visit_and_repanel"),
            "in_person_via_nemt": sum(a["draft"]["modality"] == "in_person_via_nemt" for a in actions if a["type"] == "visit_and_repanel")})

        needs, seen = [], {}
        for a in actions:
            for nd in a["needs"]:
                k = nd["field"]
                if k not in seen:
                    seen[k] = {"field": k, "label": nd["label"], "why": nd["why"], "action_ids": []}
                    needs.append(seen[k])
                seen[k]["action_ids"].append(a["action_id"])
        for k in needs:
            k["count"] = len(k["action_ids"])

        return {"package_id": package_id, "persona": PERSONA, "tier": 1, "as_of": AS_OF, "delivery": DELIVERY,
                "state": state, "last_decision": last, "summary": summary, "needs_input": needs, "notes": notes,
                "patients": patients, "actions": actions}
    finally:
        conn.close()


# ------------------------------------------------------------ approval + audit

def decide(decision, decided_by, inputs=None, note=None, log_path=None):
    """Record a person's decision. 'route' marks every READY action as routed (simulated);
    'hold' routes nothing. Anything not ready stays held. Nothing is ever sent."""
    if decision not in ("route", "hold"):
        raise ActionInputError("decision must be 'route' or 'hold'")
    who = (decided_by or "").strip()
    if not who or len(who) > 80:
        raise ActionInputError("decided_by is required (1-80 characters) so every decision is attributable")
    note = (note or "").strip()[:500] or None

    pkg = build_tier1_package(inputs, log_path)          # validates inputs
    routable = [a for a in pkg["actions"] if decision == "route" and a["status"] == "ready"]
    already = [a["action_id"] for a in pkg["actions"] if a["routed"]]
    held = [a for a in pkg["actions"] if not a["routed"] and a not in routable]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    brief = lambda xs: [{"action_id": a["action_id"], "type": a["type"], "patient_id": a["patient_id"]} for a in xs]

    # Each action is routed at most once. The primary key on routed_actions is the
    # real guard (it also holds across several server processes); the lock only
    # keeps threads in this process tidy. What was ACTUALLY routed is what gets logged.
    scope = log_scope(log_path)
    with _LOCK:
        lc = log_conn()
        try:
            cur = lc.execute(
                "INSERT INTO decisions (scope, package_id, decision, decided_by, decided_at, note, inputs_json, routed_json, held_json, delivery) "
                "VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id",
                (scope, pkg["package_id"], decision, who, now, note, json.dumps(inputs or {}), "[]", "[]", DELIVERY),
            )
            did, routed_now = cur.fetchone()[0], []
            for a in routable:
                ins = lc.execute(
                    "INSERT INTO routed_actions (scope, action_id, package_id, decision_id, routed_at, routed_by, draft_json) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT (scope, action_id) DO NOTHING",
                    (scope, a["action_id"], pkg["package_id"], did, now, who, json.dumps(a["draft"])),
                )
                if ins.rowcount == 1:
                    routed_now.append(a)
                else:
                    already.append(a["action_id"])       # another request routed it first
            held = [a for a in pkg["actions"] if a["action_id"] not in already and a not in routed_now]
            lc.execute(
                "UPDATE decisions SET routed_json = ?, held_json = ? WHERE id = ? AND scope = ?",
                (json.dumps(brief(routed_now)), json.dumps([dict(x, needs=[n["field"] for n in a["needs"]]) for x, a in zip(brief(held), held)]), did, scope),
            )
            lc.commit()
        finally:
            lc.close()
    routable = routed_now

    fresh = build_tier1_package(None, log_path)
    if decision == "hold":
        message = "Held. Nothing was routed; the package stays a draft and can be routed later."
    elif routable:
        message = (f"Recorded your approval of {len(routable)} action(s). Simulated: nothing was sent to any pharmacy, dispatcher, clinic or "
                   f"community health worker." + (f" {len(held)} action(s) are held until their missing input is supplied." if held else ""))
    else:
        message = "No action was ready to route, so nothing was recorded as routed. Supply the missing inputs and try again."
    return {"decision": decision, "package_id": pkg["package_id"], "decided_by": who, "decided_at": now, "delivery": DELIVERY,
            "message": message, "routed": brief(routable), "already_routed": already,
            "held": [dict(x, needs=[n["field"] for n in a["needs"]]) for x, a in zip(brief(held), held)], "package": fresh}


def get_audit(log_path=None):
    package_id = build_tier1_package(None, log_path)["package_id"]
    scope = log_scope(log_path)
    with _LOCK:
        lc = log_conn()
        try:
            ds = lc.execute(
                "SELECT id, decision, decided_by, decided_at, note, routed_json, held_json, delivery "
                "FROM decisions WHERE package_id = ? AND scope = ? ORDER BY id",
                (package_id, scope),
            ).fetchall()
        finally:
            lc.close()
    return {"package_id": package_id, "delivery": DELIVERY,
            "decisions": [{"id": d[0], "decision": d[1], "decided_by": d[2], "decided_at": d[3], "note": d[4],
                           "routed": json.loads(d[5]), "held": json.loads(d[6]), "delivery": d[7]} for d in ds]}
