"""Generate rain_v4.synthetic: row-level synthetic operational data that reproduces the PRD v0.4 story.

Every figure the UI shows is computed from these rows (rain-api/metrics_v4.py and the analytics views),
so nothing the UI shows is stored as a final number. The generator is calibrated to the scenario
targets in rain-api/seed/rain_v4_scenario.json (the Q3 contract checkpoint: 9,400 attributed members,
$412 vs $386 PMPM, the quality gate, low-value care, the BP campaign, the four networks...) so SQL over
these rows gives back the story. Change a row and the UI changes.

Deterministic (seed 2026). Recreates every table in schema `synthetic` from the PRD v0.4 planned DDL plus
a few documented extensions (columns and reference tables the UI needs that the planned model lacks).

    python scripts/e2e/synth/gen_synthetic_v4.py            (PG_* env selects the database; default rain_v4)
"""
import csv
import io
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from synth_ref import (AS_OF, CONTRACT_START, COUNTY_FIPS, FIRST, LAST, LBP_ICD, MONTHS, NETWORK_SITES, NETWORKS_INFO,  # noqa: E402
                       ZIPS, month_days)

SCEN = json.loads((ROOT / "rain-api/seed/rain_v4_scenario.json").read_text(encoding="utf-8"))
C, REC, GOV = SCEN["constants"], SCEN["records"], SCEN["governance"]
R = random.Random(2026)
T = defaultdict(list)          # table -> list of row dicts
_seq = Counter()


def nid(prefix, width=6):
    _seq[prefix] += 1
    return f"{prefix}{_seq[prefix]:0{width}d}"


def rnd_date(start: date, end: date) -> date:
    return start + timedelta(days=R.randrange((end - start).days + 1))


def ts(d: date, h=9, m=0):
    return datetime(d.year, d.month, d.day, h, m)


# ═══ 1. Networks, sites, providers ═══════════════════════════════════════════════════════════════════════
SITES = {s["id"]: s for s in C["SITES"]}
COUNTIES = {c["id"]: c for c in C["COUNTIES"]}
for g in NETWORKS_INFO:
    T["grantee"].append({"grantee_id": g["id"], "network_name": g["name"], "program_initiative": "Rural Health Outcomes Accelerator",
                         "site_count": len(NETWORK_SITES[g["id"]]), "county_fips": COUNTY_FIPS[g["hq"]],
                         "award_amount": g["award"], "start_date": date(2026, 1, 1)})
for g in NETWORKS_INFO:
    for site in NETWORK_SITES[g["id"]]:
        z = ZIPS[site["zip"]]
        T["clinic_site"].append({"clinic_site_id": site["id"], "site_name": f"{g['short']} {site['town']}",
                                 "site_type": site.get("type", "FQHC site"), "address": f"{site['town']}, NV {site['zip']}",
                                 "county_fips": COUNTY_FIPS[z["county"]], "latitude": z["lat"], "longitude": z["lon"],
                                 "telehealth_capable": site.get("telehealth", True), "grantee_id": g["id"]})
SITE_ROW = {s["clinic_site_id"]: s for s in T["clinic_site"]}

PROVIDERS = defaultdict(list)    # site -> provider ids (non-locum)
LOCUM_IDS = []


def add_provider(first, last, specialty, site, locum=False, pid=None):
    pid = pid or nid("PRV-", 4)
    T["provider"].append({"provider_id": pid, "npi": str(1_900_000_000 + len(T["provider"]) * 7919 % 99_999_999),
                          "first_name": first, "last_name": last, "specialty": specialty, "locum_flag": locum,
                          "clinic_site_id": site})
    if not locum:
        PROVIDERS[site].append(pid)
    return pid


for site in [s["clinic_site_id"] for s in T["clinic_site"]]:
    for _ in range(2 if site in SITES else 2):
        add_provider(R.choice(FIRST["en"]), R.choice(LAST), R.choice(["Family Medicine", "Internal Medicine", "Nurse Practitioner"]), site)
# named providers in the story
OKAFOR = add_provider("Samuel", "Okafor", "Family Medicine", "battleMountain", pid="PRV-OKAFOR")
RUIZ = add_provider("Ana", "Ruiz", "Family Medicine (telehealth)", "elko", pid="PRV-RUIZ")
PACE = add_provider("Jordan", "Pace", "Nurse Practitioner (telehealth)", "elko", pid="PRV-PACE")
for i, loc in enumerate(C["LOCUMS"], start=1):    # Winnemucca's rotating locum clinicians since April
    LOCUM_IDS.append(add_provider("Locum", f"Clinician {i}", "Family Medicine (locum)", "winnemucca", locum=True, pid=f"PRV-LOCUM{i}"))
LOVELOCK_LOCUM = add_provider("Locum", "Clinician 4", "Family Medicine (locum)", "lovelock", locum=True, pid="PRV-LOCUM4")

# ═══ 2. Patients and attribution ═════════════════════════════════════════════════════════════════════════
CAMP = {m["id"]: m for m in REC["campaignMembers"]}
SWAPS = {s["id"]: s for s in GOV["swaps"]}
PATIENTS = {}                    # pid -> dict(site, county, network, segment, zip, frontier, drive, age, ...)
TOWN_ZIP = {s["id"]: s["zip"] for g in NETWORK_SITES.values() for s in g}
COUNTY_ZIPS = defaultdict(list)
for z, info in ZIPS.items():
    COUNTY_ZIPS[info["county"]].append(z)


def pick_zip(site_id, frontier=None, county=None):
    county = county or ZIPS[TOWN_ZIP[site_id]]["county"]
    if frontier is None:
        frontier = R.random() < 0.28
    pool = [z for z in COUNTY_ZIPS[county] if ZIPS[z]["frontier"] == frontier] or COUNTY_ZIPS[county]
    if not frontier and R.random() < 0.75 and ZIPS[TOWN_ZIP[site_id]]["county"] == county:
        return TOWN_ZIP[site_id]
    return R.choice(pool)


def drive_for(zipc, site_id):
    if zipc == TOWN_ZIP[site_id]:
        return R.randint(5, 22)
    return ZIPS[zipc]["drive"] + R.randint(-8, 12) if ZIPS[zipc]["frontier"] else R.randint(25, 58)


def new_person(pid, site_id, network, age=None, lang=None, first=None, last=None, sex=None, zipc=None, frontier=None, drive=None,
               county=None):
    lang = lang or ("Spanish" if R.random() < 0.22 else "English")
    sex = sex or R.choice("FM")
    first = first or R.choice(FIRST["es" if lang == "Spanish" else "en"])
    last = last or R.choice(LAST)
    zipc = zipc or pick_zip(site_id, frontier, county)
    if frontier is None:
        frontier = ZIPS[zipc]["frontier"]
    age = age or R.choice([R.randint(1, 17), R.randint(18, 44), R.randint(45, 64), R.randint(65, 89)])
    drive = drive if drive is not None else drive_for(zipc, site_id)
    county = county or ZIPS[TOWN_ZIP[site_id]]["county"]
    PATIENTS[pid] = dict(site=site_id, county=county, network=network, zip=zipc, frontier=frontier, drive=drive, age=age,
                         lang=lang, first=first, last=last, sex=sex, segment="stable", conditions=set())
    T["patient"].append({"patient_id": pid, "mrn": f"MRN{len(T['patient']) + 100000}", "first_name": first, "last_name": last,
                         "birth_date": date(2026 - age, R.randint(1, 12), R.randint(1, 28)), "sex": sex,
                         "race": R.choice(["White", "American Indian or Alaska Native", "Black", "Asian", "Other"]),
                         "ethnicity": "Hispanic or Latino" if lang == "Spanish" or R.random() < 0.12 else "Not Hispanic or Latino",
                         "language": lang, "zip_code": zipc, "county_fips": COUNTY_FIPS[ZIPS[zipc]["county"]], "phone": None,
                         "home_site_id": site_id, "network_id": network})
    return PATIENTS[pid]


# 2a. the named campaign members (the 412 BP campaign; Linda Garcia is M-40107) keep their story attributes
for m in REC["campaignMembers"]:
    first, last = m["name"].split(" ", 1)
    zipc = None
    if m["frontier"]:
        zipc = R.choice([z for z in COUNTY_ZIPS[m["county"]] if ZIPS[z]["frontier"]] or COUNTY_ZIPS[m["county"]])
    else:
        zipc = TOWN_ZIP[m["siteId"]] if m["driveMin"] <= 60 else R.choice([z for z in COUNTY_ZIPS[m["county"]] if not ZIPS[z]["frontier"]])
    if m["id"] == "M-40107":
        zipc = "89820"
    p = new_person(m["id"], m["siteId"], "sbch", age=m["age"], lang=m["language"], first=first, last=last, zipc=zipc,
                   frontier=m["frontier"], drive=m["driveMin"])
    p["segment"] = "impactable"
    T["patient"][-1]["phone"] = m["phone"]

# 2b. Rosa Martinez, the scheduling patient (PRD v0.4 6.14)
ROSA = C["ROSA"]
rosa = new_person(ROSA["memberId"], "fallon", "sbch", age=ROSA["age"], lang=ROSA["language"], first="Rosa", last="Martínez",
                  sex="F", zipc="89406", frontier=False, drive=ROSA["driveMin"])
T["patient"][-1]["phone"] = "(775) 555-0164"
# 2c. the 114 members whose ranks swap between model versions (de-identified ids F-xxxx)
for s in GOV["swaps"]:
    site = R.choice(["winnemucca", "battleMountain", "lovelock", "ely", "elko", "wells"]) if s["direction"].startswith("Enters") else R.choice(list(SITES))
    p = new_person(s["id"], site, "sbch", age=R.randint(45, 80), frontier=s["direction"].startswith("Enters"), drive=s["driveMin"])
    p["segment"] = "impactable"
# 2d. everyone else in Sierra Basin, up to each site's attributed members
for sid, s in SITES.items():
    have = sum(1 for p in PATIENTS.values() if p["site"] == sid)
    for _ in range(s["members"] - have):
        new_person(nid("M-1", 5), sid, "sbch")
assert sum(1 for p in PATIENTS.values() if p["network"] == "sbch") == C["CONTRACT"]["members"], "SB members"
# 2e. the three other networks: members per county as the state view needs
for g in NETWORKS_INFO[1:]:
    sites = NETWORK_SITES[g["id"]]
    for county, n in g["members_by_county"].items():
        csites = [s["id"] for s in sites if ZIPS[s["zip"]]["county"] == county] or [sites[0]["id"]]
        for i in range(n):
            new_person(nid(f"{g['id'][0].upper()}-", 6), csites[i % len(csites)], g["id"], county=county)
for cid, c in COUNTIES.items():
    assert sum(1 for p in PATIENTS.values() if p["county"] == cid) == c["members"], cid

SB = [pid for pid, p in PATIENTS.items() if p["network"] == "sbch"]
for pid in SB:
    T["attributed_member"].append({"member_id": pid, "patient_id": pid, "payer": C["ORG"]["plan"], "contract_year": 2026,
                                   "attribution_start": CONTRACT_START, "attribution_end": date(2026, 12, 31),
                                   "aid_category": ("Child" if PATIENTS[pid]["age"] < 19 else "Aged/blind/disabled" if PATIENTS[pid]["age"] >= 65
                                                    else R.choice(["Expansion adult", "Expansion adult", "Parent/caretaker", "Aged/blind/disabled"])),
                                   "county_fips": COUNTY_FIPS[PATIENTS[pid]["county"]]})
for g in NETWORKS_INFO[1:]:
    for pid in [p for p, v in PATIENTS.items() if v["network"] == g["id"]]:
        T["attributed_member"].append({"member_id": pid, "patient_id": pid, "payer": g["payer"], "contract_year": 2026,
                                       "attribution_start": CONTRACT_START, "attribution_end": date(2026, 12, 31),
                                       "aid_category": "Medicaid managed care", "county_fips": COUNTY_FIPS[PATIENTS[pid]["county"]]})

# 2f. segments in Sierra Basin: 236 high-need, 1,180 impactable (incl. the campaign and swap members), the rest stable
seg_target = {s["id"]: s["members"] for s in C["SEGMENTS"]}
others = [pid for pid in SB if PATIENTS[pid]["segment"] == "stable" and pid != ROSA["memberId"]]
R.shuffle(others)
for pid in others[:seg_target["highNeed"]]:
    PATIENTS[pid]["segment"] = "highNeed"
need_imp = seg_target["impactable"] - sum(1 for pid in SB if PATIENTS[pid]["segment"] == "impactable")
for pid in others[seg_target["highNeed"]:seg_target["highNeed"] + need_imp]:
    PATIENTS[pid]["segment"] = "impactable"
segc = Counter(PATIENTS[pid]["segment"] for pid in SB)
assert segc == Counter(seg_target), segc

print(f"patients {len(T['patient'])}, sites {len(T['clinic_site'])}, providers {len(T['provider'])}, segments {dict(segc)}")
exec((Path(__file__).with_name("gen_part2.py")).read_text(encoding="utf-8"))
