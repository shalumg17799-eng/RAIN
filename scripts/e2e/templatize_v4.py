"""Turn the numbers in the v0.4 persona contracts and persona copy into placeholders.

Reads   rain-api/seed/rain_v4_ui_data.json        (never modified)
Writes  rain-api/seed/rain_v4_ui_templates.json   {"contracts", "personas", "mapping"}
        scripts/e2e/templatize_v4_review.md       one row per mapped number

Every number (digits, and spelled-out counts two..twelve) in every string of
``sections.contracts.<persona>`` and ``sections.personas.<persona>`` is
classified by MEANING through the ordered RULES below (first claim wins):

* M(...)  -> replaced by a ``{{ expr | filters }}`` placeholder (templating_v4)
* L(...)  -> left literal, with reason "rule", "not data" or "no source"
* digits inside identifiers (SIG-CEO-1, outreach300, v_2027, rc-n1...) are
  left literal automatically as "not data".

Numeric (non-string) fields are handled by NUMERIC_RULES: handoff counts and
inline viz numbers become ``{{ expr | native }}`` so render_obj returns ints.

Any number that no rule classifies stops the script.  Verification:

1. round trip: render_obj(templates, seed sections) == seed contracts/personas
2. meaning check: every placeholder still resolves when every numeric leaf of
   the sections is a unique sentinel (900001, ...), and its output changes
   (directly, or via count()/len() when the aggregates are offset); no digit
   is left in literal text except the classified literals.

Run:  python scripts/e2e/templatize_v4.py
"""

from __future__ import annotations

import copy
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "rain-api"
sys.path.insert(0, str(API))
import templating_v4 as T  # noqa: E402

SEED = API / "seed" / "rain_v4_ui_data.json"
OUT = API / "seed" / "rain_v4_ui_templates.json"
REVIEW = Path(__file__).with_name("templatize_v4_review.md")

DIGITS = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
WORDNUM = re.compile(r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b", re.I)

# --------------------------------------------------------------------------- #
# source expressions
# --------------------------------------------------------------------------- #
ACT = "constants.CONTRACT.actualPmpm"
EXP = "constants.CONTRACT.expectedPmpm"
MEMBERS = "constants.CONTRACT.members"
ABOVE = "constants.CONTRACT.abovePct"
ANNUAL = "constants.CONTRACT.annualGap"
DAYS = "constants.CONTRACT.daysLeft"
NEEDED = "constants.CONTRACT.gateNeeded"
GATE_N = "constants.CONTRACT.gateMeasures"
MET = "constants.CONTRACT.gateMet"
LAG = "constants.CONTRACT.claimsLagDays"
TOP = "constants.COHORT.topRanked"
AVOIDED = "constants.COHORT.avoidedCost12m"
CODING = "constants.CODING.members"
BP_NEAR = "constants.BP.nearControl"
NETWORKS = "constants.STATE.networks"
COUNTIES = "constants.STATE.counties"
LOW_BB = "constants.STATE.lowBroadbandZips"
CLINICIANS = "constants.LOW_VALUE.clinicians"
NO_REPLY = "count(records.reminders[status=No reply yet])"
CM = "records.campaignMembers"
PV = "records.previsitSummaries"
WIN = "siteId=winnemucca"
BTM = "siteId=battleMountain"
BOOKED = "status=Reached and booked"
# Denise Holloway: frontier patients outside Teresa's two sites (constants.TERESA_SITES)
FRONTIER = "frontier=true,siteId!=winnemucca,siteId!=battleMountain"
OTHER_COUNTIES = "constants.COUNTIES[id!=lander,id!=pershing]"


def site(i, f):
    return f"constants.SITES[id={i}].{f}"


def county(i, f):
    return f"constants.COUNTIES[id={i}].{f}"


def meas(i, f):
    return f"constants.MEASURES[id={i}].{f}"


def net(i, f):
    return f"constants.NETWORKS[id={i}].{f}"


def gap(i):
    return f"constants.GAP[id={i}].value"


def seg(i, f):
    return f"constants.SEGMENTS[id={i}].{f}"


def locum(n, f):
    return f"constants.LOCUMS[id=Locum clinician {n}].{f}"


def cm(cond):
    return f"count({CM}[{cond}])"


def share(num_cond, den_cond):
    return f"{cm(num_cond)} / {cm(den_cond)} * 100 | round:0 | pct"


# --------------------------------------------------------------------------- #
# rules
# --------------------------------------------------------------------------- #
class Rule:
    def __init__(self, rx, exprs=None, reason=None, note=None, who=None, path=None):
        self.rx = re.compile(rx)
        self.exprs = exprs
        self.reason = reason
        self.note = note
        self.who = re.compile(who) if who else None
        self.path = re.compile(path) if path else None

    def applies(self, who, path):
        return (self.who is None or self.who.fullmatch(who)) and (self.path is None or self.path.search(path))


def M(rx, *exprs, who=None, path=None):
    return Rule(rx, exprs=list(exprs), who=who, path=path)


def L(rx, reason, note, who=None, path=None):
    return Rule(rx, reason=reason, note=note, who=who, path=path)


NOSRC_FOCUS = ("number of focus counties (Lander and Pershing); no constant holds "
               "the focus-county list or its size")

RULES = [
    # ---- labels, codes, dates: not data -------------------------------------------
    L(r"CMS(\d+)", "not data", "eCQM measure code"),
    L(r"\b[A-Z]{3}-P(\d+)\b", "not data", "query id"),
    L(r"\bQ([1-4])\b", "not data", "quarter label"),
    L(r"HbA(1)c", "not data", "test name (HbA1c)"),
    L(r"FHIR R(4)", "not data", "standard version (FHIR R4)"),
    L(r"\((270)/(271)\)", "not data", "X12 eligibility transaction codes"),
    L(r"ACS (5)-year", "not data", "survey product name (ACS 5-year)"),
    L(r"\b(20[12]\d)\b", "not data", "calendar year / data vintage"),
    L(r"December (31)", "not data", "date: contract year end"),
    L(r"January (1)\b", "not data", "date: managed care transition"),
    L(r"\b(\d{1,2}):(\d\d) [AP]M", "not data", "time of day (notification timestamp)"),
    L(r"ZIP (89820)", "not data", "ZIP code"),
    L(r"version (1\.3)", "not data", "model version label (constants.MODEL.version is the string 'v1.3')"),
    L(r"Locum clinician (\d)", "not data", "clinician label (constants.LOCUMS id)"),
    L(r"^([1-3])\. ", "not data", "list numbering"),
    L(r"per (1,000)", "not data", "rate unit (per 1,000 members)"),
    L(r"over (12) months", "not data", "projection window (constants.COHORT.avoidedCost12m)"),
    L(r"\b(12)-month", "not data", "projection window"),
    # ---- business rules -------------------------------------------------------------
    L(r"within (10) points", "rule", "near-control definition (constants.BP.withinPoints)"),
    L(r"\b(140)/(90)\b", "rule", "BP control / titration threshold"),
    L(r">(9)%", "rule", "measure definition: HbA1c poor control is over 9%"),
    L(r"[Uu]nder (80)%", "rule", "medication adherence threshold"),
    L(r"[Uu]nder (11)\b", "rule", "small-cell suppression (fewer than 11)"),
    L(r"[Uu]nder (40)%", "rule", "video-ready broadband floor (constants.STATE.broadbandFloorPct)"),
    L(r"\b(72), (24) and (3) hours", "rule", "reminder timing"),
    L(r"\b(24)-hour cut-off", "rule", "reminder reply cut-off"),
    L(r"\b(six) months", "rule", "lookback window (no primary care visit in six months)"),
    L(r"\b(three) months of treatment", "rule", "clinical fact (HbA1c reflects about three months)"),
    L(r"\b(three) new slots", "rule", "number of alternative slots offered"),
    # ---- spelled-out counts that are copy, not data ---------------------------------
    L(r"\b([Tt]hree) (?:quality )?signals", "not data", "count of signal cards (editorial)"),
    L(r"\b([Tt]hree) (?:moves|things)", "not data", "editorial count"),
    L(r"\b(Two) (?:hand-offs|standing orders)", "not data", "editorial count (contract content)"),
    L(r"\b(ten)\b", "not data", "display limit (top 10)"),
    L(r"\b(five) of your patients", "not data", "display limit (top 5)"),
    L(r"\b(Six) public sources", "not data", "rows of the inline public-source table"),
    # ---- no source in the reference data --------------------------------------------
    L(r"^(6) of the 73 members shown", "no source",
      "rows shown in the inline coding table; the 73-member coding list is not in the reference data"),
    L(r"Visit in (\d+) days", "no source",
      "days to next visit for a de-identified coding-recapture member; no coding-member records in the reference data"),
    L(r"\b(2) (?:of 6 )?counties", "no source", NOSRC_FOCUS),
    L(r"\b(two) counties", "no source", NOSRC_FOCUS),

    # ================================ mapped ==========================================
    # ---- contract economics (CEO) ----
    M(r"at (\$437) and (\$431) against the network.s (\$412)",
      site("battleMountain", "pmpm") + " | usd", site("winnemucca", "pmpm") + " | usd", ACT + " | usd"),
    M(r"(\$412) (?:vs|/) (\$386)", ACT + " | usd", EXP + " | usd"),
    M(r"(\$412)", ACT + " | usd"),
    M(r"(\$431)", site("winnemucca", "pmpm") + " | usd"),
    M(r"(9,400)", MEMBERS + " | num"),
    M(r"(6\.7%)", ABOVE + " | pct"),
    M(r"(\$2\.9M)", ANNUAL + " | usdM:1"),
    M(r"(\$26) (?:PMPM )?gap", f"{ACT} - {EXP} | usd"),
    M(r"(\$12) coding gap", gap("coding") + " | usd"),
    M(r"(\$8) excess", gap("ed") + " | usd"),
    M(r"(\$5\.50) low-value", gap("lowValue") + " | usd:2"),
    M(r"(\$0\.50) noise", gap("other") + " | usd:2"),
    M(r"\b(four)(?: parts|-part gap)", "len(constants.GAP) | words"),
    M(r"(\$398)", "constants.CODING.correctedBenchmark | usd"),
    M(r"(\$1\.1M)", AVOIDED + " | usdM:1"),
    M(r"[Tt]op (300)", TOP),
    M(r"(236) high-need members \((2\.5%)\) account for (41%) of spend",
      seg("highNeed", "members"), seg("highNeed", "sharePct") + " | pct", seg("highNeed", "spendPct") + " | pct"),
    M(r"(1,180)", seg("impactable", "members") + " | num"),
    M(r"\b(73)\b", CODING),
    M(r"(3\.1%)", "constants.CODING.understatedPct | pct"),
    # ---- quality gate ----
    M(r"[Mm]eets? (2) of the (3) measures needed", MET, NEEDED),
    M(r"at (2) of the (3) measures needed", MET, NEEDED),
    M(r"meet (2) of the (5) measures and need (3)", MET, GATE_N, NEEDED),
    M(r"\b(2) of (5) met . needs (3)", MET, GATE_N, NEEDED),
    M(r"reaches (3) of (5)", NEEDED, GATE_N),
    M(r"\b(2) of (5)\b", MET, GATE_N),
    M(r"\b(Two) measures are met", MET + " | words | cap"),
    M(r"\b(five)-measure", GATE_N + " | words"),
    M(r"\b(58) days", DAYS),
    M(r"^(58)$", DAYS, who="ceo", path=r"^kpis/6/value$"),
    M(r"colorectal screening (7) points short", f"{meas('CMS130', 'target')} - {meas('CMS130', 'current')}"),
    M(r"HbA1c poor control (4) points high", f"{meas('CMS122', 'current')} - {meas('CMS122', 'target')}"),
    M(r"\b(7) points short", "constants.BP.shortPts"),
    M(r"\b(58%)", meas("CMS165", "current") + " | pct"),
    M(r"\b(65%)", meas("CMS165", "target") + " | pct"),
    M(r"\b(34%)", meas("CMS122", "current") + " | pct"),
    M(r"\b(34) percent", meas("CMS122", "current")),
    M(r"(30%) or lower", meas("CMS122", "target") + " | pct"),
    M(r"\b(30) percent", meas("CMS122", "target")),
    M(r"about (37%)", meas("CMS130", "projected") + " | pct"),
    M(r"\b(33%)", meas("CMS130", "current") + " | pct"),
    M(r"[Tt]arget (40%)", meas("CMS130", "target") + " | pct"),
    M(r"the (40%) target", meas("CMS130", "target") + " | pct"),
    M(r"[Aa]bout (4) points", "constants.FIT.gainPts"),
    # ---- BP campaign ----
    M(r"[Aa]bout (180) more", "constants.BP.needed"),
    M(r"\b(180) gets you", "constants.BP.needed"),
    M(r"[Aa]bout (210) of the", "constants.BP.projected"),
    M(r"\b(268)\b", "constants.BP.telehealth"),
    M(r"\b(144) in person", "constants.BP.inPerson"),
    M(r"\b(37) (?:need a cuff|telehealth members)", "constants.BP.cuffsToShip"),
    M(r"\b(62) of 412", "constants.CARE.booked"),
    M(r"\b(412)\b", BP_NEAR),
    M(r"\b(46)\b", "constants.CARE.teresaTop"),
    # ---- low-value care / Winnemucca imaging ----
    M(r"(\$618K)", "constants.LOW_VALUE.annual | usdK"),
    M(r"(2,140)", "constants.LOW_VALUE.services | num"),
    M(r"\b(14) measures", "constants.LOW_VALUE.measures"),
    M(r"(\$162K)", "constants.LOW_VALUE.lbpImaging | usdK"),
    M(r"(71%)", "constants.LOW_VALUE.winnemuccaSharePct | pct"),
    M(r"(\$196K)", site("winnemucca", "lowValue") + " | usdK"),
    M(r"^(27%)$", locum(1, "ratePct") + " | pct", who="cmo", path=r"^viz/v_locums/props/rows/0/rate$"),
    M(r"^(28%)$", locum(2, "ratePct") + " | pct", who="cmo", path=r"^viz/v_locums/props/rows/1/rate$"),
    M(r"^(26%)$", locum(3, "ratePct") + " | pct", who="cmo", path=r"^viz/v_locums/props/rows/2/rate$"),
    M(r"at (26) to (28%)", "min(constants.LOCUMS.ratePct)", "max(constants.LOCUMS.ratePct) | pct"),
    M(r"\b(27%)", site("winnemucca", "imagingPct") + " | pct"),
    M(r"\b(9%)", "constants.LOW_VALUE.networkRatePct | pct"),
    M(r"\b(Three) rotating clinicians", CLINICIANS + " | words | cap"),
    M(r"\b(three) rotating clinicians", CLINICIANS + " | words"),
    # ---- avoidable ED ----
    M(r"highest at (312) avoidable ED", net("sbch", "edPer1000"), who="bell"),
    M(r"\b(312)\b", "constants.ED.per1000"),
    M(r"\b(251)\b", "constants.ED.benchmark"),
    M(r"\b(298)\b", "constants.STATE.edPer1000"),
    # ---- data & model (CIO) ----
    M(r"(19) public \+ (6) synthetic", "constants.MODEL.publicSources", "constants.MODEL.syntheticSources"),
    M(r"\b(45)(?=[ -]day)", LAG),
    M(r"(Under 1 hour)", "constants.MODEL.adtLag"),
    M(r"(under 1 hour)", "constants.MODEL.adtLag | lower"),
    M(r"from 18% to (3%)", "constants.MODEL.frontierGapAfterPct | pct"),
    M(r"\b(18%)", "constants.MODEL.frontierGapPct | pct"),
    M(r"(57) lower-need town members leave", "count(governance.swaps[direction=Leaves top 300])"),
    M(r"\b(41) of the 57", "constants.MODEL.inBpDenominator"),
    M(r"\b(57)\b", "constants.MODEL.missingFromTop"),
    M(r"(31%) fewer", "constants.MODEL.fewerVisitsPct | pct"),
    M(r"(74)-minute median", "constants.MODEL.medianDriveMin"),
    M(r"(190) have no broadband", "constants.MODEL.noBroadband"),
    M(r"(41) percent of the weight",
      "(governance.FEATURES[id=cost].weight + governance.FEATURES[id=pcVisits].weight) * 100 | round:0"),
    M(r"\b(214)\b", "constants.MODEL.unmatchedRecords"),
    M(r"(38%) of these members live in frontier", share(f"{WIN},frontier=true", WIN), who="hargrove"),
    M(r"\b(38%)", "constants.MODEL.socialScreenedPct | pct"),
    # ---- state program (state, bell) ----
    M(r"(\$2\.4M)", "constants.STATE.lowValue | usdM:1"),
    M(r"(31,600)", "constants.STATE.members | num"),
    M(r"\b(4) (?:networks )?\((18) sites\)", NETWORKS, "constants.STATE.sites"),
    M(r"\b(4) grantees", NETWORKS),
    M(r"^(6) rural", COUNTIES),
    M(r"^(6) of (6)$", "constants.STATE.hpsaCounties", COUNTIES),
    M(r"\b(6) ZIP areas", LOW_BB),
    M(r"\b2 of (6) counties", COUNTIES),
    M(r"Lander and Pershing lost (14) percent", "constants.STATE.pcVisitDropPct"),
    M(r"lost (2) to (5) percent",
      f"max({OTHER_COUNTIES}.pcVisitChangePct) | abs", f"min({OTHER_COUNTIES}.pcVisitChangePct) | abs"),
    M(r"\b(14%)", "constants.STATE.pcVisitDropPct | pct"),
    M(r"\b(12%)", "constants.STATE.optionAEdCutPct | pct"),
    M(r"at (63) percent", net("rvfh", "bpControlPct")),
    M(r"lowest at (55) percent", net("hrhp", "bpControlPct")),
    M(r"other (four) counties", f"count({OTHER_COUNTIES}) | words"),
    *[r for cid, name in [("elko", "Elko"), ("humboldt", "Humboldt"), ("lander", "Lander"),
                          ("pershing", "Pershing"), ("whitePine", "White Pine"), ("churchill", "Churchill")]
      for r in (M(rf"{name} County lost (\d+) percent", county(cid, "pcVisitChangePct") + " | abs"),
                M(rf"{name} County lost .*? (?:sits at|rose to) (\d+) per", county(cid, "edPer1000")))],
    M(r"\b(296)\b", county("humboldt", "edPer1000")),
    M(r"\b(Six) frontier ZIP", LOW_BB + " | words | cap"),
    M(r"\b(six) (?:frontier |low-broadband )ZIP", LOW_BB + " | words"),
    M(r"\b(Four) grantees", NETWORKS + " | words | cap"),
    M(r"\b(four) (?:templates|grantees)", NETWORKS + " | words"),
    M(r"\b(four) (?:participating )?networks", NETWORKS + " | words"),
    M(r"\b(three) options", "len(constants.OPTIONS) | words"),
    M(r"\b(six) counties", COUNTIES + " | words"),
    M(r"of the (six)\b", COUNTIES + " | words"),
    # ---- CHW (Teresa) ----
    M(r"\b(two) sites", "len(constants.TERESA_SITES) | words"),
    M(r"\b(Nine) patients with visits tomorrow", NO_REPLY + " | words | cap"),
    M(r"\b(five) you called", "constants.CARE.teresaNoCallback | words"),
    M(r"\b(5) call-backs", "constants.CARE.teresaNoCallback"),
    M(r"^(5)$", "constants.CARE.teresaNoCallback", who="chw", path=r"^kpis/2/value$"),
    M(r"^(200)$", "constants.CARE.teresaOpen", who="chw", path=r"^kpis/3/value$"),
    M(r"^(18)$", "constants.CARE.controlled", who="chw", path=r"^kpis/5/value$"),
    M(r"an (81)-minute drive", f"{CM}[id=M-40107].driveMin"),
    # ---- access (Brandon) ----
    M(r"\b(23)\b", "constants.CARE.brandonBookings", who="access"),
    M(r"\b(9) (?:visits tomorrow|unconfirmed)", "constants.CARE.brandonUnconfirmed", who="access"),
    M(r"^(9)$", "constants.CARE.brandonUnconfirmed", who="access", path=r"^kpis/1/value$"),
    M(r"\b(4) (?:patients replied R|R replies)", "constants.CARE.brandonRReplies", who="access"),
    M(r"^(4)$", "constants.CARE.brandonRReplies", who="access", path=r"^kpis/2/value$"),
    M(r"\b(7) sites", "len(constants.SITES)", who="access"),
    M(r"\b(2) telehealth providers", "constants.CARE.telehealthProviders", who="access"),
    # ---- Winnemucca site lead (Hargrove) ----
    M(r"(1,700)", site("winnemucca", "members") + " | num"),
    M(r"\b(92)\b", cm(WIN), who="hargrove"),
    M(r"\b(6) (?:are )?booked", cm(f"{WIN},{BOOKED}"), who="hargrove"),
    M(r"\b(86) of Winnemucca", cm(f"{WIN},status!=Reached and booked"), who="hargrove"),
    M(r"(66%)", share(f"{WIN},mode=Telehealth", WIN), who="hargrove"),
    # ---- frontier CHW (Holloway) ----
    M(r"\b(89)\b", cm(FRONTIER), who="holloway"),
    M(r"\b(12)\b", cm(f"{FRONTIER},channel=Voice"), who="holloway"),
    M(r"\b(9)\b", NO_REPLY, who="holloway"),
    M(r"^(18)$", cm(f"{FRONTIER},cuff=Ship first"), who="holloway", path=r"^kpis/3/value$"),
    M(r"\b(40) of your frontier", cm(f"{FRONTIER},socialNeeds"), who="holloway"),
    # ---- Battle Mountain front desk (Brooks) ----
    M(r"^(6)$", "count(records.inboxItems[status=Open])", who="brooks", path=r"^kpis/0/value$"),
    M(r"\b(6) inbox items", "count(records.inboxItems[status=Open])", who="brooks"),
    M(r"^(8)$", "len(datasets.kb_eligibility.rows)", who="brooks", path=r"^kpis/1/value$"),
    M(r"^(9)$", cm(f"{BTM},channel=Voice"), who="brooks", path=r"^kpis/2/value$"),
    M(r"\b(9) patients", cm(f"{BTM},channel=Voice"), who="brooks"),
    M(r"^(59)$", cm(BTM), who="brooks", path=r"^kpis/3/value$"),
    M(r"\b(7) booked", cm(f"{BTM},{BOOKED}"), who="brooks"),
    # ---- clinician (Okafor) ----
    M(r"\b(8) confirmed visits", f"len({PV})", who="okafor"),
    M(r"^(8)$", f"len({PV})", who="okafor", path=r"^kpis/0/value$"),
    M(r"(75%)", f"count({PV}[mode=Telehealth]) / len({PV}) * 100 | round:0 | pct", who="okafor"),
    M(r"^(3)$", f"count({PV}[codingRecapture=true])", who="okafor", path=r"^kpis/2/value$"),
    M(r"^(3)$", f"count({PV}[adherence=Under 80%])", who="okafor", path=r"^kpis/3/value$"),
]

# Numeric (non-string) leaves: (persona regex, path regex, expr | (reason, note))
NUMERIC_RULES = [
    ("ceo", r"^handoffs/0/count$", TOP),
    ("ceo", r"^handoffs/1/count$", CODING),
    ("cmo", r"^handoffs/0/count$", BP_NEAR),
    ("state", r"^handoffs/0/count$", NETWORKS),
    ("cmo", r"^viz/v_locums/props/rows/0/orders$", locum(1, "orders")),
    ("cmo", r"^viz/v_locums/props/rows/1/orders$", locum(2, "orders")),
    ("cmo", r"^viz/v_locums/props/rows/2/orders$", locum(3, "orders")),
    ("cio", r"^viz/v_match/props/rows/\d+/count$",
     ("no source", "patient-matching failures by reason; reference data only has the total "
                   "(constants.MODEL.unmatchedRecords)")),
    (".*", r"^steps/[^/]+/step$", ("not data", "step order")),
    (".*", r"/props/columns$", ("not data", "grid layout")),
]


# --------------------------------------------------------------------------- #
# templatizing
# --------------------------------------------------------------------------- #
def leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, path + (i,))
    else:
        yield path, obj


def set_at(obj, path, value):
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value


def tokens(text):
    out = [(m.start(), m.end(), m.group(0), "digits") for m in DIGITS.finditer(text)]
    out += [(m.start(), m.end(), m.group(0), "word") for m in WORDNUM.finditer(text)]
    return sorted(out)


def identifier_around(text, s, e):
    a, b = s, e
    while a > 0 and not re.match(r"[\s(),;\"]", text[a - 1]):
        a -= 1
    while b < len(text) and not re.match(r"[\s(),;\"]", text[b]):
        b += 1
    return text[a:b]


def is_identifier_digit(text, s, e):
    prev = text[s - 1] if s > 0 else ""
    prev2 = text[s - 2] if s > 1 else ""
    nxt = text[e] if e < len(text) else ""
    return (prev.isalpha() or prev == "_" or (prev == "-" and prev2.isalpha())
            or nxt.isalpha() or nxt == "_")


def snippet(text, s, e, width=60):
    """About ``width`` characters of ``text`` around [s, e), shifted to stay inside the string."""
    pad = max(0, (width - (e - s)) // 2)
    a = max(0, s - pad)
    b = min(len(text), max(e + pad, a + width))
    a = max(0, min(a, b - width))
    return ("..." if a > 0 else "") + text[a:b] + ("..." if b < len(text) else "")


def templatize_string(section, who, path, text, mapping, errors):
    claims = []  # (s, e, entry)

    def overlaps(s, e):
        return any(s < ce and cs < e for cs, ce, _ in claims)

    for rule in RULES:
        if not rule.applies(who, path):
            continue
        for m in rule.rx.finditer(text):
            for gi in range(1, (m.re.groups or 0) + 1):
                s, e = m.span(gi)
                if s < 0 or overlaps(s, e):
                    continue
                entry = {"persona": who, "section": section, "field": path, "offset": s,
                         "original": text[s:e], "context": snippet(text, s, e)}
                if rule.exprs is not None:
                    expr = rule.exprs[gi - 1]
                    entry.update(status="mapped", placeholder="{{ " + expr + " }}",
                                 source=expr.split(" | ")[0] if " | " in expr else expr,
                                 reason=None, note=None)
                else:
                    entry.update(status="literal", placeholder=None, source=None,
                                 reason=rule.reason, note=rule.note)
                claims.append((s, e, entry))

    # every number token must be inside a claim, or be part of an identifier
    for s, e, tok, kind in tokens(text):
        inside = [c for c in claims if c[0] <= s and e <= c[1]]
        if inside:
            inside[0][2].setdefault("kind", kind)
            continue
        if overlaps(s, e):
            errors.append(f"{section}/{who}/{path}: token {tok!r} partly claimed in {text!r}")
            continue
        if kind == "digits" and is_identifier_digit(text, s, e):
            ident = identifier_around(text, s, e)
            claims.append((s, e, {"persona": who, "section": section, "field": path, "offset": s,
                                  "original": tok, "context": snippet(text, s, e), "status": "literal",
                                  "placeholder": None, "source": None, "reason": "not data",
                                  "note": f"identifier ({ident})", "kind": kind}))
            continue
        errors.append(f"{section}/{who}/{path}: unclassified {kind} {tok!r} in {text!r}")

    for s, e, entry in claims:
        if "kind" not in entry:
            errors.append(f"{section}/{who}/{path}: rule claimed {entry['original']!r} which is not a number")

    out = text
    for s, e, entry in sorted(claims, key=lambda c: -c[0]):
        if entry["status"] == "mapped":
            out = out[:s] + entry["placeholder"] + out[e:]
    for _, _, entry in sorted(claims, key=lambda c: c[0]):
        mapping.append(entry)
    return out


def templatize_number(section, who, path, value, mapping, errors):
    for prx, rx, spec in NUMERIC_RULES:
        if re.fullmatch(prx, who) and re.search(rx, path):
            entry = {"persona": who, "section": section, "field": path, "offset": None,
                     "original": str(value), "context": f"{path} = {value}", "kind": "numeric field"}
            if isinstance(spec, str):
                ph = "{{ " + spec + " | native }}"
                entry.update(status="mapped", placeholder=ph, source=spec, reason=None, note=None)
                mapping.append(entry)
                return ph
            entry.update(status="literal", placeholder=None, source=None, reason=spec[0], note=spec[1])
            mapping.append(entry)
            return value
    errors.append(f"{section}/{who}/{path}: unclassified numeric field {value!r}")
    return value


def build(seed_sections):
    mapping, errors = [], []
    stats = Counter()
    result = {}
    for section in ("contracts", "personas"):
        result[section] = copy.deepcopy(seed_sections[section])
        for who, obj in seed_sections[section].items():
            for path, value in leaves(obj):
                pstr = "/".join(map(str, path))
                if isinstance(value, str):
                    stats["strings"] += 1
                    if "{{" in value or "}}" in value:
                        errors.append(f"{section}/{who}/{pstr}: seed text already contains braces")
                    if DIGITS.search(value) or WORDNUM.search(value):
                        stats["strings_with_numbers"] += 1
                    new = templatize_string(section, who, pstr, value, mapping, errors)
                    if new != value:
                        set_at(result[section][who], path, new)
                        stats["strings_templated"] += 1
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    stats["numeric_fields"] += 1
                    new = templatize_number(section, who, pstr, value, mapping, errors)
                    if new != value:
                        set_at(result[section][who], path, new)
    return result, mapping, errors, stats


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #
def ref_sections(seed_sections):
    return {k: v for k, v in seed_sections.items() if k not in ("contracts", "personas")}


def round_trip(templates, seed_sections, ref):
    diffs = []
    for section in ("contracts", "personas"):
        rendered = T.render_obj(templates[section], ref)
        for who in seed_sections[section]:
            want = dict(leaves(seed_sections[section][who]))
            got = dict(leaves(rendered[who]))
            for path, value in want.items():
                if got.get(path) != value or type(got.get(path)) is not type(value):
                    diffs.append((section, who, "/".join(map(str, path)), value, got.get(path)))
        if rendered != seed_sections[section]:
            if not diffs:
                diffs.append((section, "*", "*", "structure differs", ""))
    return diffs


def filter_fields(templates):
    fields = set()
    for section in ("contracts", "personas"):
        for _, v in leaves(templates[section]):
            if isinstance(v, str):
                for m in T.PLACEHOLDER.finditer(v):
                    for br in re.findall(r"\[([^\]]*)\]", m.group(1)):
                        for cond in br.split(","):
                            name = re.split(r"!?=", cond.strip(), maxsplit=1)[0].strip()
                            if re.fullmatch(r"[A-Za-z_]\w*", name):
                                fields.add(name)
    return fields


def perturb(ref, keep_keys):
    counter = itertools.count(900001)

    def walk(o, key=None):
        if isinstance(o, bool) or o is None:
            return o
        if isinstance(o, (int, float)):
            return next(counter)
        if isinstance(o, str):
            if key in keep_keys:
                return o
            return DIGITS.sub(lambda m: str(next(counter)), o)
        if isinstance(o, dict):
            return {k: walk(v, k) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v, key) for v in o]
        return o

    return walk(ref)


def meaning_check(templates, ref):
    """Return per-placeholder results under numeric and aggregate perturbation."""
    pert = perturb(ref, filter_fields(templates))
    results = []
    unresolved = []
    # whole-object render under perturbation must succeed and leave no braces
    for section in ("contracts", "personas"):
        try:
            out = T.render_obj(templates[section], pert)
            for path, v in leaves(out):
                if isinstance(v, str) and ("{{" in v or "}}" in v):
                    unresolved.append((section, "/".join(map(str, path)), v))
        except T.TemplateError as exc:
            unresolved.append((section, "*", str(exc)))

    bodies = []
    for section in ("contracts", "personas"):
        for who, obj in templates[section].items():
            for path, v in leaves(obj):
                if isinstance(v, str):
                    for m in T.PLACEHOLDER.finditer(v):
                        bodies.append((section, who, "/".join(map(str, path)), m.group(1)))

    def ev(body, sections):
        try:
            return str(T.evaluate(body, sections))
        except T.TemplateError as exc:
            return f"ERROR {exc}"

    base = [ev(b, ref) for *_, b in bodies]
    p1 = [ev(b, pert) for *_, b in bodies]
    # pass 2: aggregates offset by a sentinel, numbers untouched
    orig = dict(T.FUNCS)
    counter = itertools.count(900001)
    try:
        for name, fn in orig.items():
            T.FUNCS[name] = (lambda f: (lambda v, ctx: f(v, ctx) + next(counter)))(fn)
        p2 = [ev(b, ref) for *_, b in bodies]
    finally:
        T.FUNCS.clear()
        T.FUNCS.update(orig)
    for (section, who, path, body), b0, b1, b2 in zip(bodies, base, p1, p2):
        results.append({
            "section": section, "persona": who, "field": path, "expr": body.strip(),
            "base": b0, "numeric": b1, "aggregate": b2,
            "sentinel_visible": bool(re.search(r"9\d{5}|900,\d{3}", b1)),
            "changed": (b1 != b0 and not b1.startswith("ERROR")) or (b2 != b0 and not b2.startswith("ERROR")),
            "error": b1 if b1.startswith("ERROR") else None,
        })
    return results, unresolved


def hidden_literals(templates, mapping):
    """Digits/words left in literal text must match the classified literals one to one."""
    expected = Counter((e["section"], e["persona"], e["field"]) for e in mapping
                       if e["status"] == "literal" and e["kind"] != "numeric field")
    found = Counter()
    for section in ("contracts", "personas"):
        for who, obj in templates[section].items():
            for path, v in leaves(obj):
                if isinstance(v, str):
                    text = T.PLACEHOLDER.sub(" ", v)
                    n = len(DIGITS.findall(text)) + len(WORDNUM.findall(text))
                    if n:
                        found[(section, who, "/".join(map(str, path)))] = n
    return {k: (found.get(k, 0), expected.get(k, 0)) for k in set(found) | set(expected)
            if found.get(k, 0) != expected.get(k, 0)}


# --------------------------------------------------------------------------- #
# review file
# --------------------------------------------------------------------------- #
def md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_review(mapping, stats, rt_diffs, checks):
    mapped = [e for e in mapping if e["status"] == "mapped"]
    literal = [e for e in mapping if e["status"] == "literal"]
    lines = [
        "# RAIN v0.4 templatize review",
        "",
        "Generated by `scripts/e2e/templatize_v4.py` from `rain-api/seed/rain_v4_ui_data.json`.",
        f"Templates: `rain-api/seed/rain_v4_ui_templates.json`. Renderer: `rain-api/templating_v4.py`.",
        "",
        f"- Strings scanned: {stats['strings']} ({stats['strings_with_numbers']} contain numbers), "
        f"numeric fields: {stats['numeric_fields']}",
        f"- Numbers mapped to placeholders: {len(mapped)}",
        f"- Numbers left literal: {len(literal)} ("
        + ", ".join(f"{k}: {v}" for k, v in sorted(Counter(e['reason'] for e in literal).items())) + ")",
        "- Mapped by kind: " + ", ".join(f"{k}: {v}" for k, v in sorted(Counter(e['kind'] for e in mapped).items())),
        f"- Round trip differences: {len(rt_diffs)}",
        f"- Placeholders checked under sentinels: {checks['placeholders']}, unchanged: {checks['unchanged']}, "
        f"unresolved: {checks['unresolved']}, hidden literals: {checks['hidden']}",
        "",
        "## Mapped numbers",
        "",
        "| # | Persona | Field | Number | Original text (context) | Placeholder |",
        "|---|---|---|---|---|---|",
    ]
    for i, e in enumerate(mapped, 1):
        field = ("personas/" if e["section"] == "personas" else "") + e["field"]
        lines.append(f"| {i} | {e['persona']} | `{md(field)}` | {md(e['original'])} | {md(e['context'])} | "
                     f"`{md(e['placeholder'])}` |")
    lines += ["", "## Numbers left literal", "",
              "| # | Persona | Field | Number | Original text (context) | Reason | Note |",
              "|---|---|---|---|---|---|---|"]
    for i, e in enumerate(literal, 1):
        field = ("personas/" if e["section"] == "personas" else "") + e["field"]
        lines.append(f"| {i} | {e['persona']} | `{md(field)}` | {md(e['original'])} | {md(e['context'])} | "
                     f"{e['reason']} | {md(e['note'])} |")
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
def main():
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    sections = seed["sections"]
    ref = ref_sections(sections)

    templates, mapping, errors, stats = build(sections)
    if errors:
        print(f"{len(errors)} unclassified or conflicting numbers:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    rt = round_trip(templates, sections, ref)
    results, unresolved = meaning_check(templates, ref)
    hidden = hidden_literals(templates, mapping)
    unchanged = [r for r in results if not r["changed"]]
    checks = {"placeholders": len(results), "unchanged": len(unchanged),
              "unresolved": len(unresolved), "hidden": len(hidden)}

    doc = {"contracts": templates["contracts"], "personas": templates["personas"], "mapping": mapping}
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_review(mapping, stats, rt, checks)

    mapped = [e for e in mapping if e["status"] == "mapped"]
    literal = [e for e in mapping if e["status"] == "literal"]
    summary = {
        "strings_scanned": stats["strings"],
        "strings_with_numbers": stats["strings_with_numbers"],
        "strings_templated": stats["strings_templated"],
        "numeric_fields": stats["numeric_fields"],
        "mapped": len(mapped),
        "mapped_by_kind": dict(Counter(e["kind"] for e in mapped)),
        "literal": len(literal),
        "literal_by_reason": dict(Counter(e["reason"] for e in literal)),
        "round_trip_differences": len(rt),
        "placeholders": len(results),
        "changed_with_sentinel_visible": sum(r["changed"] and r["sentinel_visible"] for r in results),
        "changed_derived_or_aggregate": sum(r["changed"] and not r["sentinel_visible"] for r in results),
        "unchanged": len(unchanged),
        "unresolved": len(unresolved),
        "hidden_literals": len(hidden),
    }
    print(json.dumps(summary, indent=1))
    for d in rt[:20]:
        print("ROUND TRIP DIFF", d)
    for r in unchanged[:20]:
        print("UNCHANGED", r)
    for u in unresolved[:20]:
        print("UNRESOLVED", u)
    for k, v in list(hidden.items())[:20]:
        print("HIDDEN LITERAL", k, v)
    print("no source:")
    for e in literal:
        if e["reason"] == "no source":
            print(f"  {e['persona']}/{e['field']}: {e['original']!r} in {e['context']!r}")
    ok = not (rt or unchanged or unresolved or hidden)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
