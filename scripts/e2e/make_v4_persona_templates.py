"""Add the patient and payer personas to rain-api/seed/rain_v4_ui_templates.json: contracts and persona copy for
Linda Garcia (linda), Rosa Martínez (rosa) and Hannah Lee (hannah), PRD v0.4 sections 6.13, 6.14 and 6.7.

Every number is a {{ ... }} placeholder over the context metrics_v4 computes (constants.PATIENTS, constants.HANNAH,
constants.ORG and the lg_/rm_/hl_ datasets from rain-api/metrics_personas_v4.py). Literal text keeps only ids, rules
(140/90, the 72/24/3 hour reminder plan, 270/271) and labels; rain-api/test_personas_templates_v4.py holds the
templates to that. Idempotent: re-running replaces the three entries and leaves the other eleven personas alone.

Usage (repo root):  python scripts/e2e/make_v4_persona_templates.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "rain-api/seed/rain_v4_ui_templates.json"


def P(key):  # a patient's computed record
    return f"constants.PATIENTS.{key}"


def dt(name):
    return {"type": "data_table", "props": {"dataset": name}}


def kpi(id_, label, value, source, icon, tone, chip=None, detail=None):
    k = {"id": id_, "label": label, "value": value}
    if detail:
        k["detail"] = detail
    k.update(source=source, icon=icon, tone=tone)
    if chip:
        k["chip"] = chip
    return k


def step(ai, sources, chips, asks=None, viz=None, next_=None, **kw):
    s = {}
    if kw.get("step"):
        s["step"] = kw.pop("step")
    if kw.get("capability"):
        s["capability"] = kw.pop("capability")
    if asks:
        s["asks"] = asks
    s["ai"] = ai
    if kw.get("points"):
        s["points"] = kw.pop("points")
    s.update(sources=sources, chips=chips)
    if next_:
        s["next"] = next_
    if kw.get("launch"):
        s["launch"] = kw.pop("launch")
    if viz:
        s["viz"] = viz
    return s


# ─── Linda Garcia: the campaign patient (Use Case B, her own record only) ────────────────────────────────────
L = P("linda")
ORG = "constants.ORG"
Q_NEXT, Q_REM, Q_READ, Q_DUE, Q_MISS, Q_REACH = ("When is my next visit?", "What reminders will I get?",
                                                 "How do I send my blood pressure reading?", "What is due at my visit?",
                                                 "What if I miss my visit?", "How do I reach the clinic?")
Q_ANSWER, Q_OPEN, Q_COVER = "How do I answer a reminder?", "Open my messages", "Is my coverage active?"
linda = {
    "signals": [],
    "kpis": [
        kpi("next", "Next visit", f"{{{{ {L}.next.date }}}}", "Clinic schedule", "calendar", "neutral", Q_NEXT,
            f"{{{{ {L}.next.time }}}} · {{{{ {L}.next.mode | cap }}}}"),
        kpi("reminders", "Reminders to come", f"{{{{ {L}.reminders.toCome }}}}", "SMS reminders", "message-square", "warning", Q_ANSWER,
            f"{{{{ {L}.reminders.offsets }}}}"),
        kpi("reading", "Latest home reading", f"{{{{ {L}.readings.latest }}}}", "Home cuff", "heart-pulse", "good", Q_READ,
            f"{{{{ {L}.readings.latestDate }}}}"),
        kpi("checks", "Checks due", f"{{{{ {L}.checks.open }}}}", "Care gaps", "clipboard-check", "critical", Q_DUE, "Open for you"),
    ],
    "steps": {
        "lg_brief": step(f"Hola, {{{{ {L}.first }}}}: your next visit is {{{{ {L}.next.modeA }}}} on {{{{ {L}.next.when }}}}.",
                         ["Clinic schedule", "SMS Reminders"], [Q_NEXT, Q_ANSWER, Q_READ], next_=Q_NEXT, viz=["v_tasks"]),
        "lg_visit": step(f"Your next visit is {{{{ {L}.next.modeA }}}} with {{{{ {L}.next.provider }}}} on {{{{ {L}.next.when }}}}, "
                         f"and your link is {{{{ {L}.next.link }}}}.",
                         ["Clinic schedule"], [Q_ANSWER, Q_MISS], asks=[Q_NEXT], viz=["v_visits"]),
        "lg_reminders": step(f"You get {{{{ {L}.reminders.planned | words }}}} reminders by {{{{ {L}.reminders.channel }}}} in "
                             f"{{{{ {L}.reminders.language }}}}, {{{{ {L}.reminders.offsets }}}}: reply C to confirm or R to change the visit.",
                             ["SMS Reminders", "Contact Preferences"], [Q_MISS, Q_REACH], asks=[Q_ANSWER, Q_REM], viz=["v_reminders"]),
        "lg_reading": step(f"Text your home cuff reading to the clinic; your latest on file is {{{{ {L}.readings.latest }}}} from "
                           f"{{{{ {L}.readings.latestDate }}}}, and a reading under 140/90 closes your blood pressure check.",
                           ["Remote BP Readings"], [Q_OPEN, Q_DUE], asks=[Q_READ, "Send my blood pressure reading"], viz=["v_readings"]),
        "lg_checks": step(f"Checks open for you: {{{{ {L}.checks.names }}}} ({{{{ {L}.checks.open }}}} in all), and your care team "
                          f"covers them at the visit.",
                          ["Care Gaps"], [Q_READ, Q_NEXT], asks=[Q_DUE], viz=["v_checks"]),
        "lg_missed": step(f"You kept {{{{ {L}.history.completed }}}} of {{{{ {L}.history.visits }}}} visits in the last "
                          f"{{{{ {L}.history.windowMonths }}}} months; if you cannot come, reply R for a new time or ask for a video "
                          f"visit so you skip the {{{{ {L}.driveMin }}}}-minute drive.",
                          ["Clinic schedule", "Pattern Profiles"], [Q_REACH, Q_NEXT], asks=[Q_MISS], viz=["v_history"]),
        "lg_contact": step(f"Reply to any reminder: anything other than C or R goes to the {{{{ {L}.contact.frontDesk }}}}, and a health "
                           f"question goes to the nurse line, never to an automated answer.",
                           ["Front-desk Inbox", "Contact Preferences"], [Q_OPEN, Q_REM], asks=[Q_REACH], viz=["v_contact", "v_messages"]),
        "lg_coverage": step(f"Your coverage with {{{{ {L}.coverage.payer }}}}: {{{{ {L}.coverage.status }}}}, checked "
                            f"{{{{ {L}.coverage.checked }}}}.", ["Eligibility (270/271)"], [Q_NEXT], asks=[Q_COVER]),
        "lg_open": step(f"Opening your text messages with {{{{ {ORG}.networkShort }}}}.", ["SMS Reminders"], [Q_NEXT], asks=[Q_OPEN],
                        launch={"workbench": "patientView", "filter": "linda", "label": "My messages",
                                "detail": "your text thread with the clinic", "auto": True}, viz=["v_launch"]),
        "__default__": step("I can help with your next visit, your reminders, sending a home reading, missed visits and how to reach "
                            "the clinic; I only see your own record.", [], [Q_NEXT, Q_ANSWER]),
    },
    "queries": [Q_NEXT, Q_REM, Q_READ, Q_DUE, Q_MISS, Q_REACH],
    "viz": {"v_tasks": {"type": "rain.task_briefing", "props": {"role": "linda"}}, "v_visits": dt("lg_visits"),
            "v_reminders": dt("lg_reminders"), "v_readings": dt("lg_readings"), "v_checks": dt("lg_checks"),
            "v_history": dt("lg_history"), "v_contact": dt("lg_contact"), "v_messages": dt("lg_messages"),
            "v_launch": {"type": "rain.launch_card", "props": {"step": "lg_open"}}},
    "handoffs": [],
    "workbenches": [{"id": "patientView", "access": "full", "scope": "self"}],
}

# ─── Rosa Martínez: the scheduling patient (Use Case B, her own record only) ─────────────────────────────────
R = P("rosa")
Q_CONFIRM, Q_VIDEO, Q_CALL = "How do I confirm my visit?", "Can I switch to a video visit?", "Can I get a call instead of a text?"
rosa = {
    "signals": [],
    "kpis": [
        kpi("next", "Next visit", f"{{{{ {R}.next.date }}}}", "Clinic schedule", "calendar", "neutral", Q_NEXT,
            f"{{{{ {R}.next.time }}}} · {{{{ {R}.town }}}}"),
        kpi("status", "Confirmation", f"{{{{ {R}.status }}}}", "SMS Reminders", "check-circle", "critical", Q_CONFIRM,
            f"{{{{ {R}.noShowBand }}}} no-show band"),
        kpi("video", "Video slots open", f"{{{{ {R}.videoSlotsOpen }}}}", "Clinic schedule", "calendar-clock", "warning", Q_VIDEO,
            "Before your visit"),
        kpi("missed", "Missed visits", f"{{{{ {R}.history.missed }}}}", "Pattern Profiles", "clock", "warning", Q_MISS,
            f"Last {{{{ {R}.history.windowMonths }}}} months"),
    ],
    "steps": {
        "rm_brief": step(f"Hi {{{{ {R}.first }}}}: your {{{{ {R}.next.visitType | lower }}}} is {{{{ {R}.next.when }}}} in "
                         f"{{{{ {R}.town }}}} ({{{{ {R}.status | lower }}}}).",
                         ["Clinic schedule", "SMS Reminders"], [Q_CONFIRM, Q_VIDEO, Q_REM], next_=Q_CONFIRM, viz=["v_tasks"]),
        "rm_confirm": step(f"Reply C to any reminder to confirm or R to change the time; reminders come {{{{ {R}.reminders.offsets }}}} "
                           f"by {{{{ {R}.contact.channels }}}}.",
                           ["SMS Reminders", "Contact Preferences"], [Q_VIDEO, Q_MISS], asks=[Q_CONFIRM, Q_ANSWER], viz=["v_reminders"]),
        "rm_visit": step(f"Your next visit is {{{{ {R}.next.modeA }}}} with {{{{ {R}.next.provider }}}} at {{{{ {R}.next.where }}}} "
                         f"on {{{{ {R}.next.when }}}}.", ["Clinic schedule"], [Q_CONFIRM, Q_VIDEO], asks=[Q_NEXT], viz=["v_visits"]),
        "rm_video": step(f"{{{{ {R}.reminders.videoOffer }}}} and skip the {{{{ {R}.driveMin }}}}-minute drive; "
                         f"{{{{ {R}.videoSlotsOpen }}}} video slots are open before your visit.",
                         ["Clinic schedule (telehealth)", "SMS Reminders"], [Q_CONFIRM, Q_OPEN], asks=[Q_VIDEO], viz=["v_video"]),
        "rm_reminders": step(f"You get {{{{ {R}.reminders.planned | words }}}} reminders, {{{{ {R}.reminders.offsets }}}}, by "
                             f"{{{{ {R}.contact.channels }}}} in {{{{ {R}.reminders.language }}}}, with quiet hours "
                             f"{{{{ {R}.contact.quietHours }}}}.",
                             ["SMS Reminders", "Contact Preferences"], [Q_CALL, Q_CONFIRM], asks=[Q_REM], viz=["v_reminders"]),
        "rm_voice": step(f"Yes: you agreed to {{{{ {R}.contact.channels }}}}, so a reminder can come as a voice call "
                         f"(phone note: {{{{ {R}.contact.phoneNote | lower }}}}).",
                         ["Contact Preferences"], [Q_REACH, Q_CONFIRM], asks=[Q_CALL], viz=["v_contact"]),
        "rm_missed": step(f"You missed {{{{ {R}.history.missed }}}} of {{{{ {R}.history.visits }}}} visits in the last "
                          f"{{{{ {R}.history.windowMonths }}}} months, so with no reply by the 24-hour cut-off a care coordinator "
                          f"calls you instead of the visit dropping.",
                          ["Pattern Profiles", "SMS Reminders"], [Q_VIDEO, Q_REACH], asks=[Q_MISS], viz=["v_history"]),
        "rm_contact": step(f"Reply to any reminder: anything other than C, R or V goes to the {{{{ {R}.contact.frontDesk }}}}, and a "
                           f"health question goes to the nurse line, never to an automated answer.",
                           ["Front-desk Inbox", "Contact Preferences"], [Q_OPEN, Q_CALL], asks=[Q_REACH], viz=["v_contact", "v_messages"]),
        "rm_coverage": step(f"Your coverage with {{{{ {R}.coverage.payer }}}}: {{{{ {R}.coverage.status }}}}.",
                            ["Eligibility (270/271)"], [Q_NEXT], asks=[Q_COVER]),
        "rm_open": step(f"Opening your text messages with {{{{ {ORG}.networkShort }}}}.", ["SMS Reminders"], [Q_CONFIRM], asks=[Q_OPEN],
                        launch={"workbench": "patientView", "filter": "rosa", "label": "My messages",
                                "detail": "your text and voice reminders", "auto": True}, viz=["v_launch"]),
        "__default__": step("I can help with confirming your visit, switching to video, your reminders, missed visits and how to "
                            "reach the clinic; I only see your own record.", [], [Q_CONFIRM, Q_VIDEO]),
    },
    "queries": [Q_CONFIRM, Q_VIDEO, Q_REM, Q_CALL, Q_MISS, Q_REACH],
    "viz": {"v_tasks": {"type": "rain.task_briefing", "props": {"role": "rosa"}}, "v_visits": dt("rm_visits"),
            "v_reminders": dt("rm_reminders"), "v_video": dt("rm_video"), "v_history": dt("rm_history"),
            "v_contact": dt("rm_contact"), "v_messages": dt("rm_messages"),
            "v_launch": {"type": "rain.launch_card", "props": {"step": "rm_open"}}},
    "handoffs": [],
    "workbenches": [{"id": "patientView", "access": "full", "scope": "self"}],
}

# ─── Hannah Lee: the payer analyst (Use Case A, the plan's members, aggregated and de-identified) ────────────
H = "constants.HANNAH"
Q_ED, Q_COST, Q_GATE = "Where are the avoidable ED visits?", "Compare the networks on cost against expected", "Which networks meet the quality gate?"
Q_BENCH, Q_SUM, Q_TREND = "What if avoidable ED came down to the benchmark?", "Generate the plan summary", "Show the avoidable ED trend"
Q_COUNTY, Q_LV, Q_ELIG = "Which counties drive preventable hospital stays?", "Where is the plan paying for low-value care?", "What are the eligibility checks returning?"
Q_MIX, Q_PRIV, Q_VI = "What is the plan's member mix?", "Can I see member-level data?", "Open Value Insights"
Q_PCP = "How do the plan's counties compare on primary care and premature death?"
CC, AD, PI, AA, FO, PRO = ("Converged Conversation", "Anomaly Detection", "Predictive Intelligence", "Automated Action",
                           "Friction Observability", "Proactive Intelligence")
hannah = {
    "signals": [
        {"id": "SIG-HAN-1", "title": "Avoidable ED Against Benchmark", "severity": "critical",
         "description": f"{{{{ {H}.ed.per1000 }}}} vs {{{{ {H}.ed.benchmark }}}} per 1,000 plan members: about "
                        f"{{{{ {H}.ed.excessVisits | num }}}} extra visits, {{{{ {H}.ed.excessCost | usdM:1 }}}} a year.",
         "metric": f"+{{{{ {H}.ed.overPct | pct }}}} over the benchmark", "sources": ["Plan claims", "Utilization benchmark"],
         "chip": Q_ED, "primary": True},
        {"id": "SIG-HAN-2", "title": "Cost Against Expected", "severity": "critical",
         "description": f"{{{{ {H}.cost.actualPmpm | usd }}}} vs {{{{ {H}.cost.expectedPmpm | usd }}}} PMPM for "
                        f"{{{{ {H}.cost.members | num }}}} members with complete claims: {{{{ {H}.cost.abovePct | pct }}}} above.",
         "metric": f"About {{{{ {H}.cost.annualAbove | usdM:1 }}}} a year", "sources": ["Plan claims", "Contract Benchmark"], "chip": Q_COST},
        {"id": "SIG-HAN-3", "title": "Quality Gate by Network", "severity": "warning",
         "description": f"{{{{ {H}.gate.networksMet }}}} of {{{{ {H}.networks }}}} networks meet {{{{ {H}.gate.needed }}}} of "
                        f"{{{{ {H}.gate.total }}}} gate measures; {{{{ {H}.daysLeft }}}} days left in the contract year.",
         "metric": f"{{{{ {H}.gate.networksMet }}}} of {{{{ {H}.networks }}}} networks", "sources": ["eCQM Engine", "Quality measure results"],
         "chip": Q_GATE},
    ],
    "kpis": [
        kpi("members", "Plan members", f"{{{{ {H}.members | num }}}}", "Attribution (MCO)", "users", "neutral",
            detail=f"{{{{ {H}.networks }}}} networks"),
        kpi("pmpm", "Actual vs. Expected PMPM", f"{{{{ {H}.cost.actualPmpm | usd }}}} / {{{{ {H}.cost.expectedPmpm | usd }}}}",
            "Claims + contract benchmark", "dollar-sign", "critical", Q_COST, "Complete claims feeds"),
        kpi("ed", "Avoidable ED per 1,000", f"{{{{ {H}.ed.per1000 }}}}", "Plan claims", "activity", "critical", Q_ED,
            f"Benchmark {{{{ {H}.ed.benchmark }}}}"),
        kpi("gate", "Networks Meeting the Gate", f"{{{{ {H}.gate.networksMet }}}} of {{{{ {H}.networks }}}}", "eCQM engine", "target",
            "warning", Q_GATE, f"{{{{ {H}.gate.needed }}}} of {{{{ {H}.gate.total }}}} measures needed"),
        kpi("lowValue", "Low-Value Care (last year)", f"{{{{ {H}.lowValue.annual | usdK }}}}", "Low-value care library",
            "alert-triangle", "warning", Q_LV),
        kpi("eligibility", "Coverage Checks Not Active", f"{{{{ {H}.eligibility.notActive }}}} of {{{{ {H}.eligibility.checks }}}}",
            "Eligibility (270/271)", "shield-check", "warning", Q_ELIG),
        kpi("days", "Days Left in Contract Year", f"{{{{ {H}.daysLeft }}}}", "Contract calendar", "clock", "neutral"),
    ],
    "steps": {
        "hl_brief": step(f"Good morning, Hannah. {{{{ {H}.quarter }}}} claims for {{{{ {H}.plan }}}}'s {{{{ {H}.members | num }}}} members "
                         f"across {{{{ {H}.networks | words }}}} networks are in, and I have flagged three signals.",
                         ["Plan claims", "Attribution (MCO)", "Contract Benchmark", "eCQM Engine"], [Q_ED, Q_COST, Q_GATE], next_=Q_ED,
                         viz=["v_ed_trend"], step=1, capability=PRO,
                         points=[f"{{{{ {H}.ed.per1000 }}}} avoidable ED visits per 1,000 plan members against a benchmark of "
                                 f"{{{{ {H}.ed.benchmark }}}}.",
                                 f"{{{{ {H}.cost.actualPmpm | usd }}}} vs {{{{ {H}.cost.expectedPmpm | usd }}}} PMPM where the claims feed is "
                                 f"complete; {{{{ {H}.cost.partialNote }}}} is not comparable yet.",
                                 f"{{{{ {H}.gate.networksMet }}}} of {{{{ {H}.networks }}}} networks meet the quality gate today, and shared "
                                 f"savings ({{{{ {H}.sharingRatePct | pct }}}} sharing) depend on it."]),
        "hl_ed": step(f"Avoidable ED runs {{{{ {H}.ed.overPct | pct }}}} over the benchmark, highest at {{{{ {H}.ed.highest }}}} "
                      f"({{{{ {H}.ed.highestPer1000 }}}} per 1,000) and in {{{{ {H}.ed.worstCounty }}}} County "
                      f"({{{{ {H}.ed.worstCountyPer1000 }}}}).",
                      ["Plan claims", "Utilization benchmark", "County Health Rankings"], [Q_BENCH, Q_TREND, Q_COUNTY], asks=[Q_ED],
                      next_=Q_BENCH, viz=["v_ed_networks", "v_counties"], step=2, capability=AD,
                      points=[f"{{{{ {H}.ed.highest }}}} {{{{ {H}.ed.highestPer1000 }}}}, {{{{ {H}.ed.lowest }}}} "
                              f"{{{{ {H}.ed.lowestPer1000 }}}}, the plan {{{{ {H}.ed.per1000 }}}} against {{{{ {H}.ed.benchmark }}}} per 1,000.",
                              f"About {{{{ {H}.ed.excessVisits | num }}}} visits a year above the benchmark, at about "
                              f"{{{{ {H}.ed.avgCost | usd }}}} a visit.",
                              f"County Health Rankings put Nevada at {{{{ {H}.chr.nvPreventableStays | num }}}} preventable hospital stays "
                              f"per 100,000 Medicare enrollees; the table shows each county the plan's members live in."]),
        "hl_scenario": step(f"Reaching the benchmark would avoid about {{{{ {H}.ed.excessVisits | num }}}} visits and "
                            f"{{{{ {H}.ed.excessCost | usdM:1 }}}} a year, and a {{{{ {H}.ed.cutPct | pct }}}} cut alone about "
                            f"{{{{ {H}.ed.cutVisits | num }}}} visits.",
                            ["RAIN Cost Model", "Plan claims", "Utilization benchmark"], [Q_SUM, Q_GATE], asks=[Q_BENCH], next_=Q_SUM,
                            viz=["v_scenario"], step=3, capability=PI,
                            points=[f"The plan runs {{{{ {H}.ed.per1000 }}}} per 1,000 against the benchmark of {{{{ {H}.ed.benchmark }}}}, "
                                    f"at about {{{{ {H}.ed.avgCost | usd }}}} a visit.",
                                    f"A {{{{ {H}.ed.cutPct | pct }}}} cut is the reduction the state's option A plans for: about "
                                    f"{{{{ {H}.ed.cutCost | usdK }}}} a year across the plan."]),
        "hl_summary": step(f"Here is the {{{{ {H}.quarter }}}} plan summary for {{{{ {H}.plan }}}}, aggregated and de-identified, with "
                           f"cells under {{{{ {H}.suppressUnder }}}} suppressed.",
                           ["Plan claims", "eCQM Engine", "Low-Value Care Library"], [Q_PRIV, Q_VI], asks=[Q_SUM, "Generate the plan summary for the networks"],
                           viz=["v_summary"], step=4, capability=AA,
                           points=[f"{{{{ {H}.members | num }}}} members across {{{{ {H}.networkNames }}}}.",
                                   "No member-level data leaves the networks without a data-use agreement."]),
        "hl_cost": step(f"Where the claims feed is complete the plan pays {{{{ {H}.cost.actualPmpm | usd }}}} against "
                        f"{{{{ {H}.cost.expectedPmpm | usd }}}} PMPM ({{{{ {H}.cost.abovePct | pct }}}} above), and "
                        f"{{{{ {H}.cost.partialNote }}}} is not comparable yet.",
                        ["Plan claims", "Contract Benchmark"], [Q_ED, Q_LV], asks=[Q_COST], next_=Q_ED, viz=["v_networks"], capability=CC),
        "hl_trend": step(f"Avoidable ED was above the benchmark of {{{{ {H}.ed.benchmark }}}} in {{{{ {H}.ed.monthsAbove }}}} of "
                         f"{{{{ {H}.ed.months }}}} months this year, {{{{ {H}.ed.per1000 }}}} per 1,000 so far.",
                         ["Plan claims", "Utilization benchmark"], [Q_BENCH, Q_COUNTY], asks=[Q_TREND], next_=Q_BENCH, viz=["v_ed_trend"],
                         capability=AD),
        "hl_counties": step(f"{{{{ {H}.ed.worstCounty }}}} County has the plan's highest avoidable ED at {{{{ {H}.ed.worstCountyPer1000 }}}} "
                            f"per 1,000; County Health Rankings put Nevada at {{{{ {H}.chr.nvPreventableStays | num }}}} preventable stays per "
                            f"100,000 and {{{{ {H}.chr.nvUninsuredPct | pct }}}} uninsured.",
                            ["Plan claims", "County Health Rankings"], [Q_PCP, Q_BENCH], asks=[Q_COUNTY], next_=Q_BENCH,
                            viz=["v_counties", "v_chr"], capability=CC),
        "hl_pcp": step("Here is how the plan's counties compare with Nevada on primary care physicians and premature death.",
                       ["County Health Rankings"], [Q_COUNTY, Q_ED], asks=[Q_PCP], viz=["v_chr_pcp"], capability=CC),
        "hl_gate": step(f"{{{{ {H}.gate.networksMet }}}} of {{{{ {H}.networks }}}} networks meet {{{{ {H}.gate.needed }}}} of "
                        f"{{{{ {H}.gate.total }}}} gate measures: {{{{ {H}.gate.bestNetwork }}}} meets {{{{ {H}.gate.bestMet }}}}, and "
                        f"{{{{ {H}.gate.notReported }}}} network measures are not reported yet.",
                        ["eCQM Engine", "Quality measure results"], [Q_SUM, Q_ED], asks=[Q_GATE], next_=Q_SUM, viz=["v_gate"], capability=PI),
        "hl_elig": step(f"{{{{ {H}.eligibility.active }}}} of {{{{ {H}.eligibility.checks }}}} eligibility checks (270/271) came back "
                        f"active, last run {{{{ {H}.eligibility.lastChecked }}}}; a booking with inactive coverage still goes ahead and "
                        f"opens an enrollment-assist task.",
                        ["Eligibility (270/271)"], [Q_MIX, Q_SUM], asks=[Q_ELIG], viz=["v_elig"], capability=FO),
        "hl_lv": step(f"The plan paid {{{{ {H}.lowValue.annual | usdK }}}} for {{{{ {H}.lowValue.services | num }}}} low-value services "
                      f"in the last year, about {{{{ {H}.lowValue.pmpm | usd:2 }}}} PMPM.",
                      ["Plan claims", "Low-Value Care Library"], [Q_COST, Q_SUM], asks=[Q_LV], viz=["v_lowvalue"], capability=AD),
        "hl_mix": step(f"Here are the plan's {{{{ {H}.members | num }}}} members by aid category, aggregated across "
                       f"{{{{ {H}.networks | words }}}} networks.",
                       ["Attribution (MCO)"], [Q_ELIG, Q_SUM], asks=[Q_MIX], viz=["v_mix"], capability=CC),
        "hl_privacy": step(f"Not without a data-use agreement: the payer view is aggregated and de-identified, and any cell under "
                           f"{{{{ {H}.suppressUnder }}}} members is suppressed.", ["RAIN governance"], [Q_SUM, Q_VI], asks=[Q_PRIV],
                           capability=CC),
        "hl_open_vi": step(f"Opening Value Insights at payer scope: {{{{ {H}.plan }}}}, aggregated.", ["Plan claims"], [Q_ED, Q_COST],
                           asks=[Q_VI], capability=CC,
                           launch={"workbench": "valueInsights", "filter": "payer", "label": "Value Insights",
                                   "detail": "payer scope, aggregated", "auto": True}, viz=["v_launch_vi"]),
        "__default__": step("I can help with avoidable ED against the benchmark, cost against expected by network, the quality gate, "
                            "low-value care, eligibility checks and the plan summary, all aggregated and de-identified.", [], [Q_ED, Q_COST]),
    },
    "queries": [Q_ED, Q_COST, Q_GATE, Q_TREND, Q_LV, Q_ELIG, Q_SUM],
    "viz": {"v_ed_trend": {"type": "chart", "props": {"dataset": "hl_ed_trend"}},
            "v_ed_networks": {"type": "chart", "props": {"dataset": "hl_ed_networks"}},
            "v_counties": dt("hl_counties"), "v_scenario": {"type": "grid", "props": {"dataset": "hl_scenario"}},
            "v_summary": dt("hl_summary"), "v_networks": dt("hl_networks"), "v_gate": dt("hl_gate"), "v_elig": dt("hl_eligibility"),
            "v_lowvalue": dt("hl_lowvalue"), "v_mix": dt("hl_mix"),
            "v_chr": {"type": "query_table", "props": {"query": "HAN-P1",
                                                       "caption": "Preventable hospital stays and uninsured residents by county (County Health Rankings, live)"}},
            "v_chr_pcp": {"type": "query_table", "props": {"query": "HAN-P2",
                                                           "caption": "Primary care physicians and premature death by county (County Health Rankings, live)"}},
            "v_launch_vi": {"type": "rain.launch_card", "props": {"step": "hl_open_vi"}}},
    "handoffs": [],
    "workbenches": [{"id": "valueInsights", "access": "view", "scope": "payer"}],
}

PERSONAS = {
    "linda": {"identity": {"name": f"{{{{ {L}.name }}}}", "initials": "LG", "role": f"Patient, {{{{ {L}.town }}}}",
                           "greeting": f"{{{{ {L}.first }}}}"},
              "inputPlaceholder": "Ask about your next visit, your reminders, a home reading or how to reach the clinic…",
              "greetingSubtitle": f"Your next visit, reminders and readings: {{{{ constants.SCOPES.linda.label | lower }}}}.",
              "notifications": [{"id": "lg-n1", "unread": True, "title": "Reminder plan for your visit",
                                 "detail": f"{{{{ {L}.next.when }}}}: reminders {{{{ {L}.reminders.offsets }}}}.", "at": "Today", "tone": "info"}]},
    "rosa": {"identity": {"name": f"{{{{ {R}.name }}}}", "initials": "RM", "role": f"Patient, {{{{ {R}.town }}}}",
                          "greeting": f"{{{{ {R}.first }}}}"},
             "inputPlaceholder": "Ask about confirming your visit, switching to video or how to reach the clinic…",
             "greetingSubtitle": f"Your visit, reminders and channels: {{{{ constants.SCOPES.rosa.label | lower }}}}.",
             "notifications": [{"id": "rm-n1", "unread": True, "title": "Your visit needs a confirmation",
                                "detail": f"{{{{ {R}.next.when }}}}: reply C to confirm, R to change or T for video.", "at": "Today",
                                "tone": "warning"}]},
    "hannah": {"identity": {"name": "Hannah Lee", "initials": "HL", "role": "Payer / Medicaid MCO Analyst", "greeting": "Hannah"},
               "inputPlaceholder": "Ask about avoidable ED, cost against expected, the quality gate or eligibility…",
               "greetingSubtitle": f"{{{{ {H}.plan }}}}: {{{{ {H}.quarter }}}} claims for {{{{ {H}.members | num }}}} members, "
                                   f"aggregated and de-identified.",
               "notifications": [{"id": "hl-n1", "unread": True, "title": f"{{{{ {H}.quarter }}}} claims loaded",
                                  "detail": f"Claims through {{{{ {H}.claimsThrough }}}}, {{{{ {H}.claimsLagDays }}}}-day lag.",
                                  "at": "Today", "tone": "info"}]},
}

if __name__ == "__main__":
    tpl = json.loads(TPL.read_text(encoding="utf-8"))
    for key, contract in (("linda", linda), ("rosa", rosa), ("hannah", hannah)):
        tpl["contracts"][key] = contract
        tpl["personas"][key] = PERSONAS[key]
    TPL.write_text(json.dumps(tpl, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", TPL.relative_to(ROOT), "contracts:", ", ".join(tpl["contracts"]))
