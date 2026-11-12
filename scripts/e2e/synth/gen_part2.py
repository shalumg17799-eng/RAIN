# Part 2 of gen_synthetic_v4.py (executed in its namespace): clinical history, claims, quality, campaign, model,
# scheduling. Every block builds rows; the targets come from the scenario so SQL over the rows gives the story back.
from synth_ref import LV_MONTHS, LOW_BB_ZIPS, MONTH_LABEL  # noqa: E402

TERESA_SITES = set(C["TERESA_SITES"])
SB_SET = set(SB)
ADULTS_SB = [pid for pid in SB if 18 <= PATIENTS[pid]["age"] <= 85]
MON = {v: k for k, v in MONTH_LABEL.items()}
MONTH_NAME = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7, "August": 8,
              "September": 9, "October": 10, "November": 11, "December": 12}


def day_in(y, m, lo=1, hi=None):
    return date(y, m, R.randint(lo, hi or month_days(y, m)))


# ═══ A. Conditions, coding recapture reference, primary condition groups ════════════════════════════════
ICD = {"Hypertension": ("I10", "38341003"), "Type 2 diabetes": ("E11.9", "44054006"), "COPD or asthma": ("J44.9", "13645005"),
       "Heart failure": ("I50.9", "84114007"), "Depression": ("F32.9", "35489007"), "Chronic kidney disease": ("N18.4", "431857002")}
HCC = [("I50.9", "Heart failure", 21000.00), ("J44.9", "COPD or asthma", 15000.00), ("N18.4", "Chronic kidney disease", None)]


def add_condition(pid, name, documented=2026, recaptured=2026, status="active", onset=None):
    code, snomed = ICD[name]
    T["condition"].append({"condition_id": nid("CND-", 7), "patient_id": pid, "icd10_code": code, "snomed_code": snomed,
                           "onset_date": onset or date(R.randint(2012, 2024), R.randint(1, 12), 1),
                           "documented_year": documented, "recaptured_year": recaptured, "status": status})
    PATIENTS[pid]["conditions"].add(name)


# A1. CMS165 denominator: 2,250 hypertensive Sierra Basin adults = the 412 near-control + 1,305 controlled + 533 far
#     The swap members (model v1.3 -> v1.4) keep their story attributes: the ones flagged inBpDenominator are
#     hypertensive members of the CMS165 denominator, the others are not.
SWAP_CONDS = {"Hypertension": ["Hypertension"], "Diabetes": ["Type 2 diabetes"], "Heart failure": ["Heart failure"],
              "Hypertension and diabetes": ["Hypertension", "Type 2 diabetes"], "COPD or asthma": ["COPD or asthma"]}
camp_ids = [m["id"] for m in REC["campaignMembers"]]
swap_bp = [s["id"] for s in GOV["swaps"] if s["inBpDenominator"]]
pool = [p for p in ADULTS_SB if p not in CAMP and p not in SWAPS]
R.shuffle(pool)
chosen = swap_bp + pool[:C["BP"]["hypertensive"] - len(camp_ids) - len(swap_bp)]
R.shuffle(chosen)
CONTROLLED, FAR = chosen[:1305], chosen[1305:]
HTN = set(camp_ids) | set(CONTROLLED) | set(FAR)
assert len(HTN) == C["BP"]["hypertensive"] and len(FAR) == 533
for pid in sorted(HTN):
    add_condition(pid, "Hypertension")
# A2. diabetes: the 174 campaign members with T2D + the diabetic swap members + others = 1,050 (CMS122, 18-75)
t2d_camp = [m["id"] for m in REC["campaignMembers"] if "Type 2 diabetes" in m["conditions"]]
swap_d = [s["id"] for s in GOV["swaps"] if "Type 2 diabetes" in SWAP_CONDS[s["condition"]]]
d_pool = [p for p in ADULTS_SB if p not in CAMP and p not in SWAPS and PATIENTS[p]["age"] <= 75]
R.shuffle(d_pool)
DIAB = t2d_camp + swap_d + d_pool[:1050 - len(t2d_camp) - len(swap_d)]
for pid in DIAB:
    add_condition(pid, "Type 2 diabetes")
for s in GOV["swaps"]:
    for name in SWAP_CONDS[s["condition"]]:
        if name not in PATIENTS[s["id"]]["conditions"]:
            add_condition(s["id"], name)
# A3. heart failure per county across all networks (state view), other chronic groups for the subgroup check
for cid, c in COUNTIES.items():
    cands = [p for p, v in PATIENTS.items() if v["county"] == cid and v["age"] >= 40 and "Heart failure" not in v["conditions"]]
    for pid in R.sample(cands, c["heartFailure"]):
        add_condition(pid, "Heart failure")
for pid in R.sample(ADULTS_SB, 900):
    if "COPD or asthma" not in PATIENTS[pid]["conditions"]:
        add_condition(pid, "COPD or asthma")
for pid in R.sample(ADULTS_SB, 1100):
    if "Depression" not in PATIENTS[pid]["conditions"]:
        add_condition(pid, "Depression")
# A4. coding recapture: 73 of the 236 high-need members carry a chronic condition documented in 2025, not yet in 2026.
HIGH = [p for p in SB if PATIENTS[p]["segment"] == "highNeed"]
UNRECAPTURED = R.sample(HIGH, C["CODING"]["members"])
need_usd = (C["CODING"]["correctedBenchmark"] - C["CONTRACT"]["expectedPmpm"]) * C["CONTRACT"]["members"] * 12
plan = ["I50.9"] * 40 + ["J44.9"] * 20 + ["N18.4"] * (len(UNRECAPTURED) - 60)
ckd_cost = round((need_usd - 40 * 21000 - 20 * 15000) / (len(UNRECAPTURED) - 60), 2)
HCC[2] = ("N18.4", "Chronic kidney disease", ckd_cost)
for pid, code in zip(UNRECAPTURED, plan):
    name = next(n for n, (c_, _) in ICD.items() if c_ == code)
    add_condition(pid, name, documented=2025, recaptured=None)
for pid in HIGH:
    if pid not in UNRECAPTURED:
        add_condition(pid, R.choice(["Heart failure", "COPD or asthma", "Chronic kidney disease"]), documented=2025, recaptured=2026)
for code, name, cost in HCC:
    T["hcc_reference"].append({"icd10_code": code, "condition_name": name, "annual_expected_cost": cost})
# A5. one primary chronic group per scored member (the model's subgroup check compares these groups)
GROUPS = ["Hypertension", "Type 2 diabetes", "COPD or asthma", "Heart failure", "Depression"]
for pid in SB:
    conds = [g for g in GROUPS if g in PATIENTS[pid]["conditions"]]
    PATIENTS[pid]["primary"] = SWAP_CONDS[SWAPS[pid]["condition"]][0] if pid in SWAPS else (conds[0] if conds else None)
for row in T["condition"]:
    p = PATIENTS[row["patient_id"]]
    if (p.get("primary") and not p.get("primary_done") and ICD[p["primary"]][0] == row["icd10_code"]
            and row["status"] == "active"):
        row["status"] = "primary"
        p["primary_done"] = True

# ═══ B. Primary care visits (all networks), last visits, low back pain visits ════════════════════════════
ENC_BY_PID = defaultdict(list)


def add_encounter(pid, d, site, provider=None, kind="office", tele=False, h=None):
    eid = nid("ENC-", 7)
    start = ts(d, h if h is not None else R.randint(8, 16), R.choice([0, 15, 30, 45]))
    T["encounter"].append({"encounter_id": eid, "patient_id": pid, "provider_id": provider or R.choice(PROVIDERS[site] or [OKAFOR]),
                           "clinic_site_id": site, "encounter_type": kind, "start_time": start,
                           "end_time": start + timedelta(minutes=30 if kind in ("office", "telehealth") else 240),
                           "telehealth_flag": tele})
    ENC_BY_PID[pid].append((d, eid, kind))
    return eid


# B1. campaign members: last primary care visit exactly `monthsSinceVisit` months before November 2026
for m in REC["campaignMembers"]:
    last_m = 11 - m["monthsSinceVisit"]
    y, mm = (2026, last_m) if last_m >= 1 else (2025, last_m + 12)
    add_encounter(m["id"], day_in(y, mm), m["siteId"])
    for _ in range(R.randint(0, 2)):
        months_before = [(yy, x) for (yy, x) in [(2025, 10), (2025, 11), (2025, 12)] + MONTHS if (yy, x) < (y, mm)]
        if months_before:
            yy, x = R.choice(months_before)
            add_encounter(m["id"], day_in(yy, x), m["siteId"], tele=R.random() < 0.3)
# B2. every county's monthly visit volume: January baseline, July-September at the PRD's change since January
weights = {pid: (0.69 if (p["network"] == "sbch" and p["frontier"]) else 1.0) for pid, p in PATIENTS.items() if pid not in CAMP}
by_county = defaultdict(list)
for pid, p in PATIENTS.items():
    if pid not in CAMP:
        by_county[p["county"]].append(pid)
for cid, c in COUNTIES.items():
    pids = by_county[cid]
    cum, tot = [], 0.0
    for pid in pids:
        tot += weights[pid]
        cum.append(tot)
    base = c["members"] * 0.22
    chg = c["pcVisitChangePct"] / 100
    for (y, mm) in [(2025, 10), (2025, 11), (2025, 12)] + MONTHS:
        f = 1.0 if y == 2025 else 1 + chg * min(mm - 1, 6) / 6
        n = round(base * f)
        n -= sum(1 for pid in CAMP if PATIENTS[pid]["county"] == cid for (d, _, k) in ENC_BY_PID[pid] if d.year == y and d.month == mm)
        import bisect
        for _ in range(max(n, 0)):
            pid = pids[bisect.bisect_left(cum, R.random() * tot)]
            add_encounter(pid, day_in(y, mm), PATIENTS[pid]["site"], tele=R.random() < 0.25)
# B3. low back pain visits at Sierra Basin sites; Winnemucca's locum rotation from April (imaging rate jumps)
SITE_LBP = {}            # (site, y, m) -> list of (encounter_id, pid, provider, imaged)
WIN_PLAN = {(2026, 1): (75, 6), (2026, 2): (67, 6), (2026, 3): (74, 6), (2026, 4): (72, 17), (2026, 5): (71, 19),
            (2026, 6): (70, 20), (2026, 7): (71, 20), (2026, 8): (70, 19), (2026, 9): (69, 19),
            (2025, 10): (70, 6), (2025, 11): (70, 6), (2025, 12): (70, 6)}
LOCUM_VISITS = [152, 136, 135]
LOCUM_ORDERS = [l["orders"] for l in C["LOCUMS"]]
locum_v = {i: [] for i in range(3)}
OTHER_RATE = {s["id"]: s["imagingPct"] for s in C["SITES"]}
lbp_per_member = 423 / (6 * SITES["winnemucca"]["members"])
EARLY = [(2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3)]
LATE = [(2026, m) for m in range(4, 10)]
PLAN = {}                                   # (site, y, m) -> (visits, imaged)
for sid, s in SITES.items():
    if sid == "winnemucca":
        for k, v in WIN_PLAN.items():
            PLAN[(sid,) + k] = v
        continue
    v = round(s["members"] * lbp_per_member)
    total_img = round(6 * v * OTHER_RATE[sid] / 100)         # April-September imaging rate = the site's imagingPct
    for i, k in enumerate(LATE):
        PLAN[(sid,) + k] = (v, total_img // 6 + (1 if i < total_img % 6 else 0))
early_needed = LVM_TOTAL = C["LV_MEASURES"][0]["services"]
early_needed -= sum(img for (sid, y, m), (_, img) in PLAN.items())
others = [sid for sid in SITES if sid != "winnemucca"]
w_mem = sum(SITES[s]["members"] for s in others)
alloc = {sid: int(early_needed * SITES[sid]["members"] / w_mem) for sid in others}
for sid in sorted(others, key=lambda s: -SITES[s]["members"])[: early_needed - sum(alloc.values())]:
    alloc[sid] += 1
for sid in others:
    v = round(SITES[sid]["members"] * lbp_per_member * 1.2)
    for i, k in enumerate(EARLY):
        img = alloc[sid] // 6 + (1 if i < alloc[sid] % 6 else 0)
        PLAN[(sid,) + k] = (max(v, img), img)
for sid, s in SITES.items():
    members = [p for p in SB if PATIENTS[p]["site"] == sid and PATIENTS[p]["age"] >= 18 and p not in CAMP and p not in SWAPS]
    for (y, mm) in LV_MONTHS:
        visits, imaged = PLAN[(sid, y, mm)]
        rows = []
        for i in range(visits):
            pid = R.choice(members)
            prov = None
            if sid == "winnemucca" and (y, mm) >= (2026, 4):
                prov = "locum"
            eid = add_encounter(pid, day_in(y, mm), sid)
            rows.append([eid, pid, prov, i < imaged])
        SITE_LBP[(sid, y, mm)] = rows
# assign Winnemucca's April-September LBP visits and imaging orders to the three locums (visits 152/136/135, orders 41/38/35)
win_rows = [r for (sid, y, mm), rows in SITE_LBP.items() if sid == "winnemucca" and (y, mm) >= (2026, 4) for r in rows]
imaged_rows = [r for r in win_rows if r[3]]
plain_rows = [r for r in win_rows if not r[3]]
assert len(win_rows) == sum(LOCUM_VISITS) and len(imaged_rows) == sum(LOCUM_ORDERS), (len(win_rows), len(imaged_rows))
pi = ii = 0
for i in range(3):
    for _ in range(LOCUM_ORDERS[i]):
        imaged_rows[ii][2] = LOCUM_IDS[i]; ii += 1
    for _ in range(LOCUM_VISITS[i] - LOCUM_ORDERS[i]):
        plain_rows[pi][2] = LOCUM_IDS[i]; pi += 1
enc_index = {e["encounter_id"]: e for e in T["encounter"]}
for rows in SITE_LBP.values():
    for eid, pid, prov, imaged in rows:
        if prov:
            enc_index[eid]["provider_id"] = prov
print(f"encounters {len(T['encounter'])}, LBP visits {sum(len(v) for v in SITE_LBP.values())}")

# ═══ C. Low-value findings plan (trailing 12 months) ════════════════════════════════════════════════════
LVM = {m["id"]: m for m in C["LV_MEASURES"]}
for m in C["LV_MEASURES"]:
    T["low_value_measure"].append({"measure_id": m["id"], "measure_name": m["name"], "basis": m["basis"],
                                   "service_codes": {"LV01": "72148;72100", "LV02": "82306", "LV03": "80048;93000", "LV04": "93000",
                                                     "LV05": "70450;70551", "LV06": "29881", "LV07": "J0696", "LV08": "G0121",
                                                     "LV09": "70450", "LV10": "88175", "LV11": "G0103", "LV12": "77080",
                                                     "LV13": "84443", "LV14": "J2270"}[m["id"]],
                                   "description": f"{m['name']} ({m['basis']})"})
LV_FIND = []      # dicts: measure, site, pid, date, amount, provider, network
# C1. LV01 = the imaged low back pain visits; Winnemucca carries 115,020 of the 162,000 dollars
lv01_rows = [(sid, y, mm, r) for (sid, y, mm), rows in SITE_LBP.items() for r in rows if r[3]]
win_lv01 = [x for x in lv01_rows if x[0] == "winnemucca"]
oth_lv01 = [x for x in lv01_rows if x[0] != "winnemucca"]
assert len(lv01_rows) == LVM["LV01"]["services"], len(lv01_rows)
win_usd = round(LVM["LV01"]["dollars"] * C["LOW_VALUE"]["winnemuccaSharePct"] / 100 + 20)   # 115,020
def spread(total, n):
    raw = [R.uniform(0.7, 1.3) for _ in range(n)]
    s = sum(raw)
    vals = [round(total * r / s, 2) for r in raw]
    vals[-1] = round(total - sum(vals[:-1]), 2)
    return vals
for (sid, y, mm, r), amt in zip(win_lv01, spread(win_usd, len(win_lv01))):
    LV_FIND.append(dict(measure="LV01", site=sid, pid=r[1], d=day_in(y, mm), amount=amt, provider=r[2] or R.choice(PROVIDERS[sid]), enc=r[0]))
for (sid, y, mm, r), amt in zip(oth_lv01, spread(LVM["LV01"]["dollars"] - win_usd, len(oth_lv01))):
    LV_FIND.append(dict(measure="LV01", site=sid, pid=r[1], d=day_in(y, mm), amount=amt, provider=R.choice(PROVIDERS[sid]), enc=r[0]))
# C2. LV02..LV14 split across sites so every site's annual low-value dollars match (iterative proportional fitting)
site_rem = {sid: s["lowValue"] - sum(f["amount"] for f in LV_FIND if f["site"] == sid) for sid, s in SITES.items()}
meas = [m for m in C["LV_MEASURES"] if m["id"] != "LV01"]
cell = {(m["id"], sid): m["dollars"] * SITES[sid]["members"] / 9400 for m in meas for sid in SITES}
for _ in range(200):
    for sid in SITES:
        s = sum(cell[(m["id"], sid)] for m in meas)
        for m in meas:
            cell[(m["id"], sid)] *= site_rem[sid] / s
    for m in meas:
        s = sum(cell[(m["id"], sid)] for sid in SITES)
        for sid in SITES:
            cell[(m["id"], sid)] *= m["dollars"] / s
for m in meas:
    # integer services per site, then dollars per finding
    shares = {sid: cell[(m["id"], sid)] / m["dollars"] for sid in SITES}
    svc = {sid: int(m["services"] * shares[sid]) for sid in SITES}
    for sid in sorted(SITES, key=lambda s: -(m["services"] * shares[s] - svc[s]))[: m["services"] - sum(svc.values())]:
        svc[sid] += 1
    for sid in SITES:
        if svc[sid] == 0:
            continue
        members = [p for p in SB if PATIENTS[p]["site"] == sid]
        for amt in spread(cell[(m["id"], sid)], svc[sid]):
            y, mm = R.choice(LV_MONTHS)
            LV_FIND.append(dict(measure=m["id"], site=sid, pid=R.choice(members), d=day_in(y, mm), amount=amt,
                                provider=R.choice(PROVIDERS[sid]), enc=None))
# exact dollars per site (rounding)
for sid, s in SITES.items():
    rows = [f for f in LV_FIND if f["site"] == sid and f["measure"] != "LV01"]
    diff = round(s["lowValue"] - sum(f["amount"] for f in LV_FIND if f["site"] == sid), 2)
    rows[-1]["amount"] = round(rows[-1]["amount"] + diff, 2)
# C3. the other three networks: low-value dollars by county (the state view's $2.4M)
sb_county_lv = defaultdict(float)
for f in LV_FIND:
    sb_county_lv[ZIPS[TOWN_ZIP[f["site"]]]["county"]] += f["amount"]
mix = [(m["id"], m["dollars"] / C["LOW_VALUE"]["annual"]) for m in C["LV_MEASURES"]]
for cid, c in COUNTIES.items():
    rem = c["lowValue"] - sb_county_lv[cid]
    pids = [p for p in by_county[cid] if PATIENTS[p]["network"] != "sbch"]
    n = max(1, round(rem / 290))
    for amt in spread(rem, n):
        mid = R.choices([x for x, _ in mix], [w for _, w in mix])[0]
        pid = R.choice(pids)
        y, mm = R.choice(LV_MONTHS)
        LV_FIND.append(dict(measure=mid, site=PATIENTS[pid]["site"], pid=pid, d=day_in(y, mm), amount=amt, provider=R.choice(PROVIDERS[PATIENTS[pid]["site"]]), enc=None))
print(f"low-value findings {len(LV_FIND)}")
exec((Path(__file__).with_name("gen_part3.py")).read_text(encoding="utf-8"))
