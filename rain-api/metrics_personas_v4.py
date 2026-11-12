"""Computed values for the patient persona, Linda Garcia (Use Case C).

metrics_v4.compute() calls extend(ctx, cur, calc) after the operator personas' context is built. Everything here is
SQL over rain_v4.synthetic at request time, like the rest of the context:

  constants.PATIENTS.linda   her own record: next visit, reminder plan, readings, open checks, visit history,
                             channels and coverage. A patient persona sees only this.
  constants.TASKS.linda      her task briefing
  constants.SCOPES.linda     her data scope (her own record only)
  datasets lg_*              her own tables

Nothing returns null: a value the data does not have yet becomes words ("No visit booked yet"), so the persona
templates (seed/rain_v4_ui_templates.json, contract and persona linda) always render.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from metrics_v4 import CONFIG, DAY, ES_DAY, ES_MON, MON, MONTH, ROUTE, age_on, bp_text, col, hm, one, rnd, rows, table

# Plain-language names of the gate measures, for a patient ("what is due for me").
CHECK_LABEL = {"CMS165": "Blood pressure check (a reading under 140/90)", "CMS122": "Diabetes A1c test",
               "CMS130": "Colorectal cancer screening", "CMS125": "Breast cancer screening", "CMS2": "Depression screening"}
WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def _when(t: datetime) -> str:
    return f"{DAY[t.weekday()]}, {MON[t.month]} {t.day} at {hm(t)}"


def _short(t: datetime) -> str:
    return f"{DAY[t.weekday()][:3]}, {MON[t.month]} {t.day}, {hm(t)}"


def _clock(v) -> str:
    """A quiet-hours time (08:00:00 or a time) as 8 AM."""
    h = int(str(v)[:2])
    return f"{h % 12 or 12} {'PM' if h >= 12 else 'AM'}"


def _list(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else (", ".join(xs[:-1]) + " and " + xs[-1]) if xs else ""


def _lower1(s: str) -> str:
    """Lower-case the first letter only (keeps "A1c", "V")."""
    return s[:1].lower() + s[1:]


def _hours(offs: list[int]) -> str:
    return (_list([str(o) for o in offs]) + " hours before") if offs else "Not planned yet"


# ─── a patient's own record ─────────────────────────────────────────────────────────────────────────────────
def _patient(cur, calc, pid: str) -> tuple[dict, dict]:
    as_of = calc.as_of
    p = rows(cur, """SELECT p.*, (SELECT min(t.drive_minutes) FROM synthetic.travel_time t
                                  WHERE t.patient_id = p.patient_id AND t.clinic_site_id = p.home_site_id) home_drive,
                            (SELECT min(t.drive_minutes) FROM synthetic.travel_time t WHERE t.patient_id = p.patient_id) min_drive
                     FROM synthetic.patient p WHERE p.patient_id = %(p)s""", {"p": pid})[0]
    site = calc.site[p["home_site_id"]]
    site_short = site["site_name"].replace("Sierra Basin ", "")
    drive = int(p["home_drive"] if p["home_drive"] is not None else (p["min_drive"] or 0))
    county = next((c["name"] for c in calc.counties if c["fips"] == p["county_fips"]), "")
    appts = rows(cur, """SELECT a.appointment_id, a.status, a.visit_mode, a.visit_type, a.visit_link, a.no_show_risk, a.provider_id,
                                s.slot_start, sc.clinic_site_id
                         FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id
                         JOIN synthetic.schedule sc ON sc.schedule_id = s.schedule_id
                         WHERE a.patient_id = %(p)s ORDER BY s.slot_start, a.appointment_id""", {"p": pid})
    upcoming = [a for a in appts if a["status"] in ("booked", "confirmed") and a["slot_start"].date() > as_of]
    year_ago = as_of - timedelta(days=365)
    past = [a for a in appts if year_ago < a["slot_start"].date() <= as_of and a["status"] in ("completed", "no-show")]
    missed = sum(1 for a in past if a["status"] == "no-show")

    def mode_words(a):
        return "video visit" if a["visit_mode"] == "telehealth" else "in-person visit"

    def where(a):
        return "Video, from home" if a["visit_mode"] == "telehealth" else calc.site[a["clinic_site_id"]]["site_name"]

    nxt = upcoming[0] if upcoming else None
    msgs = rows(cur, """SELECT * FROM synthetic.reminder_message WHERE appointment_id = %(a)s
                        ORDER BY coalesce(sent_at, scheduled_for), message_id""", {"a": nxt["appointment_id"] if nxt else ""})
    offs = sorted({m["offset_hours"] for m in msgs if m["offset_hours"]}, reverse=True)
    sent = [m for m in msgs if m["sent_at"]]
    replies = [m for m in msgs if m["reply"]]
    last_reply = replies[-1]["reply"].upper() if replies else None
    prefs = rows(cur, "SELECT * FROM synthetic.contact_preference WHERE patient_id = %(p)s ORDER BY preference_id", {"p": pid})
    channels = list(dict.fromkeys(x["channel"] for x in prefs if x["consent_flag"]))
    pref = prefs[-1] if prefs else {}
    readings = rows(cur, """SELECT DISTINCT ON (t, s, d) t, s, d, device FROM (
                              SELECT reading_time t, value_systolic s, value_diastolic d, device_type device FROM synthetic.remote_bp_reading
                               WHERE patient_id = %(p)s
                              UNION ALL SELECT reading_time, value_systolic, value_diastolic, device_type FROM synthetic.rpm_reading
                               WHERE patient_id = %(p)s AND value_systolic IS NOT NULL) x ORDER BY t, s, d""", {"p": pid})
    readings.sort(key=lambda r: r["t"])
    latest = readings[-1] if readings else None
    gaps = rows(cur, """SELECT measure_code, status, opened_at, closed_at, closed_by FROM synthetic.care_gap
                        WHERE patient_id = %(p)s ORDER BY measure_code""", {"p": pid})
    open_gaps = [g for g in gaps if g["status"] == "open"]
    elig = rows(cur, """SELECT payer, coverage_status, checked_at FROM synthetic.eligibility_check WHERE patient_id = %(p)s
                        ORDER BY checked_at DESC NULLS LAST LIMIT 1""", {"p": pid})
    plan = one(cur, "SELECT payer FROM synthetic.attributed_member WHERE patient_id = %(p)s ORDER BY contract_year DESC LIMIT 1",
               {"p": pid}) or calc.cb["payer"]
    inbox = rows(cur, "SELECT * FROM synthetic.inbox_item WHERE patient_id = %(p)s ORDER BY received_at", {"p": pid})
    video = rows(cur, """SELECT s.slot_start, sc.provider_id FROM synthetic.slot s JOIN synthetic.schedule sc ON sc.schedule_id = s.schedule_id
                         WHERE s.telehealth_flag AND s.status = 'open' AND s.slot_start::date > %(a)s AND s.slot_start < %(v)s
                         ORDER BY s.slot_start, s.slot_id""", {"a": as_of, "v": nxt["slot_start"] if nxt else as_of})
    tele_open = len(video)
    risk = float(nxt["no_show_risk"] or 0) if nxt else 0.0
    band = "High" if risk >= 0.35 else "Medium" if risk >= 0.18 else "Low"
    qs, qe = (pref.get("quiet_hours_start"), pref.get("quiet_hours_end"))
    quiet = f"{_clock(qs)} to {_clock(qe)}" if qs is not None and qe is not None else "None set"
    offers_video = any(m["template"] == "reminder_offer_telehealth" for m in msgs)
    status = ("Change requested (R)" if last_reply == "R" else "Confirmed" if last_reply == "C" or (nxt and nxt["status"] == "confirmed")
              else "Switched to video (T)" if last_reply in ("T", "V") else "Not confirmed yet")
    unconfirmed = sum(1 for a in upcoming if a["status"] == "booked")

    def visit(a):
        t = a["slot_start"]
        return {"appointmentId": a["appointment_id"], "when": _when(t), "day": DAY[t.weekday()], "date": f"{MON[t.month]} {t.day}",
                "time": hm(t), "es": f"el {ES_DAY[t.weekday()]} {t.day} de {ES_MON[t.month]} a las {hm(t)}",
                "mode": mode_words(a), "modeA": ("an " if mode_words(a)[0] in "aeiou" else "a ") + mode_words(a), "where": where(a), "provider": calc.prov_name(a["provider_id"]),
                "visitType": a["visit_type"] or "Visit", "link": a["visit_link"] or "Sent with the reminders",
                "daysAway": (t.date() - as_of).days, "status": "Confirmed" if a["status"] == "confirmed" else "Booked, not confirmed yet"}

    nv = visit(nxt) if nxt else {"appointmentId": "None", "when": "No visit booked yet", "day": "Not booked", "date": "Not booked",
                                 "time": "Not booked", "es": "sin cita", "mode": "visit", "modeA": "a visit", "where": site["site_name"],
                                 "provider": "Your care team", "visitType": "Visit", "link": "None yet", "daysAway": 0,
                                 "status": "No visit booked"}
    out = {
        "memberId": pid, "name": f"{p['first_name']} {p['last_name']}", "first": p["first_name"], "age": age_on(p["birth_date"], as_of),
        "language": p["language"], "town": site_short, "site": site["site_name"], "siteAddress": site["address"], "county": county,
        "driveMin": drive, "plan": plan,
        "next": nv, "upcoming": len(upcoming), "unconfirmed": unconfirmed, "status": status, "noShowBand": band,
        "noShowRiskPct": rnd(risk * 100),
        "reminders": {"planned": len(msgs), "sent": len(sent), "toCome": len(msgs) - len(sent), "replies": len(replies),
                      "noReply": sum(1 for m in sent if not m["reply"]), "offsets": _hours(offs),
                      "channel": _list(list(dict.fromkeys(m["channel"] for m in msgs))) or (channels[0] if channels else "SMS"),
                      "language": (msgs[0]["language"] if msgs else p["language"]), "offersVideo": offers_video,
                      "videoOffer": ("The 24-hour reminder offers a video visit: reply T to switch" if offers_video
                                     else "Your visit is already by video" if nxt and nxt["visit_mode"] == "telehealth"
                                     else "Reply R and the clinic offers other times")},
        "contact": {"channels": _list(channels) or "None on file", "channelCount": len(channels),
                    "bestTime": pref.get("best_time") or "Any time", "quietHours": quiet,
                    "phoneNote": pref.get("phone_note") or "Your own phone", "frontDesk": f"{site_short} front desk",
                    "clinical": ROUTE["Clinical question"], "messages": len(inbox),
                    "openMessages": sum(1 for x in inbox if x["status"] == "open")},
        "readings": {"count": len(readings), "latest": bp_text(latest["s"], latest["d"]) if latest else "None yet",
                     "latestDate": f"{MON[latest['t'].month]} {latest['t'].day}" if latest else "Not yet",
                     "under": sum(1 for r in readings if r["s"] < 140 and r["d"] < 90),
                     "latestUnder": bool(latest and latest["s"] < 140 and latest["d"] < 90)},
        "checks": {"open": len(open_gaps), "closed": len(gaps) - len(open_gaps),
                   "names": _list([_lower1(CHECK_LABEL.get(g["measure_code"], g["measure_code"]).split(" (")[0]) for g in open_gaps])
                   or "nothing open"},
        "history": {"visits": len(past), "completed": len(past) - missed, "missed": missed, "missedWord": WORDS[missed] if missed < len(WORDS) else str(missed),
                    "windowMonths": 12},
        "coverage": {"status": (elig[0]["coverage_status"] or "unknown").capitalize() if elig else "No 270/271 check on file yet",
                     "checked": (f"{MON[elig[0]['checked_at'].month]} {elig[0]['checked_at'].day}" if elig and elig[0]["checked_at"] else "Not checked yet"),
                     "payer": elig[0]["payer"] if elig else plan},
        "videoSlotsOpen": tele_open,
    }
    # her own datasets (a patient sees only these rows)
    ds = {
        "visits": table(f"Your upcoming visits ({len(upcoming)})",
                        [col("when", "When"), col("type", "Visit"), col("mode", "How"), col("with", "With"), col("status", "Status")],
                        [{"when": _short(a["slot_start"]), "type": a["visit_type"] or "Visit", "mode": mode_words(a).capitalize(),
                          "with": calc.prov_name(a["provider_id"]), "status": visit(a)["status"]} for a in upcoming]
                        or [{"when": "None booked", "type": "", "mode": "", "with": "", "status": ""}]),
        "history": table(f"Your visits in the last 12 months: {len(past) - missed} kept, {missed} missed",
                         [col("when", "When"), col("type", "Visit"), col("mode", "How"), col("result", "Result")],
                         [{"when": _short(a["slot_start"]), "type": a["visit_type"] or "Visit", "mode": mode_words(a).capitalize(),
                           "result": "Missed" if a["status"] == "no-show" else "Kept"} for a in past]
                         or [{"when": "None in 12 months", "type": "", "mode": "", "result": ""}]),
        "reminders": table(f"Your reminders for {nv['when']}",
                           [col("when", "When"), col("sends", "Sends"), col("channel", "Channel"), col("status", "Status")],
                           [{"when": f"{m['offset_hours']} hours before" if m["offset_hours"] else "At booking",
                             "sends": _short(m["sent_at"] or m["scheduled_for"]) if (m["sent_at"] or m["scheduled_for"]) else "",
                             "channel": f"{m['channel']}, {m['language']}",
                             "status": (f"You replied {m['reply'].upper()}" if m["reply"] else (m["delivery_status"] or "scheduled").capitalize())}
                            for m in msgs] or [{"when": "None planned", "sends": "", "channel": "", "status": ""}]),
        "readings": table(f"Your home blood pressure readings ({len(readings)})",
                          [col("when", "When"), col("reading", "Reading"), col("device", "Device"), col("under", "Under 140/90")],
                          [{"when": _short(r["t"]), "reading": bp_text(r["s"], r["d"]), "device": r["device"] or "",
                            "under": "Yes" if r["s"] < 140 and r["d"] < 90 else "No"} for r in reversed(readings)]
                          or [{"when": "None yet", "reading": "", "device": "", "under": ""}]),
        "checks": table(f"Checks due for you ({len(open_gaps)} open)", [col("check", "Check"), col("since", "Open since")],
                        [{"check": CHECK_LABEL.get(g["measure_code"], g["measure_code"]), "since": f"{MONTH[g['opened_at'].month]} {g['opened_at'].year}"}
                         for g in open_gaps] or [{"check": "Nothing open", "since": ""}]),
        "contact": table(f"How to reach {site['site_name']}", [col("way", "Way"), col("detail", "What happens")],
                         [{"way": "Reply C or R to a reminder", "detail": "C confirms your visit; R asks for a new time"},
                          {"way": "Text anything else", "detail": f"It goes to the {site_short} front desk"},
                          {"way": "A health question", "detail": f"{ROUTE['Clinical question']}; texts never give medical advice"},
                          {"way": "Your channels", "detail": _list(channels) or "None on file"},
                          {"way": "Best time to reach you", "detail": pref.get("best_time") or "Any time"},
                          {"way": "Quiet hours", "detail": f"No messages {quiet}"}]),
        "messages": table(f"Your messages to the clinic ({len(inbox)})",
                          [col("received", "Received"), col("message", "Message"), col("route", "Goes to"), col("status", "Status")],
                          [{"received": _short(x["received_at"]), "message": x["message_text"], "route": ROUTE.get(x["item_type"], "Front desk"),
                            "status": (x["status"] or "").capitalize()} for x in inbox]
                          or [{"received": "None", "message": "", "route": "", "status": ""}]),
        "video": table(f"Open video slots before your visit ({tele_open} in all, the first {min(tele_open, 8)})",
                       [col("when", "When"), col("with", "With")],
                       [{"when": _short(v["slot_start"]), "with": calc.prov_name(v["provider_id"])} for v in video[:8]]
                       or [{"when": "None open", "with": ""}]),
    }
    return out, ds


def _patients(ctx, cur, calc):
    C, DS = ctx["constants"], ctx["datasets"]
    rec, ds = _patient(cur, calc, CONFIG["linda"])
    C["PATIENTS"] = {"linda": rec}
    for name, d in ds.items():
        DS[f"lg_{name}"] = d
    L = rec
    tasks = C.setdefault("TASKS", {})

    def item(n, label, tone):
        return {"n": n, "label": label, "tone": tone}
    tasks["linda"] = {
        "title": f"Your next visit: {L['next']['when']}",
        "items": [item(L["next"]["daysAway"], f"days until your {L['next']['mode']}", "neutral"),
                  item(L["reminders"]["toCome"], "reminders still to come: reply C or R", "warning"),
                  item(L["checks"]["open"], "checks due for you at this visit", "critical")],
        "first": (f"Your {L['next']['mode']} is with {L['next']['provider']}; your link: {L['next']['link']}."
                  if L["upcoming"] else "No visit is booked yet: the clinic will text you."),
        "button": {"label": "Open my messages", "href": "/patient"}}
    C.setdefault("SCOPES", {})["linda"] = {"self": True, "memberId": L["memberId"], "label": "Your own record only"}


def extend(ctx: dict, cur, calc) -> dict:
    """Add the patient persona's computed values to the context (in place) and return it."""
    _patients(ctx, cur, calc)
    return ctx
