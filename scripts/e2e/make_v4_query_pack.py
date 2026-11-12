"""Write doc/queries/rain_v4_persona_queries.sql: the v0.4 persona query pack.

The six v0.3 personas keep their 60 validated queries (the 38 v0.3 tables are unchanged in rain_v4).
PRD v0.4 adds 10 queries (5 synthetic + 5 public) for each of the five v0.2 operator personas, the
two patients and the payer analyst (Hannah Lee): 140 queries for 14 personas. Patients' synthetic queries
are anchored to their own synthetic patient record (Linda Garcia M-40107, Rosa Martinez R-50214); the payer
analyst's are aggregated over the plan's members and de-identified.

A few v0.3 and v0.4 queries are patched below (FIXES) where the regenerated, calibrated synthetic schema made
them return no rows; each patch keeps the question's intent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = (ROOT / "doc/queries/rain_v3_persona_queries.sql").read_text(encoding="utf-8")
OUT = ROOT / "doc/queries/rain_v4_persona_queries.sql"

SIX = "VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill')"
SIX_UP = "('ELKO', 'HUMBOLDT', 'LANDER', 'PERSHING', 'WHITE PINE', 'CHURCHILL')"
LINDA, ROSA = "M-40107", "R-50214"
# Dr. Hargrove's site (metrics_v4.CONFIG hargrove_site) and the patients seen there (one row per patient).
SITE = ("WITH site AS (SELECT 'winnemucca'::text AS clinic_site_id),\n"
        "seen AS (SELECT DISTINCT e.patient_id FROM synthetic.encounter e JOIN site ON site.clinic_site_id = e.clinic_site_id)")
PLAN = "High Desert Health Plan"
# The plan's networks (contract_benchmark.payer), the contract year, and the claims-through quarter end
# (the latest refresh less the claims lag, to the end of that quarter), as metrics_v4 computes them.
PLAN_CTE = f"""WITH plan AS (
  SELECT cb.network_id, cb.expected_pmpm, cb.contract_start, cb.contract_year, cb.quality_gate_required, cb.quality_gate_total
  FROM synthetic.contract_benchmark cb
  WHERE cb.payer = '{PLAN}' AND cb.contract_year = (SELECT max(contract_year) FROM synthetic.contract_benchmark)),
thru AS (
  SELECT (date_trunc('quarter', max(ds.last_refreshed)
            - make_interval(days => (SELECT lag_days FROM synthetic.data_source WHERE data_source_id = 'SYN-claim')))
          + interval '3 months' - interval '1 day')::date AS period_end
  FROM synthetic.data_source ds),
mem AS (
  SELECT p.network_id, count(*) AS members
  FROM synthetic.attributed_member am JOIN synthetic.patient p ON p.patient_id = am.patient_id
  JOIN plan ON plan.network_id = p.network_id AND plan.contract_year = am.contract_year
  WHERE am.payer = '{PLAN}' GROUP BY p.network_id)"""
# Months of claims in the contract year so far (contract start to the claims-through quarter end).
MONTHS = ("((extract(year FROM thru.period_end) * 12 + extract(month FROM thru.period_end))"
          " - (extract(year FROM plan.contract_start) * 12 + extract(month FROM plan.contract_start)) + 1)")

HEADER = f"""-- =====================================================================================================
-- RAIN v0.4 - persona query pack for pgAdmin and the backend (database: rain_v4)
-- 14 personas x (5 synthetic + 5 public) = 140 queries. Each query is standalone: select it and press F5.
-- Served by GET /api/v4/queries/{{id}} and answerable in the chat by id or by question.
--
-- Schemas
--   synthetic    59 tables of row-level synthetic operational data (scripts/e2e/synth/gen_synthetic_v4.py, see
--                doc/queries/RAIN_v4_synthetic_extensions.md), calibrated to the Q3 checkpoint: 31,600 attributed
--                members, claims, encounters, quality results, readings, appointments. The UI computes every figure
--                from these rows (rain-api/metrics_v4.py), so these queries and the screens read the same data.
--   public_data  Real public datasets for NV + TN, listed with URL, release and download date in
--                .data/public/MANIFEST.md: CDC PLACES, CDC/ATSDR SVI, USDA RUCC, HRSA HPSA, HRSA health center
--                sites, NPPES, Census gazetteer + ZCTA-to-county + county boundaries, Census ACS 2020-2024,
--                HRSA FORHP rural areas, CMS Hospital General Information + Unplanned Hospital Visits,
--                CMS Provider of Services (via HRSA), HRSA UDS 2025, CMS eCQM specifications, and drive times
--                computed with OSRM on OpenStreetMap, County Health Rankings 2025 (county_health_rankings).
--                Not loaded yet (blocked): FCC broadband, CMS Geographic Variation.
--
-- The network: Sierra Basin Community Health serves six rural NV counties
--   Elko 32007 | Humboldt 32013 (Winnemucca) | Lander 32015 (Battle Mountain) | Pershing 32027 | White Pine 32033 |
--   Churchill 32001 (Fallon)
-- Patient anchors in the synthetic schema: Linda Garcia = {LINDA}, Rosa Martinez = {ROSA}.
-- Payer analyst scope: {PLAN} members (contract_benchmark.payer, attributed_member.payer), aggregated.
-- =====================================================================================================
"""

v3_body = V3[V3.index("-- #####"):].replace("rain_v3", "rain_v4")

# FIXES to the v3 part for the regenerated synthetic schema (the v3 file itself stays as validated for rain_v3).
# ACCESS-S2: appointment.status has no 'pending' value now; a visit not yet confirmed is 'booked'.
_old = "WHERE a.status = 'pending' OR a.status IS NULL"
assert v3_body.count(_old) == 1, "ACCESS-S2 changed in the v3 pack"
v3_body = v3_body.replace(_old, "WHERE a.status = 'booked'")


def section(title):
    return f"\n\n-- {'#' * 101}\n-- {title}\n-- {'#' * 101}\n"


def q(qid, persona, data, question, sql):
    return f"\n-- @id {qid}\n-- @persona {persona}\n-- @data {data}\n-- @question {question}\n{sql.strip()};\n"


NEW = []
# ── Dr. Linda Hargrove (clinic medical / quality director, one site) ───────────────────────────────
P = "rain_hargrove"
NEW.append(section("HARGROVE - Dr. Linda Hargrove (Clinic Medical / Quality Director): one site's risk mix, care gaps,\n-- closure, low-value care, telehealth; public quality and access benchmarks"))
NEW += [
    q("HAR-S1", P, "synthetic", "What is the risk mix of the patients seen at my site?", f"""
{SITE}
SELECT i.segment AS risk_segment, count(*) AS patients, round(avg(i.score)::numeric, 2) AS avg_impactability,
       round(sum(i.predicted_cost_avoided)) AS predicted_cost_avoided
FROM synthetic.impactability_score i JOIN seen ON seen.patient_id = i.patient_id
WHERE i.model_version = (SELECT model_version FROM synthetic.model_card WHERE release_status = 'released' ORDER BY model_version DESC LIMIT 1)
GROUP BY i.segment ORDER BY patients DESC"""),
    q("HAR-S2", P, "synthetic", "Which care gaps are still open for patients seen at my site?", f"""
{SITE}
SELECT cg.measure_code, cg.status, count(*) AS gaps, min(cg.opened_at) AS oldest_opened
FROM synthetic.care_gap cg JOIN seen ON seen.patient_id = cg.patient_id
WHERE cg.status <> 'closed'
GROUP BY cg.measure_code, cg.status ORDER BY gaps DESC"""),
    q("HAR-S3", P, "synthetic", "How are outreach tasks closing for my site's patients, open against closed?", f"""
{SITE}
SELECT CASE WHEN ot.closed_at IS NULL THEN 'Open' ELSE 'Closed' END AS state, count(*) AS tasks,
       round(avg(ot.priority_score)::numeric, 2) AS avg_priority
FROM synthetic.outreach_task ot JOIN seen ON seen.patient_id = ot.patient_id
GROUP BY 1 ORDER BY 1"""),
    q("HAR-S4", P, "synthetic", "Which low-value findings were billed at my site, by measure and dollars?", f"""
{SITE}
SELECT lvf.measure_id, lvf.classification, count(*) AS findings, round(sum(lvf.allowed_amount)::numeric, 2) AS allowed_dollars
FROM synthetic.low_value_finding lvf JOIN site ON site.clinic_site_id = lvf.clinic_site_id
GROUP BY lvf.measure_id, lvf.classification ORDER BY allowed_dollars DESC NULLS LAST"""),
    q("HAR-S5", P, "synthetic", "What share of my site's encounters were telehealth?", f"""
{SITE}
SELECT count(*) AS encounters, count(*) FILTER (WHERE e.telehealth_flag) AS telehealth,
       round(100.0 * count(*) FILTER (WHERE e.telehealth_flag) / NULLIF(count(*), 0), 1) AS telehealth_pct
FROM synthetic.encounter e JOIN site ON site.clinic_site_id = e.clinic_site_id"""),
    q("HAR-P1", P, "public", "How common are high blood pressure and diabetes in Humboldt County against the other five counties?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, p.measureid, p.data_value AS crude_prevalence_pct, p.year
FROM six JOIN public_data.cdc_places p ON p.locationid = six.fips
WHERE p.measureid IN ('BPHIGH', 'DIABETES') AND p.data_value_type = 'Crude prevalence'
ORDER BY p.measureid, p.data_value DESC"""),
    q("HAR-P2", P, "public", "How do the hospitals in our six counties do on unplanned visits and readmissions?", f"""
SELECT facility_name, county_parish AS county, measure_id, measure_name, compared_to_national, score, end_date
FROM public_data.cms_unplanned_visits
WHERE state = 'NV' AND county_parish IN {SIX_UP} AND score NOT IN ('Not Available', '')
ORDER BY county_parish, facility_name, measure_id"""),
    q("HAR-P3", P, "public", "How do Nevada and US health centers score on the UDS clinical quality measures?", """
SELECT measure, geography, year, value
FROM public_data.uds_state_national_cqm
WHERE geo_abbr IN ('NV', 'US') AND year = (SELECT max(year) FROM public_data.uds_state_national_cqm)
ORDER BY measure, geography"""),
    q("HAR-P4", P, "public", "Which Nevada health centers report hypertension and diabetes control in UDS 2025?", """
SELECT health_center_name, city, urban_rural_flag, htn_controlled_pct_derived AS htn_controlled_pct,
       diabetes_glycemic_gt9_pct_derived AS hba1c_gt9_pct, colorectal_cancer_screening_pct
FROM public_data.uds_health_center_cqm WHERE state = 'NV' ORDER BY htn_controlled_pct_derived DESC NULLS LAST"""),
    q("HAR-P5", P, "public", "Is Humboldt County a primary care shortage area, and how vulnerable is it?", """
SELECT s.county, s.rpl_themes AS svi_overall, h.hpsa_name, h.designation_type, h.hpsa_component_type_description,
       h.hpsa_score, h.hpsa_status
FROM public_data.svi_county s
LEFT JOIN public_data.hpsa_primary_care h
  ON h.common_county_name = s.county || ', NV' AND h.hpsa_status = 'Designated'
WHERE s.fips = 32013 ORDER BY h.hpsa_score DESC NULLS LAST"""),
]

# ── Marcus Bell (State RHTP program manager) ───────────────────────────────────────────────────────
P = "rain_bell"
NEW.append(section("BELL - Marcus Bell (State RHTP Program Manager): grantees, RHTP report cells, suppression, sites;\n-- public county access, broadband (ACS), facilities, rural status, drive times"))
NEW += [
    q("BEL-S1", P, "synthetic", "How many people served and services delivered does each grantee report?", """
SELECT g.network_name, g.program_initiative, count(r.rhtp_report_id) AS report_rows,
       sum(r.people_served) AS people_served, sum(r.services_delivered) AS services_delivered
FROM synthetic.grantee g LEFT JOIN synthetic.rhtp_report r ON r.grantee_id = g.grantee_id
GROUP BY g.network_name, g.program_initiative ORDER BY people_served DESC NULLS LAST"""),
    q("BEL-S2", P, "synthetic", "Which RHTP report cells must be suppressed because fewer than 11 people were served?", """
SELECT r.rhtp_report_id, g.network_name, r.county_fips, r.reporting_period, r.people_served,
       t.threshold::int AS suppress_under, (r.people_served < t.threshold) AS must_suppress, r.suppressed_flag
FROM synthetic.rhtp_report r JOIN synthetic.grantee g ON g.grantee_id = r.grantee_id
CROSS JOIN (SELECT coalesce((SELECT value FROM synthetic.assumption WHERE assumption_code = 'suppress_under'), 11) AS threshold) t
ORDER BY (r.people_served < t.threshold OR r.suppressed_flag) DESC, r.people_served"""),
    q("BEL-S3", P, "synthetic", "How many clinic sites does each grantee network run, and how many are telehealth-capable?", """
SELECT g.network_name, count(cs.clinic_site_id) AS sites, count(*) FILTER (WHERE cs.telehealth_capable) AS telehealth_capable
FROM synthetic.grantee g LEFT JOIN synthetic.clinic_site cs ON cs.grantee_id = g.grantee_id
GROUP BY g.network_name ORDER BY sites DESC"""),
    q("BEL-S4", P, "synthetic", "What awards and initiatives do the grantees hold?", """
SELECT network_name, program_initiative, site_count, award_amount, start_date
FROM synthetic.grantee ORDER BY award_amount DESC NULLS LAST"""),
    q("BEL-S5", P, "synthetic", "Which outcome measures do grantees report, with the average value?", """
SELECT outcome_measure, count(*) AS report_rows, round(avg(outcome_value)::numeric, 2) AS avg_value,
       count(*) FILTER (WHERE suppressed_flag) AS suppressed_rows
FROM synthetic.rhtp_report GROUP BY outcome_measure ORDER BY report_rows DESC"""),
    q("BEL-P1", P, "public", "Which public datasets are loaded, and how many rows does each hold?", """
SELECT t.table_name AS public_table,
       (xpath('/row/cnt/text()', query_to_xml(format('SELECT count(*) AS cnt FROM public_data.%I', t.table_name), false, true, '')))[1]::text::int AS row_count
FROM information_schema.tables t WHERE t.table_schema = 'public_data' ORDER BY t.table_name"""),
    q("BEL-P2", P, "public", "What share of households have broadband in each of our six counties?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, a.households_internet_universe AS households, a.households_with_broadband_any_type AS with_broadband,
       a.pct_households_broadband, a.households_no_internet_access AS no_internet, a.acs_release
FROM six JOIN public_data.acs_county a ON a.county_fips = six.fips ORDER BY a.pct_households_broadband"""),
    q("BEL-P3", P, "public", "How many health center sites, rural health clinics and critical access hospitals are in each of our six counties?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county,
       (SELECT count(*) FROM public_data.health_center_sites h
         WHERE h.state_and_county_federal_information_processing_standard_code::bigint = six.fips) AS hrsa_health_center_sites,
       count(*) FILTER (WHERE f.hrsa_layer_name = 'Rural Health Clinics') AS rural_health_clinics,
       count(*) FILTER (WHERE f.hrsa_layer_name = 'Critical Access Hospitals') AS critical_access_hospitals,
       count(*) FILTER (WHERE f.hrsa_layer_name = 'Federally Qualified Health Centers') AS fqhc_pos_records
FROM six LEFT JOIN public_data.cms_pos_facilities f ON f.county_fips_derived = six.fips
GROUP BY six.fips, six.county ORDER BY six.county"""),
    q("BEL-P4", P, "public", "How do our six counties compare on FORHP rural status, RUCC code and social vulnerability?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, f.rural_status_desc AS forhp_rural_status,
       (SELECT r.value FROM public_data.rucc_county r WHERE r.fips = six.fips AND r.attribute = 'RUCC_2023') AS rucc_2023,
       s.rpl_themes AS svi_overall
FROM six
LEFT JOIN public_data.forhp_county_status f ON f.state_county_fips_cd = six.fips
LEFT JOIN public_data.svi_county s ON s.fips = six.fips ORDER BY svi_overall DESC NULLS LAST"""),
    q("BEL-P5", P, "public", "How long is the drive to the nearest health center from each Nevada county's ZIP codes?", """
SELECT z.namelsad_county_20 AS county, count(DISTINCT n.zcta) AS zip_codes,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY n.drive_minutes)::numeric, 1) AS median_minutes,
       round(max(n.drive_minutes)::numeric, 1) AS max_minutes
FROM public_data.osrm_nearest_site n
JOIN public_data.zcta_county z ON z.geoid_zcta5_20 = n.zcta
WHERE n.state = 'NV' AND z.geoid_county_20 BETWEEN 32000 AND 32999
GROUP BY z.namelsad_county_20 ORDER BY median_minutes DESC"""),
]

# ── Denise Holloway (field CHW) ─────────────────────────────────────────────────────────────────────
P = "rain_holloway"
NEW.append(section("HOLLOWAY - Denise Holloway (Community Health Worker, field): call list, non-responders, consent,\n-- social needs; public no-vehicle, no-internet, long drives, rural tracts, language"))
NEW += [
    q("HOL-S1", P, "synthetic", "Which open outreach tasks should I call first?", """
SELECT ot.task_id, ot.patient_id, ot.task_type, ot.priority_score, ot.reason_summary, ot.created_at
FROM synthetic.outreach_task ot WHERE ot.closed_at IS NULL ORDER BY ot.priority_score DESC NULLS LAST LIMIT 25"""),
    q("HOL-S2", P, "synthetic", "Which reminders have no reply yet, and how were they sent?", """
SELECT rm.patient_id, rm.channel, rm.language, rm.offset_hours, rm.delivery_status, rm.sent_at
FROM synthetic.reminder_message rm WHERE rm.reply IS NULL OR rm.reply = '' ORDER BY rm.sent_at DESC NULLS LAST LIMIT 25"""),
    q("HOL-S3", P, "synthetic", "Which patients have no SMS consent on file?", """
SELECT cp.patient_id, cp.channel, cp.language, cp.consent_flag, cp.updated_at
FROM synthetic.contact_preference cp WHERE NOT cp.consent_flag ORDER BY cp.updated_at DESC NULLS LAST"""),
    q("HOL-S4", P, "synthetic", "Which social-need domains did my patients screen positive on?", """
SELECT domain, count(*) AS screenings, count(DISTINCT patient_id) AS patients
FROM synthetic.sdoh_screening GROUP BY domain ORDER BY screenings DESC"""),
    q("HOL-S5", P, "synthetic", "How many outreach tasks closed against how many are still open?", """
SELECT CASE WHEN closed_at IS NULL THEN 'Open' ELSE 'Closed' END AS state, task_type, count(*) AS tasks
FROM synthetic.outreach_task GROUP BY 1, 2 ORDER BY 1, tasks DESC"""),
    q("HOL-P1", P, "public", "How many households have no vehicle or no internet in our six counties?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, a.households_no_vehicle, a.pct_households_no_vehicle, a.households_no_internet_access,
       a.total_population
FROM six JOIN public_data.acs_county a ON a.county_fips = six.fips ORDER BY a.pct_households_no_vehicle DESC"""),
    q("HOL-P2", P, "public", "Which Nevada ZIP codes are more than an hour from the nearest health center?", """
SELECT n.zcta, z.namelsad_county_20 AS county, n.site_name AS nearest_site, n.drive_minutes, n.drive_miles
FROM public_data.osrm_nearest_site n
LEFT JOIN public_data.zcta_county z ON z.geoid_zcta5_20 = n.zcta AND z.geoid_county_20 BETWEEN 32000 AND 32999
WHERE n.state = 'NV' AND n.drive_minutes > 60 ORDER BY n.drive_minutes DESC"""),
    q("HOL-P3", P, "public", "How many census tracts in our six counties count as rural for FORHP?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, count(t.census_tract_cd) AS forhp_rural_tracts, max(t.report_yr) AS report_year
FROM six LEFT JOIN public_data.forhp_rural_tracts t ON t.cmn_state_county_fips_cd::bigint = six.fips
GROUP BY six.county ORDER BY forhp_rural_tracts DESC"""),
    q("HOL-P4", P, "public", "How many households in our six counties speak Spanish with limited English?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, a.lep_households_spanish, a.lep_households_total, a.pct_lep_households, a.pop_5plus_speak_spanish
FROM six JOIN public_data.acs_county a ON a.county_fips = six.fips ORDER BY a.lep_households_spanish DESC"""),
    q("HOL-P5", P, "public", "What share of adults lack reliable transportation or face food insecurity in our six counties?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, p.measureid, p.measure, p.data_value AS crude_prevalence_pct, p.year
FROM six JOIN public_data.cdc_places p ON p.locationid = six.fips
WHERE p.measureid IN ('LACKTRPT', 'FOODINSECU') AND p.data_value_type = 'Crude prevalence'
ORDER BY p.measureid, p.data_value DESC"""),
]

# ── Kayla Brooks (clinic scheduler / front desk) ───────────────────────────────────────────────────
P = "rain_brooks"
NEW.append(section("BROOKS - Kayla Brooks (Clinic Scheduler / Front Desk): no-show risk and history, eligibility, the inbox,\n-- slots; public drive times, health center sites, rural clinics, hospitals, shortage areas"))
NEW += [
    q("BRK-S1", P, "synthetic", "Which booked appointments carry the highest no-show risk?", """
SELECT a.appointment_id, a.patient_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id
ORDER BY a.no_show_risk DESC NULLS LAST LIMIT 25"""),
    q("BRK-S2", P, "synthetic", "What is the no-show history by visit type?", """
SELECT visit_type, count(*) AS patients, sum(scheduled_count) AS scheduled, sum(no_show_count) AS no_shows,
       round(100.0 * sum(no_show_count) / NULLIF(sum(scheduled_count), 0), 1) AS no_show_pct
FROM synthetic.no_show_rate GROUP BY visit_type ORDER BY no_show_pct DESC NULLS LAST"""),
    q("BRK-S3", P, "synthetic", "What did the eligibility checks return for upcoming appointments?", """
SELECT ec.coverage_status, ec.payer, count(*) AS checks, max(ec.checked_at) AS last_checked
FROM synthetic.eligibility_check ec GROUP BY ec.coverage_status, ec.payer ORDER BY checks DESC"""),
    q("BRK-S4", P, "synthetic", "What is in the front-desk inbox, by item type and status?", """
SELECT ii.item_type, ii.status, count(*) AS items, max(ii.received_at) AS latest
FROM synthetic.inbox_item ii GROUP BY ii.item_type, ii.status ORDER BY items DESC"""),
    q("BRK-S5", P, "synthetic", "How many slots are open, telehealth against in person?", """
SELECT CASE WHEN telehealth_flag THEN 'Telehealth' ELSE 'In person' END AS mode, status, count(*) AS slots
FROM synthetic.slot GROUP BY 1, 2 ORDER BY 1, slots DESC"""),
    q("BRK-P1", P, "public", "How long is the drive from Battle Mountain ZIP 89820 to the nearest health center sites?", """
SELECT rank_by_drive_time AS rank, site_name, drive_minutes, drive_miles, straight_line_miles, osm_extract_date
FROM public_data.osrm_drive_times WHERE zcta = 89820 ORDER BY rank_by_drive_time"""),
    q("BRK-P2", P, "public", "Which HRSA health center sites operate in our six counties, and how many hours a week?", f"""
WITH six(fips, county) AS ({SIX})
SELECT six.county, h.site_name, h.site_city, h.operating_hours_per_week, h.health_center_location_type_description
FROM six JOIN public_data.health_center_sites h
  ON h.state_and_county_federal_information_processing_standard_code::bigint = six.fips
ORDER BY six.county, h.site_name"""),
    q("BRK-P3", P, "public", "Which rural health clinics in Nevada are certified by CMS?", """
SELECT facility_nm, cms_provider_city, county_name_derived AS county, cms_provider_num, cms_provider_cat_sub_typ_desc
FROM public_data.cms_pos_facilities
WHERE hrsa_layer_name = 'Rural Health Clinics' AND cms_provider_state_abbr = 'NV' ORDER BY county, facility_nm"""),
    q("BRK-P4", P, "public", "Which hospitals in our six counties have an emergency department?", f"""
SELECT facility_name, city_town, county_parish AS county, hospital_type, emergency_services, hospital_overall_rating
FROM public_data.cms_hospitals WHERE state = 'NV' AND county_parish IN {SIX_UP} ORDER BY county_parish, facility_name"""),
    q("BRK-P5", P, "public", "Which primary care shortage areas cover Lander County?", """
SELECT hpsa_name, designation_type, hpsa_component_type_description, hpsa_score, hpsa_status
FROM public_data.hpsa_primary_care
WHERE common_county_name = 'Lander County, NV' AND hpsa_status = 'Designated' ORDER BY hpsa_score DESC NULLS LAST"""),
]

# ── Dr. Samuel Okafor (rural provider) ──────────────────────────────────────────────────────────────
P = "rain_okafor"
NEW.append(section("OKAFOR - Dr. Samuel Okafor (Rural Provider): pre-visit summaries, adherence, home readings, coding\n-- recapture, standing orders; public eCQM specs, UDS trends, prevalence, providers"))
NEW += [
    q("OKA-S1", P, "synthetic", "Which appointments have a pre-visit summary, with risk tier and open gaps?", """
SELECT ps.appointment_id, ps.patient_id, ps.risk_tier, ps.top_reasons, ps.open_gap_count, ps.adherence_gap_flag,
       ps.latest_bp, ps.coding_recapture_flag, a.visit_mode
FROM synthetic.previsit_summary ps JOIN synthetic.appointment a ON a.appointment_id = ps.appointment_id
ORDER BY ps.open_gap_count DESC NULLS LAST LIMIT 25"""),
    q("OKA-S2", P, "synthetic", "Which patients take a medication with adherence under 80 percent?", """
SELECT patient_id, rxnorm_code, adherence_ratio, start_date, end_date
FROM synthetic.medication WHERE adherence_ratio < 0.8 ORDER BY adherence_ratio LIMIT 25"""),
    q("OKA-S3", P, "synthetic", "What is each patient's latest home blood pressure reading?", """
SELECT DISTINCT ON (patient_id) patient_id, value_systolic, value_diastolic, reading_time, device_type, counts_for_measure
FROM synthetic.remote_bp_reading ORDER BY patient_id, reading_time DESC NULLS LAST"""),
    q("OKA-S4", P, "synthetic", "Which chronic conditions are not yet recaptured this year?", """
SELECT patient_id, icd10_code, documented_year, recaptured_year, status
FROM synthetic.condition WHERE recaptured_year IS NULL OR recaptured_year < documented_year
ORDER BY documented_year DESC NULLS LAST LIMIT 25"""),
    q("OKA-S5", P, "synthetic", "Which standing orders are waiting for provider review?", """
SELECT so.standing_order_id, c.campaign_name, so.order_type, so.description, so.status, so.reviewed_at
FROM synthetic.standing_order so JOIN synthetic.campaign c ON c.campaign_id = so.campaign_id
ORDER BY so.reviewed_at NULLS FIRST LIMIT 25"""),
    q("OKA-P1", P, "public", "What does each quality gate measure count, per the CMS eCQM specification?", """
SELECT measure_family, ecqm_version_id, performance_period, title, improvement_notation, telehealth_eligible, url
FROM public_data.ecqm_measures
WHERE performance_period = (SELECT max(performance_period) FROM public_data.ecqm_measures) ORDER BY measure_family"""),
    q("OKA-P2", P, "public", "What are the numerator and denominator of the blood pressure control measure CMS165?", """
SELECT ecqm_version_id, performance_period, initial_population, denominator, denominator_exclusions, numerator
FROM public_data.ecqm_measures WHERE measure_family = 'CMS165' ORDER BY performance_period DESC"""),
    q("OKA-P3", P, "public", "How have Nevada health centers trended on hypertension control and HbA1c poor control?", """
SELECT measure, year, value FROM public_data.uds_state_national_cqm
WHERE geo_abbr = 'NV' AND (measure ILIKE '%blood pressure%' OR measure ILIKE '%A1c%') ORDER BY measure, year"""),
    q("OKA-P4", P, "public", "How many registered providers practice in the towns of our six counties?", """
SELECT city, count(*) AS providers, count(*) FILTER (WHERE enumeration_type = 'NPI-1') AS individuals
FROM public_data.providers
WHERE state = 'NV' AND upper(city) IN ('ELKO', 'WELLS', 'WINNEMUCCA', 'BATTLE MOUNTAIN', 'LOVELOCK', 'ELY', 'FALLON')
GROUP BY city ORDER BY providers DESC"""),
    q("OKA-P5", P, "public", "How common are high blood pressure and diabetes in Lander and Pershing counties?", """
SELECT locationname AS county, measureid, data_value AS crude_prevalence_pct, low_confidence_limit, high_confidence_limit, year
FROM public_data.cdc_places
WHERE locationid IN (32015, 32027) AND measureid IN ('BPHIGH', 'DIABETES') AND data_value_type = 'Crude prevalence'
ORDER BY locationname, measureid"""),
]

# ── Linda Garcia (patient) ──────────────────────────────────────────────────────────────────────────
P = "patient_linda_garcia"
NEW.append(section(f"LINDA GARCIA - patient, Battle Mountain (Lander County), synthetic anchor {LINDA}: her appointments,\n-- reminders, readings, gaps, consent; public drive time, broadband, blood pressure, shortage area, language"))
NEW += [
    q("GAR-S1", P, "synthetic", "What appointments do I have?", f"""
SELECT a.appointment_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start, s.telehealth_flag
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id WHERE a.patient_id = '{LINDA}'"""),
    q("GAR-S2", P, "synthetic", "Which reminders were sent to me, and what did I reply?", f"""
SELECT channel, language, offset_hours, delivery_status, reply, sent_at
FROM synthetic.reminder_message WHERE patient_id = '{LINDA}' ORDER BY sent_at"""),
    q("GAR-S3", P, "synthetic", "What are my home blood pressure readings?", f"""
SELECT value_systolic, value_diastolic, reading_time, device_type, counts_for_measure
FROM synthetic.remote_bp_reading WHERE patient_id = '{LINDA}' ORDER BY reading_time DESC"""),
    q("GAR-S4", P, "synthetic", "Which care gaps are open for me?", f"""
SELECT measure_code, status, opened_at, closed_at, closed_by FROM synthetic.care_gap WHERE patient_id = '{LINDA}'"""),
    q("GAR-S5", P, "synthetic", "What are my contact preferences and consent?", f"""
SELECT channel, language, consent_flag, quiet_hours_start, quiet_hours_end, updated_at
FROM synthetic.contact_preference WHERE patient_id = '{LINDA}'"""),
    q("GAR-P1", P, "public", "How far do I drive from Battle Mountain to the nearest health center?", """
SELECT site_name, site_location_type, drive_minutes, drive_miles, straight_line_miles, origin_snap_meters, osm_extract_date
FROM public_data.osrm_nearest_site WHERE zcta = 89820"""),
    q("GAR-P2", P, "public", "What share of households in my county, Lander, have broadband?", """
SELECT county_name, households_internet_universe AS households, households_with_broadband_any_type, pct_households_broadband, acs_release
FROM public_data.acs_county WHERE county_fips = 32015"""),
    q("GAR-P3", P, "public", "What share of adults in my county, Lander, have high blood pressure?", """
SELECT locationname AS county, measure, data_value AS crude_prevalence_pct, low_confidence_limit, high_confidence_limit, year
FROM public_data.cdc_places WHERE locationid = 32015 AND measureid IN ('BPHIGH', 'BPMED') AND data_value_type = 'Crude prevalence'"""),
    q("GAR-P4", P, "public", "Is my county, Lander, a primary care shortage area?", """
SELECT hpsa_name, designation_type, hpsa_component_type_description, hpsa_score
FROM public_data.hpsa_primary_care WHERE common_county_name = 'Lander County, NV' AND hpsa_status = 'Designated'
ORDER BY hpsa_score DESC NULLS LAST"""),
    q("GAR-P5", P, "public", "How many households in my county, Lander, speak Spanish with limited English?", """
SELECT county_name, lep_households_spanish, lep_households_total, pct_lep_households, pop_5plus_speak_spanish
FROM public_data.acs_county WHERE county_fips = 32015"""),
]

# ── Rosa Martinez (patient) ─────────────────────────────────────────────────────────────────────────
P = "patient_rosa_martinez"
NEW.append(section(f"ROSA MARTINEZ - patient, Fallon (Churchill County), synthetic anchor {ROSA}: appointments, no-show\n-- history, reminders, coverage, social needs; public drive time, vehicles, rural status, diabetes, eCQM"))
NEW += [
    q("ROS-S1", P, "synthetic", "What appointments do I have, and how likely am I to miss one?", f"""
SELECT a.appointment_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start, s.telehealth_flag
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id WHERE a.patient_id = '{ROSA}'"""),
    q("ROS-S2", P, "synthetic", "What is my no-show history by visit type?", f"""
SELECT visit_type, window_months, scheduled_count, no_show_count, rate, computed_at
FROM synthetic.no_show_rate WHERE patient_id = '{ROSA}'"""),
    q("ROS-S3", P, "synthetic", "Which reminders went to me, and by which channel?", f"""
SELECT channel, language, offset_hours, delivery_status, reply, sent_at
FROM synthetic.reminder_message WHERE patient_id = '{ROSA}' ORDER BY sent_at"""),
    q("ROS-S4", P, "synthetic", "Is my coverage active, and what did my eligibility check return?", f"""
SELECT am.payer, am.contract_year, am.aid_category, am.attribution_start, am.attribution_end,
       (SELECT max(last_refreshed)::date FROM synthetic.data_source) BETWEEN am.attribution_start AND am.attribution_end AS attributed_today,
       coalesce(ec.coverage_status, 'no 270/271 check on file') AS latest_eligibility_check, ec.checked_at
FROM synthetic.attributed_member am
LEFT JOIN LATERAL (SELECT e.coverage_status, e.checked_at FROM synthetic.eligibility_check e
                   WHERE e.patient_id = am.patient_id ORDER BY e.checked_at DESC NULLS LAST LIMIT 1) ec ON true
WHERE am.patient_id = '{ROSA}'"""),
    q("ROS-S5", P, "synthetic", "Which channels have I consented to, and is my phone shared?", f"""
SELECT channel, language, consent_flag, best_time, phone_note, quiet_hours_start, quiet_hours_end, updated_at
FROM synthetic.contact_preference WHERE patient_id = '{ROSA}' ORDER BY updated_at DESC"""),
    q("ROS-P1", P, "public", "How far do I drive from Fallon to the nearest health center sites?", """
SELECT rank_by_drive_time AS rank, site_name, drive_minutes, drive_miles, osm_extract_date
FROM public_data.osrm_drive_times WHERE zcta = 89406 ORDER BY rank_by_drive_time"""),
    q("ROS-P2", P, "public", "What share of households in my county, Churchill, have no vehicle?", """
SELECT county_name, households_vehicle_universe AS households, households_no_vehicle, pct_households_no_vehicle, acs_release
FROM public_data.acs_county WHERE county_fips = 32001"""),
    q("ROS-P3", P, "public", "Is my county, Churchill, rural for FORHP, and what is its RUCC code?", """
SELECT f.county_nm, f.rural_status_desc,
       (SELECT r.value FROM public_data.rucc_county r WHERE r.fips = 32001 AND r.attribute = 'RUCC_2023') AS rucc_2023,
       (SELECT r.value FROM public_data.rucc_county r WHERE r.fips = 32001 AND r.attribute = 'Description') AS rucc_description
FROM public_data.forhp_county_status f WHERE f.state_county_fips_cd = 32001"""),
    q("ROS-P4", P, "public", "What share of adults in my county, Churchill, have diagnosed diabetes?", """
SELECT locationname AS county, measure, data_value AS crude_prevalence_pct, low_confidence_limit, high_confidence_limit, year
FROM public_data.cdc_places WHERE locationid = 32001 AND measureid = 'DIABETES' AND data_value_type = 'Crude prevalence'"""),
    q("ROS-P5", P, "public", "Can my diabetes follow-up count by telehealth for the HbA1c measure CMS122?", """
SELECT ecqm_version_id, performance_period, title, telehealth_eligible, improvement_notation, url
FROM public_data.ecqm_measures WHERE measure_family = 'CMS122' ORDER BY performance_period DESC"""),
]

# ── Hannah Lee (payer / Medicaid MCO analyst, phase 2) ─────────────────────────────────────────────
# Scope: the plan's attributed members, aggregated and de-identified (no member ids or names in any result).
P = "payer_hannah_lee"
SIX_FIPS = "(32001, 32007, 32013, 32015, 32027, 32033)"
NEW.append(section(f"HANNAH LEE - Payer / Medicaid MCO Analyst ({PLAN}, phase 2): plan members by network, cost against\n"
                   "-- expected, avoidable ED against the benchmark, the quality gate, low-value spend; public County Health\n"
                   "-- Rankings, CDC PLACES and CMS hospital measures for the counties where the plan's members live"))
NEW += [
    q("HAN-S1", P, "synthetic", f"How many {PLAN} members does each network carry, by Medicaid aid category?", f"""
{PLAN_CTE}
SELECT g.network_name, am.aid_category, count(*) AS members,
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY g.network_name), 1) AS pct_of_network
FROM synthetic.attributed_member am
JOIN synthetic.patient p ON p.patient_id = am.patient_id
JOIN plan ON plan.network_id = p.network_id AND plan.contract_year = am.contract_year
JOIN synthetic.grantee g ON g.grantee_id = p.network_id
WHERE am.payer = '{PLAN}'
GROUP BY g.network_name, am.aid_category ORDER BY g.network_name, members DESC"""),
    q("HAN-S2", P, "synthetic", "What does the plan pay per member per month at each network against the expected PMPM, and is each claims feed complete?", f"""
{PLAN_CTE},
types AS (SELECT array_agg(DISTINCT claim_type ORDER BY claim_type) AS all_types FROM synthetic.claim),
cl AS (
  SELECT p.network_id, sum(c.allowed_amount) AS allowed, array_agg(DISTINCT c.claim_type ORDER BY c.claim_type) AS claim_types
  FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
  JOIN plan ON plan.network_id = p.network_id CROSS JOIN thru
  WHERE c.service_date BETWEEN plan.contract_start AND thru.period_end
  GROUP BY p.network_id)
SELECT g.network_name, mem.members, thru.period_end AS claims_through, {MONTHS}::int AS months,
       round(cl.allowed / (mem.members * {MONTHS}), 2) AS actual_pmpm, plan.expected_pmpm,
       round(100 * (cl.allowed / (mem.members * {MONTHS}) - plan.expected_pmpm) / plan.expected_pmpm, 1) AS pct_vs_expected,
       array_to_string(cl.claim_types, ', ') AS claim_types_received,
       CASE WHEN cl.claim_types @> types.all_types THEN 'Complete'
            ELSE 'Partial: no ' || array_to_string(ARRAY(SELECT unnest(types.all_types) EXCEPT SELECT unnest(cl.claim_types)), ', ') || ' claims'
       END AS claims_feed
FROM plan JOIN mem ON mem.network_id = plan.network_id JOIN cl ON cl.network_id = plan.network_id
JOIN synthetic.grantee g ON g.grantee_id = plan.network_id CROSS JOIN thru CROSS JOIN types
ORDER BY g.network_name"""),
    q("HAN-S3", P, "synthetic", "How many avoidable ED visits per 1,000 plan members does each network have, annualized, against the benchmark?", f"""
{PLAN_CTE},
ed AS (
  SELECT p.network_id, count(*) AS avoidable_ed_visits, sum(c.allowed_amount) AS allowed
  FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
  JOIN plan ON plan.network_id = p.network_id CROSS JOIN thru
  WHERE c.avoidable_ed_flag AND c.service_date BETWEEN plan.contract_start AND thru.period_end
  GROUP BY p.network_id),
bench AS (SELECT benchmark_value FROM synthetic.utilization_benchmark WHERE metric_code = 'avoidable_ed_per_1000'),
per AS (
  SELECT g.network_name, mem.members, ed.avoidable_ed_visits, {MONTHS} AS months, ed.allowed
  FROM plan JOIN mem ON mem.network_id = plan.network_id JOIN ed ON ed.network_id = plan.network_id
  JOIN synthetic.grantee g ON g.grantee_id = plan.network_id CROSS JOIN thru),
totals AS (
  SELECT network_name, members, avoidable_ed_visits, months, allowed, 1 AS sort FROM per
  UNION ALL
  SELECT 'All plan networks', sum(members), sum(avoidable_ed_visits), max(months), sum(allowed), 2 FROM per)
SELECT t.network_name, t.members::int AS members, t.avoidable_ed_visits::int AS avoidable_ed_visits_ytd,
       round(t.avoidable_ed_visits * 1000.0 / t.members * 12 / t.months)::int AS per_1000_annualized,
       round(bench.benchmark_value)::int AS benchmark_per_1000,
       greatest(0, round((t.avoidable_ed_visits * 1000.0 / t.members * 12 / t.months - bench.benchmark_value) / 1000 * t.members))::int
         AS visits_above_benchmark_per_year,
       round(t.allowed / t.avoidable_ed_visits)::int AS avg_allowed_per_visit
FROM totals t CROSS JOIN bench ORDER BY t.sort, t.network_name"""),
    q("HAN-S4", P, "synthetic", "Which quality gate measures does each plan network meet against target this year?", f"""
{PLAN_CTE},
res AS (
  SELECT p.network_id, r.measure_code,
         count(*) FILTER (WHERE r.denominator_flag) AS denominator, count(*) FILTER (WHERE r.numerator_flag) AS numerator
  FROM synthetic.quality_measure_result r JOIN synthetic.patient p ON p.patient_id = r.patient_id
  JOIN plan ON plan.network_id = p.network_id
  WHERE r.period_year = plan.contract_year
  GROUP BY p.network_id, r.measure_code)
SELECT g.network_name, qm.measure_code, qm.measure_name, res.denominator, res.numerator,
       round(100.0 * res.numerator / NULLIF(res.denominator, 0), 1) AS rate_pct, qm.target_rate,
       CASE WHEN qm.lower_is_better THEN 'lower' ELSE 'higher' END AS better_when,
       CASE WHEN res.denominator IS NULL THEN 'not reported'
            WHEN qm.lower_is_better AND 100.0 * res.numerator / NULLIF(res.denominator, 0) <= qm.target_rate THEN 'meets'
            WHEN NOT qm.lower_is_better AND 100.0 * res.numerator / NULLIF(res.denominator, 0) >= qm.target_rate THEN 'meets'
            ELSE 'below target' END AS status,
       plan.quality_gate_required AS gate_needs, plan.quality_gate_total AS gate_measures
FROM plan CROSS JOIN synthetic.quality_measure qm
JOIN synthetic.grantee g ON g.grantee_id = plan.network_id
LEFT JOIN res ON res.network_id = plan.network_id AND res.measure_code = qm.measure_code
WHERE qm.gate_flag
ORDER BY g.network_name, qm.measure_code"""),
    q("HAN-S5", P, "synthetic", "How much does the plan pay for low-value care at each network, by measure, over the last 12 months?", f"""
{PLAN_CTE},
small AS (SELECT coalesce((SELECT value FROM synthetic.assumption WHERE assumption_code = 'suppress_under'), 11) AS n),
lv AS (
  SELECT p.network_id, f.measure_id, count(*) AS services, sum(f.allowed_amount) AS allowed
  FROM synthetic.low_value_finding f
  JOIN synthetic.claim_line cl ON cl.claim_line_id = f.claim_line_id
  JOIN synthetic.claim c ON c.claim_id = cl.claim_id
  JOIN synthetic.patient p ON p.patient_id = c.patient_id
  JOIN plan ON plan.network_id = p.network_id CROSS JOIN thru
  WHERE f.classification <> 'necessary' AND f.service_date > thru.period_end - interval '12 months' AND f.service_date <= thru.period_end
  GROUP BY p.network_id, f.measure_id)
SELECT g.network_name, lv.measure_id, m.measure_name, m.basis,
       CASE WHEN lv.services < small.n THEN NULL ELSE lv.services END AS services,
       CASE WHEN lv.services < small.n THEN NULL ELSE round(lv.allowed) END AS allowed_dollars,
       lv.services < small.n AS suppressed_small_cell
FROM lv JOIN synthetic.low_value_measure m ON m.measure_id = lv.measure_id
JOIN synthetic.grantee g ON g.grantee_id = lv.network_id CROSS JOIN small
ORDER BY g.network_name, lv.allowed DESC"""),
    q("HAN-P1", P, "public", "Where the plan's members live, how many preventable hospital stays and uninsured residents does each county have against Nevada?", f"""
SELECT county, year, v005_rawvalue AS preventable_stays_per_100k_medicare, round((100 * v085_rawvalue)::numeric, 1) AS uninsured_pct,
       CASE WHEN fipscode = 32000 THEN 'State' ELSE 'County' END AS level
FROM public_data.county_health_rankings
WHERE fipscode BETWEEN 32000 AND 32999 AND (fipscode = 32000 OR fipscode IN {SIX_FIPS})
ORDER BY fipscode = 32000 DESC, v005_rawvalue DESC NULLS LAST"""),
    q("HAN-P2", P, "public", "How do the plan's counties compare with Nevada on primary care physicians, mental health providers and premature death?", f"""
SELECT county, year, round((100000 * v004_rawvalue)::numeric, 1) AS primary_care_physicians_per_100k,
       round((100000 * v062_rawvalue)::numeric, 1) AS mental_health_providers_per_100k,
       round(v001_rawvalue::numeric) AS premature_death_ypll_per_100k
FROM public_data.county_health_rankings
WHERE fipscode BETWEEN 32000 AND 32999 AND (fipscode = 32000 OR fipscode IN {SIX_FIPS})
ORDER BY fipscode = 32000 DESC, v004_rawvalue NULLS LAST"""),
    q("HAN-P3", P, "public", "How common are COPD, asthma and coronary heart disease, the drivers of avoidable ED visits, in the plan's counties?", f"""
SELECT locationname AS county, year,
       max(data_value) FILTER (WHERE measureid = 'COPD') AS copd_pct,
       max(data_value) FILTER (WHERE measureid = 'CASTHMA') AS asthma_pct,
       max(data_value) FILTER (WHERE measureid = 'CHD') AS coronary_heart_disease_pct
FROM public_data.cdc_places
WHERE locationid IN {SIX_FIPS} AND measureid IN ('COPD', 'CASTHMA', 'CHD') AND data_value_type = 'Crude prevalence'
GROUP BY locationname, year ORDER BY copd_pct DESC NULLS LAST"""),
    q("HAN-P4", P, "public", "How do hospitals in the plan's counties do on heart failure and COPD readmissions and return days?", f"""
SELECT facility_name, county_parish AS county, measure_id, measure_name, score, compared_to_national, end_date
FROM public_data.cms_unplanned_visits
WHERE state = 'NV' AND county_parish IN {SIX_UP}
  AND measure_id IN ('READM_30_HF', 'READM_30_COPD', 'EDAC_30_HF') AND score NOT IN ('Not Available', '')
ORDER BY measure_id, county_parish, facility_name"""),
    q("HAN-P5", P, "public", "How many adults in the plan's counties report fair or poor health or a disability?", f"""
SELECT locationname AS county, year,
       max(data_value) FILTER (WHERE measureid = 'GHLTH') AS fair_or_poor_health_pct,
       max(data_value) FILTER (WHERE measureid = 'DISABILITY') AS any_disability_pct,
       max(totalpopulation) AS population
FROM public_data.cdc_places
WHERE locationid IN {SIX_FIPS} AND measureid IN ('GHLTH', 'DISABILITY') AND data_value_type = 'Crude prevalence'
GROUP BY locationname, year ORDER BY fair_or_poor_health_pct DESC NULLS LAST"""),
]

OUT.write_text(HEADER + "\n" + v3_body.rstrip() + "\n" + "".join(NEW), encoding="utf-8", newline="\n")
text = OUT.read_text(encoding="utf-8")
print("wrote", OUT.relative_to(ROOT), "queries:", text.count("-- @id "))
