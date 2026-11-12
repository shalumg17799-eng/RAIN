# Part 3 (executed in gen_synthetic_v4's namespace): ED visits, claims calibrated to the PMPM story, quality measures,
# blood pressure readings and the BP campaign.

def ipf(cells, row_tot, col_tot, iters=300):
    for _ in range(iters):
        for r, t in row_tot.items():
            s = sum(v for (a, b), v in cells.items() if a == r)
            for k in [k for k in cells if k[0] == r]:
                cells[k] *= t / s if s else 0
        for c_, t in col_tot.items():
            s = sum(v for (a, b), v in cells.items() if b == c_)
            for k in [k for k in cells if k[1] == c_]:
                cells[k] *= t / s if s else 0
    return cells


def integerize(cells):
    out = {k: int(v) for k, v in cells.items()}
    rest = round(sum(cells.values())) - sum(out.values())
    for k in sorted(cells, key=lambda k: -(cells[k] - int(cells[k])))[:rest]:
        out[k] += 1
    return out


NETS = [g["id"] for g in NETWORKS_INFO]
NET_INFO = {n["id"]: n for n in C["NETWORKS"]}
mem_nc = Counter((p["network"], p["county"]) for p in PATIENTS.values())
mem_n = Counter(p["network"] for p in PATIENTS.values())

# ═══ D. Avoidable ED visits, January-September (9 months; rates are annualized per 1,000) ════════════════
ed_n = {n: NET_INFO[n]["edPer1000"] * mem_n[n] / 1000 * 0.75 for n in NETS}
ed_c = {c: COUNTIES[c]["edPer1000"] * COUNTIES[c]["members"] / 1000 * 0.75 for c in COUNTIES}
scale = sum(ed_n.values()) / sum(ed_c.values())
ed_c = {k: v * scale for k, v in ed_c.items()}
ED_CELL = integerize(ipf({k: float(v) for k, v in mem_nc.items()}, ed_n, ed_c))
ED_EVENTS = []          # (pid, date)
ed_reason = {m["id"] for m in REC["campaignMembers"] if "Avoidable ED visit this year" in m["reasons"]}
for (n, cid), k in ED_CELL.items():
    pids = [p for p, v in PATIENTS.items() if v["network"] == n and v["county"] == cid]
    if n == "sbch":
        fixed = [p for p in pids if p in ed_reason]
        for p in fixed:
            ED_EVENTS.append((p, day_in(2026, R.randint(1, 9))))
        heavy = [p for p in pids if PATIENTS[p]["segment"] in ("highNeed", "impactable") and p not in CAMP]
        for _ in range(k - len(fixed)):
            ED_EVENTS.append((R.choice(heavy), day_in(2026, R.randint(1, 9))))
    else:
        for _ in range(k):
            ED_EVENTS.append((R.choice(pids), day_in(2026, R.randint(1, 9))))
sb_ed = [e for e in ED_EVENTS if PATIENTS[e[0]]["network"] == "sbch"]
rate_sb = len(sb_ed) / C["CONTRACT"]["members"] * 1000 / 0.75
bench = C["ED"]["benchmark"]
ED_AVG = 8.0 * 12000 / (rate_sb - bench)      # the excess-ED part of the gap is $8 PMPM
print(f"avoidable ED: SB {len(sb_ed)} visits ({rate_sb:.1f}/1,000), average cost {ED_AVG:.2f}; all {len(ED_EVENTS)}")

# ═══ E. Claims ═══════════════════════════════════════════════════════════════════════════════════════════
months_w = [p["actual"] for p in C["PMPM_TREND"]]
site_total = {s["id"]: s["pmpm"] * s["members"] * 9 for s in C["SITES"]}
seg_share = {s["id"]: s["spendPct"] / 100 for s in C["SEGMENTS"]}
TARGET = {(sid, seg, m): site_total[sid] * seg_share[seg] * months_w[m - 1] / sum(months_w)
          for sid in SITES for seg in seg_share for m in range(1, 10)}
EVENTS = defaultdict(list)    # cell -> list of event dicts (fixed amount or base weight)
OTHER_CLAIMS = []


def ev(pid, d, kind, base=None, fixed=None, **kw):
    e = dict(pid=pid, d=d, kind=kind, base=base, fixed=fixed, **kw)
    p = PATIENTS[pid]
    if p["network"] == "sbch" and d.year == 2026 and d.month <= 9:
        EVENTS[(p["site"], p["segment"], d.month)].append(e)
    else:
        OTHER_CLAIMS.append(e)
    return e


lbp_enc = {r[0] for rows in SITE_LBP.values() for r in rows}
for e in T["encounter"]:
    d = e["start_time"].date()
    ev(e["patient_id"], d, "visit", base=1.0, enc=e["encounter_id"], site=e["clinic_site_id"], prov=e["provider_id"],
       lbp=e["encounter_id"] in lbp_enc)
ed_amounts = spread(ED_AVG * len(sb_ed), len(sb_ed))
k = 0
for pid, d in ED_EVENTS:
    site = PATIENTS[pid]["site"]
    eid = add_encounter(pid, d, site, kind="ed", h=R.randint(0, 23))
    if PATIENTS[pid]["network"] == "sbch":
        ev(pid, d, "ed_avoidable", fixed=ed_amounts[k], enc=eid, site=site); k += 1
    else:
        ev(pid, d, "ed_avoidable", fixed=round(R.uniform(1100, 1900), 2), enc=eid, site=site)
for pid in SB:
    p = PATIENTS[pid]
    if R.random() < (0.35 if p["segment"] != "stable" else 0.04):
        d = day_in(2026, R.randint(1, 9))
        ev(pid, d, "ed_other", base=6.0, enc=add_encounter(pid, d, p["site"], kind="ed", h=R.randint(0, 23)), site=p["site"])
    n_adm = R.randint(1, 3) if p["segment"] == "highNeed" else (1 if p["segment"] == "impactable" and R.random() < 0.06 else 0)
    for _ in range(n_adm):
        d = day_in(2026, R.randint(1, 9))
        ev(pid, d, "inpatient", base=40.0, enc=add_encounter(pid, d, p["site"], kind="inpatient"), site=p["site"])
    if p["conditions"]:
        for m in range(1, 10):
            ev(pid, day_in(2026, m), "pharmacy", base=4.0 if p["segment"] == "highNeed" else 1.2, site=p["site"])
    for _ in range(R.randint(0, 2)):
        ev(pid, day_in(2026, R.randint(1, 9)), "lab", base=0.6, site=p["site"])
for f in LV_FIND:
    ev(f["pid"], f["d"], "low_value", fixed=f["amount"], site=f["site"], lv=f)
# calibrate each (site, segment, month) cell: fixed amounts stay, the rest is scaled to the target
for key, events in EVENTS.items():
    fixed = sum(e["fixed"] for e in events if e["fixed"] is not None)
    base = sum(e["base"] for e in events if e["fixed"] is None)
    room = TARGET[key] - fixed
    if base == 0 or room <= 0:
        raise SystemExit(f"cell {key}: target {TARGET[key]:.0f}, fixed {fixed:.0f}, base {base}")
    for e in events:
        if e["fixed"] is None:
            e["amount"] = round(e["base"] * room / base, 2)
        else:
            e["amount"] = e["fixed"]
    var = [e for e in events if e["fixed"] is None]
    var[-1]["amount"] = round(var[-1]["amount"] + TARGET[key] - sum(e["amount"] for e in events), 2)
for e in OTHER_CLAIMS:
    e["amount"] = e["fixed"] if e["fixed"] is not None else round(R.uniform(60, 240) * (e["base"] or 1), 2)

PROC = {"visit": "99214", "ed_other": "99284", "ed_avoidable": "99283", "inpatient": "99223", "pharmacy": "J3490", "lab": "80053"}
TYPE = {"visit": "professional", "ed_other": "facility", "ed_avoidable": "facility", "inpatient": "facility", "pharmacy": "pharmacy",
        "lab": "professional", "low_value": "professional"}
POS = {"visit": "11", "ed_other": "23", "ed_avoidable": "23", "inpatient": "21", "pharmacy": "01", "lab": "81", "low_value": "22"}
DX_OF = {"Hypertension": "I10", "Type 2 diabetes": "E11.9", "COPD or asthma": "J44.9", "Heart failure": "I50.9", "Depression": "F32.9"}
for e in [x for evs in EVENTS.values() for x in evs] + OTHER_CLAIMS:
    p = PATIENTS[e["pid"]]
    cid_ = nid("CLM-", 8)
    T["claim"].append({"claim_id": cid_, "patient_id": e["pid"], "encounter_id": e.get("enc"), "claim_type": TYPE[e["kind"]],
                       "service_date": e["d"], "paid_date": e["d"] + timedelta(days=R.randint(35, 55)), "allowed_amount": e["amount"],
                       "ed_flag": e["kind"].startswith("ed"), "avoidable_ed_flag": e["kind"] == "ed_avoidable",
                       "admission_flag": e["kind"] == "inpatient"})
    dx = LBP_ICD if e.get("lbp") else DX_OF.get(next(iter(sorted(p["conditions"])), ""), "Z00.00")
    if e["kind"] == "low_value":
        f = e["lv"]
        proc = T["low_value_measure"][int(f["measure"][2:]) - 1]["service_codes"].split(";")[0]
        lid = nid("CLL-", 8)
        T["claim_line"].append({"claim_line_id": lid, "claim_id": cid_, "line_number": 1, "procedure_code": proc,
                                "diagnosis_code": LBP_ICD if f["measure"] == "LV01" else dx, "place_of_service": "22",
                                "ordering_provider_id": f["provider"], "clinic_site_id": f["site"], "allowed_amount": e["amount"]})
        T["low_value_finding"].append({"finding_id": nid("LVF-", 7), "claim_line_id": lid, "measure_id": f["measure"],
                                       "classification": R.choice(["wasteful", "likely wasteful"]), "allowed_amount": e["amount"],
                                       "clinic_site_id": f["site"], "ordering_provider_id": f["provider"], "service_date": f["d"]})
        if f["measure"] == "LV01":
            T["ehr_order"].append({"order_id": nid("ORD-", 7), "patient_id": f["pid"], "encounter_id": f.get("enc"),
                                   "ordering_provider_id": f["provider"], "clinic_site_id": f["site"], "order_type": "imaging",
                                   "procedure_code": proc, "diagnosis_code": LBP_ICD, "ordered_at": ts(f["d"], 11)})
        continue
    lines = 1 if e["kind"] in ("pharmacy", "lab") else 2
    amounts = [e["amount"]] if lines == 1 else [round(e["amount"] * 0.7, 2), round(e["amount"] - round(e["amount"] * 0.7, 2), 2)]
    for i, a in enumerate(amounts, start=1):
        T["claim_line"].append({"claim_line_id": nid("CLL-", 8), "claim_id": cid_, "line_number": i,
                                "procedure_code": PROC[e["kind"]] if i == 1 else "36415", "diagnosis_code": dx,
                                "place_of_service": POS[e["kind"]], "ordering_provider_id": e.get("prov"),
                                "clinic_site_id": e.get("site") or p["site"], "allowed_amount": a})
# a share of reviewed services are classed necessary (they never count as low-value)
for cl in R.sample([x for x in T["claim_line"] if x["procedure_code"] in ("99214", "80053")], 380):
    T["low_value_finding"].append({"finding_id": nid("LVF-", 7), "claim_line_id": cl["claim_line_id"], "measure_id": R.choice(list(LVM)),
                                   "classification": "necessary", "allowed_amount": cl["allowed_amount"], "clinic_site_id": cl["clinic_site_id"],
                                   "ordering_provider_id": cl["ordering_provider_id"], "service_date": None})
print(f"claims {len(T['claim'])}, claim lines {len(T['claim_line'])}")

# ═══ F. Quality measures and care gaps ═══════════════════════════════════════════════════════════════════
QM = [("CMS2", "Depression screening", 70, False), ("CMS125", "Breast cancer screening", 50, False),
      ("CMS165", "Controlling high blood pressure", 65, False), ("CMS122", "HbA1c poor control (over 9%)", 30, True),
      ("CMS130", "Colorectal cancer screening", 40, False)]
for code, name, target, lower in QM:
    T["quality_measure"].append({"measure_code": code, "measure_name": name, "target_rate": target, "lower_is_better": lower, "gate_flag": True})
CUR = {m["id"]: m["current"] for m in C["MEASURES"]}


def results(code, den, num_set, dates=None, period_end=date(2026, 9, 30)):
    for pid in den:
        met = pid in num_set
        d = (dates or {}).get(pid) or rnd_date(date(2025, 10, 1), period_end)
        T["quality_measure_result"].append({"result_id": nid("QMR-", 7), "measure_code": code, "patient_id": pid, "period_year": 2026,
                                            "denominator_flag": True, "numerator_flag": met, "computed_at": ts(d, 6)})
        if PATIENTS[pid]["network"] != "sbch":
            continue
        gap_open = (met if code == "CMS122" else not met)
        T["care_gap"].append({"care_gap_id": nid("GAP-", 7), "patient_id": pid, "measure_code": code,
                              "status": "open" if gap_open else "closed", "opened_at": ts(date(2026, 1, 1)),
                              "closed_at": None if gap_open else ts(d, 6), "closed_by": None if gap_open else
                              ("reading" if code == "CMS165" else "visit")})


def trend_dates(num, late_per_month, months=(7, 8, 9)):
    dates = {}
    late = num[: late_per_month * len(months)]
    for i, pid in enumerate(late):
        dates[pid] = day_in(2026, months[i // late_per_month])
    for pid in num[len(late):]:
        dates[pid] = rnd_date(date(2025, 4, 1), date(2026, 6, 30))
    return dates


ages = {pid: PATIENTS[pid]["age"] for pid in SB}
# CMS2: depression screening, 12+, 74% met; July-September closures project 75% by December 31
den = R.sample([p for p in SB if ages[p] >= 12], 6900)
num = den[: round(0.74 * len(den))]
results("CMS2", den, set(num), trend_dates(num, 23))
# CMS125: breast cancer screening, women 50-74, 52% met, ~4 closures a month
den = [p for p in SB if PATIENTS[p]["sex"] == "F" and 50 <= ages[p] <= 74]
num = den[: round(0.5203 * len(den))]
need = math.ceil((0.525 * len(den) - len(num)) / 3)
results("CMS125", den, set(num), trend_dates(num, max(need, 1)))
CMS125_DEN = len(den)
# CMS165: the 2,250 hypertensive members, 1,305 controlled by the Q3 checkpoint (latest reading dates are set in G)
results("CMS165", sorted(HTN), set(CONTROLLED), dates={})
# CMS122: 1,050 diabetics, 34% in poor control (lower is better) - includes the 34 campaign members with an open diabetes gap
diab_gap = [m["id"] for m in REC["campaignMembers"] if "Open diabetes gap" in m["reasons"]]
diab_gap += [v["memberId"] for v in REC["previsitSummaries"] if any("CMS122" in g for g in v["openGaps"]) and v["memberId"] not in diab_gap]
assert all(p in DIAB for p in diab_gap), "previsit HbA1c gaps must be diabetic"
others_ = [p for p in DIAB if p not in diab_gap and p not in CAMP]
POOR = diab_gap + others_[: 357 - len(diab_gap)]
results("CMS122", DIAB, set(POOR))
# CMS130: colorectal screening 45-75, 33% met, flat trend (the FIT kit mailing is what moves it)
den = [p for p in SB if 45 <= ages[p] <= 75]
num = den[: round(0.33 * len(den))]
results("CMS130", den, set(num), {p: rnd_date(date(2017, 1, 1), date(2026, 6, 30)) for p in num})
CMS130_DEN, CMS130_UNSCREENED = len(den), [p for p in den if p not in set(num)]
# other networks: CMS165 and CMS130 by network and county (state view, network comparison)
htn_n = {(n, c_): mem_nc[(n, c_)] * 0.239 for (n, c_) in mem_nc if n != "sbch"}
num_n = {n: NET_INFO[n]["bpControlPct"] / 100 * sum(v for (a, _), v in htn_n.items() if a == n) for n in NETS if n != "sbch"}
sb_c_num = Counter(PATIENTS[p]["county"] for p in CONTROLLED)
sb_c_den = Counter(PATIENTS[p]["county"] for p in HTN)
num_c = {c_: COUNTIES[c_]["bpControlPct"] / 100 * (sb_c_den[c_] + sum(v for (_, b), v in htn_n.items() if b == c_)) - sb_c_num[c_]
         for c_ in COUNTIES}
fit = sum(num_c.values()) / sum(num_n.values())
num_c = {k: v / fit for k, v in num_c.items()}
NUM_CELL = integerize(ipf({k: v * 0.58 for k, v in htn_n.items()}, num_n, num_c))
for (n, c_), dn in integerize(htn_n).items():
    pids = R.sample([p for p, v in PATIENTS.items() if v["network"] == n and v["county"] == c_ and v["age"] >= 18], dn)
    for pid in pids:
        add_condition(pid, "Hypertension")
    results("CMS165", pids, set(pids[: min(NUM_CELL[(n, c_)], dn)]))
for n in NETS[1:]:
    pids = [p for p, v in PATIENTS.items() if v["network"] == n and 45 <= v["age"] <= 75]
    results("CMS130", pids, set(pids[: round(NET_INFO[n]["colorectalPct"] / 100 * len(pids))]))
print(f"quality results {len(T['quality_measure_result'])}, care gaps {len(T['care_gap'])}")

# ═══ G. Blood pressure readings and the BP campaign ═════════════════════════════════════════════════════
def bp_row(pid, d, sys_, dia, home):
    if home:
        T["remote_bp_reading"].append({"reading_id": nid("RBP-", 7), "patient_id": pid, "value_systolic": sys_, "value_diastolic": dia,
                                       "reading_time": ts(d, 7, 30), "device_type": "home cuff", "counts_for_measure": True})
    else:
        T["observation"].append({"observation_id": nid("OBS-", 7), "patient_id": pid, "encounter_id": None, "loinc_code": "85354-9",
                                 "observation_type": "blood pressure", "value_numeric": None, "value_systolic": sys_,
                                 "value_diastolic": dia, "unit": "mm[Hg]", "observed_at": ts(d, 10)})


qmr165 = {r["patient_id"]: r for r in T["quality_measure_result"] if r["measure_code"] == "CMS165"}
for pid in CONTROLLED:
    d = rnd_date(date(2026, 2, 1), date(2026, 9, 30))
    bp_row(pid, d - timedelta(days=60), R.randint(140, 150), R.randint(88, 94), False)
    bp_row(pid, d, R.randint(112, 138), R.randint(68, 88), R.random() < 0.4)
    qmr165[pid]["computed_at"] = ts(d, 6)
for pid in FAR:
    d = rnd_date(date(2026, 2, 1), date(2026, 9, 30))
    bp_row(pid, d, R.randint(150, 178), R.randint(90, 104), R.random() < 0.3)
    qmr165[pid]["computed_at"] = ts(d, 6)
CAMPAIGN_START = date(2026, 10, 1)
booked = [m for m in sorted(REC["campaignMembers"], key=lambda m: m["rank"]) if m["status"] == "Reached and booked"]
controlled_after = {m["id"] for m in booked[: C["CARE"]["controlled"]]}
for m in REC["campaignMembers"]:
    pid = m["id"]
    sys_, dia = map(int, m["lastBp"].split("/"))
    d = day_in(2026, MONTH_NAME[m["lastBpMonth"]])
    bp_row(pid, d - timedelta(days=75), sys_ + R.randint(2, 9), dia + R.randint(0, 5), False)
    bp_row(pid, d, sys_, dia, m["cuff"] == "On file")
    qmr165[pid]["computed_at"] = ts(d, 6)
    if pid in controlled_after:
        bp_row(pid, day_in(2026, 10, 15, 31), R.randint(122, 136), R.randint(72, 86), True)
    T["risk_score"].append({"risk_score_id": nid("RSK-", 7), "patient_id": pid, "model_name": "bp_control_likelihood",
                            "score": m["likelihood"], "risk_tier": "High" if m["likelihood"] >= 70 else "Rising",
                            "top_reasons": "; ".join(m["reasons"]), "computed_at": ts(CAMPAIGN_START, 5)})
    # contact preferences (consent decides SMS or voice), travel time to the home site
    best = m.get("bestTime", "Any time")
    quiet = ("20:00", "08:00")          # quiet hours 8 PM to 8 AM; best_time is a preference inside the window
    T["contact_preference"].append({"preference_id": nid("PREF-", 7), "patient_id": pid, "channel": m["channel"], "language": m["language"],
                                    "consent_flag": m["channel"] == "SMS", "quiet_hours_start": quiet[0], "quiet_hours_end": quiet[1],
                                    "updated_at": ts(date(2026, 3, 1)), "best_time": best, "phone_note": m.get("phoneNote")})
for pid, p in PATIENTS.items():
    if p["network"] == "sbch":
        T["travel_time"].append({"travel_time_id": nid("TT-", 7), "patient_zcta": p["zip"], "clinic_site_id": p["site"],
                                 "drive_minutes": p["drive"], "computed_at": ts(date(2026, 10, 1)), "patient_id": pid})
        if pid not in CAMP:
            consent = R.random() < 0.55
            T["contact_preference"].append({"preference_id": nid("PREF-", 7), "patient_id": pid, "channel": "SMS" if consent else "Voice",
                                            "language": p["lang"], "consent_flag": consent, "quiet_hours_start": "20:00",
                                            "quiet_hours_end": "08:00", "updated_at": ts(date(2026, 2, 1)),
                                            "best_time": R.choice(["Mornings", "Midday", "After 5 PM", "Any time"]), "phone_note": None})
# the campaign itself, its members, standing orders, the outreach tasks and the hand-off that sent it to the care team
T["campaign"] += [
    {"campaign_id": "BP2026", "campaign_name": "Blood pressure control recheck", "measure_code": "CMS165",
     "created_by": "Dr. Naomi Castellanos", "status": "active", "created_at": ts(CAMPAIGN_START, 9), "target_count": len(CAMP)},
    {"campaign_id": "FIT2026", "campaign_name": "Mailed FIT kits", "measure_code": "CMS130", "created_by": "Dr. Naomi Castellanos",
     "status": "planned", "created_at": ts(date(2026, 11, 3), 9), "target_count": None},
    {"campaign_id": "TOP300", "campaign_name": "Top 300 impactable outreach", "measure_code": None, "created_by": "Gregory Haskins",
     "status": "proposed", "created_at": ts(date(2026, 11, 3), 9), "target_count": C["COHORT"]["topRanked"]}]
for m in REC["campaignMembers"]:
    T["campaign_member"].append({"campaign_member_id": nid("CM-", 6), "campaign_id": "BP2026", "patient_id": m["id"],
                                 "outreach_rank": m["rank"], "recommended_visit_mode": m["mode"],
                                 "cuff_on_file": m["cuff"] == "On file" if m["mode"] == "Telehealth" else None,
                                 "booked_flag": m["status"] == "Reached and booked", "outcome": m["status"]})
    T["standing_order"].append({"standing_order_id": nid("SO-", 6), "campaign_id": "BP2026", "provider_id": None,
                                "order_type": "BP recheck", "description": m["standingOrder"], "status": "pending review",
                                "reviewed_at": None, "patient_id": m["id"]})
    who = ("Teresa Lopez" if m["siteId"] in TERESA_SITES else "Denise Holloway" if m["frontier"] else "Care team")
    status = {"Reached and booked": "closed", "Left message": "left_message"}.get(m["status"], "open")
    attempt = {"Left message": ts(AS_OF - timedelta(days=1), 15)}.get(m["status"])
    T["outreach_task"].append({"task_id": nid("TSK-", 7), "patient_id": m["id"], "campaign_id": "BP2026", "task_type": "bp_campaign_call",
                               "priority_score": m["likelihood"], "reason_summary": None, "assigned_to": who, "status": status,
                               "created_at": ts(CAMPAIGN_START, 9), "closed_at": ts(day_in(2026, 10, 2, 31)) if status == "closed" else None,
                               "last_attempt_at": attempt or (ts(day_in(2026, 10, 2, 31)) if status == "closed" else None)})
teresa_open = sum(1 for t in T["outreach_task"] if t["assigned_to"] == "Teresa Lopez" and t["status"] != "closed")
for _ in range(C["CARE"]["teresaOpen"] - teresa_open):
    pid = R.choice([p for p in SB if PATIENTS[p]["site"] in TERESA_SITES and p not in CAMP])
    T["outreach_task"].append({"task_id": nid("TSK-", 7), "patient_id": pid, "campaign_id": None, "task_type": "care_gap_followup",
                               "priority_score": round(R.uniform(10, 60), 2), "reason_summary": None, "assigned_to": "Teresa Lopez",
                               "status": "open", "created_at": ts(day_in(2026, R.randint(6, 10))), "closed_at": None, "last_attempt_at": None})
for _ in range(51):     # follow-ups the care team closed this year
    pid = R.choice(SB)
    T["outreach_task"].append({"task_id": nid("TSK-", 7), "patient_id": pid, "campaign_id": None, "task_type": "care_gap_followup",
                               "priority_score": round(R.uniform(10, 60), 2), "reason_summary": None, "assigned_to": R.choice(["Teresa Lopez", "Denise Holloway"]),
                               "status": "closed", "created_at": ts(day_in(2026, R.randint(2, 8))), "closed_at": ts(day_in(2026, R.randint(9, 10))),
                               "last_attempt_at": None})
for b in REC["pendingBookings"]:
    T["outreach_task"].append({"task_id": nid("TSK-", 7), "patient_id": b["memberId"], "campaign_id": "BP2026", "task_type": "book_visit",
                               "priority_score": CAMP[b["memberId"]]["likelihood"] if b["memberId"] in CAMP else 50,
                               "reason_summary": f"{b['mode']} recheck", "assigned_to": "Brandon Kee", "status": "open",
                               "created_at": ts(AS_OF - timedelta(days=1), 16), "closed_at": None, "last_attempt_at": None,
                               "handed_off_by": b["from"]})
T["handoff"] += [
    {"handoff_id": "HO-BP2026", "campaign_id": "BP2026", "from_bucket": "Use case A: insights", "to_bucket": "Use case B: Worklist",
     "member_count": len(CAMP), "approved_by": "Dr. Naomi Castellanos", "approved_at": ts(CAMPAIGN_START, 10), "status": "sent"},
    {"handoff_id": "HO-TOP300", "campaign_id": "TOP300", "from_bucket": "Use case A: insights", "to_bucket": "Use case B: Worklist",
     "member_count": C["COHORT"]["topRanked"], "approved_by": None, "approved_at": None, "status": "pending approval"},
    {"handoff_id": "HO-CODING", "campaign_id": None, "from_bucket": "Use case A: insights", "to_bucket": "CMO: coding recapture",
     "member_count": len(UNRECAPTURED), "approved_by": None, "approved_at": None, "status": "pending approval"}]
# FIT kits: mailed to enough unscreened members that the expected returns add 4 points to CMS130
FIT_RETURN = 0.22
fit_n = round(C["FIT"]["gainPts"] / 100 * CMS130_DEN / FIT_RETURN)
for pid in CMS130_UNSCREENED[:fit_n]:
    T["campaign_member"].append({"campaign_member_id": nid("CM-", 6), "campaign_id": "FIT2026", "patient_id": pid, "outreach_rank": None,
                                 "recommended_visit_mode": "Mail", "cuff_on_file": None, "booked_flag": False, "outcome": "Kit to mail"})
# HbA1c rechecks ordered for members in poor control (they drive the CMS122 projection)
for pid in POOR[len(diab_gap):len(diab_gap) + 22]:
    T["ehr_order"].append({"order_id": nid("ORD-", 7), "patient_id": pid, "encounter_id": None, "ordering_provider_id": OKAFOR,
                           "clinic_site_id": PATIENTS[pid]["site"], "order_type": "lab", "procedure_code": "83036",
                           "diagnosis_code": "E11.65", "ordered_at": ts(day_in(2026, 11, 3, 30))})
print(f"campaign members {len(T['campaign_member'])}, outreach tasks {len(T['outreach_task'])}")
exec((Path(__file__).with_name("gen_part4.py")).read_text(encoding="utf-8"))
