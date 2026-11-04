"""
Verified business rules for the PRD v0.2 persona wave (kayla, denise,
samuel, linda, marcus), same contract as business_rules.BUSINESS_RULES /
BREAKDOWN_RULES: every entry's SQL was executed against the live synthetic
schema and its result recorded in verified_result before being added.

These power the FAST ask path (no insights agent): each persona's chat
chips match a rule here via the same Jaccard matcher, the pre-verified SQL
runs directly against Postgres, and the phrase carries the live numbers.
Every rule is persona-scoped ("personas") so a scheduler's slot rule can
never answer a medical director's question.

Data notes (synthetic generator):
- no_show_risk is on a 0..100000 scale; >= 70000 is the high band.
- risk_score.score is 0..1; >= 0.7 is the high band.
- the shared status vocabulary is active/pending/approved/closed/rejected
  (plus NULLs); there is no 'booked' status.
- county_fips / source_dataset hold faker words, so answers count them but
  never print them as labels; clinic_site_id (CLINIC_S000197) is printable.
"""

from prdv2_personas import ROSA_PATIENT_ID as _ROSA

PRDV2_BUSINESS_RULES = [
    # ---- Rosa Martinez: rural patient (UC-01) -- first-person, anchored to
    # her own synthetic record (prdv2_personas.ROSA_PATIENT_ID) -------------
    {
        "term": "When is my next visit and is it confirmed",
        "table": "synthetic.appointment",
        "personas": ("rosa",),
        "rule": "her appointments on file vs still pending",
        "verified_result": "2 visits, 1 pending",
        "sql": (f"SELECT (SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{_ROSA}'), "
                f"(SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{_ROSA}' AND status = 'pending')"),
        "columns": ["visits", "pending"],
        "phrase": ("You have {visits} visits on file and {pending} is still waiting on your "
                   "confirmation. Reply YES to the reminder text or answer the voice call and "
                   "the clinic sees it instantly."),
    },
    {
        "term": "Can I switch my visit to telehealth",
        "table": "synthetic.slot",
        "personas": ("rosa",),
        "gate": r"switch",
        "rule": "open telehealth slots near her",
        "verified_result": "39",
        "sql": "SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')",
        "phrase": ("Yes -- {result} telehealth slots are open across nearby clinics and your visit "
                   "reason is telehealth-eligible. Reply T to the 24-hour reminder and the visit "
                   "converts to video with the link and a device checklist, no 60-plus-minute drive."),
    },
    {
        "term": "Is my coverage active",
        "table": "synthetic.eligibility_check",
        "personas": ("rosa",),
        "rule": "her latest 270/271 coverage status",
        "verified_result": "Active",
        "sql": (f"SELECT COALESCE(INITCAP(MAX(coverage_status)), 'Unknown') "
                f"FROM synthetic.eligibility_check WHERE patient_id = '{_ROSA}'"),
        "phrase": ("Your coverage check shows {result} with your payer -- nothing is needed from "
                   "you before the visit, and a coverage question never blocks care."),
    },
    {
        "term": "Why am I getting these reminders",
        "table": "synthetic.reminder_message",
        "personas": ("rosa",),
        "rule": "her reminders sent vs replied",
        "verified_result": "3 sent, 0 replied",
        "sql": (f"SELECT (SELECT COUNT(*) FROM synthetic.reminder_message WHERE patient_id = '{_ROSA}'), "
                f"(SELECT COUNT(*) FROM synthetic.reminder_message WHERE patient_id = '{_ROSA}' "
                f"AND delivery_status IN ('approved','closed'))"),
        "columns": ["sent", "replies"],
        "phrase": ("You've received {sent} reminders about your upcoming visit and {replies} have a "
                   "reply so far. They come at 72, 24 and 3 hours in your preferred language; one "
                   "YES stops the rest, and nothing arrives between 8pm and 8am."),
    },
    {
        "term": "How do I confirm by text",
        "table": "synthetic.contact_preference",
        "personas": ("rosa",),
        "gate": r"\btext\b|\bsms\b",
        "rule": "her consent flag + pending visit",
        "verified_result": "consent Yes, 1 pending",
        "sql": (f"SELECT (SELECT CASE WHEN BOOL_OR(consent_flag) THEN 'Yes' ELSE 'No' END "
                f"FROM synthetic.contact_preference WHERE patient_id = '{_ROSA}'), "
                f"(SELECT COUNT(*) FROM synthetic.appointment WHERE patient_id = '{_ROSA}' AND status = 'pending')"),
        "columns": ["consent", "pending"],
        "phrase": ("Your SMS consent is on file ({consent}), so just reply YES to the reminder "
                   "text -- it confirms your {pending} pending visit instantly. Texts only go out "
                   "between 8am and 8pm, per the consent rules."),
    },
    {
        "term": "What happens if I miss my visit",
        "table": "synthetic.appointment",
        "personas": ("rosa",),
        "gate": r"\bmiss\b",
        "rule": "her pending visit in the high no-show band",
        "verified_result": "1",
        "sql": (f"SELECT COUNT(*) FROM synthetic.appointment "
                f"WHERE patient_id = '{_ROSA}' AND status = 'pending' AND no_show_risk >= 70000"),
        "phrase": ("Nothing gets cancelled for not replying. Your pending visit sits in the high "
                   "no-show band ({result} visit flagged), so at the 24-hour mark a care "
                   "coordinator calls to help instead -- reschedule, a telehealth switch, or "
                   "transport if the drive is the problem."),
    },
    {
        "term": "Confirm my visit",
        "table": "synthetic.appointment",
        "personas": ("rosa",),
        "gate": r"^\s*confirm",
        "rule": "pending visit marked for confirmation",
        "verified_result": "1",
        "sql": (f"SELECT COUNT(*) FROM synthetic.appointment "
                f"WHERE patient_id = '{_ROSA}' AND status = 'pending'"),
        "phrase": ("{result} pending visit marked for confirmation -- you'll get a text in a "
                   "moment; reply YES and you're done. The clinic sees it instantly."),
    },
    {
        "term": "Switch me to telehealth",
        "table": "synthetic.slot",
        "personas": ("rosa",),
        "gate": r"^\s*switch",
        "rule": "switch queued against open slots",
        "verified_result": "39 slots open",
        "sql": "SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')",
        "phrase": ("Done -- your visit is queued for a telehealth switch. With {result} open slots "
                   "across nearby clinics, the front desk confirms today and sends the video link "
                   "with a device checklist."),
    },
    {
        "term": "Reschedule my visit",
        "table": "synthetic.slot",
        "personas": ("rosa",),
        "gate": r"^\s*reschedul",
        "rule": "reschedule request routed; telehealth alternative counted",
        "verified_result": "39 slots open",
        "sql": "SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')",
        "phrase": ("A reschedule request is on its way to the front desk with your preferred "
                   "windows. If the drive is the problem, {result} telehealth slots are open as "
                   "an alternative -- reply T to take one."),
    },

    # ---- Kayla Brooks: clinic scheduler / front desk (UC-01) -----------------
    {
        "term": "Booked visits highest no-show risk band",
        "table": "synthetic.appointment",
        "personas": ("kayla",),
        "rule": "no_show_risk >= 70000 of all booked appointments",
        "verified_result": "53 of 200",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000), "
                "(SELECT COUNT(*) FROM synthetic.appointment)"),
        "columns": ["high", "total"],
        "phrase": ("Of {total} booked visits, {high} score in the high no-show band "
                   "(>= 70,000 on the 0-100,000 risk scale). They are first in line for the "
                   "72h / 24h / 3h reminder ladder."),
    },
    {
        "term": "This week's confirmations board replies",
        "table": "synthetic.reminder_message",
        "personas": ("kayla",),
        "gate": r"confirmations board",
        "rule": "reminder replies: approved/closed = confirmed, pending = awaiting",
        "verified_result": "confirmed 73, awaiting 34 (distinct appointments)",
        "sql": ("SELECT (SELECT COUNT(DISTINCT appointment_id) FROM synthetic.reminder_message "
                "WHERE delivery_status IN ('approved','closed')), "
                "(SELECT COUNT(DISTINCT appointment_id) FROM synthetic.reminder_message "
                "WHERE delivery_status = 'pending')"),
        "columns": ["confirmed", "awaiting"],
        "phrase": ("The confirmations board shows {confirmed} visits confirmed through reminder "
                   "replies and {awaiting} still awaiting a response."),
    },
    {
        "term": "Who has not confirmed their visit yet",
        "table": "synthetic.reminder_message",
        "personas": ("kayla",),
        "rule": "distinct appointments whose reminder is still pending",
        "verified_result": "34",
        "sql": ("SELECT COUNT(DISTINCT appointment_id) FROM synthetic.reminder_message "
                "WHERE delivery_status = 'pending'"),
        "phrase": ("{result} visits have a reminder still pending a reply -- those patients have "
                   "not confirmed yet and move to the call list at the 24h cut-off."),
    },
    {
        "term": "Which visits can switch to telehealth candidates",
        "table": "synthetic.slot",
        "personas": ("kayla",),
        "gate": r"switch",
        "rule": "open telehealth slots vs high no-show candidates",
        "verified_result": "39 slots, 53 candidates",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000)"),
        "columns": ["slots", "candidates"],
        "phrase": ("Matching high no-show visits against the open inventory: {candidates} "
                   "high-risk visits are switch candidates and {slots} telehealth slots are open "
                   "across nearby clinics. The 24h reminder carries the switch offer."),
    },
    {
        "term": "Open telehealth slots across nearby clinics",
        "table": "synthetic.slot",
        "personas": ("kayla",),
        "rule": "slot.telehealth_flag AND status active/pending",
        "verified_result": "39",
        "sql": ("SELECT COUNT(*) FROM synthetic.slot "
                "WHERE telehealth_flag AND status IN ('active','pending')"),
        "phrase": "There are {result} open telehealth slots (active or pending) across nearby clinics right now.",
    },
    {
        "term": "Telehealth slot gap against high-risk demand",
        "table": "synthetic.slot",
        "personas": ("kayla",),
        "gate": r"slot gap",
        "rule": "high no-show candidates minus open telehealth slots",
        "verified_result": "53 candidates, 39 slots, gap 14",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000), "
                "(SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')), "
                "GREATEST((SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000) - "
                "(SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')), 0)"),
        "columns": ["candidates", "slots", "gap"],
        "phrase": ("{candidates} high no-show visits are telehealth candidates against {slots} open "
                   "telehealth slots -- a gap of {gap} visits that stay in-person unless more "
                   "virtual blocks open."),
    },
    {
        "term": "Run eligibility checks for this week's bookings",
        "table": "synthetic.eligibility_check",
        "personas": ("kayla",),
        "gate": r"eligibility",
        "rule": "270/271 checks: total vs coverage_status = 'active'",
        "verified_result": "200 checks, 41 active, 159 non-active",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.eligibility_check), "
                "(SELECT COUNT(*) FROM synthetic.eligibility_check WHERE coverage_status = 'active'), "
                "(SELECT COUNT(*) FROM synthetic.eligibility_check WHERE coverage_status IS DISTINCT FROM 'active')"),
        "columns": ["checks", "active", "rest"],
        "phrase": ("Eligibility checks ran for all {checks} bookings through the 270/271 service: "
                   "{active} came back active; the other {rest} show pending, rejected, closed or "
                   "no response. Each non-active result is flagged on its appointment -- the flag "
                   "routes help, it never blocks care."),
    },
    {
        "term": "Lapsed coverage list non-active eligibility",
        "table": "synthetic.eligibility_check",
        "personas": ("kayla",),
        "rule": "coverage_status not 'active' (incl. NULL)",
        "verified_result": "159",
        "sql": ("SELECT COUNT(*) FROM synthetic.eligibility_check "
                "WHERE coverage_status IS DISTINCT FROM 'active'"),
        "phrase": ("{result} eligibility checks are not showing active coverage (pending, rejected, "
                   "closed or no response) -- that is the lapsed-coverage work list, each one "
                   "flagged on its appointment with the payer's response code."),
    },
    {
        "term": "Patients with no SMS consent on file",
        "table": "synthetic.contact_preference",
        "personas": ("kayla",),
        "rule": "NOT COALESCE(consent_flag, false)",
        "verified_result": "103",
        "sql": ("SELECT COUNT(*) FROM synthetic.contact_preference "
                "WHERE NOT COALESCE(consent_flag, false)"),
        "phrase": ("{result} contact records have no SMS consent on file -- TCPA rules route those "
                   "patients to voice or mail reminders instead, and no message goes out 8pm-8am."),
    },
    {
        "term": "Build reminder plans drafted high-risk touches",
        "table": "synthetic.appointment",
        "personas": ("kayla",),
        "gate": r"\bbuild\b",
        "rule": "high no-show count + SMS-consented patients",
        "verified_result": "53 high, 97 consented",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000), "
                "(SELECT COUNT(*) FROM synthetic.contact_preference WHERE consent_flag)"),
        "columns": ["high", "sms"],
        "phrase": ("Reminder plans drafted for the {high} high no-show visits: 72h, 24h and 3h "
                   "touches, with the telehealth offer in the 24h message. {sms} patients on the "
                   "panel hold SMS consent; everyone else routes to voice."),
    },
    {
        "term": "Send the reminder plans queued consented window",
        "table": "synthetic.appointment",
        "personas": ("kayla",),
        "gate": r"^\s*send\b",
        "rule": "same counts, send confirmation",
        "verified_result": "53 high, 97 consented",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000), "
                "(SELECT COUNT(*) FROM synthetic.contact_preference WHERE consent_flag)"),
        "columns": ["high", "sms"],
        "phrase": ("{high} reminder plans are queued. Sends respect each patient's consent "
                   "({sms} have SMS on file; the rest go to voice) and hold during the 8pm-8am "
                   "quiet window."),
    },
    {
        "term": "Apply the telehealth switches to eligible visits",
        "table": "synthetic.slot",
        "personas": ("kayla",),
        "gate": r"\bapply\b",
        "rule": "LEAST(open telehealth slots, high no-show candidates)",
        "verified_result": "39 switched (39 slots vs 53 candidates)",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000), "
                "LEAST((SELECT COUNT(*) FROM synthetic.slot WHERE telehealth_flag AND status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.appointment WHERE no_show_risk >= 70000))"),
        "columns": ["slots", "candidates", "switched"],
        "phrase": ("{switched} visits switched to telehealth ({slots} open slots against "
                   "{candidates} candidates). The remainder stay in-person and are flagged for "
                   "transport or a clinic-hosted telehealth room."),
    },
    {
        "term": "Create CHW call tasks for the non-responders",
        "table": "synthetic.reminder_message",
        "personas": ("kayla",),
        "gate": r"\bchw\b|non-responder",
        "rule": "reminders still pending a reply",
        "verified_result": "39",
        "sql": ("SELECT COUNT(*) FROM synthetic.reminder_message WHERE delivery_status = 'pending'"),
        "phrase": ("{result} CHW call tasks created for reminder non-responders, ordered by "
                   "no-show risk -- escalation per the 24h cut-off rule."),
    },

    # ---- Denise Holloway: CHW / care coordinator -----------------------------
    {
        "term": "Today's call list open outreach tasks",
        "table": "synthetic.outreach_task",
        "personas": ("denise",),
        "gate": r"call list",
        "rule": "open tasks + high-risk patients on top",
        "verified_result": "80 open, 60 high-risk",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7)"),
        "columns": ["open", "high"],
        "phrase": ("Today's call list holds {open} open outreach tasks; {high} panel patients "
                   "score in the high-risk band (>= 0.7), so their tasks sit at the top of the list."),
    },
    {
        "term": "My patients highest risk band scored",
        "table": "synthetic.risk_score",
        "personas": ("denise",),
        "rule": "score >= 0.7 of all scored",
        "verified_result": "60 of 200",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7), "
                "(SELECT COUNT(*) FROM synthetic.risk_score)"),
        "columns": ["high", "scored"],
        "phrase": "{high} of {scored} scored patients are in the high-risk band (risk score >= 0.7).",
    },
    {
        "term": "Who has not replied to their reminders",
        "table": "synthetic.reminder_message",
        "personas": ("denise",),
        "rule": "delivery_status = 'pending'",
        "verified_result": "39",
        "sql": ("SELECT COUNT(*) FROM synthetic.reminder_message WHERE delivery_status = 'pending'"),
        "phrase": ("{result} reminder messages are still pending a reply -- those patients have "
                   "not responded and roll onto the outreach queue."),
    },
    {
        "term": "High-risk patients who cannot be reached by SMS",
        "table": "synthetic.risk_score",
        "personas": ("denise",),
        "rule": "score >= 0.7 joined to contact_preference without consent",
        "verified_result": "19 distinct patients",
        "sql": ("SELECT COUNT(DISTINCT r.patient_id) FROM synthetic.risk_score r "
                "JOIN synthetic.contact_preference c ON c.patient_id = r.patient_id "
                "WHERE r.score >= 0.7 AND NOT COALESCE(c.consent_flag, false)"),
        "phrase": ("{result} high-risk patients (score >= 0.7) have no SMS consent on file -- "
                   "they need calls or in-person visits, which is exactly the field-plan list."),
    },
    {
        "term": "Patients screened positive for a social need",
        "table": "synthetic.sdoh_screening",
        "personas": ("denise",),
        "rule": "distinct screened patients + total screenings",
        "verified_result": "127 patients, 200 screenings",
        "sql": ("SELECT (SELECT COUNT(DISTINCT patient_id) FROM synthetic.sdoh_screening), "
                "(SELECT COUNT(*) FROM synthetic.sdoh_screening)"),
        "columns": ["patients", "screenings"],
        "phrase": ("{patients} patients have SDOH screenings on file ({screenings} screenings in "
                   "all); positive domains route into outreach tasks automatically."),
    },
    {
        "term": "What did outreach close this month",
        "table": "synthetic.outreach_task",
        "personas": ("denise",),
        "rule": "status = 'closed'",
        "verified_result": "51",
        "sql": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status = 'closed'",
        "phrase": "Outreach closed {result} tasks this period; the rest of the queue is still active or pending.",
    },
    {
        "term": "Plan my field visits for the week",
        "table": "synthetic.outreach_task",
        "personas": ("denise",),
        "gate": r"field visit",
        "rule": "open tasks + patients without SMS consent",
        "verified_result": "80 open, 103 no-SMS",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.contact_preference WHERE NOT COALESCE(consent_flag, false))"),
        "columns": ["open", "nosms"],
        "phrase": ("{open} open tasks are mapped into the weekly field plan; the {nosms} patients "
                   "without SMS consent are prioritized for in-person stops."),
    },
    {
        "term": "Generate the day sheet for tomorrow",
        "table": "synthetic.outreach_task",
        "personas": ("denise",),
        "gate": r"day sheet",
        "rule": "open tasks + pending reminder replies",
        "verified_result": "80 open, 39 pending",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.reminder_message WHERE delivery_status = 'pending')"),
        "columns": ["open", "pending"],
        "phrase": ("Tomorrow's day sheet is ready: {open} open outreach tasks, plus {pending} "
                   "unanswered reminders to chase first."),
    },

    # ---- Dr. Samuel Okafor: rural primary care provider ----------------------
    {
        "term": "Walk me through this week's schedule encounters",
        "table": "synthetic.encounter",
        "personas": ("samuel",),
        "gate": r"schedule",
        "rule": "encounter volume + telehealth share of flagged encounters",
        "verified_result": "200 encounters, 54%",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.encounter), "
                "(SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE telehealth_flag) / "
                "NULLIF(COUNT(*) FILTER (WHERE telehealth_flag IS NOT NULL), 0))::int FROM synthetic.encounter)"),
        "columns": ["visits", "pct"],
        "phrase": ("This week's schedule holds {visits} encounters; {pct}% of the flagged "
                   "encounters run as telehealth."),
    },
    {
        "term": "How much of my schedule is telehealth share",
        "table": "synthetic.encounter",
        "personas": ("samuel",),
        "rule": "telehealth_flag true vs flagged encounters",
        "verified_result": "103 of 191 = 54%",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.encounter WHERE telehealth_flag), "
                "(SELECT COUNT(*) FROM synthetic.encounter WHERE telehealth_flag IS NOT NULL), "
                "(SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE telehealth_flag) / "
                "NULLIF(COUNT(*) FILTER (WHERE telehealth_flag IS NOT NULL), 0))::int FROM synthetic.encounter)"),
        "columns": ["tele", "flagged", "pct"],
        "phrase": "{tele} of {flagged} flagged encounters are telehealth -- a {pct}% share of the schedule.",
    },
    {
        "term": "Which of my patients are rising risk",
        "table": "synthetic.risk_score",
        "personas": ("samuel",),
        "rule": "score >= 0.7 of all scored",
        "verified_result": "60 of 200",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7), "
                "(SELECT COUNT(*) FROM synthetic.risk_score)"),
        "columns": ["high", "scored"],
        "phrase": ("{high} of {scored} scored panel patients sit in the high or rising band "
                   "(score >= 0.7) -- the platform flags them, the visit decision stays yours."),
    },
    {
        "term": "Medication adherence gap before their visit",
        "table": "synthetic.medication",
        "personas": ("samuel",),
        "rule": "adherence_ratio < 0.8",
        "verified_result": "161",
        "sql": "SELECT COUNT(*) FROM synthetic.medication WHERE adherence_ratio < 0.8",
        "phrase": ("{result} medications show an adherence ratio below 0.8 -- those patients are "
                   "flagged for a pre-visit medication review."),
    },
    {
        "term": "Latest remote monitoring readings feed",
        "table": "synthetic.rpm_reading",
        "personas": ("samuel",),
        "rule": "reading volume + distinct patients transmitting",
        "verified_result": "200 readings, 122 patients",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.rpm_reading), "
                "(SELECT COUNT(DISTINCT patient_id) FROM synthetic.rpm_reading)"),
        "columns": ["readings", "patients"],
        "phrase": ("The remote monitoring feed holds {readings} readings from {patients} patients; "
                   "out-of-range values flag straight onto the worklist."),
    },
    {
        "term": "Which visits still need a confirmation",
        "table": "synthetic.reminder_message",
        "personas": ("samuel",),
        "rule": "distinct appointments with a pending reminder",
        "verified_result": "34",
        "sql": ("SELECT COUNT(DISTINCT appointment_id) FROM synthetic.reminder_message "
                "WHERE delivery_status = 'pending'"),
        "phrase": "{result} visits still have a reminder pending a reply -- not yet confirmed.",
    },
    {
        "term": "Generate pre-visit summaries for tomorrow",
        "table": "synthetic.encounter",
        "personas": ("samuel",),
        "gate": r"generate pre-?visit|summaries for tomorrow",
        "rule": "encounters in scope + adherence gaps highlighted",
        "verified_result": "200 encounters, 161 gaps",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.encounter), "
                "(SELECT COUNT(*) FROM synthetic.medication WHERE adherence_ratio < 0.8)"),
        "columns": ["visits", "gaps"],
        "phrase": ("Pre-visit summaries are queued for {visits} encounters; {gaps} medication "
                   "adherence gaps are highlighted inside them."),
    },

    # ---- Dr. Linda Hargrove: quality / population health director -----------
    {
        "term": "Walk me through the clinic risk mix",
        "table": "synthetic.risk_score",
        "personas": ("linda",),
        "gate": r"risk mix",
        "rule": "high band share of scored panel",
        "verified_result": "60 of 200 = 30%",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7), "
                "(SELECT COUNT(*) FROM synthetic.risk_score), "
                "(SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE score >= 0.7) / NULLIF(COUNT(*), 0))::int "
                "FROM synthetic.risk_score)"),
        "columns": ["high", "scored", "pct"],
        "phrase": ("The clinic risk mix: {high} of {scored} scored patients ({pct}%) sit in the "
                   "high band (>= 0.7); the remainder split rising and low. Tiers come with top "
                   "reasons attached -- clinicians decide, the platform only flags."),
    },
    {
        "term": "Which care gaps are still open",
        "table": "synthetic.outreach_task",
        "personas": ("linda",),
        "rule": "status active/pending",
        "verified_result": "80",
        "sql": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')",
        "phrase": "{result} care-gap tasks are still open (active or pending) across the panel.",
    },
    {
        "term": "Trending on care-gap closure rate",
        "table": "synthetic.outreach_task",
        "personas": ("linda",),
        "gate": r"closure|trending",
        "rule": "closed / (closed + open)",
        "verified_result": "51 closed, 80 open, 39%",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.outreach_task WHERE status = 'closed'), "
                "(SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')), "
                "(SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'closed') / "
                "NULLIF(COUNT(*) FILTER (WHERE status IN ('closed','active','pending')), 0))::int "
                "FROM synthetic.outreach_task)"),
        "columns": ["closed", "open", "pct"],
        "phrase": ("Care-gap closure stands at {pct}% this period: {closed} gaps closed against "
                   "{open} still open."),
    },
    {
        "term": "Where is ED utilization concentrating",
        "table": "synthetic.claim",
        "personas": ("linda",),
        "gate": r"\bed\b.*concentrat|concentrat.*\bed\b",
        "rule": "ED-flagged claims + county spread",
        "verified_result": "96 ED claims",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.claim WHERE ed_flag), "
                "(SELECT COUNT(DISTINCT p.county_fips) FROM synthetic.claim c "
                "JOIN synthetic.patient p ON p.patient_id = c.patient_id WHERE c.ed_flag)"),
        "columns": ["ed", "counties"],
        "phrase": ("ED-flagged claims total {ed}, spread across {counties} county codes; the top "
                   "quartile of that concentration is flagged for review against the county benchmarks."),
    },
    {
        "term": "What is our social-need screening coverage",
        "table": "synthetic.sdoh_screening",
        "personas": ("linda",),
        "rule": "distinct screened patients / panel",
        "verified_result": "127 of 200 = 64%",
        "sql": ("SELECT (SELECT COUNT(DISTINCT patient_id) FROM synthetic.sdoh_screening), "
                "(SELECT COUNT(*) FROM synthetic.patient), "
                "(SELECT ROUND(100.0 * (SELECT COUNT(DISTINCT patient_id) FROM synthetic.sdoh_screening) / "
                "NULLIF((SELECT COUNT(*) FROM synthetic.patient), 0))::int)"),
        "columns": ["patients", "total", "pct"],
        "phrase": "{patients} of {total} panel patients have an SDOH screening on file -- {pct}% coverage.",
    },
    {
        "term": "What is our telehealth share trend",
        "table": "synthetic.encounter",
        "personas": ("linda",),
        "rule": "telehealth share of flagged encounters",
        "verified_result": "54%",
        "sql": ("SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE telehealth_flag) / "
                "NULLIF(COUNT(*) FILTER (WHERE telehealth_flag IS NOT NULL), 0))::int "
                "FROM synthetic.encounter"),
        "phrase": "Telehealth now carries {result}% of flagged encounters this period.",
    },
    {
        "term": "Compare our measures against county benchmarks",
        "table": "synthetic.county_metric",
        "personas": ("linda",),
        "gate": r"benchmark",
        "rule": "benchmark records / counties / distinct measures",
        "verified_result": "200 records, 165 counties, measures counted live",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.county_metric), "
                "(SELECT COUNT(DISTINCT county_fips) FROM synthetic.county_metric), "
                "(SELECT COUNT(DISTINCT metric_code) FROM synthetic.county_metric)"),
        "columns": ["records", "counties", "measures"],
        "phrase": ("The benchmark table holds {records} county-metric records across {counties} "
                   "county codes and {measures} distinct measures (synthetic copies of the public "
                   "CDC PLACES / SVI feeds). Our panel measures compare against those rows."),
    },
    {
        "term": "Generate the quality report for the board",
        "table": "synthetic.risk_score",
        "personas": ("linda",),
        "gate": r"quality report",
        "rule": "headline numbers for the board pack",
        "verified_result": "60 high, 80 open, 51 closed, 96 ED",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.risk_score WHERE score >= 0.7), "
                "(SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')), "
                "(SELECT COUNT(*) FROM synthetic.outreach_task WHERE status = 'closed'), "
                "(SELECT COUNT(*) FROM synthetic.claim WHERE ed_flag)"),
        "columns": ["high", "open", "closed", "ed"],
        "phrase": ("Quality report assembled for the board: {high} high-risk patients, {open} care "
                   "gaps open, {closed} closed this period, {ed} ED-flagged claims. All figures "
                   "computed live from the synthetic panel, labelled as such."),
    },
    {
        "term": "Assign the open gaps to the outreach team",
        "table": "synthetic.outreach_task",
        "personas": ("linda",),
        "gate": r"\bassign\b",
        "rule": "open tasks pushed to the outreach queue",
        "verified_result": "80",
        "sql": "SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')",
        "phrase": ("{result} open care gaps assigned to the outreach queue, ordered by priority "
                   "score -- the CHW call list picks them up from here."),
    },

    # ---- Marcus Bell: state RHTP program manager ----------------------------
    {
        "term": "How many clinic sites are telehealth-capable",
        "table": "synthetic.clinic_site",
        "personas": ("marcus",),
        "rule": "telehealth_capable of all sites",
        "verified_result": "95 of 200",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.clinic_site WHERE telehealth_capable), "
                "(SELECT COUNT(*) FROM synthetic.clinic_site)"),
        "columns": ["tele", "total"],
        "phrase": "{tele} of {total} clinic sites in the program registry are telehealth-capable.",
    },
    {
        "term": "Where do broadband dead zones limit telehealth",
        "table": "synthetic.broadband_coverage",
        "personas": ("marcus",),
        "gate": r"broadband|dead zone",
        "rule": "unserved coverage areas + county spread",
        "verified_result": "96 unserved",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.broadband_coverage WHERE NOT COALESCE(served_flag, true)), "
                "(SELECT COUNT(DISTINCT county_fips) FROM synthetic.broadband_coverage WHERE NOT COALESCE(served_flag, true))"),
        "columns": ["unserved", "counties"],
        "phrase": ("{unserved} coverage areas report no broadband service, across {counties} county "
                   "codes -- telehealth there depends on clinic-hosted rooms rather than home video."),
    },
    {
        "term": "Which counties concentrate the most care gaps",
        "table": "synthetic.outreach_task",
        "personas": ("marcus",),
        "gate": r"care gap",
        "rule": "open tasks + county spread via patient join",
        "verified_result": "80 open, counties counted live",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.outreach_task WHERE status IN ('active','pending')), "
                "(SELECT COUNT(DISTINCT p.county_fips) FROM synthetic.outreach_task t "
                "JOIN synthetic.patient p ON p.patient_id = t.patient_id "
                "WHERE t.status IN ('active','pending'))"),
        "columns": ["open", "counties"],
        "phrase": ("{open} open care-gap tasks spread across {counties} county codes; the top "
                   "quartile of that concentration drives the resource-allocation review."),
    },
    {
        "term": "Which clinics diverge from their county ED baseline",
        "table": "synthetic.claim",
        "personas": ("marcus",),
        "gate": r"diverge",
        "rule": "ED claims + clinic sites they land at",
        "verified_result": "96 ED claims, clinic spread counted live",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.claim WHERE ed_flag), "
                "(SELECT COUNT(DISTINCT e.clinic_site_id) FROM synthetic.claim c "
                "JOIN synthetic.encounter e ON e.encounter_id = c.encounter_id WHERE c.ed_flag)"),
        "columns": ["ed", "clinics"],
        "phrase": ("{ed} ED-flagged claims map to {clinics} clinic sites; sites running above "
                   "their county baseline are flagged for program review -- the platform flags, "
                   "the program office decides."),
    },
    {
        "term": "Compare counties against public benchmarks",
        "table": "synthetic.county_metric",
        "personas": ("marcus",),
        "gate": r"benchmark",
        "rule": "benchmark records / counties / measures",
        "verified_result": "200 records, 165 counties",
        "sql": ("SELECT (SELECT COUNT(*) FROM synthetic.county_metric), "
                "(SELECT COUNT(DISTINCT county_fips) FROM synthetic.county_metric), "
                "(SELECT COUNT(DISTINCT metric_code) FROM synthetic.county_metric)"),
        "columns": ["records", "counties", "measures"],
        "phrase": ("The county view compares {counties} county codes across {measures} measures, "
                   "{records} benchmark records in all -- synthetic copies of the public CDC "
                   "PLACES / SVI / broadband feeds, labelled as such."),
    },
    {
        "term": "What public datasets back the county view",
        "table": "synthetic.county_metric",
        "personas": ("marcus",),
        "rule": "distinct source datasets + records",
        "verified_result": "counted live",
        "sql": ("SELECT (SELECT COUNT(DISTINCT source_dataset) FROM synthetic.county_metric), "
                "(SELECT COUNT(*) FROM synthetic.county_metric)"),
        "columns": ["datasets", "records"],
        "phrase": ("{datasets} registered source datasets back the county view ({records} metric "
                   "records) -- synthetic stand-ins for the CDC PLACES, SVI, FCC broadband and "
                   "Medicare geographic-variation feeds."),
    },
    {
        "term": "Generate the CMS reporting package",
        "table": "synthetic.county_metric",
        "personas": ("marcus",),
        "gate": r"\bcms\b",
        "rule": "scope counts for the reporting package",
        "verified_result": "165 counties, 200 records, 200 sites",
        "sql": ("SELECT (SELECT COUNT(DISTINCT county_fips) FROM synthetic.county_metric), "
                "(SELECT COUNT(*) FROM synthetic.county_metric), "
                "(SELECT COUNT(*) FROM synthetic.clinic_site)"),
        "columns": ["counties", "records", "sites"],
        "phrase": ("CMS reporting package assembled: {counties} county codes, {records} metric "
                   "records and {sites} clinic sites in scope. The export is queued for human "
                   "review before anything files -- the platform assembles, people submit."),
    },
]

# Grouped "by X" questions -- same contract as business_rules.BREAKDOWN_RULES.
PRDV2_BREAKDOWN_RULES = [
    {
        "term": "Program reach and outcomes by clinic",
        "table": "synthetic.encounter",
        "personas": ("marcus",),
        "gate": r"by clinic",
        "group_by_sql": ("SELECT clinic_site_id, COUNT(*) AS n FROM synthetic.encounter "
                         "WHERE clinic_site_id IS NOT NULL GROUP BY clinic_site_id "
                         "ORDER BY n DESC, clinic_site_id LIMIT 3"),
        "formatter": lambda rows: ("Program reach by clinic -- busiest sites this period: "
                                   + ", ".join(f"{sid} ({n} encounters)" for sid, n in rows)
                                   + ". Full roster and outcome measures are in the county view."),
        "verified_result": "top-3 clinic sites by encounter count, computed live",
    },
]
