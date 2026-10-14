"""
Real business-rule definitions for RAIN's data, discovered and verified
through direct SQL testing (see maria/sarah/james/priya/david_live_data.py
for the original verification).

James's Q1 test exposed the real reason business_rules.py alone wasn't
enough: even with the correct definition IN the prompt, the LLM still
sometimes writes a fresh, wrong query instead of using it. The fix here
is stronger than a prompt instruction -- for the 15 facts below that
already have a single, unambiguous, tested SQL query, that exact query is
matched and run DIRECTLY, with no LLM SQL-generation step at all. The LLM
is only asked to generate fresh SQL for questions that don't match any of
these already-known facts.

Every entry was individually tested against rain.db and confirmed to
produce the exact known-correct number before being recorded here.
"""

import pg_compat as sqlite3
import os
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "rain.db")  # unused by pg_compat.connect(); kept so call sites below don't need to change

BUSINESS_RULES = [
    {
        "term": "Active pregnancy total count",
        "table": "PregnancyEpisode",
        "rule": "COUNT(*) -- all active pregnancy episodes",
        "verified_result": "126 patients",
        "sql": "SELECT COUNT(*) FROM PregnancyEpisode",
        "phrase": "There are {result} active pregnancies in the service area.",
    },
    {
        "term": "Elevated-risk pregnancy",
        "table": "PregnancyEpisode",
        "rule": "distance_to_delivery_miles = 115",
        "verified_result": "38 patients",
        "sql": "SELECT COUNT(*) FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115",
        "phrase": "There are {result} elevated-risk pregnancies in the service area (distance to delivering hospital = 115 miles).",
    },
    {
        "term": "Third-trimester within elevated-risk cohort",
        "table": "PregnancyEpisode",
        "rule": "trimester = 3 AND distance_to_delivery_miles = 115",
        "verified_result": "14 patients",
        "sql": "SELECT COUNT(*) FROM PregnancyEpisode WHERE trimester = 3 AND distance_to_delivery_miles = 115",
        "phrase": "{result} patients in the elevated-risk cohort are in their third trimester.",
    },
    {
        "term": "Missed prenatal visit within elevated-risk cohort",
        "table": "PregnancyEpisode",
        "rule": "last_prenatal_visit_date < '2026-04-01' AND distance_to_delivery_miles = 115",
        "verified_result": "6 patients",
        "sql": "SELECT COUNT(*) FROM PregnancyEpisode WHERE last_prenatal_visit_date < '2026-04-01' AND distance_to_delivery_miles = 115",
        "phrase": "{result} patients in the elevated-risk cohort have missed a prenatal visit since the closure.",
    },
    {
        "term": "Prenatal completion rate current",
        "table": "PregnancyEpisode",
        "rule": "100.0 * SUM(last_prenatal_visit_date >= '2026-04-01') / COUNT(*), scoped to distance_to_delivery_miles = 115",
        "verified_result": "84%",
        "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN last_prenatal_visit_date >= '2026-04-01' THEN 1 ELSE 0 END) / COUNT(*)) FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115",
        "phrase": "Prenatal completion in the elevated-risk cohort is {result}%.",
    },
    {
        "term": "ED delivery birth before arrival event",
        "table": "ClaimEncounter",
        "rule": "encounter_type = 'ED_delivery_or_BBA'",
        "verified_result": "3 events",
        "sql": "SELECT COUNT(*) FROM ClaimEncounter WHERE encounter_type = 'ED_delivery_or_BBA'",
        "phrase": "There have been {result} ED deliveries / births-before-arrival in the last 60 days.",
    },
    {
        "term": "ED delivery risk trend",
        "table": "ClaimEncounter",
        "rule": "ED_delivery_or_BBA encounters before vs on/after the 2026-03-01 closure",
        "verified_result": "0 before the closure, 3 after (2026-04-16, 2026-04-17, 2026-05-15)",
        "sql": ("SELECT "
                "SUM(CASE WHEN date < '2026-03-01' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN date >= '2026-03-01' THEN 1 ELSE 0 END), "
                "MIN(date), MAX(date) "
                "FROM ClaimEncounter WHERE encounter_type = 'ED_delivery_or_BBA'"),
        "columns": ["before", "after", "first", "last"],
        "gate": r"ed delivery",
        "phrase": "There were {before} ED deliveries before the 2026-03-01 closure and {after} after it, dated {first} through {last}.",
    },
    {
        "term": "No transport scheduled patients",
        "table": "TransportRequest",
        "rule": "patients not in TransportRequest with scheduled = true",
        "verified_result": "22 patients",
        "sql": "SELECT COUNT(*) FROM PregnancyEpisode pe WHERE pe.patient_id NOT IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'True')",
        "phrase": "{result} active pregnancy patients have no transport scheduled for an upcoming appointment.",
    },
    {
        "term": "Prenatal care gaps",
        "table": "PregnancyEpisode",
        "rule": "elevated-risk completion rate, missed visits in that cohort, and active pregnancies with no scheduled transport",
        "verified_result": "84% completion, 6 missed visits, 22 with no transport -- the same three verified rules, read together",
        "sql": ("SELECT "
                "(SELECT ROUND(100.0 * SUM(CASE WHEN last_prenatal_visit_date >= '2026-04-01' THEN 1 ELSE 0 END) / COUNT(*)) FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115), "
                "(SELECT COUNT(*) FROM PregnancyEpisode WHERE last_prenatal_visit_date < '2026-04-01' AND distance_to_delivery_miles = 115), "
                "(SELECT COUNT(*) FROM PregnancyEpisode pe WHERE pe.patient_id NOT IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'True'))"),
        "columns": ["completion", "missed", "no_transport"],
        "gate": r"prenatal care gap",
        "phrase": "Prenatal completion in the elevated-risk cohort is {completion}%. {missed} of those patients have missed a prenatal visit since the closure, and {no_transport} active pregnancy patients have no transport scheduled.",
    },
    {
        "term": "CHF COPD worsening RPM deterioration cluster",
        "table": "RPMReading",
        "rule": "condition_type IN ('CHF','COPD'), COUNT(DISTINCT patient_id)",
        "verified_result": "17 patients",
        "sql": "SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type IN ('CHF','COPD')",
        "phrase": "{result} CHF/COPD patients are showing worsening RPM readings.",
    },
    {
        "term": "Diabetes patients overdue A1c",
        "table": "ChronicConditionEnrollment",
        "rule": "condition_type = 'diabetes'",
        "verified_result": "112 patients",
        "sql": "SELECT COUNT(*) FROM ChronicConditionEnrollment WHERE condition_type='diabetes'",
        "phrase": "{result} diabetes patients are overdue for an A1c.",
    },
    {
        "term": "Diabetes control gaps care coordination",
        "table": "ChronicConditionEnrollment",
        "rule": "diabetes patients overdue for an A1c, and diabetes patients assigned to a deactivated provider, read together",
        "verified_result": "112 overdue A1c, 42 on a deactivated provider -- the same two verified rules, read together",
        "sql": ("SELECT "
                "(SELECT COUNT(*) FROM ChronicConditionEnrollment WHERE condition_type='diabetes'), "
                "(SELECT COUNT(*) FROM ChronicConditionEnrollment WHERE condition_type='diabetes' "
                "AND assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status='deactivated'))"),
        "columns": ["overdue_a1c", "lost_provider"],
        "gate": r"diabetes control gap",
        "phrase": "{overdue_a1c} diabetes patients are overdue for an A1c, and {lost_provider} of them are assigned to a provider who was deactivated in the closure.",
    },
    {
        "term": "Lost provider continuity",
        "table": "ChronicConditionEnrollment",
        "rule": "assigned_provider_id IN ('PRV-001','PRV-002')",
        "verified_result": "49 chronic patients in total (5 CHF, 42 diabetes, 2 hypertension) -- answered directly by 'Patients lost provider deactivated'; this entry has no SQL of its own because a bare 'lost provider' is ambiguous across personas",
        "sql": None,  # ambiguous without a specific cohort -- left for the LLM, with this note as guidance
        "phrase": None,
    },
    {
        "term": "SDOH transport barrier prevalence",
        "table": "SDOHFlag",
        "rule": "COUNT(*) -- all rows are flag_type='transportation'",
        "verified_result": "186 records",
        "sql": "SELECT COUNT(*) FROM SDOHFlag",
        "phrase": "{result} patients have a documented SDOH transportation barrier.",
    },
    {
        "term": "Medication non-adherence gap",
        "table": "MedicationFill",
        "rule": "patients whose most recent fill is more than 30 days before today (2026-05-15, the dataset's 'today')",
        "verified_result": "94 patients -- same figure as the dashboard's total fill-record count, now stated as what it means. The cached '10' answer is a follow-up scoped to the 17 worsening RPM patients (10 of them have a fill record, all last filled 45 days ago) and depends on conversational context this tier doesn't have",
        "sql": "SELECT COUNT(*) FROM (SELECT patient_id, MAX(fill_date) AS last_fill FROM MedicationFill GROUP BY patient_id) WHERE julianday('2026-05-15') - julianday(last_fill) > 30",
        "phrase": "{result} patients have gone more than 30 days since their last medication fill.",
    },
    {
        "term": "Hypertension RPM transmission compliance rate",
        "table": "RPMReading",
        "rule": "condition_type = 'hypertension', received/total ratio",
        "verified_result": "61%",
        "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN transmission_status='received' THEN 1 ELSE 0 END) / COUNT(*)) FROM RPMReading WHERE condition_type='hypertension'",
        "phrase": "Hypertension RPM transmission compliance is {result}%.",
    },
    {
        "term": "RPM adherence transmission received",
        "table": "RPMReading",
        "rule": "received/total by condition_type",
        "verified_result": "hypertension 61% (2,880 readings), CHF 100% (154), COPD 100% (84). Overall 64% is mostly the hypertension readings",
        "sql": ("SELECT "
                "(SELECT ROUND(100.0 * SUM(CASE WHEN transmission_status = 'received' THEN 1 ELSE 0 END) / COUNT(*)) FROM RPMReading WHERE condition_type = 'hypertension'), "
                "(SELECT ROUND(100.0 * SUM(CASE WHEN transmission_status = 'received' THEN 1 ELSE 0 END) / COUNT(*)) FROM RPMReading WHERE condition_type = 'CHF'), "
                "(SELECT ROUND(100.0 * SUM(CASE WHEN transmission_status = 'received' THEN 1 ELSE 0 END) / COUNT(*)) FROM RPMReading WHERE condition_type = 'COPD')"),
        "columns": ["hypertension", "chf", "copd"],
        "gate": r"rpm adherence",
        "phrase": "RPM readings marked received: hypertension {hypertension}%, CHF {chf}%, COPD {copd}%.",
    },
    {
        "term": "Transport queue over capacity unscheduled",
        "table": "TransportRequest",
        "rule": "COUNT(*) WHERE scheduled = false",
        "verified_result": "9 requests",
        "sql": "SELECT COUNT(*) FROM TransportRequest WHERE scheduled = 'False'",
        "phrase": "{result} transport requests are currently unscheduled, over capacity.",
    },
    {
        "term": "Transport queue today capacity scheduled",
        "table": "TransportRequest",
        "rule": "today's requests, today's scheduled requests, and the current unscheduled count, read together",
        "verified_result": "73 today, 64 scheduled, 9 unscheduled. There is no separate capacity column; the 9 is the existing over-capacity count",
        "sql": ("SELECT "
                "(SELECT COUNT(*) FROM TransportRequest WHERE date = '2026-05-15'), "
                "(SELECT COUNT(*) FROM TransportRequest WHERE date = '2026-05-15' AND scheduled = 'True'), "
                "(SELECT COUNT(*) FROM TransportRequest WHERE scheduled = 'False')"),
        "columns": ["today", "scheduled", "unscheduled"],
        "gate": r"transport queue",
        "phrase": "There are {today} transport requests today. {scheduled} of today's transport requests are scheduled. {unscheduled} transport requests are currently unscheduled, over capacity.",
    },
    {
        "term": "EMS coverage gap ZIP no unit within 60 minutes",
        "table": "EMSCoverage",
        "rule": "COUNT(*) WHERE unit_available_within_60min = false",
        "verified_result": "2 ZIP codes",
        "sql": "SELECT COUNT(*) FROM EMSCoverage WHERE unit_available_within_60min = 'False'",
        "phrase": "{result} ZIP codes have no EMS unit available within 60 minutes.",
    },
    {
        "term": "Telehealth connectivity dead zone broadband",
        "table": "ConnectivityRegistry",
        "rule": "COUNT(*) WHERE broadband_available = false",
        "verified_result": "5 ZIP codes",
        "sql": "SELECT COUNT(*) FROM ConnectivityRegistry WHERE broadband_available = 'False'",
        "phrase": "{result} ZIP codes are telehealth connectivity dead zones (no broadband).",
    },
    {
        "term": "Patients living in telehealth dead zone population",
        "table": "Patient",
        "rule": "Patient JOIN ConnectivityRegistry ON zip_code WHERE broadband_available = false",
        "verified_result": "574 patients -- the number repeated across Priya's Q4/Q5/Q6/Q8 cached answers as '574 elevated-risk patients'; the real data supports 574 as the total patient population in dead-zone ZIPs, with no additional elevated-risk filter found to reproduce the same number more narrowly",
        "sql": "SELECT COUNT(*) FROM Patient p JOIN ConnectivityRegistry cr ON p.zip_code = cr.zip_code WHERE cr.broadband_available = 'False'",
        "phrase": "{result} patients live in a ZIP code with no reliable telehealth connectivity.",
    },
    {
        "term": "Elevated risk patients telehealth dead zone",
        "table": "PregnancyEpisode",
        "rule": "elevated-risk pregnancies, and all active pregnancies, living in a ZIP with no broadband",
        "verified_result": "15 elevated-risk pregnancies and 48 active pregnancies in no-broadband ZIPs. 574 is every patient in those ZIPs, not this cohort",
        "sql": ("SELECT "
                "(SELECT COUNT(*) FROM PregnancyEpisode e JOIN Patient p ON p.patient_id = e.patient_id JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code WHERE c.broadband_available = 'False' AND e.distance_to_delivery_miles = 115), "
                "(SELECT COUNT(*) FROM PregnancyEpisode e JOIN Patient p ON p.patient_id = e.patient_id JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code WHERE c.broadband_available = 'False')"),
        "columns": ["elevated", "pregnant"],
        "gate": r"elevated[\s-]risk.*\bdead\b|\bdead\b.*elevated[\s-]risk",
        "phrase": "{elevated} elevated-risk pregnancies live in a ZIP with no broadband, out of {pregnant} active pregnancies in those ZIPs.",
    },
    {
        "term": "Unresolved provider reference",
        "table": "ProviderReferenceIssue",
        "rule": "status = 'unresolved'",
        "verified_result": "1,240 records",
        "sql": "SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'",
        "phrase": "There are {result} unresolved provider reference records.",
    },
    {
        "term": "Deactivated provider count",
        "table": "Provider",
        "rule": "status = 'deactivated'",
        "verified_result": "2 providers",
        "sql": "SELECT COUNT(*) FROM Provider WHERE status = 'deactivated'",
        "phrase": "{result} providers were deactivated in the Battle Mountain closure.",
    },
    {
        "term": "Provider crosswalk mismatch",
        "table": "ProviderReferenceIssue",
        "rule": "status = 'mismatched'",
        "verified_result": "180 records",
        "sql": "SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched'",
        "phrase": "There are {result} provider crosswalk mismatches.",
    },
    {
        "term": "Open data quality event count",
        "table": "DataQualityEvent",
        "rule": "COUNT(*) -- total event-log entries",
        "verified_result": "4 events",
        "sql": "SELECT COUNT(*) FROM DataQualityEvent",
        "phrase": "There are {result} open data-quality events.",
    },
    {
        "term": "Maternal care desert rate percentage",
        "table": "PregnancyEpisode",
        "rule": "100.0 * (patients with distance=115) / (total active pregnancies)",
        "verified_result": "30% -- exactly 38/126",
        "sql": "SELECT ROUND(100.0 * (SELECT COUNT(*) FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115) / COUNT(*)) FROM PregnancyEpisode",
        "phrase": "{result}% of active pregnancies are in a maternal care desert (more than 100 miles from delivery care).",
    },
    {
        "term": "Maternal care desert before after Battle Mountain",
        "table": "MetricTrend",
        "rule": "MetricTrend maternal_care_desert_pct before_value to after_value",
        "verified_result": "31% on 2026-01-30 to 58% on 2026-05-15. The 30% figure is the current pregnancy-row snapshot (38 of 126), not this trend",
        "sql": "SELECT before_value, after_value, before_date, after_date FROM MetricTrend WHERE metric_id = 'maternal_care_desert_pct'",
        "columns": ["before", "after", "before_date", "after_date"],
        "gate": r"before and after",
        "phrase": "The maternal care desert share moved from {before}% on {before_date} to {after}% on {after_date}.",
    },
    {
        "term": "Avoidable ED event total excluding deliveries",
        "table": "ClaimEncounter",
        "rule": "avoidable_ed_flag = true AND encounter_type != 'ED_delivery_or_BBA'",
        "verified_result": "219 events -- a distinct, broader category from the 3 ED-delivery-specific events",
        "sql": "SELECT COUNT(*) FROM ClaimEncounter WHERE avoidable_ed_flag = 'True' AND encounter_type != 'ED_delivery_or_BBA'",
        "phrase": "There are {result} avoidable ED events total.",
    },
    {
        "term": "Total transport requests today",
        "table": "TransportRequest",
        "rule": "COUNT(*) WHERE date = '2026-05-15' -- the earliest date in the dataset, treated as 'today' in James's operational narrative",
        "verified_result": "73 requests",
        "sql": "SELECT COUNT(*) FROM TransportRequest WHERE date = '2026-05-15'",
        "phrase": "There are {result} transport requests today.",
    },
    {
        "term": "Scheduled transport requests today",
        "table": "TransportRequest",
        "rule": "COUNT(*) WHERE date = '2026-05-15' AND scheduled = true",
        "verified_result": "64 requests",
        "sql": "SELECT COUNT(*) FROM TransportRequest WHERE date = '2026-05-15' AND scheduled = 'True'",
        "phrase": "{result} of today's transport requests are scheduled.",
    },
    {
        "term": "Patients lost provider deactivated",
        "table": "ChronicConditionEnrollment",
        "rule": "distinct chronic-condition patients whose assigned_provider_id belongs to a deactivated provider",
        "verified_result": "49 patients -- 5 CHF, 42 diabetes, 2 hypertension. The cached 5 + 41 + 3 is the same 49 with the 3 pregnant patients (1 diabetes + 2 hypertension) split out",
        "sql": "SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated')",
        "phrase": "{result} chronic-disease patients are currently assigned to a provider who was deactivated in the closure.",
    },
    {
        "term": "Worsening RPM deterioration patients transport barrier",
        "table": "SDOHFlag",
        "rule": "patients with worsening CHF/COPD RPM readings who also have an SDOH transportation flag",
        "verified_result": "4 patients -- also 4 within the 10 worsening patients who have a fill record, i.e. the same 4 patients",
        "sql": "SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type IN ('CHF','COPD') AND patient_id IN (SELECT patient_id FROM SDOHFlag)",
        "gate": r"transport\w*\s+barrier",
        "phrase": "{result} of the patients with worsening RPM readings also have a documented transportation barrier on file.",
        "kinds": (None, "cross_reference"),
    },
    {
        "term": "Avoidable hospitalizations elevated risk cohort",
        "table": "ClaimEncounter",
        "rule": "avoidable ED encounters (excluding ED deliveries) before vs on/after the 2026-03-01 closure; those on/after with a rendering provider who is now deactivated",
        "verified_result": "100 before, 119 after (+19%), 76 of the 119 (64%) with a deactivated rendering provider. Claims run 2025-04-10 to 2026-05-15, so a genuine before/after exists here. 100 + 119 = 219, the verified avoidable-ED total",
        "sql": ("SELECT b, a, t, ROUND(100.0 * (a - b) / b), ROUND(100.0 * t / a) FROM ("
                "SELECT SUM(CASE WHEN date < '2026-03-01' THEN 1 ELSE 0 END) AS b, "
                "SUM(CASE WHEN date >= '2026-03-01' THEN 1 ELSE 0 END) AS a, "
                "SUM(CASE WHEN date >= '2026-03-01' AND rendering_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated') THEN 1 ELSE 0 END) AS t "
                "FROM ClaimEncounter WHERE avoidable_ed_flag = 'True' AND encounter_type != 'ED_delivery_or_BBA')"),
        "columns": ["before", "after", "tied", "rise_pct", "tied_pct"],
        "phrase": "Avoidable ED visits rose from {before} to {after} since the closure, a {rise_pct}% increase, and {tied} of those {after} ({tied_pct}%) were seen by a provider who was deactivated in the closure.",
        "kinds": ("model",),
    },
    {
        "term": "Compare outcomes affected unaffected ZIP codes",
        "table": "ConnectivityRegistry",
        "rule": "patients in ZIPs with no broadband vs patients in ZIPs with broadband",
        "verified_result": "574 vs 889 (total 1,463 patients) -- exact match to the cached figures. Patient counts only; there are no outcome measures in the data",
        "sql": ("SELECT SUM(CASE WHEN c.broadband_available = 'False' THEN 1 ELSE 0 END), SUM(CASE WHEN c.broadband_available = 'True' THEN 1 ELSE 0 END) "
                "FROM Patient p JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code"),
        "columns": ["limited", "connected"],
        "gate": r"affected",  # matches "affected" and "unaffected"; "ZIP codes" alone must not trigger it
        "phrase": "{limited} patients live in ZIP codes with no broadband, versus {connected} in ZIP codes with broadband. This compares patient counts by connectivity -- the data holds no outcome measures for these two groups.",
    },
    {
        "term": "Mobile obstetric outreach equity impact",
        "table": "PregnancyEpisode",
        "rule": "active pregnancies (and elevated-risk pregnancies) in ZIPs with no broadband, alongside all patients in those ZIPs",
        "verified_result": ("48 active pregnancies (15 elevated-risk) in no-broadband ZIPs; 574 patients in total. The cached answer sizes an OBSTETRIC outreach program at 574, "
                            "but 574 is every patient in those ZIPs, not the pregnant ones"),
        "sql": ("SELECT "
                "(SELECT COUNT(*) FROM PregnancyEpisode e JOIN Patient p ON p.patient_id = e.patient_id JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code WHERE c.broadband_available = 'False'), "
                "(SELECT COUNT(*) FROM PregnancyEpisode e JOIN Patient p ON p.patient_id = e.patient_id JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code WHERE c.broadband_available = 'False' AND e.distance_to_delivery_miles = 115), "
                "(SELECT COUNT(*) FROM Patient p JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code WHERE c.broadband_available = 'False')"),
        "columns": ["pregnant", "elevated", "all_patients"],
        "gate": r"obstetric",
        "phrase": "Mobile obstetric outreach would directly address the {pregnant} active pregnancies ({elevated} of them elevated-risk) that live in a ZIP code with no broadband; {all_patients} patients in total live in those ZIPs.",
        "kinds": ("model",),
    },
    {
        "term": "Elevated risk pregnancy chronic conditions",
        "table": "ChronicConditionEnrollment",
        "rule": "patients with an elevated-risk pregnancy (distance = 115) who also have a chronic-condition enrollment",
        "verified_result": "3 patients (1 diabetes, 2 hypertension), all 3 assigned to a deactivated provider -- exact match to the cached answer",
        "sql": ("SELECT COUNT(DISTINCT patient_id), "
                "COUNT(DISTINCT CASE WHEN condition_type = 'diabetes' THEN patient_id END), "
                "COUNT(DISTINCT CASE WHEN condition_type = 'hypertension' THEN patient_id END), "
                "COUNT(DISTINCT CASE WHEN assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated') THEN patient_id END) "
                "FROM ChronicConditionEnrollment WHERE patient_id IN (SELECT patient_id FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115)"),
        "columns": ["total", "diabetes", "hypertension", "lost_provider"],
        "phrase": "{total} patients carry both an elevated-risk pregnancy and an active chronic condition ({diabetes} with diabetes, {hypertension} with hypertension), and {lost_provider} of them are assigned to a provider who was deactivated in the closure.",
        "kinds": ("cross_reference",),
    },
    {
        "term": "Compounding chronic disease cases",
        "table": "ChronicConditionEnrollment",
        "rule": "patients with an elevated-risk pregnancy (distance = 115) who also have a chronic-condition enrollment",
        "verified_result": "3 patients (1 diabetes, 2 hypertension), all 3 assigned to a deactivated provider",
        "sql": ("SELECT COUNT(DISTINCT patient_id), "
                "COUNT(DISTINCT CASE WHEN condition_type = 'diabetes' THEN patient_id END), "
                "COUNT(DISTINCT CASE WHEN condition_type = 'hypertension' THEN patient_id END), "
                "COUNT(DISTINCT CASE WHEN assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated') THEN patient_id END) "
                "FROM ChronicConditionEnrollment WHERE patient_id IN (SELECT patient_id FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115)"),
        "columns": ["total", "diabetes", "hypertension", "lost_provider"],
        "gate": r"compounding",
        "phrase": "{total} patients carry both an elevated-risk pregnancy and an active chronic condition ({diabetes} with diabetes, {hypertension} with hypertension), and {lost_provider} of them are assigned to a provider who was deactivated in the closure.",
    },
    {
        "term": "Elevated risk patients awaiting transport",
        "table": "TransportRequest",
        "rule": "the unscheduled transport requests, checked against the elevated-risk pregnancy and worsening-RPM cohorts",
        "verified_result": "9 unscheduled requests for 9 patients; 0 are elevated-risk pregnancies, 0 have worsening RPM readings, all 9 are enrolled in chronic-condition care. The cached answer only recommends this cross-check",
        "sql": ("SELECT COUNT(*), COUNT(DISTINCT patient_id), "
                "(SELECT COUNT(DISTINCT patient_id) FROM PregnancyEpisode WHERE distance_to_delivery_miles = 115 AND patient_id IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'False')), "
                "(SELECT COUNT(DISTINCT patient_id) FROM RPMReading WHERE condition_type IN ('CHF','COPD') AND patient_id IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'False')), "
                "(SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE patient_id IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'False')) "
                "FROM TransportRequest WHERE scheduled = 'False'"),
        "columns": ["unscheduled", "patients", "elevated", "worsening", "chronic"],
        "gate": r"awaiting transport",
        "phrase": "{unscheduled} transport requests are unscheduled, for {patients} different patients. Of them, {elevated} are elevated-risk pregnancy patients and {worsening} have worsening RPM readings; {chronic} are enrolled in chronic-condition care.",
    },
    {
        "term": "Transport demand changed since closure",
        "table": "TransportRequest",
        "rule": "coverage of the transport table relative to the 2026-03-01 closure",
        "verified_result": "169 requests, 2026-05-15 to 2026-05-25, none before the closure -- no baseline exists, so 'changed since the closure' cannot be computed. The LLM tier said 'none beforehand', which turns missing data into a claim about demand",
        "sql": "SELECT COUNT(*), MIN(date), MAX(date), SUM(CASE WHEN date < '2026-03-01' THEN 1 ELSE 0 END) FROM TransportRequest",
        "columns": ["n", "first", "last", "before"],
        "gate": r"transport demand",
        "phrase": "Transport records cover {first} to {last} ({n} requests); {before} are dated before the 2026-03-01 closure, so there is no earlier baseline to compare demand against.",
    },
    {
        "term": "Transports converted convert replace telehealth home capable visit",
        "table": "TransportRequest",
        "rule": "PROXY: today's scheduled transports for patients who also have an eligible telehealth session booked",
        "verified_result": "3 of 64 (1 if the session must be the same day). The data has no 'convertible' flag and no definition yields the cached 13, so this is a labelled proxy, not the cached figure",
        "sql": ("SELECT (SELECT COUNT(*) FROM TransportRequest WHERE date = '2026-05-15' AND scheduled = 'True'), "
                "(SELECT COUNT(DISTINCT t.request_id) FROM TransportRequest t JOIN TelehealthSession s ON s.patient_id = t.patient_id "
                "WHERE t.date = '2026-05-15' AND t.scheduled = 'True' AND s.eligibility_status = 'eligible')"),
        "columns": ["scheduled", "with_eligible_session"],
        "gate": r"convert|replace",
        "phrase": "The data has no flag marking a transport as convertible to telehealth. As a proxy, {with_eligible_session} of today's {scheduled} scheduled transports are for patients who also have an eligible telehealth session booked.",
    },
    {
        "term": "Connected sources across",
        "table": "ProviderReferenceIssue",
        "rule": "unresolved references, crosswalk mismatches and data-quality events, together",
        "verified_result": "1,240 unresolved, 180 mismatched, 4 events -- exact match to the cached answer",
        "sql": ("SELECT (SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched'), "
                "(SELECT COUNT(*) FROM DataQualityEvent)"),
        "columns": ["unresolved", "mismatched", "events"],
        "gate": r"data[\s-]quality",
        "phrase": "Across the connected sources: {unresolved:,} unresolved provider references, {mismatched:,} crosswalk mismatches, and {events} open data-quality events.",
    },
    {
        "term": "Reconciliation failure unresolved reference",
        "table": "ProviderReferenceIssue",
        "rule": "unresolved provider references by source_table, plus crosswalk mismatches",
        "verified_result": "Orders 433, Encounters 419, Pending claims 388 (1,240), plus 180 crosswalk mismatches",
        "sql": ("SELECT "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved' AND source_table = 'order'), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved' AND source_table = 'encounter'), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved' AND source_table = 'pending_claim'), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched')"),
        "columns": ["orders", "encounters", "claims", "mismatched"],
        "gate": r"reconciliation failure",
        "phrase": "The reconciliation failure is {orders} unresolved order references, {encounters} unresolved encounter references, and {claims} unresolved pending-claim references, plus {mismatched} crosswalk mismatches.",
    },
    {
        "term": "Remediation plan open issues",
        "table": "ProviderReferenceIssue",
        "rule": "unresolved references, crosswalk mismatches and data-quality events, together",
        "verified_result": "1,240 unresolved, 180 mismatched, 4 events",
        "sql": ("SELECT (SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched'), "
                "(SELECT COUNT(*) FROM DataQualityEvent)"),
        "columns": ["unresolved", "mismatched", "events"],
        "gate": r"remediation plan",
        "phrase": "The open issues are {unresolved:,} unresolved provider references, {mismatched:,} crosswalk mismatches, and {events} data-quality events. This does not apply a fix.",
    },
    {
        "term": "Silent patient no contact history",
        "table": "DataQualityEvent",
        "rule": "event_type = no_contact_24d",
        "verified_result": "1 event on 2026-05-15. The row has no patient id, so no history can be listed",
        "sql": "SELECT detected_date, affected_record_count FROM DataQualityEvent WHERE event_type = 'no_contact_24d'",
        "columns": ["detected", "patients"],
        "gate": r"silent patient",
        "phrase": "A data-quality event on {detected} records {patients} patient with no contact in 24 days. That row does not name the patient, so there is no history to show.",
    },
    {
        "term": "Double booked overlapping trips same day",
        "table": "TransportRequest",
        "rule": "patients with more than one transport request on the same date",
        "verified_result": "0. TransportRequest has no hour or vehicle column",
        "sql": "SELECT COUNT(*) FROM (SELECT patient_id, date FROM TransportRequest GROUP BY patient_id, date HAVING COUNT(*) > 1)",
        "gate": r"double-booked|double booked|overlapping trip",
        "phrase": "{result} patients have more than one transport request on the same day. There is no hour or vehicle column to find any other overlap.",
    },
    {
        "term": "Downstream impact closure desert avoidable",
        "table": "MetricTrend",
        "rule": "maternal care desert before/after, avoidable ED before/after, and whether any transport request predates the closure",
        "verified_result": "desert 31 to 58, avoidable ED 100 to 119, 0 transport requests before 2026-03-01",
        "sql": ("SELECT "
                "(SELECT before_value FROM MetricTrend WHERE metric_id = 'maternal_care_desert_pct'), "
                "(SELECT after_value FROM MetricTrend WHERE metric_id = 'maternal_care_desert_pct'), "
                "(SELECT SUM(CASE WHEN date < '2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag = 'True' AND encounter_type != 'ED_delivery_or_BBA'), "
                "(SELECT SUM(CASE WHEN date >= '2026-03-01' THEN 1 ELSE 0 END) FROM ClaimEncounter WHERE avoidable_ed_flag = 'True' AND encounter_type != 'ED_delivery_or_BBA'), "
                "(SELECT SUM(CASE WHEN date < '2026-03-01' THEN 1 ELSE 0 END) FROM TransportRequest)"),
        "columns": ["desert_before", "desert_after", "ed_before", "ed_after", "transport_before"],
        "gate": r"downstream impact",
        "phrase": "Since the closure, the maternal care desert share moved from {desert_before}% to {desert_after}%, and avoidable ED visits went from {ed_before} to {ed_after}. Transport records include {transport_before} requests dated before the closure, so that demand change cannot be computed.",
    },
    {
        "term": "Downstream risk scores affected issues",
        "table": "ChronicConditionEnrollment",
        "rule": "what the provider-reconciliation issue touches, and the absence of any stored issue-to-risk-score link",
        "verified_result": "49 chronic patients assigned to a deactivated provider; 0 pregnancy episodes (all were reassigned to PRV-010..019, so the cached 'every pregnancy episode still assigned' is none); no table links a data-quality issue to a risk score",
        "sql": ("SELECT (SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated')), "
                "(SELECT COUNT(*) FROM PregnancyEpisode WHERE assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated')), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'unresolved'), "
                "(SELECT COUNT(*) FROM ProviderReferenceIssue WHERE status = 'mismatched')"),
        "columns": ["chronic", "pregnancies", "unresolved", "mismatched"],
        "gate": r"downstream",
        "phrase": "The provider-reconciliation issue directly touches {chronic} chronic-disease patients assigned to the two deactivated providers; {pregnancies} pregnancy episodes are still assigned to one, and {unresolved:,} unresolved references plus {mismatched} crosswalk mismatches remain. The data holds no stored link from these issues to specific risk scores, so the affected scores can't be listed from data alone.",
    },
]

_STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "for", "of", "on", "in", "at", "me", "my", "our", "i",
    "what", "show", "tell", "give", "about", "this", "that", "these", "those", "it", "can",
    "do", "does", "please", "some", "any", "how", "why", "where", "which", "who", "and", "or",
    "but", "right", "now", "today", "currently", "current",
    # "data" and "quality" appear in nearly every one of David's real
    # questions (his whole domain is data quality), so they can't
    # discriminate between his specific facts -- keeping them was causing
    # "Open data quality event count" to win on nearly any David question
    # that just mentions his domain generally (Jaccard ~0.2-0.22 from
    # those 2 words alone). No other rule's term depends on them.
    "data", "quality",
}

# Matches "by ZIP code", "by feed", "by provider", etc. -- a request for a
# GROUPED breakdown. None of the 16 rules above answer a breakdown (all
# verified single aggregate numbers, confirmed by checking none contain
# GROUP BY) -- Tier 0 is structurally the wrong tool for these regardless
# of how well it scores, so they're routed straight to SQL generation
# instead, which can actually write a GROUP BY query. Found via Q3
# ("RPM transmission completeness by ZIP code") matching the wrong rule --
# the real cause wasn't a scoring problem, it was asking Tier 0 a question
# no Tier 0 rule could ever correctly answer.
_BREAKDOWN_PATTERN = re.compile(r"\bby\s+(zip|feed|county|provider|source|type|region|facility|condition|status|connectivity)\b", re.IGNORECASE)

# "Cross-reference A with B" / "cross reference A and B" -- asks for a
# JOIN between two different facts, which no single-fact rule can ever
# answer correctly. Found via Maria's Q3 ("cross-reference pregnancy risk
# with chronic conditions") confidently matching "Elevated-risk pregnancy"
# (Jaccard 0.25, no tie) even though the real answer needs a join this
# rule can't provide. Same treatment as breakdown questions: skip Tier 0,
# route to real SQL generation, which can write an actual JOIN.
_CROSS_REFERENCE_PATTERN = re.compile(r"\bcross[\s-]?reference\b", re.IGNORECASE)

# A request that OPENS with the verb "Model ..." ("Model avoidable
# hospitalizations for the elevated-risk cohort", "Model the equity impact
# of ...") asks for a projection or analysis, never a single stored fact.
# Found via Sarah's Q8 confidently answering "14 third-trimester patients"
# purely because "elevated-risk cohort" overlapped a rule's term (Jaccard
# 0.33) while the words that carried the real meaning ("avoidable",
# "hospitalizations") matched nothing. Anchored to the start of the
# question so "data model" phrasings elsewhere are unaffected.
_MODEL_REQUEST_PATTERN = re.compile(r"^\s*model\b", re.IGNORECASE)


def _keywords(text: str) -> set:
    words = re.findall(r"[a-z]+", text.lower())
    # Strip a trailing 's' for basic singular/plural matching (e.g. "zones"
    # vs. rule term "zone") -- found via Priya's Q4, where this exact
    # mismatch cost the correct rule a keyword and let an unrelated rule
    # win instead. Only applied to words long enough that this is safe
    # (avoids mangling short words like "is").
    stemmed = {w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words}
    return {w for w in stemmed if len(w) > 2 and w not in _STOPWORDS}


def match_known_metric(query: str):
    """Jaccard-similarity match against each rule's term (overlap size
    divided by the union of both word sets), same family of approach as
    Ultra's own frontend matcher but weighted by how much of BOTH sides
    is actually covered, not just raw overlap count. Raw overlap-count
    was too coarse: it tied "Elevated-risk pregnancy" against its own
    more-specific siblings ("Third-trimester...", "Missed visit...") on
    ANY question mentioning "elevated-risk", even when the general rule
    was clearly the better match. Jaccard resolves that correctly while
    still flagging Q5's genuine ambiguity ("awaiting transport" tying
    pregnancy vs. transport at equal similarity) as a real tie, not a
    guess -- that case still correctly falls through to the LLM.
    """
    if _BREAKDOWN_PATTERN.search(query):
        return None  # a grouped breakdown -- no Tier 0 rule can answer this correctly, skip straight to SQL generation
    # What KIND of request is this? A join ("cross-reference A with B") or a
    # projection ("Model ...") can only be answered by a rule that was itself
    # built and verified as that kind of answer (its "kinds" says so). Every
    # ordinary single-fact rule steps aside for them; conversely a
    # cross-reference/model rule is never offered to an ordinary question.
    if _CROSS_REFERENCE_PATTERN.search(query):
        query_kind = "cross_reference"
    elif _MODEL_REQUEST_PATTERN.match(query):
        query_kind = "model"
    else:
        query_kind = None

    query_words = _keywords(query)
    if not query_words:
        return None

    scores = []
    for rule in BUSINESS_RULES:
        if not rule["sql"]:
            continue
        if query_kind not in rule.get("kinds", (None,)):
            continue
        if rule.get("gate") and not re.search(rule["gate"], query, re.IGNORECASE):
            continue  # this rule only applies when its own trigger word is present
        rule_words = _keywords(rule["term"])
        overlap = query_words & rule_words
        if not overlap:
            continue
        union = query_words | rule_words
        jaccard = len(overlap) / len(union)
        scores.append((jaccard, len(overlap), rule))

    if not scores:
        return None
    scores.sort(key=lambda x: -x[0])
    best_jaccard, best_overlap, best_rule = scores[0]
    second_jaccard = scores[1][0] if len(scores) > 1 else 0

    min_overlap = 1 if len(query_words) <= 2 else 2
    if best_overlap < min_overlap:
        return None
    if best_jaccard == second_jaccard:
        return None  # tie -- genuinely ambiguous, don't guess
    return best_rule


def _clean_result(value):
    """SQLite's ROUND() always returns a float, even for whole numbers
    (84.0 instead of 84) -- this affects every percentage rule, cleaned
    up centrally here rather than per-rule."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def run_known_metric(rule: dict):
    """Executes a matched rule's pre-verified SQL directly and phrases
    the result. Returns a full response dict, or None on any failure."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(rule["sql"]).fetchone()
        conn.close()
        if rule.get("columns"):
            # multi-value rule: one row, several named values
            result = {c: _clean_result(v) for c, v in zip(rule["columns"], row)}
            message = rule["phrase"].format(**result)
        else:
            result = _clean_result(row[0])
            message = rule["phrase"].format(result=result)
        return {
            "ai_message": message,
            "suggested_chips": [],
            "confidence": None,
            "data_sources_used": [rule["table"]],
            "visualization": [{
                "type": "KnownMetricResult",
                "variant": None,
                "data": {"term": rule["term"], "sql": rule["sql"], "result": result},
            }],
            "source": "known_metric_lookup",
        }
    except Exception as e:
        print(f"[business_rules] known-metric lookup failed for '{rule['term']}': {e}")
        return None


# Breakdown rules -- verified GROUP BY queries for "by X" questions. A
# single-number rule (above) can never correctly answer these; this is
# what "by X" questions get routed to instead once match_known_metric
# correctly steps aside for them. Only added when the query has actually
# been tested against real data and confirmed to reproduce known-correct
# numbers exactly -- same standard as every other rule tonight.
def _tie_phrases(rows, unit="", noun="ZIP"):
    """[(label, value), ...] already ordered -> ["ZIP a (v)", "ZIPs b, c (v each, tied)", ...].
    Ties are stated, never silently cut: when several rows share a value the
    cached narrative names only one of them. noun=None for labels that need
    no prefix (feed names)."""
    groups = []
    for label, v in rows:
        if groups and groups[-1][0] == v:
            groups[-1][1].append(str(label))
        else:
            groups.append((v, [str(label)]))
    out = []
    for v, labels in groups:
        v = _clean_result(v)
        if len(labels) == 1:
            out.append(f"{noun + ' ' if noun else ''}{labels[0]} ({v}{unit})")
        else:
            out.append(f"{noun + 's ' if noun else ''}{', '.join(labels)} ({v}{unit} each, tied)")
    return out


def _fmt_maria_outreach(rows):
    """Ranked third-trimester list. Same five factors as maria_action_package._factors."""
    telehealth = sum(1 for r in rows if r[2] == "telehealth")
    hybrid = sum(1 for r in rows if r[2] == "hybrid")
    in_person = sum(1 for r in rows if r[2] == "in_person")
    no_transport = _clean_result(rows[0][3])
    chronic = _clean_result(rows[0][4])
    groups = []
    for pid, score in ((r[0], _clean_result(r[1])) for r in rows):
        if groups and groups[-1][0] == score:
            groups[-1][1].append(pid)
        else:
            groups.append((score, [pid]))
    listing = "; ".join(f"{', '.join(pids)} -- {score} of 5" for score, pids in groups)
    return (f"Priority outreach list: {len(rows)} third-trimester elevated-risk patients, ranked by risk factors met (of 5). "
            f"Recommended intervention: {telehealth} telehealth, {hybrid} hybrid, {in_person} in-person. "
            f"{hybrid + no_transport} transport drafts: the {hybrid} hybrid patients plus {no_transport} pregnancies with no scheduled transport. "
            f"{chronic} of the {len(rows)} are also in a chronic program. {listing}.")


def _fmt_maria_eligibility(rows):
    d = {label: (n, pts) for label, n, pts in rows}
    g = lambda k: d.get(k, (0, 0))[0]
    total = g("sessions:eligible") + g("sessions:hybrid") + g("sessions:dead-zone")
    return (f"Of the {g('cohort')} third-trimester elevated-risk patients, {total} telehealth sessions are booked: "
            f"{g('sessions:eligible')} eligible, {g('sessions:hybrid')} hybrid, {g('sessions:dead-zone')} dead-zone "
            f"(one patient has two sessions). By ZIP broadband records, though, {g('zip_no_broadband')} of the {g('cohort')} "
            f"patients live in a ZIP with no broadband, more than the session eligibility labels suggest.")


def _fmt_telehealth_demand(rows):
    total = sum(n for _, n, _ in rows)
    today = sum(t or 0 for _, _, t in rows)
    by_type = {t: n for t, n, _ in rows}
    return (f"{total} telehealth sessions are booked ({by_type.get('prenatal', 0)} prenatal, {by_type.get('chronic-care', 0)} chronic-care), "
            f"{today} of them today. The data holds no room or bandwidth capacity figure, so demand can't be compared against capacity.")


_DQ_EVENT_PHRASES = {
    "unresolved_reference": "unresolved provider references",
    "missing_transmission": "missing RPM transmissions",
    "conformance_error": "FHIR conformance errors",
    "no_contact_24d": "a patient with no contact in 24 days",
}


def _fmt_degraded(rows):
    deact = [(a, d) for k, a, d, n in rows if k == "deactivated"]
    events = []
    for k, a, d, n in rows:
        if k == "deactivated":
            continue
        what = _DQ_EVENT_PHRASES.get(k, k)
        count = f"{n} " if str(n).isdigit() and int(n) > 1 else ""
        events.append(f"{count}{what} ({a}, {d})")
    when = deact[0][1] if deact else "the closure"
    who = " and ".join(a for a, _ in deact)
    return (f"Providers {who} were deactivated on {when}. Since then the data shows: " + "; ".join(events) + ". "
            "Provider-crosswalk mismatches carry no date in the data, so their timing can't be confirmed.")


def _fmt_pipeline(rows):
    delayed = sorted([(n, float(h)) for n, h, s in rows if s == "delayed"], key=lambda x: -x[1])
    on_time = [float(h) for n, h, s in rows if s != "delayed"]
    if not delayed:
        return "No feeds are running delayed."
    lag = ", ".join(f"{n} ({_clean_result(h)} hours)" for n, h in delayed)
    verb = "feed is" if len(delayed) == 1 else "feeds are"
    tail = f" The other {len(on_time)} are on time, at most {_clean_result(max(on_time))} hours behind." if on_time else ""
    return f"{len(delayed)} {verb} running delayed: {lag}.{tail}"


BREAKDOWN_RULES = [
    {
        "term": "Patient count by county access disparities",
        "table": "Patient",
        "group_by_sql": "SELECT county, COUNT(*) AS n FROM Patient GROUP BY county ORDER BY county",
        "verified_result": "Humboldt 480, Lander 494, Pershing 489 -- exact match to the cached spec figures",
    },
    {
        # Optional keys, used by rules that aren't a plain "by X" breakdown:
        #   gate       regex that makes this rule applicable (besides "by X")
        #   personas   only these personas may receive it -- a list that is
        #              right for one persona would be wrong for another
        #   formatter  rows -> message, when the default "label: value" isn't right
        "term": "Avoidable ED utilization concentrate ZIP after closure",
        "table": "ClaimEncounter",
        "group_by_sql": ("SELECT p.zip_code, COUNT(*) AS n FROM ClaimEncounter c JOIN Patient p ON p.patient_id = c.patient_id "
                         "WHERE c.avoidable_ed_flag = 'True' AND c.encounter_type != 'ED_delivery_or_BBA' AND c.date >= '2026-03-01' "
                         "GROUP BY p.zip_code ORDER BY n DESC, p.zip_code LIMIT 3"),
        "gate": r"\bavoidable\b.*\b(concentrat|where)|\bwhere\b.*\bavoidable\b",
        "formatter": lambda rows: "Since the 2026-03-01 closure, avoidable ED visits are concentrated in " + ", ".join(f"ZIP {z} ({n})" for z, n in rows) + ".",
        "verified_result": ("89828 (26), 89823 (16), 89821 (15) since the closure. NOTE the cached 37 / 25 / 19 are the ALL-TIME counts "
                            "(89821 and 89825 tie at 19 all-time) -- same three ZIPs, same order, but the cached figures are not post-closure"),
    },
    {
        "term": "Risk ranked outreach list chronic patients",
        "table": "RPMReading",
        "personas": ("sarah",),
        "gate": r"risk[\s-]?ranked|outreach list",
        "group_by_sql": ("SELECT patient_id, 1 + med_gap + lost_provider + transport_barrier AS score FROM ("
                         "SELECT w.patient_id, "
                         "CASE WHEN EXISTS (SELECT 1 FROM MedicationFill m WHERE m.patient_id = w.patient_id AND julianday('2026-05-15') - julianday(m.fill_date) > 30) THEN 1 ELSE 0 END AS med_gap, "
                         "CASE WHEN EXISTS (SELECT 1 FROM ChronicConditionEnrollment e WHERE e.patient_id = w.patient_id AND e.assigned_provider_id IN (SELECT provider_id FROM Provider WHERE status = 'deactivated')) THEN 1 ELSE 0 END AS lost_provider, "
                         "CASE WHEN EXISTS (SELECT 1 FROM SDOHFlag s WHERE s.patient_id = w.patient_id) THEN 1 ELSE 0 END AS transport_barrier "
                         "FROM (SELECT DISTINCT patient_id FROM RPMReading WHERE condition_type IN ('CHF','COPD')) w) "
                         "WHERE 1 + med_gap + lost_provider + transport_barrier >= 3 ORDER BY score DESC, patient_id"),
        "formatter": lambda rows: ("Highest-priority outreach list (worsening RPM readings, medication gap over 30 days, deactivated provider, transportation barrier): "
                                   + "; ".join(f"{', '.join(pid for pid, s in rows if s == sc)} -- {sc} of 4" for sc in sorted({s for _, s in rows}, reverse=True)) + "."),
        "verified_result": ("PT-00127..130 hit all 4 factors, PT-00131 hits 3 of 4. The cached prose names the factors as RPM / medication gap / lost provider, "
                            "but all five have those three -- what separates PT-00131 in the data is the transportation barrier (127-130 have one, 131 does not)"),
    },
    {
        "term": "Priority maternal outreach list",
        "table": "PregnancyEpisode",
        "personas": ("maria",),
        "gate": r"priority outreach",
        "group_by_sql": (
            "SELECT e.patient_id, "
            "(CASE WHEN TRIM(COALESCE(e.risk_diagnoses, '')) <> '' THEN 1 ELSE 0 END) "
            "+ (CASE WHEN e.last_prenatal_visit_date < '2026-04-01' THEN 1 ELSE 0 END) "
            "+ (CASE WHEN NOT EXISTS (SELECT 1 FROM TransportRequest t WHERE t.patient_id = e.patient_id AND t.scheduled = 'True') THEN 1 ELSE 0 END) "
            "+ (CASE WHEN NOT EXISTS (SELECT 1 FROM TelehealthSession s WHERE s.patient_id = e.patient_id AND s.eligibility_status = 'eligible') THEN 1 ELSE 0 END) "
            "+ (CASE WHEN EXISTS (SELECT 1 FROM ChronicConditionEnrollment c WHERE c.patient_id = e.patient_id) THEN 1 ELSE 0 END) AS score, "
            "CASE WHEN EXISTS (SELECT 1 FROM TelehealthSession s WHERE s.patient_id = e.patient_id AND s.eligibility_status = 'eligible') THEN 'telehealth' "
            "WHEN EXISTS (SELECT 1 FROM TelehealthSession s WHERE s.patient_id = e.patient_id AND s.eligibility_status = 'hybrid') THEN 'hybrid' "
            "ELSE 'in_person' END AS kind, "
            "(SELECT COUNT(*) FROM PregnancyEpisode pe WHERE pe.patient_id NOT IN (SELECT patient_id FROM TransportRequest WHERE scheduled = 'True')) AS no_transport, "
            "(SELECT COUNT(DISTINCT patient_id) FROM ChronicConditionEnrollment WHERE patient_id IN "
            "(SELECT patient_id FROM PregnancyEpisode WHERE trimester = 3 AND distance_to_delivery_miles = 115)) AS chronic "
            "FROM PregnancyEpisode e WHERE e.trimester = 3 AND e.distance_to_delivery_miles = 115 "
            "ORDER BY score DESC, e.expected_delivery_date, e.patient_id"
        ),
        "formatter": _fmt_maria_outreach,
        "verified_result": "14 third-trimester patients, 8 telehealth / 3 hybrid / 3 in-person, 25 transport drafts, 3 chronic handoffs. Same ranking as maria_action_package.",
    },
    {
        "term": "Highest maternal access risk ZIP codes",
        "table": "PregnancyEpisode",
        "gate": r"\bmaternal\b.*\bzip|\bzip\b.*\bmaternal\b",
        "group_by_sql": ("WITH z AS (SELECT p.zip_code AS zip, COUNT(*) AS n FROM PregnancyEpisode e JOIN Patient p ON p.patient_id = e.patient_id "
                         "WHERE e.distance_to_delivery_miles = 115 GROUP BY p.zip_code) "
                         "SELECT zip, n FROM z WHERE n >= (SELECT n FROM z ORDER BY n DESC LIMIT 1 OFFSET 2) ORDER BY n DESC, zip"),
        "formatter": lambda rows: "Elevated-risk pregnancies are most concentrated in " + "; ".join(_tie_phrases(rows)) + ".",
        "verified_result": "89828 (7), 89810 (6), then 89816 / 89818 / 89825 tied at 4. The cached answer names only 89825 for third place",
    },
    {
        "term": "Target resources first maternal ZIP",
        "table": "PregnancyEpisode",
        "personas": ("priya",),
        "gate": r"target resource",
        "group_by_sql": ("WITH z AS (SELECT p.zip_code AS zip, COUNT(*) AS n FROM PregnancyEpisode e JOIN Patient p ON p.patient_id = e.patient_id "
                         "WHERE e.distance_to_delivery_miles = 115 GROUP BY p.zip_code) "
                         "SELECT zip, n FROM z WHERE n >= (SELECT n FROM z ORDER BY n DESC LIMIT 1 OFFSET 2) ORDER BY n DESC, zip"),
        "formatter": lambda rows: "Elevated-risk pregnancies are most concentrated in " + "; ".join(_tie_phrases(rows)) + ".",
        "verified_result": "89828 (7), 89810 (6), then 89816 / 89818 / 89825 tied at 4",
    },
    {
        "term": "Transport options request type",
        "table": "TransportRequest",
        "personas": ("maria",),
        "gate": r"transport option",
        "group_by_sql": "SELECT request_type, COUNT(*) FROM TransportRequest GROUP BY request_type ORDER BY request_type",
        "formatter": lambda rows: "Transport options on file are " + ", ".join(f"{label} ({_clean_result(n)})" for label, n in rows) + ".",
        "verified_result": "EMS 10, NEMT 159",
    },
    {
        "term": "Telehealth equity gap ZIP",
        "table": "ConnectivityRegistry",
        "personas": ("priya",),
        "gate": r"equity gap",
        "group_by_sql": ("SELECT c.zip_code, COUNT(p.patient_id) FROM ConnectivityRegistry c "
                         "LEFT JOIN Patient p ON p.zip_code = c.zip_code "
                         "WHERE c.broadband_available = 'False' "
                         "GROUP BY c.zip_code ORDER BY COUNT(p.patient_id) DESC, c.zip_code"),
        "formatter": lambda rows: (
            "The telehealth equity gaps are the ZIPs with no broadband: "
            + ", ".join(f"ZIP {z} ({_clean_result(n)} patients)" for z, n in rows)
            + f". {_clean_result(sum(_clean_result(n) for _, n in rows))} patients live in those ZIPs."
        ),
        "verified_result": "89828 (125), 89825 (118), 89823 (115), 89821 (109), 89820 (107). 574 patients total. The cached 240 elevated-risk figure is not this population",
    },
    {
        "term": "RPM transmission completeness gap by ZIP code",
        "table": "RPMReading",
        "gate": r"\bby\s+zip\b|rpm.*gap|prioritize.*rpm",
        "group_by_sql": ("WITH z AS (SELECT p.zip_code AS zip, ROUND(100.0 * SUM(CASE WHEN r.transmission_status = 'received' THEN 1 ELSE 0 END) / COUNT(*)) AS pct "
                         "FROM RPMReading r JOIN Patient p ON p.patient_id = r.patient_id GROUP BY p.zip_code) "
                         "SELECT zip, pct FROM z WHERE pct <= (SELECT pct FROM z ORDER BY pct ASC LIMIT 1 OFFSET 2) ORDER BY pct, zip"),
        "formatter": lambda rows: "The weakest RPM transmission completeness is in " + "; ".join(_tie_phrases(rows, unit="%")) + ".",
        "verified_result": ("89825 42%, 89823 45%, then 89820 and 89821 tied at 49%. RPMReading has no ZIP of its own but joins to Patient.zip_code -- "
                            "the earlier 'no ZIP dimension' answer was wrong. The cached answer names only 89820 for third"),
    },
    {
        "term": "Telehealth eligible prenatal patients connectivity",
        "table": "TelehealthSession",
        "personas": ("maria",),
        "gate": r"telehealth prenatal",
        # cohort = the 14 third-trimester elevated-risk patients
        "group_by_sql": (
            "SELECT 'sessions:' || eligibility_status, COUNT(*), COUNT(DISTINCT patient_id) FROM TelehealthSession WHERE patient_id IN (SELECT patient_id FROM PregnancyEpisode WHERE trimester = 3 AND distance_to_delivery_miles = 115) GROUP BY eligibility_status "
            "UNION ALL SELECT 'zip_no_broadband', COUNT(*), COUNT(*) FROM Patient p JOIN ConnectivityRegistry c ON c.zip_code = p.zip_code WHERE p.patient_id IN (SELECT patient_id FROM PregnancyEpisode WHERE trimester = 3 AND distance_to_delivery_miles = 115) AND c.broadband_available = 'False' "
            "UNION ALL SELECT 'cohort', COUNT(*), COUNT(*) FROM Patient WHERE patient_id IN (SELECT patient_id FROM PregnancyEpisode WHERE trimester = 3 AND distance_to_delivery_miles = 115)"
        ),
        "formatter": _fmt_maria_eligibility,
        "verified_result": ("9 eligible / 3 hybrid / 3 dead-zone SESSIONS across the 14 third-trimester elevated-risk patients (one has 2 sessions), exactly the cached split. "
                            "But 9 of the 14 patients live in a no-broadband ZIP -- the eligibility labels and the ZIP data disagree"),
    },
    {
        "term": "Telehealth demand against room capacity",
        "table": "TelehealthSession",
        "personas": ("james",),
        "gate": r"telehealth demand|capacity gap",
        "group_by_sql": "SELECT session_type, COUNT(*), SUM(CASE WHEN scheduled_date = '2026-05-15' THEN 1 ELSE 0 END) FROM TelehealthSession GROUP BY session_type",
        "formatter": _fmt_telehealth_demand,
        "verified_result": ("60 sessions booked (52 prenatal, 8 chronic-care), 17 today. The cached '52 prenatal' is real but across all dates; '65 virtual visits today' is not "
                            "supported (17 today), and no capacity data exists anywhere"),
    },
    {
        "term": "Degraded after closure",
        "table": "DataQualityEvent",
        "personas": ("david",),
        "gate": r"\bdegrad",
        "group_by_sql": ("SELECT 'deactivated' AS k, provider_id AS a, deactivation_date AS d, '' AS n FROM Provider WHERE status = 'deactivated' "
                         "UNION ALL SELECT event_type, source_system, detected_date, CAST(affected_record_count AS TEXT) FROM DataQualityEvent WHERE detected_date >= '2026-03-01' ORDER BY d, k"),
        "formatter": _fmt_degraded,
        "verified_result": ("PRV-001/PRV-002 deactivated 2026-03-01; the 1,240 unresolved references detected 2026-03-06, plus events on 05-01, 05-08, 05-15. "
                            "The 180 crosswalk mismatches have no date column, so 'both appeared after March 1st' can only be confirmed for the 1,240"),
    },
    {
        "term": "FHIR conformance rate by feed",
        "table": "DataSourceFeed",
        "gate": r"fhir conformance",
        "group_by_sql": ("WITH f AS (SELECT source_name AS s, CAST(fhir_conformance_pct AS REAL) AS p FROM DataSourceFeed) "
                         "SELECT s, p FROM f WHERE p <= (SELECT p FROM f ORDER BY p LIMIT 1 OFFSET 2) ORDER BY p, s"),
        "formatter": lambda rows: "FHIR conformance is weakest for " + "; ".join(_tie_phrases(rows, unit="%", noun=None)) + ".",
        "verified_result": "New Rural Clinic EHR Connector 88%, RPM Platform 91%, NEMT / Transportation Logs 95% -- exact match to the cached figures",
    },
    {
        "term": "Pipeline freshness ingestion lag",
        "table": "DataSourceFeed",
        "gate": r"freshness|ingestion lag|pipeline lag",
        "group_by_sql": "SELECT source_name, pipeline_freshness_hours, ingestion_lag_status FROM DataSourceFeed",
        "formatter": _fmt_pipeline,
        "verified_result": "2 delayed: RPM Platform 14h, New Rural Clinic EHR Connector 12h; the other 10 within 6h -- exact match to the cached figures",
    },
]


def match_breakdown_rule(query: str, persona: str = None):
    """Same Jaccard-similarity approach as match_known_metric, scoped to
    BREAKDOWN_RULES only. A rule applies to an actual 'by X' question, or to
    a question matching its own "gate" -- never just because its term shares
    generic words. A rule with "personas" is only offered to those personas.

    Requires a minimum overlap, same as match_known_metric -- found via
    Maria's Q5 ("...by connectivity") matching the county rule on the
    single generic shared word "patient" alone. With only one rule in
    the list there was no second-best score to lose to, so any nonzero
    overlap won by default; a minimum score closes that gap.
    """
    import re as _re
    query_words = _keywords(query)
    if not query_words:
        return None
    min_overlap = 1 if len(query_words) <= 2 else 2
    best_rule, best_jaccard, second_jaccard = None, 0, 0
    for rule in BREAKDOWN_RULES:
        if rule.get("personas") and persona not in rule["personas"]:
            continue
        gated = _BREAKDOWN_PATTERN.search(query) or (rule.get("gate") and _re.search(rule["gate"], query, _re.IGNORECASE))
        if not gated:
            continue
        rule_words = _keywords(rule["term"])
        overlap = query_words & rule_words
        if len(overlap) < min_overlap:
            continue
        jaccard = len(overlap) / len(query_words | rule_words)
        if jaccard > best_jaccard:
            second_jaccard, best_jaccard, best_rule = best_jaccard, jaccard, rule
        elif jaccard > second_jaccard:
            second_jaccard = jaccard
    if best_rule and best_jaccard > second_jaccard:
        return best_rule
    return None


def run_breakdown_rule(rule: dict):
    """Executes a matched breakdown rule's query and phrases every row into
    one sentence (default "label: value", or the rule's own formatter).
    Returns a full response dict, or None on any failure."""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(rule["group_by_sql"]).fetchall()
        conn.close()
        if not rows:
            return None
        if rule.get("formatter"):
            message = rule["formatter"](rows)
        else:
            message = "By the numbers -- " + ", ".join(f"{label}: {value}" for label, value in rows) + "."
        return {
            "ai_message": message,
            "suggested_chips": [],
            "confidence": None,
            "data_sources_used": [rule["table"]],
            "visualization": [{
                "type": "KnownBreakdownResult",
                "variant": None,
                "data": {"term": rule["term"], "sql": rule["group_by_sql"], "rows": rows},
            }],
            "source": "known_breakdown_lookup",
        }
    except Exception as e:
        print(f"[business_rules] breakdown lookup failed for '{rule['term']}': {e}")
        return None


def rules_for_tables(table_names: list) -> list:
    """Returns only the business rules relevant to the given table names --
    used to keep the LLM prompt focused, not dump all rules into every
    query regardless of relevance."""
    table_set = set(table_names)
    return [r for r in BUSINESS_RULES if r["table"] in table_set]


def format_rules_for_prompt(rules: list) -> str:
    if not rules:
        return ""
    lines = ["\nKnown business-rule definitions for terms in this schema (use these EXACT definitions, don't guess your own):"]
    for r in rules:
        lines.append(f'- "{r["term"]}" = {r["table"]}: {r["rule"]}  (verified: {r["verified_result"]})')
    return "\n".join(lines)


# Persona-scoped summary requests ("generate a brief/summary for X") ask
# for SEVERAL known facts combined, not one -- neither the single-metric
# nor the breakdown tier above can answer these, and asking a single-
# concept classifier "which ONE concept is this about" correctly returns
# nothing for a genuinely multi-topic question (confirmed: the LLM tier
# already does this correctly, it's not a bug -- there's just nowhere to
# route the "correctly nothing" to). This tier gives it somewhere to go,
# for personas where enough of their real summary content has a verified
# rule behind it. Each persona below lists only facts that already have
# a verified single-value rule.
_SUMMARY_PATTERN = re.compile(r"\bgenerate\b.*\b(brief|summary|report)\b|\boperations plan\b", re.IGNORECASE)

PERSONA_SUMMARY_FACTS = {
    "maria": [
        "Active pregnancy total count",
        "Elevated-risk pregnancy",
        "Missed prenatal visit within elevated-risk cohort",
        "Prenatal completion rate current",
        "No transport scheduled patients",
    ],
    "david": [
        "Unresolved provider reference",
        "Provider crosswalk mismatch",
        "Open data quality event count",
    ],
    "priya": [
        "Maternal care desert rate percentage",
        "Avoidable ED event total excluding deliveries",
        "Patients living in telehealth dead zone population",
    ],
    "sarah": [
        "CHF COPD worsening RPM deterioration cluster",
        "Medication non-adherence gap",
        "Patients lost provider deactivated",
        "Diabetes patients overdue A1c",
        "Hypertension RPM transmission compliance rate",
    ],
    "james": [
        "Total transport requests today",
        "Scheduled transport requests today",
        "Transport queue over capacity unscheduled",
    ],
}


def is_summary_request(query: str) -> bool:
    return bool(_SUMMARY_PATTERN.search(query))


def run_persona_summary(persona: str):
    """Combines every rule in PERSONA_SUMMARY_FACTS[persona] into one
    answer, each fact genuinely computed live. Returns None if this
    persona isn't populated yet (falls through to the normal tiers) or
    if the database is unreachable."""
    fact_terms = PERSONA_SUMMARY_FACTS.get(persona)
    if not fact_terms:
        return None
    rules_by_term = {r["term"]: r for r in BUSINESS_RULES}
    try:
        conn = sqlite3.connect(DB_PATH)
        parts = []
        sources = set()
        for term in fact_terms:
            rule = rules_by_term[term]
            result = _clean_result(conn.execute(rule["sql"]).fetchone()[0])
            parts.append(rule["phrase"].format(result=result))
            sources.add(rule["table"])
        conn.close()
        return {
            "ai_message": " ".join(parts),
            "suggested_chips": [],
            "confidence": None,
            "data_sources_used": sorted(sources),
            "visualization": [{"type": "KnownSummaryResult", "variant": None, "data": {"facts": fact_terms}}],
            "source": "known_summary_lookup",
        }
    except Exception as e:
        print(f"[business_rules] persona summary failed for '{persona}': {e}")
        return None