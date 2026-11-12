"""Build rain-api/seed/rain_v4_ui_data.json: the v0.3 UI seed plus the PRD v0.4 additions.

Adds the five v0.2 operator personas brought into v0.4 (Section 6.3, 6.6, 6.9, 6.11, 6.12) and the
second patient (6.14), all anchored to the same Q3 contract checkpoint: every number below is derived
from the v0.3 records and master numbers (campaign members, sites, counties, reminders, bookings), not
typed in. Steps that answer with public or synthetic database rows use the `query_table` visual: the
backend (chat_v4) runs that pack query live against rain_v4 when it builds the answer.

    python scripts/e2e/make_v4_ui_seed.py
"""
import copy
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "rain-api/seed/rain_v3_ui_data.json"
OUT = ROOT / "rain-api/seed/rain_v4_ui_data.json"

seed = json.loads(V3.read_text(encoding="utf-8"))
S = seed["sections"]
C, REC, DS = S["constants"], S["records"], S["datasets"]
MEMBERS = REC["campaignMembers"]
SITES = {s["id"]: s for s in C["SITES"]}
COUNTIES = {c["id"]: c for c in C["COUNTIES"]}
TERESA_SITES = C["TERESA_SITES"]
num = lambda n: f"{n:,}"
usd_k = lambda n: f"${round(n / 1000):,}K"
pct = lambda a, b: round(100 * a / b) if b else 0

# ─── Scopes chosen for the v0.2 personas (PRD v0.4 Section 13, item 2: proposed) ─────────────────────
HARGROVE_SITE = "winnemucca"
BROOKS_SITE = "battleMountain"
OKAFOR_SITES = ["battleMountain", "lovelock"]

hg_site = SITES[HARGROVE_SITE]
hg_members = [m for m in MEMBERS if m["siteId"] == HARGROVE_SITE]
hg_booked = [m for m in hg_members if m["status"] == "Reached and booked"]
hg_county = COUNTIES[hg_site["county"]]

frontier = [m for m in MEMBERS if m["frontier"] and m["siteId"] not in TERESA_SITES]
frontier.sort(key=lambda m: m["rank"])
dh_voice = [m for m in frontier if m["channel"] == "Voice"]
dh_ship = [m for m in frontier if m["cuff"] == "Ship first"]
dh_social = [m for m in frontier if m["socialNeeds"]]
noreply = [r for r in REC["reminders"] if r["status"].startswith("No reply")]

kb_members = [m for m in MEMBERS if m["siteId"] == BROOKS_SITE]
kb_ids = {m["id"] for m in kb_members}
kb_voice = [m for m in kb_members if m["channel"] == "Voice"]
kb_booked = [m for m in kb_members if m["status"] == "Reached and booked"]
kb_pending = [b for b in REC["pendingBookings"] if b["memberId"] in kb_ids]
kb_reminders = [r for r in REC["reminders"] if r["memberId"] in kb_ids]

# The provider's week: the panel's booked rechecks first, then the next patients by rank, alternating
# visit mode so the week holds both in-person and telehealth visits, as a real panel does.
_panel = sorted([m for m in MEMBERS if m["siteId"] in OKAFOR_SITES], key=lambda m: m["rank"])
so_week = [m for m in _panel if m["status"] == "Reached and booked"][:4]
for mode in ("In person", "Telehealth", "In person", "Telehealth", "In person", "Telehealth", "In person", "Telehealth"):
    if len(so_week) >= 8:
        break
    nxt = next((m for m in _panel if m["mode"] == mode and m not in so_week), None)
    if nxt:
        so_week.append(nxt)
DAYS = ["Mon, Nov 9", "Mon, Nov 9", "Tue, Nov 10", "Tue, Nov 10", "Wed, Nov 11", "Thu, Nov 12", "Thu, Nov 12", "Fri, Nov 13"]
TIMES = ["9:00 AM", "10:30 AM", "9:30 AM", "1:00 PM", "11:00 AM", "9:00 AM", "2:30 PM", "10:00 AM"]


def table(caption, columns, rows):
    return {"caption": caption, "columns": columns, "rows": rows}


def col(key, label, **kw):
    return {"key": key, "label": label, **kw}


# ─── Records: the pre-visit summaries, the front-desk inbox and the standing orders ─────────────────────
previsit = []
for i, m in enumerate(so_week[:8]):
    systolic = int(m["lastBp"].split("/")[0])
    previsit.append({
        "id": f"PV-{i + 1:02d}", "memberId": m["id"], "name": m["name"], "age": m["age"], "site": m["site"],
        "day": DAYS[i], "time": TIMES[i], "mode": m["mode"], "riskTier": "High" if m["likelihood"] >= 70 else "Rising",
        "reasons": m["reasons"], "openGaps": ["BP control (CMS165)"] + (["HbA1c >9% (CMS122)"] if "Type 2 diabetes" in m["conditions"] else []),
        # Rule (stated in the pre-visit summary): no visit in 6+ months means no refill review, so flag adherence.
        "adherence": "Under 80%" if m["monthsSinceVisit"] >= 6 or systolic >= 150 else "On track",
        "latestBp": f"{m['lastBp']} ({m['lastBpMonth']})",
        "codingRecapture": len(m["conditions"]) > 1, "standingOrder": m["standingOrder"], "conditions": m["conditions"],
    })

inbox_types = [("Free-text reply", "Can I come in the morning instead? I work afternoons."),
               ("Clinical question", "My blood pressure was 160 this morning, should I take another pill?"),
               ("Undeliverable number", "SMS failed: the number is no longer in service."),
               ("Coverage flag", "Eligibility check returned inactive coverage."),
               ("Free-text reply", "Who is this? I did not book anything."),
               ("Clinical question", "Is it okay to skip my metformin before the video visit?"),
               ("Undeliverable number", "Voice call failed twice: no voicemail set up."),
               ("Free-text reply", "Thank you, I will be there.")]
inbox = []
for i, (kind, text) in enumerate(inbox_types):
    m = kb_members[(i * 5) % len(kb_members)]
    route = {"Clinical question": "Nurse line (no automated clinical advice)", "Coverage flag": "Enrollment assister",
             "Undeliverable number": "Front desk: update the number", "Free-text reply": "Front desk"}[kind]
    inbox.append({"id": f"IN-{i + 1:02d}", "memberId": m["id"], "name": m["name"], "type": kind, "message": text,
                  "received": f"Today, {8 + i // 2}:{'15' if i % 2 else '40'} AM", "route": route,
                  "status": "Open" if i < 6 else "Resolved"})

REC["previsitSummaries"] = previsit
REC["inboxItems"] = inbox

# ─── Constants: persona map in the PRD v0.4 switcher order, task queues, the second patient ───────────
C["PERSONAS"] = {"ceo": "rain_ceo", "cmo": "rain_cmo", "hargrove": "rain_hargrove", "cio": "rain_cio",
                 "state": "rain_state", "bell": "rain_bell", "chw": "rain_chw", "holloway": "rain_holloway",
                 "access": "rain_access", "brooks": "rain_brooks", "okafor": "rain_okafor"}
C["SCOPES"] = {"hargrove": {"siteId": HARGROVE_SITE, "label": f"{hg_site['name']} site"},
               "brooks": {"siteId": BROOKS_SITE, "label": f"{SITES[BROOKS_SITE]['name']} front desk"},
               "okafor": {"siteIds": OKAFOR_SITES, "label": " and ".join(SITES[s]["name"] for s in OKAFOR_SITES) + " panel"},
               "holloway": {"frontier": True, "excludeSites": TERESA_SITES, "label": "Frontier ZIP codes outside Teresa's sites"},
               "bell": {"state": True, "label": "State program, aggregated"}}
C["TASKS"] = {
    "holloway": {"title": f"{len(frontier)} frontier patients on your list",
                 "items": [{"n": len(frontier), "label": "frontier patients in the BP campaign outside Teresa's two sites", "tone": "warning"},
                           {"n": len(dh_voice), "label": "reachable by voice only (no SMS consent)", "tone": "critical"},
                           {"n": len(noreply), "label": "reminders with no reply before the cut-off", "tone": "warning"}],
                 "first": f"Start with {frontier[0]['name']}: {', '.join(frontier[0]['reasons'])}.",
                 "button": {"label": "Open my worklist", "href": "/worklist?filter=frontier"}},
    "brooks": {"title": f"{SITES[BROOKS_SITE]['name']} front desk",
               "items": [{"n": sum(1 for x in inbox if x["status"] == "Open"), "label": "open items in the front-desk inbox", "tone": "warning"},
                         {"n": len(kb_reminders), "label": "reminders out for this site's visits", "tone": "neutral"},
                         {"n": len(kb_voice), "label": "patients reachable by voice only", "tone": "critical"}],
               "first": f"First in the inbox: {inbox[1]['name']} asked a clinical question; it routes to the nurse line.",
               "button": {"label": "Open the front-desk inbox", "href": "/front-desk-inbox"}},
    "okafor": {"title": f"{len(previsit)} visits this week with a pre-visit summary",
               "items": [{"n": len(previsit), "label": "confirmed visits this week", "tone": "neutral"},
                         {"n": sum(1 for p in previsit if p["codingRecapture"]), "label": "patients due for coding recapture", "tone": "warning"},
                         {"n": sum(1 for p in previsit if p["adherence"] != "On track"), "label": "medication adherence gaps", "tone": "critical"}],
               "first": f"First visit: {previsit[0]['name']}, {previsit[0]['day']} {previsit[0]['time']} ({previsit[0]['mode'].lower()}).",
               "button": {"label": "Open the pre-visit summary", "href": "/pre-visit-summary"}},
}
C["ROSA"] = {"name": "Rosa Martínez", "first": "Rosa", "age": 46, "driveMin": 64, "language": "English",
             "channels": ["SMS", "Voice (IVR)"], "visitType": "Diabetes follow-up", "noShowBand": "High",
             "missedVisits": 2, "phoneNote": "Shares a phone with her sister",
             "visit": {"day": "Tuesday", "date": "Nov 17", "time": "10:30 AM", "site": "Fallon"},
             "link": "sierrabasin.example/v/5317", "memberId": "R-50214",
             "why": "Two missed visits in 12 months and a 64-minute drive put her visit in the high no-show band, "
                    "so she gets reminders at 72, 24 and 3 hours, and the 24-hour reminder offers telehealth."}

# ─── Personas (identity and copy) ────────────────────────────────────────────────────────────────────
P = S["personas"]
P["hargrove"] = {"identity": {"name": "Dr. Linda Hargrove", "initials": "LH", "role": "Clinic Medical / Quality Director",
                              "greeting": "Dr. Hargrove"},
                 "inputPlaceholder": f"Ask about {hg_site['name']}'s risk mix, care gaps, ED use or imaging…",
                 "greetingSubtitle": f"Your site briefing for {hg_site['name']}: the BP campaign, an imaging outlier and ED use.",
                 "notifications": [{"id": "lh-n1", "unread": True, "title": "Feedback note from Dr. Castellanos",
                                    "detail": f"Choosing Wisely note on low back pain imaging at {hg_site['name']}.",
                                    "at": "Today, 8:10 AM", "tone": "warning"}]}
P["bell"] = {"identity": {"name": "Marcus Bell", "initials": "MB", "role": "State RHTP Program Manager", "greeting": "Marcus"},
             "inputPlaceholder": "Ask about county care gaps, broadband, clinic sites or the RHTP report…",
             "greetingSubtitle": "Your program briefing: county need, broadband and the CMS report.",
             "notifications": [{"id": "mb-n1", "unread": True, "title": "CMS progress report",
                                "detail": "People served, services and outcomes by county, for all four grantees.",
                                "at": "Today, 7:55 AM", "tone": "info"}]}
P["holloway"] = {"identity": {"name": "Denise Holloway", "initials": "DH", "role": "Community Health Worker (field)", "greeting": "Denise"},
                 "inputPlaceholder": "Ask about your call list, non-responders or who you can't reach by text…",
                 "greetingSubtitle": f"Your field queue: {len(frontier)} frontier patients, {len(dh_voice)} voice-only.",
                 "notifications": [{"id": "dh-n1", "unread": True, "title": f"{len(noreply)} reminders with no reply",
                                    "detail": "Each becomes a call task at the 24-hour cut-off.", "at": "Today, 8:05 AM", "tone": "warning"}]}
P["brooks"] = {"identity": {"name": "Kayla Brooks", "initials": "KB", "role": "Clinic Scheduler / Front Desk", "greeting": "Kayla"},
               "inputPlaceholder": "Ask about the confirmations board, no-show risk, eligibility or the inbox…",
               "greetingSubtitle": f"Your {SITES[BROOKS_SITE]['name']} front desk: inbox, confirmations and coverage.",
               "notifications": [{"id": "kb-n1", "unread": True, "title": "Clinical question in the inbox",
                                  "detail": "Routed to the nurse line; no automated clinical advice.", "at": "Today, 8:15 AM", "tone": "warning"}]}
P["okafor"] = {"identity": {"name": "Dr. Samuel Okafor", "initials": "SO", "role": "Rural Provider", "greeting": "Dr. Okafor"},
               "inputPlaceholder": "Ask about this week's schedule, rising-risk patients, adherence or coding…",
               "greetingSubtitle": f"Your week: {len(previsit)} confirmed visits, each with a pre-visit summary.",
               "notifications": [{"id": "so-n1", "unread": True, "title": "Standing orders to review",
                                  "detail": "BP campaign: recheck and titrate per protocol.", "at": "Today, 7:40 AM", "tone": "info"}]}

# ─── Datasets ─────────────────────────────────────────────────────────────────────────────────────────
status_counts = Counter(m["status"] for m in hg_members)
mode_counts = Counter(m["mode"] for m in hg_members)
DS["hg_site_mix"] = table(f"{hg_site['name']} in the BP campaign ({len(hg_members)} of {len(MEMBERS)} members)",
                          [col("group", "Group"), col("members", "Members", kind="number"), col("share", "Share", align="right")],
                          [{"group": f"Status: {k}", "members": v, "share": f"{pct(v, len(hg_members))}%"} for k, v in status_counts.most_common()]
                          + [{"group": f"Visit mode: {k}", "members": v, "share": f"{pct(v, len(hg_members))}%"} for k, v in mode_counts.most_common()]
                          + [{"group": "Frontier ZIP", "members": sum(m["frontier"] for m in hg_members),
                              "share": f"{pct(sum(m['frontier'] for m in hg_members), len(hg_members))}%"}])
open_gaps = sorted([m for m in hg_members if m["status"] != "Reached and booked"], key=lambda m: m["rank"])
DS["hg_open_gaps"] = table(f"Open BP gaps at {hg_site['name']}: {len(open_gaps)} members not yet booked (top 10 by rank)",
                           [col("rank", "Rank", kind="number"), col("name", "Patient"), col("why", "Why now"), col("mode", "Visit mode"), col("status", "Status")],
                           [{"rank": m["rank"], "name": m["name"], "why": ", ".join(m["reasons"]), "mode": m["mode"], "status": m["status"]} for m in open_gaps[:10]])
hg_modes = Counter(m["mode"] for m in hg_members)
DS["hg_telehealth"] = table(f"Recommended visit mode at {hg_site['name']}",
                            [col("mode", "Mode"), col("members", "Members", kind="number"), col("share", "Share", align="right")],
                            [{"mode": k, "members": v, "share": f"{pct(v, len(hg_members))}%"} for k, v in hg_modes.most_common()])
hg_social = Counter(n for m in hg_members for n in m["socialNeeds"])
DS["hg_social"] = table(f"Social needs flagged among {hg_site['name']}'s campaign members",
                        [col("need", "Need"), col("members", "Members", kind="number")],
                        [{"need": k, "members": v} for k, v in hg_social.most_common()] or [{"need": "None flagged", "members": 0}])

DS["dh_top"] = table(f"Your frontier patients, highest priority first ({len(frontier)} in all)",
                     [col("rank", "Rank", kind="number"), col("name", "Patient"), col("site", "Site"), col("drive", "Drive", align="right"),
                      col("channel", "Channel"), col("why", "Why now")],
                     [{"rank": m["rank"], "name": m["name"], "site": m["site"], "drive": f"{m['driveMin']} min", "channel": m["channel"],
                       "why": ", ".join(m["reasons"])} for m in frontier[:10]])
DS["dh_noreply"] = table("Reminders with no reply: each becomes a call task at the 24-hour cut-off",
                         [col("name", "Patient"), col("visit", "Visit"), col("language", "Language"), col("status", "Status")],
                         [{"name": r["name"], "visit": r["visit"], "language": r["language"], "status": r["status"]} for r in noreply])
DS["dh_social"] = table("Frontier patients with a social need on file",
                        [col("name", "Patient"), col("needs", "Needs"), col("drive", "Drive", align="right"), col("phone", "Phone note")],
                        [{"name": m["name"], "needs": ", ".join(m["socialNeeds"]), "drive": f"{m['driveMin']} min", "phone": m.get("phoneNote") or ""} for m in dh_social[:12]])
DS["dh_voice"] = table(f"Voice-only patients ({len(dh_voice)}): no SMS consent, so a call or a visit",
                       [col("name", "Patient"), col("site", "Site"), col("best", "Best time"), col("phone", "Phone note")],
                       [{"name": m["name"], "site": m["site"], "best": m.get("bestTime", "Any time"), "phone": m.get("phoneNote") or ""} for m in dh_voice[:12]])

DS["kb_board"] = table(f"Confirmations board, {SITES[BROOKS_SITE]['name']}",
                       [col("name", "Patient"), col("visit", "Visit"), col("plan", "Reminder plan"), col("status", "Status")],
                       [{"name": r["name"], "visit": r["visit"], "plan": r["plan"], "status": r["status"]} for r in kb_reminders]
                       or [{"name": b["name"], "visit": f"{b['mode']} booking", "plan": "Built at booking", "status": "Waiting to book"} for b in kb_pending])
kb_risk = sorted(kb_members, key=lambda m: (-m["monthsSinceVisit"], -m["driveMin"]))[:10]
DS["kb_noshow"] = table("Highest no-show risk at this site (missed visits and long drives)",
                        [col("name", "Patient"), col("drive", "Drive", align="right"), col("since", "Months since visit", kind="number"),
                         col("last", "Last contact"), col("plan", "Reminders")],
                        [{"name": m["name"], "drive": f"{m['driveMin']} min", "since": m["monthsSinceVisit"], "last": m["lastContact"],
                          "plan": "72, 24 and 3 hours" if m["driveMin"] > 60 or "Missed" in m["lastContact"] else "48 and 3 hours"} for m in kb_risk])
DS["kb_eligibility"] = table("Eligibility (270/271) for this site's pending bookings",
                             [col("name", "Patient"), col("mode", "Mode"), col("plan", "Plan"), col("eligibility", "Coverage")],
                             [{"name": b["name"], "mode": b["mode"], "plan": b["planName"], "eligibility": b["eligibility"]} for b in kb_pending])
DS["kb_nosms"] = table(f"No SMS consent on file ({len(kb_voice)} patients): voice reminders only",
                       [col("name", "Patient"), col("language", "Language"), col("best", "Best time")],
                       [{"name": m["name"], "language": m["language"], "best": m.get("bestTime", "Any time")} for m in kb_voice])
DS["kb_inbox"] = table("Front-desk inbox", [col("received", "Received"), col("name", "Patient"), col("type", "Type"),
                                            col("route", "Routed to"), col("status", "Status")],
                       [{k: x[k] for k in ("received", "name", "type", "route", "status")} for x in inbox])

DS["so_week"] = table("This week's confirmed visits", [col("when", "When"), col("name", "Patient"), col("mode", "Mode"),
                                                       col("tier", "Risk tier"), col("gaps", "Open gaps")],
                      [{"when": f"{p['day']}, {p['time']}", "name": p["name"], "mode": p["mode"], "tier": p["riskTier"],
                        "gaps": ", ".join(p["openGaps"])} for p in previsit])
so_modes = Counter(p["mode"] for p in previsit)
DS["so_modes"] = table("Visit mode this week", [col("mode", "Mode"), col("visits", "Visits", kind="number"), col("share", "Share", align="right")],
                       [{"mode": k, "visits": v, "share": f"{pct(v, len(previsit))}%"} for k, v in so_modes.most_common()])
DS["so_risk"] = table("Rising and high-risk patients this week, with the top reasons",
                      [col("name", "Patient"), col("tier", "Tier"), col("reasons", "Top reasons")],
                      [{"name": p["name"], "tier": p["riskTier"], "reasons": ", ".join(p["reasons"])} for p in previsit])
DS["so_adherence"] = table("Medication adherence before the visit", [col("name", "Patient"), col("adherence", "Adherence"), col("bp", "Latest BP")],
                           [{"name": p["name"], "adherence": p["adherence"], "bp": p["latestBp"]} for p in previsit])
DS["so_readings"] = table("Latest blood pressure readings", [col("name", "Patient"), col("bp", "Latest BP"), col("mode", "Visit mode")],
                          [{"name": p["name"], "bp": p["latestBp"], "mode": p["mode"]} for p in previsit])
DS["so_coding"] = table("Coding recapture due at the visit", [col("name", "Patient"), col("conditions", "Chronic conditions to recapture"), col("when", "Visit")],
                        [{"name": p["name"], "conditions": ", ".join(p["conditions"]), "when": f"{p['day']}, {p['time']}"} for p in previsit if p["codingRecapture"]])
DS["so_orders"] = table("Standing orders from the BP campaign", [col("name", "Patient"), col("order", "Standing order")],
                        [{"name": p["name"], "order": p["standingOrder"]} for p in previsit])


def q(query, caption):
    return {"type": "query_table", "props": {"query": query, "caption": caption}}


def dt(dataset):
    return {"type": "data_table", "props": {"dataset": dataset}}


def launch(step):
    return {"type": "rain.launch_card", "props": {"step": step}}


# ─── Contracts ────────────────────────────────────────────────────────────────────────────────────────
CT = S["contracts"]
hg_name = hg_site["name"]
CT["hargrove"] = {
    "signals": [
        {"id": "SIG-LH-1", "title": f"BP Campaign at {hg_name}", "severity": "critical",
         "description": f"{len(hg_members)} of the {len(MEMBERS)} BP campaign members are yours; {len(hg_booked)} are booked so far.",
         "metric": f"{len(hg_members)} members", "sources": ["EHR (FHIR)", "eCQM Engine"], "chip": "Which care gaps are still open?", "primary": True},
        {"id": "SIG-LH-2", "title": "Low-Value Imaging at My Site", "severity": "warning",
         "description": f"Low back pain imaging at {hg_site['imagingPct']}% of visits against 9% network-wide since April.",
         "metric": f"{hg_site['imagingPct']}% vs 9%", "sources": ["Claims", "Low-Value Care Library"], "chip": "Why is imaging high at my site?"},
        {"id": "SIG-LH-3", "title": "ED Use Above Benchmark", "severity": "warning",
         "description": f"{hg_county['name']} County avoidable ED at {hg_county['edPer1000']} per 1,000 against a 251 benchmark.",
         "metric": f"{hg_county['edPer1000']} per 1,000", "sources": ["Claims", "CMS Unplanned Hospital Visits"], "chip": "Where is ED use concentrating?"},
    ],
    "kpis": [
        {"id": "members", "label": "Attributed members", "value": num(hg_site["members"]), "detail": f"{hg_name} site", "source": "MCO eligibility", "icon": "users", "tone": "neutral"},
        {"id": "pmpm", "label": "Site PMPM", "value": f"${hg_site['pmpm']}", "detail": f"Network ${C['CONTRACT']['actualPmpm']}", "source": "Claims", "icon": "dollar-sign",
         "tone": "warning" if hg_site["pmpm"] > C["CONTRACT"]["actualPmpm"] else "good", "chip": "Walk me through the clinic risk mix"},
        {"id": "bp", "label": "BP campaign members", "value": str(len(hg_members)), "detail": f"{len(hg_booked)} booked", "source": "Quality Gate", "icon": "heart-pulse", "tone": "warning", "chip": "Which care gaps are still open?"},
        {"id": "imaging", "label": "LBP imaging", "value": f"{hg_site['imagingPct']}%", "detail": "Network 9%", "source": "Claims", "icon": "scan", "tone": "critical", "chip": "Why is imaging high at my site?"},
        {"id": "lowValue", "label": "Low-value care", "value": usd_k(hg_site["lowValue"]), "detail": "A year", "source": "Low-value care library", "icon": "trending-down", "tone": "warning"},
        {"id": "ed", "label": "Avoidable ED per 1,000", "value": str(hg_county["edPer1000"]), "detail": f"{hg_county['name']} County, benchmark 251", "source": "Claims + CMS", "icon": "activity", "tone": "warning", "chip": "Where is ED use concentrating?"},
    ],
    "steps": {
        "hg_brief": {"step": 1, "capability": "Proactive Intelligence",
                     "ai": f"Good morning, Dr. Hargrove. {hg_name} carries three signals this week.",
                     "points": [f"{len(hg_members)} BP campaign members are yours; {len(hg_booked)} are booked.",
                                f"Low back pain imaging is at {hg_site['imagingPct']}% against 9% network-wide, and avoidable ED is {hg_county['edPer1000']} per 1,000."],
                     "sources": ["EHR (FHIR)", "Claims", "eCQM Engine", "Low-Value Care Library"],
                     "chips": ["Walk me through the clinic risk mix", "Why is imaging high at my site?", "Which care gaps are still open?"],
                     "next": "Walk me through the clinic risk mix", "viz": ["v_site_mix"]},
        "hg_mix": {"step": 2, "capability": "Converged Conversation", "asks": ["Walk me through the clinic risk mix"],
                   "ai": f"Here is {hg_name}'s share of the BP campaign by status, visit mode and frontier ZIP.",
                   "points": [f"{pct(sum(m['frontier'] for m in hg_members), len(hg_members))}% of these members live in frontier ZIP codes, so telehealth rechecks carry the campaign."],
                   "sources": ["EHR (FHIR)", "Travel Time (OpenStreetMap)", "USDA RUCC"],
                   "chips": ["Why is imaging high at my site?", "Which care gaps are still open?", "What is our telehealth share trend?"], "next": "Why is imaging high at my site?",
                   "viz": ["v_site_mix"]},
        "hg_gaps": {"capability": "Converged Conversation", "asks": ["Which care gaps are still open?"],
                    "ai": f"{len(open_gaps)} of {hg_name}'s campaign members are not booked yet; here are the ten Teresa calls first.",
                    "sources": ["EHR (FHIR)", "Worklist"], "chips": ["How are we trending on care-gap closure?", "Open the Quality Gate"],
                    "next": "How are we trending on care-gap closure?", "viz": ["v_open_gaps"]},
        "hg_closure": {"capability": "Converged Conversation", "asks": ["How are we trending on care-gap closure?"],
                       "ai": "Here is the BP campaign's progress across the network; closed gaps update the quality gate as readings arrive.",
                       "sources": ["Worklist", "Remote BP Readings"], "chips": ["Which care gaps are still open?", "Where is ED use concentrating?"],
                       "viz": ["v_progress"]},
        "hg_ed": {"capability": "Anomaly Detection", "asks": ["Where is ED use concentrating?"],
                  "ai": f"{hg_county['name']} County avoidable ED is {hg_county['edPer1000']} per 1,000 against 251; here are the CMS unplanned-visit and readmission results for the six counties' hospitals.",
                  "sources": ["Claims", "CMS Unplanned Hospital Visits"], "chips": ["Why is imaging high at my site?", "How do we compare with health center benchmarks?"],
                  "viz": ["v_ed_public"]},
        "hg_imaging": {"step": 3, "capability": "Anomaly Detection", "asks": ["Why is imaging high at my site?", f"What is driving imaging at {hg_name}?"],
                       "ai": f"Imaging at {hg_name} jumped to {hg_site['imagingPct']}% when the April locum rotation began; it is a missing order set, not one clinician.",
                       "points": ["Three rotating clinicians show the same ordering rate, and none of the flagged cases had red-flag diagnoses coded."],
                       "sources": ["Claims", "EHR Orders", "Provider Directory (NPPES)", "Low-Value Care Library"],
                       "chips": ["Fix the order set at my site", "Open Low-Value Care", "Which care gaps are still open?"], "next": "Fix the order set at my site",
                       "viz": ["v_imaging_trend", "v_site_imaging"]},
        "hg_fix": {"step": 4, "capability": "Automated Action", "asks": ["Fix the order set at my site", "Draft the order-set fix"],
                   "ai": "I drafted the order-set change and a note for the rotating clinicians; it goes out when you approve.",
                   "points": ["Adds red-flag prompts to the low back pain order set and points to the Choosing Wisely guidance."],
                   "sources": ["EHR Orders", "Low-Value Care Library"], "chips": ["Open Low-Value Care", "Walk me through the clinic risk mix"],
                   "viz": ["v_note"]},
        "hg_telehealth": {"capability": "Friction Observability", "asks": ["What is our telehealth share trend?", "What is our telehealth share?"],
                          "ai": f"{pct(hg_modes['Telehealth'], len(hg_members))}% of {hg_name}'s campaign members are set for a telehealth recheck.",
                          "sources": ["EHR Schedule", "FCC Broadband", "Travel Time (OpenStreetMap)"], "chips": ["Walk me through the clinic risk mix"],
                          "viz": ["v_telehealth"]},
        "hg_social": {"capability": "Converged Conversation", "asks": ["What is our social-need screening coverage?"],
                      "ai": f"Network-wide 38% of members have a screening on file; among {hg_name}'s campaign members these needs are flagged.",
                      "sources": ["Screening Tool", "EHR (FHIR)"], "chips": ["Which care gaps are still open?"], "viz": ["v_social"]},
        "hg_uds": {"capability": "Converged Conversation", "asks": ["How do we compare with health center benchmarks?"],
                   "ai": "Here are the public HRSA UDS clinical quality rates for comparison with your site.",
                   "sources": ["HRSA Uniform Data System (UDS)"], "chips": ["Which care gaps are still open?"], "viz": ["v_uds"]},
        "hg_open_vi": {"capability": "Converged Conversation", "asks": ["Open Value Insights"], "ai": f"Opening Value Insights at {hg_name}'s scope.", "sources": ["Claims"],
                       "chips": ["Walk me through the clinic risk mix"],
                       "launch": {"workbench": "valueInsights", "filter": f"site:{HARGROVE_SITE}", "label": "Value Insights", "detail": f"{hg_name} site", "auto": True},
                       "viz": ["v_launch_vi"]},
        "hg_open_qg": {"capability": "Converged Conversation", "asks": ["Open the Quality Gate"], "ai": f"Opening Quality Gate and Campaigns, view only, at {hg_name}.", "sources": ["eCQM Engine"],
                       "chips": ["Which care gaps are still open?"],
                       "launch": {"workbench": "qualityGate", "filter": f"site:{HARGROVE_SITE}", "label": "Quality Gate and Campaigns", "detail": f"{hg_name} members", "auto": True},
                       "viz": ["v_launch_qg"]},
        "hg_open_lvc": {"capability": "Anomaly Detection", "asks": ["Open Low-Value Care"], "ai": f"Opening Low-Value Care at {hg_name}.", "sources": ["Low-Value Care Library"],
                        "chips": ["Why is imaging high at my site?"],
                        "launch": {"workbench": "lowValueCare", "filter": f"site:{HARGROVE_SITE}", "label": "Low-Value Care", "detail": f"{hg_name} site", "auto": True},
                        "viz": ["v_launch_lvc"]},
        "__default__": {"ai": f"I can answer on {hg_name}'s risk mix, open care gaps, closure, ED use, imaging, telehealth and social needs.",
                        "sources": [], "chips": ["Walk me through the clinic risk mix", "Why is imaging high at my site?", "Which care gaps are still open?"]},
    },
    "queries": ["Walk me through the clinic risk mix", "Which care gaps are still open?", "How are we trending on care-gap closure?",
                "Where is ED use concentrating?", "What is our telehealth share trend?", "What is our social-need screening coverage?",
                "Why is imaging high at my site?"],
    "viz": {"v_site_mix": dt("hg_site_mix"), "v_open_gaps": dt("hg_open_gaps"), "v_progress": {"type": "rain.campaign_progress", "props": {}},
            "v_ed_public": q("HAR-P2", "CMS unplanned hospital visits and readmissions, hospitals in the six counties (live)"),
            "v_imaging_trend": {"type": "rain.annotated_trend", "props": {}}, "v_site_imaging": {"type": "chart", "props": {"dataset": "site_imaging"}},
            "v_note": {"type": "rain.brief_preview", "props": {"kind": "note"}},
            "v_telehealth": dt("hg_telehealth"), "v_social": dt("hg_social"),
            "v_uds": q("HAR-P3", "HRSA UDS clinical quality rates (live)"),
            "v_launch_vi": launch("hg_open_vi"), "v_launch_qg": launch("hg_open_qg"), "v_launch_lvc": launch("hg_open_lvc")},
    "handoffs": [],
    "workbenches": [{"id": "valueInsights", "access": "view", "scope": f"site:{HARGROVE_SITE}"},
                    {"id": "qualityGate", "access": "view", "scope": f"site:{HARGROVE_SITE}"},
                    {"id": "lowValueCare", "access": "view", "scope": f"site:{HARGROVE_SITE}"},
                    {"id": "worklist", "access": "view", "scope": f"site:{HARGROVE_SITE}"}],
}

lander, pershing = COUNTIES["lander"], COUNTIES["pershing"]
CT["bell"] = {
    "signals": [
        {"id": "SIG-MB-1", "title": "County Care-Gap Concentration", "severity": "critical",
         "description": f"Lander and Pershing: primary care visits down {abs(lander['pcVisitChangePct'])}%, the highest avoidable ED of the six.",
         "metric": "2 of 6 counties", "sources": ["Aggregated Claims", "HRSA HPSA"], "chip": "Which counties concentrate the most care gaps?", "primary": True},
        {"id": "SIG-MB-2", "title": "Broadband Dead Zones Limiting Telehealth", "severity": "warning",
         "description": "Six frontier ZIP codes have under 40% video-ready broadband.",
         "metric": "Under 40% video-ready", "sources": ["FCC Broadband", "USDA RUCC"], "chip": "Where do broadband dead zones limit telehealth?"},
        {"id": "SIG-MB-3", "title": "CMS Progress Report Due", "severity": "warning",
         "description": "Four grantees, four templates: RAIN builds one county report, small cells suppressed.",
         "metric": "4 grantees", "sources": ["Grantee Registry", "Aggregated Claims"], "chip": "Generate the RHTP report"},
    ],
    "kpis": [
        {"id": "networks", "label": "Grantee networks", "value": "4 (18 sites)", "source": "Grantee registry", "icon": "building", "tone": "neutral", "chip": "Which clinics diverge from their county ED baseline?"},
        {"id": "members", "label": "Members in view", "value": "31,600", "detail": "De-identified", "source": "Aggregated MCO data", "icon": "users", "tone": "neutral"},
        {"id": "hcSites", "label": "Health center sites (NV)", "value": "live", "live": "nv_health_center_sites", "source": "HRSA health center sites", "icon": "map-pin", "tone": "neutral", "chip": "How many clinic sites are telehealth-capable?"},
        {"id": "ruralFacilities", "label": "RHCs and CAHs (NV)", "value": "live", "live": "nv_rhc_cah", "source": "CMS Provider of Services", "icon": "hospital", "tone": "neutral"},
        {"id": "ed", "label": "Avoidable ED per 1,000", "value": "298", "detail": "Aggregated", "source": "Aggregated claims", "icon": "activity", "tone": "warning", "chip": "Which clinics diverge from their county ED baseline?"},
        {"id": "suppressed", "label": "Small cells", "value": "Suppressed", "detail": "Counts under 11", "source": "Suppression rule", "icon": "eye-off", "tone": "neutral"},
    ],
    "steps": {
        "mb_brief": {"step": 1, "capability": "Proactive Intelligence", "ai": "Good morning, Marcus. Three things for the RHTP program today.",
                     "points": [f"Lander and Pershing concentrate the care gaps: primary care visits down {abs(lander['pcVisitChangePct'])}%, avoidable ED the highest of the six.",
                                "Broadband limits telehealth in the frontier ZIP codes, and the CMS progress report is due."],
                     "sources": ["Aggregated Claims", "CDC PLACES", "HRSA HPSA", "FCC Broadband"],
                     "chips": ["Which counties concentrate the most care gaps?", "Where do broadband dead zones limit telehealth?", "Generate the RHTP report"],
                     "next": "Which counties concentrate the most care gaps?", "viz": ["v_map_ed"]},
        "mb_gaps": {"step": 2, "capability": "Converged Conversation", "asks": ["Which counties concentrate the most care gaps?"],
                    "ai": "Here are the six counties side by side; Lander and Pershing stand out.",
                    "points": ["Cells under 11 members are suppressed."], "sources": ["CDC PLACES", "CDC SVI", "HRSA HPSA", "Aggregated Claims"],
                    "chips": ["Generate the RHTP report", "What public datasets back the county view?", "Open County Explorer"], "next": "Generate the RHTP report",
                    "viz": ["v_county_table"]},
        "mb_datasets": {"capability": "Converged Conversation", "asks": ["What public datasets back the county view?"],
                        "ai": "These public tables are loaded in Postgres right now, with their row counts for Nevada and Tennessee.",
                        "sources": ["All public sources"], "chips": ["Where do broadband dead zones limit telehealth?", "Generate the RHTP report"],
                        "viz": ["v_public_tables"]},
        "mb_bb": {"capability": "Friction Observability", "asks": ["Where do broadband dead zones limit telehealth?", "Where does broadband limit telehealth?"],
                  "ai": "Here is household broadband by county from the Census ACS; where it is low, telehealth rechecks need a phone or mobile clinic fallback.",
                  "sources": ["Census ACS 5-year", "USDA RUCC"], "chips": ["How many clinic sites are telehealth-capable?", "Which counties concentrate the most care gaps?"],
                  "viz": ["v_map_bb", "v_fcc"]},
        "mb_sites": {"capability": "Converged Conversation", "asks": ["How many clinic sites are telehealth-capable?", "How many clinic sites are there?"],
                     "ai": "Here are the HRSA health center sites, rural health clinics and critical access hospitals in each of the six counties; telehealth capability comes from the grantee site registry.",
                     "sources": ["HRSA Health Center Sites", "CMS Provider of Services (via HRSA)"], "chips": ["Where do broadband dead zones limit telehealth?"],
                     "viz": ["v_sites"]},
        "mb_ed": {"capability": "Anomaly Detection", "asks": ["Which clinics diverge from their county ED baseline?"],
                  "ai": "Sierra Basin is highest at 312 avoidable ED visits per 1,000; here are the four networks and the CMS unplanned-visit results for the six counties' hospitals.",
                  "sources": ["Aggregated Claims", "CMS Unplanned Hospital Visits"], "chips": ["Generate the RHTP report"],
                  "viz": ["v_networks", "v_geovar"]},
        "mb_report": {"step": 3, "capability": "Automated Action", "asks": ["Generate the RHTP report", "Generate the CMS progress summary"],
                      "ai": "Here is the RHTP report: people served, services delivered and outcomes by county, sourced and suppressed.",
                      "points": ["Every figure ties to its source; cells under 11 show as a dash."], "sources": ["All aggregated sources"],
                      "chips": ["Export PDF", "Export CSV", "Open RHTP Reporting"], "next": "Open RHTP Reporting", "viz": ["v_cms"]},
        "mb_pdf": {"capability": "Automated Action", "asks": ["Export PDF"], "ai": "The PDF is ready to save.", "sources": ["All aggregated sources"],
                   "chips": ["Export CSV", "Open RHTP Reporting"], "viz": ["v_export_pdf"]},
        "mb_csv": {"capability": "Automated Action", "asks": ["Export CSV"], "ai": "Here is the CSV, with suppressed cells shown as a dash.",
                   "sources": ["All aggregated sources"], "chips": ["Export PDF", "Open RHTP Reporting"], "viz": ["v_export_csv"]},
        "mb_open_rhtp": {"step": 4, "capability": "Automated Action", "asks": ["Open RHTP Reporting"], "ai": "Opening RHTP Reporting, where you own the CMS export.",
                         "sources": ["All aggregated sources"], "chips": ["Export PDF", "Export CSV"],
                         "launch": {"workbench": "rhtpReporting", "filter": "all", "label": "RHTP Reporting", "detail": "people served, services and outcomes", "auto": True},
                         "viz": ["v_launch_rhtp"]},
        "mb_open_ce": {"capability": "Converged Conversation", "asks": ["Open County Explorer"], "ai": "Opening County Explorer, view only.", "sources": ["CDC PLACES", "CDC SVI", "HRSA HPSA", "FCC Broadband"],
                       "chips": ["Which counties concentrate the most care gaps?"],
                       "launch": {"workbench": "countyExplorer", "filter": "all", "label": "County Explorer", "detail": "six counties", "auto": True},
                       "viz": ["v_launch_ce"]},
        "__default__": {"ai": "I can answer on county care gaps, the public datasets, broadband, clinic sites, ED by network and the RHTP report.",
                        "sources": [], "chips": ["Which counties concentrate the most care gaps?", "Generate the RHTP report", "Where do broadband dead zones limit telehealth?"]},
    },
    "queries": ["Which counties concentrate the most care gaps?", "What public datasets back the county view?", "Where do broadband dead zones limit telehealth?",
                "How many clinic sites are telehealth-capable?", "Which clinics diverge from their county ED baseline?", "Generate the RHTP report"],
    "viz": {"v_map_ed": {"type": "rain.county_map", "props": {"mode": "ed"}}, "v_county_table": {"type": "rain.county_table", "props": {}},
            "v_public_tables": q("BEL-P1", "Public datasets loaded in rain_v4.public_data (live row counts)"),
            "v_map_bb": {"type": "rain.county_map", "props": {"mode": "broadband"}},
            "v_fcc": q("BEL-P2", "Households with broadband by county (Census ACS 2020-2024, live)"),
            "v_sites": q("BEL-P3", "Health center sites and rural facilities in the six counties (HRSA, CMS POS, live)"),
            "v_networks": dt("networks"), "v_geovar": q("HAR-P2", "CMS unplanned hospital visits and readmissions, the six counties (live)"),
            "v_cms": {"type": "rain.brief_preview", "props": {"kind": "cms"}},
            "v_export_pdf": {"type": "rain.export_card", "props": {"format": "pdf"}}, "v_export_csv": {"type": "rain.export_card", "props": {"format": "csv"}},
            "v_launch_rhtp": launch("mb_open_rhtp"), "v_launch_ce": launch("mb_open_ce")},
    "handoffs": [],
    "workbenches": [{"id": "rhtpReporting", "access": "full"}, {"id": "countyExplorer", "access": "view"},
                    {"id": "valueInsights", "access": "view", "scope": "state"}],
}

CT["holloway"] = {
    "signals": [],
    "kpis": [
        {"id": "frontier", "label": "Frontier patients", "value": str(len(frontier)), "detail": "Outside Teresa's sites", "source": "Worklist", "icon": "map-pin", "tone": "warning", "chip": "Walk me through today's call list"},
        {"id": "voice", "label": "Voice only", "value": str(len(dh_voice)), "detail": "No SMS consent", "source": "Contact preferences", "icon": "phone", "tone": "critical", "chip": "Which high-risk patients can't be reached by SMS?"},
        {"id": "noreply", "label": "No reply yet", "value": str(len(noreply)), "detail": "Before the cut-off", "source": "SMS reminders", "icon": "message-square", "tone": "warning", "chip": "Who has not replied to their reminders?"},
        {"id": "cuffs", "label": "Cuffs to deliver", "value": str(len(dh_ship)), "detail": "Ship before the visit", "source": "Quality Gate", "icon": "package", "tone": "neutral"},
    ],
    "steps": {
        "dh_brief": {"ai": f"Good morning, Denise. {len(frontier)} frontier patients are on your list, {len(dh_voice)} reachable by voice only, and {len(noreply)} reminders have no reply.",
                     "sources": ["Worklist", "SMS Reminders", "Contact Preferences"],
                     "chips": ["Walk me through today's call list", "Who has not replied to their reminders?", "Which high-risk patients can't be reached by SMS?"],
                     "next": "Walk me through today's call list", "viz": ["v_tasks"]},
        "dh_calls": {"asks": ["Walk me through today's call list", "Open my worklist"], "ai": "Opening your worklist at the frontier patients, highest priority first.",
                     "sources": ["Worklist"], "chips": ["Which of my patients are highest risk?", "Who has not replied to their reminders?"],
                     "launch": {"workbench": "worklist", "filter": "frontier", "label": "Worklist", "detail": "frontier patients", "auto": True}, "viz": ["v_launch_wl"]},
        "dh_risk": {"asks": ["Which of my patients are highest risk?"], "ai": f"Here are your ten highest-priority frontier patients; {frontier[0]['name']} is first.",
                    "sources": ["Worklist", "EHR (FHIR)", "Travel Time (OpenStreetMap)"], "chips": ["Which high-risk patients can't be reached by SMS?", "Walk me through today's call list"],
                    "viz": ["v_top"]},
        "dh_noreply": {"asks": ["Who has not replied to their reminders?"], "ai": f"{len(noreply)} reminders have no reply; each becomes a call task on your list at the 24-hour cut-off.",
                       "sources": ["SMS Reminders"], "chips": ["Walk me through today's call list"], "viz": ["v_noreply"]},
        "dh_social": {"asks": ["Which patients screened positive for a social need?"], "ai": f"{len(dh_social)} of your frontier patients have a social need on file; transportation leads.",
                      "sources": ["Screening Tool", "EHR (FHIR)"], "chips": ["Where do patients lack a vehicle or broadband?"], "viz": ["v_social"]},
        "dh_closed": {"asks": ["What did outreach close this month?"], "ai": "Here is the BP campaign's progress: booked and controlled against the 412.",
                      "sources": ["Worklist", "Remote BP Readings"], "chips": ["Walk me through today's call list"], "viz": ["v_progress"]},
        "dh_nosms": {"asks": ["Which high-risk patients can't be reached by SMS?"], "ai": f"{len(dh_voice)} of your patients have no SMS consent, so it is a call or a home visit.",
                     "sources": ["Contact Preferences"], "chips": ["Which of my patients are highest risk?"], "viz": ["v_voice"]},
        "dh_acs": {"asks": ["Where do patients lack a vehicle or broadband?"], "ai": "Here are the Census ACS household figures for the six counties: no vehicle and no broadband subscription.",
                   "sources": ["Census ACS 5-year"], "chips": ["Which patients screened positive for a social need?"], "viz": ["v_acs"]},
        "__default__": {"ai": "I can help with your call list, the highest-risk patients, non-responders, social needs and who can't be reached by text.",
                        "sources": [], "chips": ["Walk me through today's call list", "Who has not replied to their reminders?"]},
    },
    "queries": ["Walk me through today's call list", "Which of my patients are highest risk?", "Who has not replied to their reminders?",
                "Which patients screened positive for a social need?", "What did outreach close this month?", "Which high-risk patients can't be reached by SMS?"],
    "viz": {"v_tasks": {"type": "rain.task_briefing", "props": {"role": "holloway"}}, "v_launch_wl": launch("dh_calls"),
            "v_top": dt("dh_top"), "v_noreply": dt("dh_noreply"), "v_social": dt("dh_social"), "v_progress": {"type": "rain.campaign_progress", "props": {}},
            "v_voice": dt("dh_voice"), "v_acs": q("HOL-P1", "No vehicle and no broadband, the six counties (Census ACS, live)")},
    "handoffs": [],
    "workbenches": [{"id": "worklist", "access": "full", "scope": "frontier"}, {"id": "scheduling", "access": "full"},
                    {"id": "reminders", "access": "view"}],
}

bm = SITES[BROOKS_SITE]["name"]
CT["brooks"] = {
    "signals": [],
    "kpis": [
        {"id": "inbox", "label": "Inbox items open", "value": str(sum(1 for x in inbox if x["status"] == "Open")), "source": "Front-desk inbox", "icon": "inbox", "tone": "warning", "chip": "Open the front-desk inbox"},
        {"id": "pending", "label": "Bookings waiting", "value": str(len(kb_pending)), "detail": f"{bm} patients", "source": "Worklist hand-off", "icon": "calendar", "tone": "neutral", "chip": "Show me this week's confirmations board"},
        {"id": "voice", "label": "No SMS consent", "value": str(len(kb_voice)), "detail": "Voice reminders only", "source": "Contact preferences", "icon": "phone", "tone": "critical", "chip": "Which patients have no SMS consent on file?"},
        {"id": "campaign", "label": "Campaign patients", "value": str(len(kb_members)), "detail": f"{len(kb_booked)} booked", "source": "Quality Gate", "icon": "users", "tone": "neutral"},
    ],
    "steps": {
        "kb_brief": {"ai": f"Good morning, Kayla. {sum(1 for x in inbox if x['status'] == 'Open')} inbox items are open at {bm}, and {len(kb_voice)} patients can only get voice reminders.",
                     "sources": ["Front-desk Inbox", "SMS Reminders", "EHR Schedule"],
                     "chips": ["Open the front-desk inbox", "Show me this week's confirmations board", "Which booked visits carry the highest no-show risk?"],
                     "next": "Open the front-desk inbox", "viz": ["v_tasks"]},
        "kb_inbox": {"asks": ["Open the front-desk inbox"], "ai": "Opening the front-desk inbox: free-text replies, clinical questions, bad numbers and coverage flags.",
                     "sources": ["Front-desk Inbox"], "chips": ["Show me this week's confirmations board", "Run eligibility checks for this week's bookings"],
                     "launch": {"workbench": "frontDeskInbox", "filter": "open", "label": "Front-desk inbox", "detail": f"{bm}", "auto": True}, "viz": ["v_launch_inbox"]},
        "kb_board": {"asks": ["Show me this week's confirmations board"], "ai": f"Here is the confirmations board for {bm}.", "sources": ["SMS Reminders", "EHR Schedule"],
                     "chips": ["Who has not confirmed their visit yet?", "Which booked visits carry the highest no-show risk?"], "viz": ["v_board"]},
        "kb_noshow": {"asks": ["Which booked visits carry the highest no-show risk?"], "ai": "These patients carry the highest no-show risk, so they get reminders at 72, 24 and 3 hours.",
                      "sources": ["Pattern Profiles", "Travel Time (OpenStreetMap)"], "chips": ["Show me open telehealth slots across nearby clinics"], "viz": ["v_noshow"]},
        "kb_slots": {"asks": ["Show me open telehealth slots across nearby clinics", "Show open telehealth slots"],
                     "ai": "Here are the open slots, and the public drive times from Battle Mountain to the nearest health center sites.",
                     "sources": ["EHR Schedule", "HRSA Health Center Sites", "Travel Time (OpenStreetMap)"], "chips": ["Open Scheduling"],
                     "viz": ["v_slots", "v_drive"]},
        "kb_elig": {"asks": ["Run eligibility checks for this week's bookings"], "ai": f"Coverage for {bm}'s pending bookings: a lapsed result still books and creates an enrollment-assist task.",
                    "sources": ["Eligibility (270/271)"], "chips": ["Open the front-desk inbox"], "viz": ["v_elig"]},
        "kb_unconfirmed": {"asks": ["Who has not confirmed their visit yet?"], "ai": "These visits have no reply yet; at the cut-off each becomes a CHW call task.",
                           "sources": ["SMS Reminders"], "chips": ["Show me this week's confirmations board"], "viz": ["v_unconfirmed"]},
        "kb_nosms": {"asks": ["Which patients have no SMS consent on file?"], "ai": f"{len(kb_voice)} patients have no SMS consent, so their reminders go by voice.",
                     "sources": ["Contact Preferences"], "chips": ["Show me this week's confirmations board"], "viz": ["v_nosms"]},
        "kb_open_sched": {"asks": ["Open Scheduling"], "ai": f"Opening Scheduling at {bm}.", "sources": ["EHR Schedule"], "chips": ["Open the front-desk inbox"],
                          "launch": {"workbench": "scheduling", "filter": "next", "label": "Scheduling", "detail": f"{bm} site", "auto": True}, "viz": ["v_launch_sched"]},
        "__default__": {"ai": "I can help with the inbox, the confirmations board, no-show risk, open slots, eligibility and SMS consent.",
                        "sources": [], "chips": ["Open the front-desk inbox", "Show me this week's confirmations board"]},
    },
    "queries": ["Show me this week's confirmations board", "Which booked visits carry the highest no-show risk?", "Show me open telehealth slots across nearby clinics",
                "Run eligibility checks for this week's bookings", "Who has not confirmed their visit yet?", "Which patients have no SMS consent on file?"],
    "viz": {"v_tasks": {"type": "rain.task_briefing", "props": {"role": "brooks"}}, "v_launch_inbox": launch("kb_inbox"), "v_board": dt("kb_board"),
            "v_noshow": dt("kb_noshow"), "v_slots": {"type": "context", "props": {"kind": "slots"}},
            "v_drive": q("BRK-P1", "Drive time from Battle Mountain ZIP 89820 to the nearest health center sites (OpenStreetMap, live)"),
            "v_elig": dt("kb_eligibility"), "v_unconfirmed": dt("reminders_unconfirmed"), "v_nosms": dt("kb_nosms"), "v_launch_sched": launch("kb_open_sched")},
    "handoffs": [],
    "workbenches": [{"id": "frontDeskInbox", "access": "full", "scope": f"site:{BROOKS_SITE}"},
                    {"id": "scheduling", "access": "full", "scope": f"site:{BROOKS_SITE}"},
                    {"id": "reminders", "access": "full", "scope": f"site:{BROOKS_SITE}"}],
}

CT["okafor"] = {
    "signals": [],
    "kpis": [
        {"id": "visits", "label": "Visits this week", "value": str(len(previsit)), "detail": "Confirmed", "source": "EHR schedule", "icon": "calendar", "tone": "neutral", "chip": "Walk me through this week's schedule"},
        {"id": "telehealth", "label": "Telehealth share", "value": f"{pct(so_modes['Telehealth'], len(previsit))}%", "source": "EHR schedule", "icon": "video", "tone": "good", "chip": "How much of my schedule is telehealth?"},
        {"id": "coding", "label": "Coding recapture due", "value": str(sum(1 for p in previsit if p["codingRecapture"])), "detail": "Of the 73-member list", "source": "EHR + claims", "icon": "file-check", "tone": "warning", "chip": "Which of today's patients need coding recapture?"},
        {"id": "adherence", "label": "Adherence gaps", "value": str(sum(1 for p in previsit if p["adherence"] != "On track")), "detail": "Under 80%", "source": "Medication history", "icon": "pill", "tone": "critical", "chip": "Who has a medication adherence gap before their visit?"},
    ],
    "steps": {
        "so_brief": {"ai": f"Good morning, Dr. Okafor. You have {len(previsit)} confirmed visits this week, each with a pre-visit summary.",
                     "sources": ["EHR Schedule", "Risk Engine", "Medication History"],
                     "chips": ["Walk me through this week's schedule", "Which of my patients are rising risk?", "Which of today's patients need coding recapture?"],
                     "next": "Walk me through this week's schedule", "viz": ["v_tasks"]},
        "so_week": {"asks": ["Walk me through this week's schedule"], "ai": f"Here is your week: {len(previsit)} confirmed visits.",
                    "sources": ["EHR Schedule"], "chips": ["Open the pre-visit summary", "How much of my schedule is telehealth?"], "viz": ["v_week"]},
        "so_tele": {"asks": ["How much of my schedule is telehealth?"], "ai": f"{pct(so_modes['Telehealth'], len(previsit))}% of this week's visits are telehealth.",
                    "sources": ["EHR Schedule"], "chips": ["Walk me through this week's schedule"], "viz": ["v_modes"]},
        "so_risk": {"asks": ["Which of my patients are rising risk?"], "ai": "Here are this week's patients by risk tier with the top reasons; you decide what changes clinically.",
                    "sources": ["Risk Engine", "EHR (FHIR)"], "chips": ["Who has a medication adherence gap before their visit?"], "viz": ["v_risk"]},
        "so_adh": {"asks": ["Who has a medication adherence gap before their visit?"], "ai": "These patients show an adherence gap, so it is in their pre-visit summary.",
                   "sources": ["Medication History"], "chips": ["Show me the latest remote monitoring readings"], "viz": ["v_adh"]},
        "so_readings": {"asks": ["Show me the latest remote monitoring readings"], "ai": "Here are the latest blood pressure readings for this week's patients.",
                        "sources": ["Remote BP Readings"], "chips": ["What counts for the BP control measure?"], "viz": ["v_readings"]},
        "so_coding": {"asks": ["Which of today's patients need coding recapture?"], "ai": "These patients have chronic conditions to recapture at the visit.",
                      "sources": ["EHR (FHIR)", "Claims"], "chips": ["Review the standing orders"], "viz": ["v_coding"]},
        "so_orders": {"asks": ["Review the standing orders"], "ai": "Here are the BP campaign's standing orders for your patients; you approve them.",
                      "sources": ["Care Plan Templates"], "chips": ["Open the pre-visit summary"], "viz": ["v_orders"]},
        "so_ecqm": {"asks": ["What counts for the BP control measure?"], "ai": "Here is the public CMS specification for the measures in the quality gate; home cuff readings count for CMS165.",
                    "sources": ["CMS eCQMs"], "chips": ["Show me the latest remote monitoring readings"], "viz": ["v_ecqm"]},
        "so_open": {"asks": ["Open the pre-visit summary"], "ai": "Opening the pre-visit summaries for this week.", "sources": ["EHR Schedule", "Risk Engine"],
                    "chips": ["Which of my patients are rising risk?"],
                    "launch": {"workbench": "preVisitSummary", "filter": "week", "label": "Pre-visit Summary", "detail": "this week's visits", "auto": True},
                    "viz": ["v_launch_pv"]},
        "__default__": {"ai": "I can help with your week, rising-risk patients, adherence gaps, readings, coding recapture and standing orders.",
                        "sources": [], "chips": ["Walk me through this week's schedule", "Which of my patients are rising risk?"]},
    },
    "queries": ["Walk me through this week's schedule", "How much of my schedule is telehealth?", "Which of my patients are rising risk?",
                "Who has a medication adherence gap before their visit?", "Show me the latest remote monitoring readings", "Which of today's patients need coding recapture?"],
    "viz": {"v_tasks": {"type": "rain.task_briefing", "props": {"role": "okafor"}}, "v_week": dt("so_week"), "v_modes": dt("so_modes"), "v_risk": dt("so_risk"),
            "v_adh": dt("so_adherence"), "v_readings": dt("so_readings"), "v_coding": dt("so_coding"), "v_orders": dt("so_orders"),
            "v_ecqm": q("OKA-P1", "CMS eCQM specifications in the quality gate (eCQI Resource Center, live)"), "v_launch_pv": launch("so_open")},
    "handoffs": [],
    "workbenches": [{"id": "preVisitSummary", "access": "full"}, {"id": "scheduling", "access": "view"}, {"id": "worklist", "access": "view"}],
}

S["client"]["branding"] = {**S["client"]["branding"], "tagline": "Value-Based Care and Population Health Intelligence"}
seed["note"] = ("RAIN v0.4 UI data (PRD v0.4, 11 operator personas + 2 patients). Built by scripts/e2e/make_v4_ui_seed.py from the "
                "v0.3 seed; the v0.2 personas' figures are derived from the same Q3 records. Synthetic data for a demo.")
OUT.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {OUT.relative_to(ROOT)}: {len(CT)} contracts, {len(DS)} datasets, records {[(k, len(v)) for k, v in REC.items()]}")
print("frontier", len(frontier), "voice", len(dh_voice), "noreply", len(noreply), "brooks members", len(kb_members),
      "pending", len(kb_pending), "previsit", len(previsit), "hargrove members", len(hg_members))
