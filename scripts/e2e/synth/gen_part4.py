# Part 4 (executed in gen_synthetic_v4's namespace): the impactability model, scheduling and the front desk,
# social needs, broadband, ADT, record matching, contracts, benchmarks and planning assumptions.
from synth_ref import LOW_BB_ZIPS as _LOW_BB  # noqa: E402

PNAME = {"ceo": "Gregory Haskins", "cmo": "Dr. Naomi Castellanos", "cio": "Raj Malhotra"}

# ═══ H. Impactability model: v1.3 (released) and v1.4 (candidate, access-adjusted) ═══════════════════════
SUB = {g["group"]: g for g in GOV["SUBGROUP"]}
GROUP_LABEL = {"Hypertension": "Hypertension", "Type 2 diabetes": "Diabetes", "COPD or asthma": "COPD or asthma",
               "Heart failure": "Heart failure", "Depression": "Depression"}
IMP = [p for p in SB if PATIENTS[p]["segment"] == "impactable"]


def cell_of(pid):
    p = PATIENTS[pid]
    return GROUP_LABEL.get(p.get("primary")), p["frontier"]


def target(pid, after):
    g, fr = cell_of(pid)
    if g is None:
        return 50 if not fr else (48 if after else 41)
    return SUB[g]["town"] if not fr else (SUB[g]["frontierAfter"] if after else SUB[g]["frontier"])


noise = {pid: R.gauss(0, 11) for pid in IMP}
S13 = {pid: target(pid, False) + noise[pid] for pid in IMP}
S14 = {pid: target(pid, True) + noise[pid] + R.gauss(0, 2) for pid in IMP}
for S, after in ((S13, False), (S14, True)):           # exact cell means, then clip to 1..99
    cells = defaultdict(list)
    for pid in IMP:
        cells[cell_of(pid)].append(pid)
    for key, pids in cells.items():
        shift = target(pids[0], after) - sum(S[p] for p in pids) / len(pids)
        for p in pids:
            S[p] = min(99.0, max(1.0, S[p] + shift))


def ranked(S, fixed, keep_top=None):
    rest = sorted((p for p in IMP if p not in SWAPS), key=lambda p: -S[p])
    if keep_top is not None:        # v1.4 reorders inside the two groups; only the 114 swap members cross rank 300
        rest = [p for p in rest if p in keep_top] + [p for p in rest if p not in keep_top]
    order = list(rest)
    for pid, rk in sorted(fixed.items(), key=lambda x: x[1]):
        order.insert(rk - 1, pid)
    # scores follow the ranking: swap members sit between their neighbours, nobody outranks a higher score
    for i, pid in enumerate(order):
        if pid in SWAPS:
            nxt = next((S[q] for q in order[i + 1:] if q not in SWAPS), 1.0)
            prv = S[order[i - 1]] if i else 99.0
            S[pid] = (prv + nxt) / 2
        if i and S[pid] > S[order[i - 1]]:
            S[pid] = S[order[i - 1]]
    return order


TOP = C["COHORT"]["topRanked"]


def unique_ranks(key):
    """The story list has tied ranks; a ranking cannot. Move each tie to the nearest free rank on the same side of 300."""
    taken, out = set(), {}
    for s in sorted(GOV["swaps"], key=lambda s: (s[key], s["id"])):
        r0, top_side = s[key], s[key] <= TOP
        for d in range(0, 400):
            for r in (r0 + d, r0 - d):
                if r >= 1 and r not in taken and (r <= TOP) == top_side:
                    break
            else:
                continue
            break
        taken.add(r)
        out[s["id"]] = r
    return out


FIX13, FIX14 = unique_ranks("rankBefore"), unique_ranks("rankAfter")
ORDER13 = ranked(S13, FIX13)
top13_rest = {p for p in ORDER13[:TOP] if p not in SWAPS}
ORDER14 = ranked(S14, FIX14, keep_top=top13_rest)
for s in GOV["swaps"]:
    assert ORDER13.index(s["id"]) + 1 == FIX13[s["id"]] and ORDER14.index(s["id"]) + 1 == FIX14[s["id"]], s["id"]
    assert (FIX13[s["id"]] <= TOP) != (FIX14[s["id"]] <= TOP), s["id"]
RANK13 = {p: i + 1 for i, p in enumerate(ORDER13)}
RANK14 = {p: i + 1 for i, p in enumerate(ORDER14)}
avoided = sorted(spread(C["COHORT"]["avoidedCost12m"], TOP), reverse=True)
for pid in SB:
    seg = PATIENTS[pid]["segment"]
    if seg == "impactable":
        sc13, sc14 = S13[pid], S14[pid]
        cost13 = avoided[RANK13[pid] - 1] if RANK13[pid] <= TOP else round(R.uniform(400, 2200), 2)
    else:
        sc13 = R.uniform(80, 99) if seg == "highNeed" else R.uniform(1, 35)
        sc14, cost13 = sc13, round(R.uniform(100, 900), 2)
    T["impactability_score"].append({"score_id": nid("IMP-", 7), "patient_id": pid, "model_version": "v1.3", "score": round(sc13, 2),
                                     "segment": seg, "outreach_rank": RANK13.get(pid), "predicted_cost_avoided": cost13,
                                     "computed_at": ts(date(2026, 10, 15), 4)})
    if seg == "impactable":
        T["impactability_score"].append({"score_id": nid("IMP-", 7), "patient_id": pid, "model_version": "v1.4", "score": round(sc14, 2),
                                         "segment": seg, "outreach_rank": RANK14[pid], "predicted_cost_avoided": None,
                                         "computed_at": ts(date(2026, 10, 30), 4)})
T["model_card"] += [
    {"model_version": "v1.3", "model_name": C["MODEL"]["name"], "purpose": "Rank members whose costs a care-team action can change",
     "feature_summary": "Prior cost, primary care visits, ED visits, chronic conditions, latest BP and HbA1c, open gaps",
     "access_adjusted_flag": False, "release_status": "released", "signed_off_by": PNAME["cio"], "cosigned_by": PNAME["cmo"],
     "released_at": ts(date(2026, 4, 1)), "auc": 0.79, "release_threshold_pct": 5},
    {"model_version": "v1.4", "model_name": C["MODEL"]["name"], "purpose": "v1.3 plus access features so distance is not read as low need",
     "feature_summary": "v1.3 features plus drive time, broadband, missed appointments and shortage-area status",
     "access_adjusted_flag": True, "release_status": "candidate", "signed_off_by": None, "cosigned_by": None, "released_at": None,
     "auc": C["MODEL"]["auc"], "release_threshold_pct": 5}]
for f in GOV["FEATURES"]:
    for ver in (["v1.3", "v1.4"] if f["kind"] == "Current" else ["v1.4"]):
        T["model_feature"].append({"model_feature_id": nid("MF-", 4), "model_version": ver, "feature_code": f["id"], "feature_name": f["name"],
                                   "weight": f["weight"], "kind": f["kind"], "note": f["note"]})
for ver, S in (("v1.3", S13), ("v1.4", S14)):
    for g in list(SUB) + ["All chronic groups"]:
        town = [S[p] for p in IMP if not PATIENTS[p]["frontier"] and (g == "All chronic groups" and cell_of(p)[0] or cell_of(p)[0] == g)]
        fr = [S[p] for p in IMP if PATIENTS[p]["frontier"] and (g == "All chronic groups" and cell_of(p)[0] or cell_of(p)[0] == g)]
        gap = (sum(town) / len(town) - sum(fr) / len(fr)) / (sum(town) / len(town)) * 100
        T["subgroup_check"].append({"model_version": ver, "subgroup": f"Frontier: {g}", "comparison_group": f"Town: {g}",
                                    "metric": "mean impactability score", "gap_percent": round(gap, 1), "threshold_percent": 5,
                                    "passed": gap <= 5})
print(f"impactability rows {len(T['impactability_score'])}")

# ═══ I. Scheduling, reminders, the front desk, pre-visit summaries ═══════════════════════════════════════
HALE = add_provider("Owen", "Hale", "Family Medicine", "winnemucca", pid="PRV-HALE")
T["clinic_site"].append({"clinic_site_id": "sb-mobile", "site_name": "Sierra Basin Mobile Clinic", "site_type": "Mobile clinic",
                         "address": "Rotating stops, Battle Mountain, NV 89820", "county_fips": COUNTY_FIPS["lander"],
                         "latitude": ZIPS["89820"]["lat"], "longitude": ZIPS["89820"]["lon"], "telehealth_capable": False, "grantee_id": "sbch"})
MOBILE = add_provider("Mobile", "team", "Mobile clinic team", "sb-mobile", pid="PRV-MOBILE")
PROV_BY_NAME = {"Dr. Ana Ruiz": RUIZ, "Jordan Pace, NP": PACE, "Dr. Owen Hale": HALE, "Mobile team": MOBILE}
SCHED = {}


def schedule_for(prov, site, category):
    key = (prov, site, category)
    if key not in SCHED:
        SCHED[key] = nid("SCH-", 4)
        T["schedule"].append({"schedule_id": SCHED[key], "provider_id": prov, "clinic_site_id": site, "service_category": category,
                              "horizon_start": date(2026, 10, 1), "horizon_end": date(2026, 11, 30)})
    return SCHED[key]


def parse_when(day, time_):
    """'Thu, Nov 5' or 'Mon, Nov 9' (+ '2:00 PM') -> datetime in November 2026."""
    d = int(re.search(r"(\d+)$", day.strip()).group(1))
    hh, mm_ap = time_.split(":")
    mm, ap = mm_ap.split()
    h = int(hh) % 12 + (12 if ap.upper() == "PM" else 0)
    return datetime(2026, 11, d, h, int(mm))


def add_slot(prov, site, category, start, tele, status="open", code=None):
    sid_ = code or nid("SLT-", 5)
    T["slot"].append({"slot_id": sid_, "schedule_id": schedule_for(prov, site, category), "slot_start": start,
                      "slot_end": start + timedelta(minutes=30), "status": status, "telehealth_flag": tele})
    return sid_


def add_appt(pid, start, prov, site, mode, status, via="front desk", booked_at=None, link=None, visit_type=None):
    tele = mode == "telehealth"
    slot_ = add_slot(prov, "sb-mobile" if mode == "mobile" else site, {"telehealth": "telehealth", "mobile": "mobile clinic"}.get(mode, "primary care"),
                     start, tele, status="booked")
    aid = nid("APT-", 6)
    T["appointment"].append({"appointment_id": aid, "slot_id": slot_, "patient_id": pid, "provider_id": prov, "visit_mode": mode,
                             "status": status, "booked_via": via, "booked_at": booked_at or start - timedelta(days=R.randint(5, 20)),
                             "no_show_risk": None, "visit_type": visit_type or "BP recheck", "visit_link": link})
    return aid


# I1. the open slots offered to Linda for her BP recheck (S1-S6)
for s in REC["slots"]:
    start = parse_when(s["day"], s["time"])
    prov = PROV_BY_NAME[s["provider"]]
    if s["mode"].startswith("Telehealth"):
        add_slot(prov, "elko", "telehealth", start, True, code=s["id"])
    elif s["mode"] == "Mobile clinic":
        add_slot(prov, "sb-mobile", "mobile clinic", start, False, code=s["id"])
    else:
        add_slot(prov, "winnemucca", "primary care", start, False, code=s["id"])
# Linda's drive to each place a slot is offered (her home site is 81 minutes away; the mobile clinic stops 14 minutes out)
for site_, mins in (("winnemucca", 81), ("sb-mobile", 14)):
    T["travel_time"].append({"travel_time_id": nid("TT-", 7), "patient_zcta": "89820", "clinic_site_id": site_, "drive_minutes": mins,
                             "computed_at": ts(date(2026, 10, 1)), "patient_id": CAMP["M-40107"]["id"]})
# I2. visit history for the last 12 months (completed and missed visits) -> no-show rates
MISSED = {m["id"]: int(re.search(r"\d+", m["lastContact"]).group()) for m in REC["campaignMembers"] if m["lastContact"].startswith("Missed")}
MISSED[ROSA["memberId"]] = ROSA["missedVisits"]
history = list(CAMP) + [ROSA["memberId"]] + [p for p in R.sample(SB, 1500) if p not in CAMP and p != ROSA["memberId"]]
for pid in history:
    p = PATIENTS[pid]
    missed = MISSED.get(pid, 0 if pid in CAMP else (1 if (p["frontier"] and R.random() < 0.18) else 0))
    done = R.randint(1, 4)
    for i in range(missed + done):
        d = rnd_date(date(2025, 11, 4), date(2026, 10, 25))
        add_appt(pid, ts(d, R.randint(8, 16)), R.choice(PROVIDERS[p["site"]]), p["site"],
                 "telehealth" if R.random() < 0.2 else "in person", "no-show" if i < missed else "completed",
                 visit_type="Diabetes follow-up" if pid == ROSA["memberId"] else "Primary care")
# I3. the BP campaign's booked visits (62): October visits, 18 of them already controlled
for m in REC["campaignMembers"]:
    if m["status"] == "Reached and booked":
        d = day_in(2026, 10, 6, 30)
        add_appt(m["id"], ts(d, R.randint(8, 16)), RUIZ if m["mode"] == "Telehealth" else R.choice(PROVIDERS[m["siteId"]]), m["siteId"],
                 m["mode"].lower(), "completed", booked_at=ts(d - timedelta(days=4), 10))
# I4. reminders: tomorrow's 9 visits with no reply, 4 change requests (R), Linda's booked video visit
APPT_OF = {}
for r_ in REC["reminders"]:
    pid = r_["memberId"]
    p = PATIENTS[pid]
    visit = r_["visit"]
    when, where = [x.strip() for x in re.split("\\s[\u00b7\u2014\u2013-]\\s", visit, maxsplit=1)]
    if when.startswith("Tomorrow"):
        start = parse_when("Nov 4", when.split(",", 1)[1].strip())
    else:
        parts = [x.strip() for x in when.split(",")]
        start = parse_when(parts[-2], parts[-1])
    mode = "telehealth" if where == "video" else "in person"
    site = p["site"] if mode == "telehealth" else next(s for s in SITES if SITES[s]["name"] == where)
    prov = (RUIZ if pid == "M-40107" else R.choice([RUIZ, PACE])) if mode == "telehealth" else R.choice(PROVIDERS[site])
    booked_at = ts(AS_OF, 8, 15) if "R" in r_["status"] or pid == "M-40107" else ts(AS_OF - timedelta(days=9), 11)
    link = C["LINDA"]["link"] if pid == "M-40107" else None
    if pid == "M-40107":       # Linda took slot S1
        slot_row = next(x for x in T["slot"] if x["slot_id"] == "S1")
        slot_row["status"] = "booked"
        aid = nid("APT-", 6)
        T["appointment"].append({"appointment_id": aid, "slot_id": "S1", "patient_id": pid, "provider_id": prov, "visit_mode": mode,
                                 "status": "booked", "booked_via": "front desk", "booked_at": booked_at, "no_show_risk": None,
                                 "visit_type": "BP recheck", "visit_link": link})
    else:
        aid = add_appt(pid, start, prov, site, mode, "booked", booked_at=booked_at)
    APPT_OF[pid] = aid
    offsets = [72, 24, 3] if "72" in r_["plan"] else [24, 3]
    for off in offsets:
        due = start - timedelta(hours=off)
        sent = r_["status"] == "No reply yet" and off == 24
        T["reminder_message"].append({"message_id": nid("MSG-", 6), "appointment_id": aid, "patient_id": pid,
                                      "channel": CAMP[pid]["channel"] if pid in CAMP else "SMS", "language": r_["language"],
                                      "template": "reminder", "offset_hours": off, "sent_at": ts(AS_OF, 8) if sent else None,
                                      "delivery_status": "delivered" if sent else "scheduled", "reply": None, "replied_at": None,
                                      "scheduled_for": due})
    if "R" in r_["status"]:
        T["reminder_message"].append({"message_id": nid("MSG-", 6), "appointment_id": aid, "patient_id": pid, "channel": "SMS",
                                      "language": r_["language"], "template": "booking_confirmation", "offset_hours": None,
                                      "sent_at": ts(AS_OF, 8, 15), "delivery_status": "delivered", "reply": "R",
                                      "replied_at": ts(AS_OF, 8, 40), "scheduled_for": ts(AS_OF, 8, 15)})
# I5. Rosa's diabetes follow-up (high no-show band: reminders at 72, 24 and 3 hours, the 24-hour one offers telehealth)
rv = ROSA["visit"]
rosa_start = parse_when(rv["date"], rv["time"])
ROSA_APPT = add_appt(ROSA["memberId"], rosa_start, R.choice(PROVIDERS["fallon"]), "fallon", "in person", "booked",
                     booked_at=ts(date(2026, 10, 20), 10), link=ROSA["link"], visit_type=ROSA["visitType"])
for off in (72, 24, 3):
    T["reminder_message"].append({"message_id": nid("MSG-", 6), "appointment_id": ROSA_APPT, "patient_id": ROSA["memberId"],
                                  "channel": "SMS", "language": ROSA["language"],
                                  "template": "reminder_offer_telehealth" if off == 24 else "reminder", "offset_hours": off,
                                  "sent_at": None, "delivery_status": "scheduled", "reply": None, "replied_at": None,
                                  "scheduled_for": rosa_start - timedelta(hours=off)})
T["eligibility_check"].append({"patient_id": ROSA["memberId"], "appointment_id": ROSA_APPT, "payer": C["ORG"]["plan"],
                               "coverage_status": "active", "response_code": "1", "checked_at": ts(date(2026, 10, 20), 10, 5)})
for ch, consent in (("SMS", True), ("Voice (IVR)", True)):
    T["contact_preference"].append({"preference_id": nid("PREF-", 7), "patient_id": ROSA["memberId"], "channel": ch, "language": ROSA["language"],
                                    "consent_flag": consent, "quiet_hours_start": "20:00", "quiet_hours_end": "08:00",
                                    "updated_at": ts(date(2026, 6, 1)), "best_time": "Mornings", "phone_note": ROSA["phoneNote"]})
# I6. Dr. Okafor's week: 8 confirmed visits with a pre-visit summary
for v in REC["previsitSummaries"]:
    start = parse_when(v["day"], v["time"])
    mode = "telehealth" if v["mode"] == "Telehealth" else "in person"
    site = "battleMountain" if PATIENTS[v["memberId"]]["site"] not in ("battleMountain", "lovelock") else PATIENTS[v["memberId"]]["site"]
    aid = add_appt(v["memberId"], start, OKAFOR, site, mode, "confirmed", booked_at=ts(date(2026, 10, 28), 10))
    T["previsit_summary"].append({"previsit_summary_id": v["id"], "appointment_id": aid, "patient_id": v["memberId"], "provider_id": OKAFOR,
                                  "risk_tier": None, "top_reasons": None, "open_gap_count": None, "adherence_gap_flag": None,
                                  "latest_bp": None, "coding_recapture_flag": None, "generated_at": ts(AS_OF, 6)})
    if v["codingRecapture"] and v["memberId"] not in UNRECAPTURED:
        add_condition(v["memberId"], "Chronic kidney disease", documented=2025, recaptured=None)
# I7. medications: antihypertensives and metformin, adherence (proportion of days covered); 3 of Okafor's patients under 80%
under80 = {v["memberId"] for v in REC["previsitSummaries"] if v["adherence"].startswith("Under")}
on_track = {v["memberId"] for v in REC["previsitSummaries"]} - under80
for pid in sorted(HTN) + [p for p in DIAB if p not in HTN]:
    meds = []
    if pid in HTN:
        meds.append(R.choice([("314076", "lisinopril 10 MG"), ("197361", "amlodipine 5 MG"), ("310798", "hydrochlorothiazide 25 MG")]))
    if "Type 2 diabetes" in PATIENTS[pid]["conditions"]:
        meds.append(("860975", "metformin 500 MG"))
    for code, _ in meds:
        adh = (R.uniform(0.55, 0.78) if pid in under80 else R.uniform(0.82, 0.99) if pid in on_track
               else (R.uniform(0.5, 0.79) if R.random() < 0.22 else R.uniform(0.8, 1.0)))
        T["medication"].append({"medication_id": nid("MED-", 7), "patient_id": pid, "rxnorm_code": code,
                                "start_date": rnd_date(date(2019, 1, 1), date(2025, 12, 31)), "end_date": None,
                                "adherence_ratio": round(adh, 2)})
# I8. no-show rates from the visit history, appointment risk bands
hist = defaultdict(lambda: [0, 0])
for a in T["appointment"]:
    if a["status"] in ("completed", "no-show"):
        hist[a["patient_id"]][0] += 1
        hist[a["patient_id"]][1] += a["status"] == "no-show"
for pid, (n, ns) in hist.items():
    T["no_show_rate"].append({"no_show_rate_id": nid("NSR-", 6), "patient_id": pid, "visit_type": "all", "window_months": 12,
                              "scheduled_count": n, "no_show_count": ns, "rate": round(ns / n, 3), "computed_at": ts(AS_OF, 5)})
for a in T["appointment"]:
    if a["status"] in ("booked", "confirmed"):
        n, ns = hist.get(a["patient_id"], (0, 0))
        drive = PATIENTS[a["patient_id"]]["drive"]
        # probability of a no-show; bands (metrics_v4): High >= 0.35, Medium >= 0.18, else Low
        a["no_show_risk"] = round(min(0.95, 0.06 + 0.15 * ns + 0.002 * max(0, drive - 30)), 3)
# I9. eligibility (270/271) for the 23 pending bookings: one lapsed; plus the coverage flag in the inbox
for b in REC["pendingBookings"]:
    T["eligibility_check"].append({"patient_id": b["memberId"], "appointment_id": APPT_OF.get(b["memberId"]), "payer": b["planName"],
                                   "coverage_status": b["eligibility"].lower(), "response_code": "1" if b["eligibility"] == "Active" else "6",
                                   "checked_at": ts(AS_OF, 7, 30)})
# I10. the front-desk inbox (Battle Mountain)
for it in REC["inboxItems"]:
    hh, rest_ = it["received"].split(", ")[1].split(":")
    mm_, ap = rest_.split()
    rec_at = datetime(AS_OF.year, AS_OF.month, AS_OF.day, int(hh) % 12 + (12 if ap == "PM" else 0), int(mm_))
    T["inbox_item"].append({"inbox_item_id": it["id"], "clinic_site_id": "battleMountain", "patient_id": it["memberId"],
                            "appointment_id": APPT_OF.get(it["memberId"]), "item_type": it["type"], "message_text": it["message"],
                            "received_at": rec_at, "status": it["status"].lower(),
                            "resolved_by": "Kayla Brooks" if it["status"] == "Resolved" else None})
    if it["type"] == "Coverage flag":
        T["eligibility_check"].append({"patient_id": it["memberId"], "appointment_id": APPT_OF.get(it["memberId"]), "payer": C["ORG"]["plan"],
                                       "coverage_status": "inactive", "response_code": "6", "checked_at": rec_at})
print(f"appointments {len(T['appointment'])}, reminders {len(T['reminder_message'])}, slots {len(T['slot'])}")

# ═══ J. Social needs, broadband, ADT, home monitoring, record matching ══════════════════════════════════
DOMAIN = {"Transportation": ("71802-3", "Z59.82"), "Food": ("88124-3", "Z59.41"), "Housing": ("71802-3", "Z59.00"),
          "Utilities": ("96779-4", "Z59.12")}
need_of = {m["id"]: set(m["socialNeeds"]) for m in REC["campaignMembers"]}
for sid, pct in C["SITE_SOCIAL"].items():
    members = [p for p in SB if PATIENTS[p]["site"] == sid]
    forced = [p for p in members if need_of.get(p)]
    rest_ = [p for p in members if not need_of.get(p)]
    R.shuffle(rest_)
    screened = forced + rest_[: round(len(members) * pct / 100) - len(forced)]
    for pid in screened:
        d = rnd_date(date(2025, 11, 1), date(2026, 10, 31))
        for dom, (loinc, z) in DOMAIN.items():
            pos = dom in need_of.get(pid, ()) or (pid not in CAMP and R.random() < 0.07)
            T["sdoh_screening"].append({"screening_id": nid("SDH-", 7), "patient_id": pid, "domain": dom, "loinc_code": loinc,
                                        "z_code": z if pos else None, "response": "positive" if pos else "negative",
                                        "screened_at": ts(d, 10)})
# broadband by ZIP (FCC BDC is blocked here, so this is a labelled synthetic stand-in): six frontier ZIPs lack video speeds
for z, info in ZIPS.items():
    low = z in _LOW_BB
    T["broadband_coverage"].append({"coverage_id": nid("BB-", 4), "county_fips": COUNTY_FIPS[info["county"]], "zcta": z,
                                    "technology": "Licensed fixed wireless" if low else "Cable / fiber", "max_down_mbps": R.randint(3, 9) if low else R.choice([100, 300, 1000]),
                                    "max_up_mbps": 1 if low else R.choice([10, 20, 35]), "served_flag": not low,
                                    "household_pct": R.randint(20, 38) if low else R.randint(70, 95)})
for cid, c in COUNTIES.items():
    T["county_metric"].append({"county_metric_id": nid("CMX-", 5), "county_fips": COUNTY_FIPS[cid], "zcta": None, "metric_code": "broadband_25_3_pct",
                               "metric_name": "Households with 25/3 Mbps broadband (synthetic stand-in for FCC BDC)", "value": c["broadbandPct"],
                               "year": 2026, "source_dataset": "synthetic (FCC BDC needs an account token)", "suppressed_flag": False})
for z, info in ZIPS.items():
    T["zip_place"].append({"zcta": z, "place_name": info["place"], "county_id": info["county"], "county_fips": COUNTY_FIPS[info["county"]],
                           "latitude": info["lat"], "longitude": info["lon"], "frontier_flag": info["frontier"], "typical_drive_minutes": info["drive"]})
# ADT: ED visits and admissions since the claims window closed (claims run 45 days behind; ADT arrives within the hour)
HOSP = {"elko": "290008", "humboldt": "291302", "lander": "291313", "pershing": "291306", "whitePine": "291300", "churchill": "290006"}
heavy = [p for p in SB if PATIENTS[p]["segment"] in ("highNeed", "impactable")]
for _ in range(96):
    pid = R.choice(heavy)
    d = rnd_date(date(2026, 10, 1), AS_OF)
    t0 = ts(d, R.randint(0, 23), R.randint(0, 59))
    etype = R.choice(["A04", "A04", "A04", "A01"])
    T["adt_event"].append({"adt_event_id": nid("ADT-", 6), "patient_id": pid, "facility_id": HOSP[PATIENTS[pid]["county"]],
                           "event_type": etype, "event_time": t0, "ed_flag": etype == "A04",
                           "received_at": t0 + timedelta(minutes=R.randint(4, 52))})
# home BP cuffs: readings that count for CMS165 also land in rpm_reading (device feed)
for r_ in T["remote_bp_reading"]:
    T["rpm_reading"].append({"reading_id": "RPM-" + r_["reading_id"][4:], "patient_id": r_["patient_id"], "loinc_code": "85354-9",
                             "value_systolic": r_["value_systolic"], "value_diastolic": r_["value_diastolic"], "value_numeric": None,
                             "unit": "mm[Hg]", "reading_time": r_["reading_time"], "device_type": "cellular BP cuff"})
# Linda's cellular cuff sent a raw reading this morning; it counts for CMS165 once the care team records it (write-back flow)
_ls, _ld = map(int, C["LINDA"]["reading"].split("/"))
T["rpm_reading"].append({"reading_id": "RPM-LINDA-1", "patient_id": "M-40107", "loinc_code": "85354-9", "value_systolic": _ls,
                         "value_diastolic": _ld, "value_numeric": None, "unit": "mm[Hg]", "reading_time": ts(AS_OF, 7, 30),
                         "device_type": "cellular BP cuff"})
# record matching: ADT and claims records that did not match a patient on name, birth date and ZIP
REASONS = ["Name spelling differs", "Birth date mismatch", "No ZIP on the record", "Two candidate patients"]
for i in range(C["MODEL"]["unmatchedRecords"] + 120):
    unmatched = i < C["MODEL"]["unmatchedRecords"]
    T["match_review"].append({"match_review_id": nid("MR-", 5), "source_feed": R.choice(["HIE ADT", "Payer claims", "Payer claims", "Lab results"]),
                              "source_record_id": f"SRC{R.randint(10**7, 10**8 - 1)}", "candidate_patient_id": None if unmatched else R.choice(SB),
                              "match_score": round(R.uniform(0.41, 0.79) if unmatched else R.uniform(0.92, 0.99), 2),
                              "reason": R.choices(REASONS, [43, 28, 18, 11])[0] if unmatched else None,
                              "status": "unmatched" if unmatched else "matched",
                              "received_at": ts(rnd_date(date(2026, 7, 1), AS_OF), R.randint(0, 23))})

# ═══ K. Contracts, benchmarks, grantee reports, planning assumptions ════════════════════════════════════
EXPECTED = {"sbch": C["CONTRACT"]["expectedPmpm"], "gbrc": 371, "hrhp": 379, "rvfh": 368}
for g in NETWORKS_INFO:
    T["contract_benchmark"].append({"benchmark_id": f"CB-{g['id']}-2026", "contract_year": 2026, "payer": g["payer"],
                                    "expected_pmpm": EXPECTED[g["id"]], "sharing_rate": 0.5, "quality_gate_required": C["CONTRACT"]["gateNeeded"],
                                    "quality_gate_total": C["CONTRACT"]["gateMeasures"], "contract_start": date(2026, 1, 1),
                                    "contract_end": date(2026, 12, 31), "network_id": g["id"], "claims_lag_days": C["CONTRACT"]["claimsLagDays"]})
T["utilization_benchmark"] += [
    {"benchmark_id": "UB-ED-NV", "geo_id": "32", "geo_type": "state", "metric_code": "avoidable_ed_per_1000",
     "benchmark_value": C["ED"]["benchmark"], "year": 2026},
    {"benchmark_id": "UB-LBP-NV", "geo_id": "32", "geo_type": "state", "metric_code": "lbp_imaging_pct", "benchmark_value": 8.0, "year": 2026}]
ASSUME = [
    ("bp_reach_rate", 0.70, "share", "Share of the 412 near-control members the campaign reaches before December 31", "Dr. Naomi Castellanos"),
    ("bp_control_if_reached", 0.624, "share", "Share of reached members whose recheck is under 140/90", "Dr. Naomi Castellanos"),
    ("fit_return_rate", FIT_RETURN, "share", "Share of mailed FIT kits returned with a result", "Dr. Naomi Castellanos"),
    ("hba1c_recheck_improve_rate", 0.5, "share", "Share of ordered HbA1c rechecks that come back at or under 9%", "Dr. Naomi Castellanos"),
    ("projection_months_left", 3, "months", "Months between the Q3 checkpoint and December 31", "Gregory Haskins"),
    ("option_a_cost", 1_400_000, "usd", "Option A: care coordinators and telehealth rechecks in Lander and Pershing", "Dr. Lauren Pike"),
    ("option_b_cost", 0, "usd", "Option B: shared low-value care feedback", "Dr. Lauren Pike"),
    ("option_c_cost", 600_000, "usd", "Option C: mobile clinic days in the six low-broadband ZIP areas", "Dr. Lauren Pike"),
    ("option_a_ed_cut_pct", C["STATE"]["optionAEdCutPct"], "pct", "Avoidable ED reduction expected from option A", "Dr. Lauren Pike"),
    ("option_b_lowvalue_cut", 0.33, "share", "Share of low-value spend option B removes", "Dr. Lauren Pike"),
    ("suppress_under", C["STATE"]["suppressUnder"], "count", "Small-cell suppression threshold for state reports", "Marcus Bell"),
    ("broadband_floor_pct", C["STATE"]["broadbandFloorPct"], "pct", "Household broadband share under which video visits are not offered", "Marcus Bell"),
    ("gap_drift_pts_per_quarter", 0.17, "pts", "Quarterly growth of the cost gap if nothing changes (2026 PMPM trend net of benchmark trend)", "Gregory Haskins"),
    ("three_moves_pts_per_quarter", 0.58, "pts", "Quarterly gap reduction once ED and low-value moves take effect, after coding recapture", "Gregory Haskins"),
    ("chw_list_min_likelihood", 70, "pct", "Lowest likelihood of control on a CHW's call list today", "Teresa Lopez, CHW"),
    ("high_risk_min_likelihood", 70, "pct", "Likelihood of control at or above which a pre-visit summary says High", "Dr. Samuel Okafor"),
    ("model_release_threshold_pct", C["MODEL"]["releaseThresholdPct"], "pct", "Largest frontier-town score gap a model may ship with", "Raj Malhotra"),
]
for code, val, unit, desc, owner in ASSUME:
    T["assumption"].append({"assumption_code": code, "value": val, "unit": unit, "description": desc, "owner": owner,
                            "updated_at": ts(date(2026, 10, 1))})
# RHTP quarterly report per grantee and county (people served, visits, BP control) with small-cell suppression
qrows = {r_["patient_id"]: r_ for r_ in T["quality_measure_result"] if r_["measure_code"] == "CMS165"}
visits = Counter((PATIENTS[e["patient_id"]]["network"], PATIENTS[e["patient_id"]]["county"]) for e in T["encounter"]
                 if e["start_time"].date() >= date(2026, 7, 1) and e["start_time"].date() <= date(2026, 9, 30) and e["encounter_type"] in ("office", "telehealth"))
served = Counter((PATIENTS[e["patient_id"]]["network"], PATIENTS[e["patient_id"]]["county"]) for e in
                 {(e["patient_id"],): e for e in T["encounter"] if date(2026, 7, 1) <= e["start_time"].date() <= date(2026, 9, 30)}.values())
for (n, cid), k in sorted(mem_nc.items()):
    den = [r_ for p, r_ in qrows.items() if PATIENTS[p]["network"] == n and PATIENTS[p]["county"] == cid]
    rate = round(100 * sum(r_["numerator_flag"] for r_ in den) / len(den), 1) if den else None
    T["rhtp_report"].append({"rhtp_report_id": nid("RHTP-", 4), "grantee_id": n, "county_fips": COUNTY_FIPS[cid], "reporting_period": "2026-Q3",
                             "people_served": served[(n, cid)], "services_delivered": visits[(n, cid)],
                             "outcome_measure": "Controlling high blood pressure (CMS165)", "outcome_value": rate,
                             "suppressed_flag": len(den) < C["STATE"]["suppressUnder"], "exported_at": None})
print(f"rows: {sum(len(v) for v in T.values())} across {len(T)} tables")
exec((Path(__file__).with_name("gen_load.py")).read_text(encoding="utf-8"))
