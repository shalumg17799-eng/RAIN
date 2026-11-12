-- =====================================================================================================
-- RAIN v0.4 - persona query pack for pgAdmin and the backend (database: rain_v4)
-- 7 personas x (5 synthetic + 5 public) = 70 queries. Each query is standalone: select it and press F5.
-- Served by GET /api/v4/queries/{id} and answerable in the chat by id or by question.
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
-- Patient anchor in the synthetic schema: Linda Garcia = M-40107.
-- =====================================================================================================

-- #####################################################################################################
-- CEO - Gregory Haskins, MBA (Chief Executive Officer): cost vs expected, quality gate, low-value care,
-- sites, board brief
-- #####################################################################################################

-- @id CEO-S1
-- @persona rain_ceo
-- @data synthetic
-- @question What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)?
SELECT count(DISTINCT am.patient_id)                                   AS attributed_members,
       count(c.claim_id)                                               AS claims,
       round(sum(c.allowed_amount)::numeric, 2)                        AS total_allowed,
       round((sum(c.allowed_amount) / NULLIF(count(DISTINCT am.patient_id), 0))::numeric, 2) AS allowed_per_member
FROM synthetic.attributed_member am
LEFT JOIN synthetic.claim c ON c.patient_id = am.patient_id;

-- @id CEO-S2
-- @persona rain_ceo
-- @data synthetic
-- @question How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members?
WITH members AS (SELECT count(DISTINCT patient_id) AS n FROM synthetic.attributed_member)
SELECT count(*) FILTER (WHERE c.ed_flag)                                          AS ed_claims,
       count(*) FILTER (WHERE c.avoidable_ed_flag)                                AS avoidable_ed_claims,
       count(*) FILTER (WHERE c.admission_flag)                                   AS admissions,
       round(1000.0 * count(*) FILTER (WHERE c.ed_flag) / m.n, 1)                 AS ed_per_1000,
       round(1000.0 * count(*) FILTER (WHERE c.avoidable_ed_flag) / m.n, 1)       AS avoidable_ed_per_1000
FROM synthetic.claim c CROSS JOIN members m
GROUP BY m.n;

-- @id CEO-S3
-- @persona rain_ceo
-- @data synthetic
-- @question Where is the low-value care? Top sites by low-value spend.
SELECT cs.clinic_site_id, cs.site_name,
       count(lf.finding_id)                       AS low_value_findings,
       round(sum(lf.allowed_amount)::numeric, 2)  AS low_value_allowed
FROM synthetic.low_value_finding lf
JOIN synthetic.clinic_site cs ON cs.clinic_site_id = lf.clinic_site_id
GROUP BY cs.clinic_site_id, cs.site_name
ORDER BY low_value_allowed DESC NULLS LAST
LIMIT 10;

-- @id CEO-S4
-- @persona rain_ceo
-- @data synthetic
-- @question How close are we to the quality gate? Rate vs target for every gate measure.
SELECT qm.measure_code, qm.measure_name, qm.target_rate, qm.lower_is_better,
       count(*) FILTER (WHERE r.denominator_flag)                         AS denominator,
       count(*) FILTER (WHERE r.denominator_flag AND r.numerator_flag)    AS numerator,
       round(count(*) FILTER (WHERE r.denominator_flag AND r.numerator_flag)::numeric
             / NULLIF(count(*) FILTER (WHERE r.denominator_flag), 0), 3)  AS rate
FROM synthetic.quality_measure qm
JOIN synthetic.quality_measure_result r ON r.measure_code = qm.measure_code
WHERE qm.gate_flag
GROUP BY qm.measure_code, qm.measure_name, qm.target_rate, qm.lower_is_better
ORDER BY denominator DESC, qm.measure_code
LIMIT 15;

-- @id CEO-S5
-- @persona rain_ceo
-- @data synthetic
-- @question Compare our sites on cost per member.
SELECT cs.clinic_site_id, cs.site_name, cs.telehealth_capable,
       count(DISTINCT c.patient_id)                                                   AS members_seen,
       round(sum(cl.allowed_amount)::numeric, 2)                                      AS allowed,
       round((sum(cl.allowed_amount) / NULLIF(count(DISTINCT c.patient_id), 0))::numeric, 2) AS allowed_per_member
FROM synthetic.claim_line cl
JOIN synthetic.claim c        ON c.claim_id = cl.claim_id
JOIN synthetic.clinic_site cs ON cs.clinic_site_id = cl.clinic_site_id
GROUP BY cs.clinic_site_id, cs.site_name, cs.telehealth_capable
ORDER BY allowed_per_member DESC NULLS LAST
LIMIT 10;

-- @id CEO-P1
-- @persona rain_ceo
-- @data public
-- @question Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability.
WITH network(fips) AS (VALUES (32007),(32013),(32015),(32027),(32033),(32001))
SELECT s.county, s.fips, s.e_totpop AS population, r.value AS rucc_2023,
       round(s.rpl_themes::numeric, 3) AS svi_percentile, s.ep_pov150 AS pct_below_150_poverty, s.ep_uninsur AS pct_uninsured
FROM network n
JOIN public_data.svi_county s  ON s.fips = n.fips
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
ORDER BY s.e_totpop DESC;

-- @id CEO-P2
-- @persona rain_ceo
-- @data public
-- @question What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)?
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'BPHIGH')   AS high_bp_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'DIABETES') AS diabetes_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'OBESITY')  AS obesity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'CSMOKING') AS smoking_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'COPD')     AS copd_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY high_bp_pct DESC;

-- @id CEO-P3
-- @persona rain_ceo
-- @data public
-- @question How do our counties compare with the Nevada county average on annual checkups and insurance gaps?
SELECT p.measureid, p.short_question_text,
       round(avg(p.data_value) FILTER (WHERE p.locationid IN (32007,32013,32015,32027,32033,32001))::numeric, 1) AS network_avg_pct,
       round(avg(p.data_value)::numeric, 1)                                                                      AS nv_county_avg_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.measureid IN ('CHECKUP', 'ACCESS2', 'BPMED', 'CHOLSCREEN', 'COLON_SCREEN')
GROUP BY p.measureid, p.short_question_text
ORDER BY p.measureid;

-- @id CEO-P4
-- @persona rain_ceo
-- @data public
-- @question Which of our counties have designated primary care shortage areas (HRSA HPSA), and how severe?
SELECT h.common_county_name,
       count(*)                                       AS designated_hpsas,
       max(h.hpsa_score)                              AS max_hpsa_score,
       sum(h.hpsa_designation_population)             AS designation_population,
       string_agg(DISTINCT h.designation_type, '; ')  AS designation_types
FROM public_data.hpsa_primary_care h
WHERE h.hpsa_status = 'Designated'
  AND h.common_county_name IN ('Elko County, NV','Humboldt County, NV','Lander County, NV',
                               'Pershing County, NV','White Pine County, NV','Churchill County, NV')
GROUP BY h.common_county_name
ORDER BY max_hpsa_score DESC;

-- @id CEO-P5
-- @persona rain_ceo
-- @data public
-- @question Where does each of our counties rank among Nevada's 17 counties for high blood pressure?
SELECT * FROM (
    SELECT p.locationname AS county, p.locationid AS fips, p.data_value AS high_bp_pct,
           rank() OVER (ORDER BY p.data_value DESC) AS rank_of_17
    FROM public_data.cdc_places p
    WHERE p.stateabbr = 'NV' AND p.measureid = 'BPHIGH' AND p.data_value_type = 'Crude prevalence'
) ranked
WHERE fips IN (32007, 32013, 32015, 32027, 32033, 32001)
ORDER BY rank_of_17;


-- #####################################################################################################
-- CMO - Dr. Naomi Castellanos (Chief Medical Officer, VBC Quality Lead): BP control, HbA1c, screening,
-- Winnemucca low-value imaging, coding recapture
-- #####################################################################################################

-- @id CMO-S1
-- @persona rain_cmo
-- @data synthetic
-- @question How close are we to each quality target? Performance gap per measure.
SELECT qm.measure_code, qm.measure_name, qm.gate_flag, qm.target_rate,
       round(avg(CASE WHEN r.numerator_flag THEN 1.0 ELSE 0.0 END) FILTER (WHERE r.denominator_flag), 3) AS rate,
       round(avg(CASE WHEN r.numerator_flag THEN 1.0 ELSE 0.0 END) FILTER (WHERE r.denominator_flag)
             - qm.target_rate::numeric, 3)                                                                AS gap_to_target,
       count(*) FILTER (WHERE r.denominator_flag)                                                         AS patients_in_denominator
FROM synthetic.quality_measure qm
JOIN synthetic.quality_measure_result r ON r.measure_code = qm.measure_code
GROUP BY qm.measure_code, qm.measure_name, qm.gate_flag, qm.target_rate
HAVING count(*) FILTER (WHERE r.denominator_flag) > 0
ORDER BY qm.gate_flag DESC, patients_in_denominator DESC
LIMIT 15;

-- @id CMO-S2
-- @persona rain_cmo
-- @data synthetic
-- @question Which care gaps are still open, by measure?
SELECT g.measure_code, qm.measure_name,
       count(*)                                              AS gaps,
       count(*) FILTER (WHERE g.closed_at IS NULL)           AS never_closed,
       count(*) FILTER (WHERE g.status = 'pending')          AS pending,
       min(g.opened_at::timestamp)::date                     AS oldest_opened
FROM synthetic.care_gap g
LEFT JOIN synthetic.quality_measure qm ON qm.measure_code = g.measure_code
GROUP BY g.measure_code, qm.measure_name
ORDER BY gaps DESC, never_closed DESC
LIMIT 15;

-- @id CMO-S3
-- @persona rain_cmo
-- @data synthetic
-- @question Which patients with an open care gap have home BP readings that count toward the measure?
SELECT p.patient_id, p.first_name, p.last_name,
       count(b.reading_id)                     AS readings_counting,
       max(b.reading_time::timestamp)          AS latest_reading,
       count(DISTINCT g.care_gap_id)           AS open_gaps
FROM synthetic.patient p
JOIN synthetic.remote_bp_reading b ON b.patient_id = p.patient_id AND b.counts_for_measure
JOIN synthetic.care_gap g          ON g.patient_id = p.patient_id AND g.closed_at IS NULL
GROUP BY p.patient_id, p.first_name, p.last_name
ORDER BY readings_counting DESC, latest_reading DESC NULLS LAST
LIMIT 20;

-- @id CMO-S4
-- @persona rain_cmo
-- @data synthetic
-- @question Which providers order the most low-value services (the Winnemucca imaging question), and are they locums?
SELECT pr.provider_id, pr.first_name || ' ' || pr.last_name AS provider, pr.locum_flag, cs.site_name,
       count(lf.finding_id)                      AS low_value_findings,
       round(sum(lf.allowed_amount)::numeric, 2) AS low_value_allowed
FROM synthetic.low_value_finding lf
JOIN synthetic.provider pr         ON pr.provider_id = lf.ordering_provider_id
LEFT JOIN synthetic.clinic_site cs ON cs.clinic_site_id = lf.clinic_site_id
GROUP BY pr.provider_id, provider, pr.locum_flag, cs.site_name
ORDER BY low_value_findings DESC, low_value_allowed DESC NULLS LAST
LIMIT 10;

-- @id CMO-S5
-- @persona rain_cmo
-- @data synthetic
-- @question Which members need risk-coding recapture (documented condition not recaptured)?
SELECT c.patient_id, p.first_name, p.last_name,
       count(*)                                                                      AS conditions,
       count(*) FILTER (WHERE c.recaptured_year IS NULL OR c.recaptured_year < c.documented_year) AS not_recaptured
FROM synthetic.condition c
JOIN synthetic.patient p ON p.patient_id = c.patient_id
GROUP BY c.patient_id, p.first_name, p.last_name
HAVING count(*) FILTER (WHERE c.recaptured_year IS NULL OR c.recaptured_year < c.documented_year) > 0
ORDER BY not_recaptured DESC, conditions DESC
LIMIT 20;

-- @id CMO-P1
-- @persona rain_cmo
-- @data public
-- @question How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada?
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'BPHIGH') AS high_bp_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'BPMED')  AS on_bp_medication_pct,
       CASE WHEN p.locationid IN (32007,32013,32015,32027,32033,32001) THEN 'network' ELSE 'other NV' END AS grp
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence' AND p.measureid IN ('BPHIGH', 'BPMED')
GROUP BY p.locationname, p.locationid
ORDER BY grp, high_bp_pct DESC;

-- @id CMO-P2
-- @persona rain_cmo
-- @data public
-- @question Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context).
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'DIABETES') AS diabetes_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'OBESITY')  AS obesity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'LPA')      AS physical_inactivity_pct,
       p.locationid IN (32007,32013,32015,32027,32033,32001)     AS is_network_county
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
GROUP BY p.locationname, p.locationid
ORDER BY diabetes_pct DESC;

-- @id CMO-P3
-- @persona rain_cmo
-- @data public
-- @question Preventive screening rates in our counties (colorectal, mammography, cholesterol).
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'COLON_SCREEN') AS colorectal_screening_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'MAMMOUSE')     AS mammography_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'CHOLSCREEN')   AS cholesterol_screening_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY colorectal_screening_pct;

-- @id CMO-P4
-- @persona rain_cmo
-- @data public
-- @question Social needs that block BP control in our counties (food, housing, transport, utilities, loneliness).
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'FOODINSECU')  AS food_insecurity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'HOUSINSECU')  AS housing_insecurity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'LACKTRPT')    AS transport_barrier_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'SHUTUTILITY') AS utility_threat_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'LONELINESS')  AS loneliness_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY food_insecurity_pct DESC;

-- @id CMO-P5
-- @persona rain_cmo
-- @data public
-- @question Mental health burden and designated mental health shortage areas in our counties.
WITH mh AS (
    SELECT common_county_name, count(*) AS designated_mh_hpsas, max(hpsa_score) AS max_mh_hpsa_score
    FROM public_data.hpsa_mental_health
    WHERE hpsa_status = 'Designated' AND primary_state_abbreviation = 'NV'
    GROUP BY common_county_name
)
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'MHLTH')      AS frequent_mental_distress_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'DEPRESSION') AS depression_pct,
       coalesce(max(mh.designated_mh_hpsas), 0)                    AS designated_mh_hpsas,
       max(mh.max_mh_hpsa_score)                                   AS max_mh_hpsa_score
FROM public_data.cdc_places p
LEFT JOIN mh ON mh.common_county_name = p.locationname || ' County, NV'
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY depression_pct DESC;


-- #####################################################################################################
-- CIO - Raj Malhotra (CIO, Data and AI Governance Lead): model subgroup check, model card, data freshness,
-- social needs coverage, patient matching, public data feeds
-- #####################################################################################################

-- @id CIO-S1
-- @persona rain_cio
-- @data synthetic
-- @question Show the model cards: release status, sign-off and how many subgroup checks each passed.
SELECT mc.model_version, mc.model_name, mc.release_status, mc.access_adjusted_flag,
       mc.signed_off_by, mc.cosigned_by,
       count(sc.check_id)                               AS subgroup_checks,
       count(sc.check_id) FILTER (WHERE sc.passed)      AS passed,
       count(sc.check_id) FILTER (WHERE NOT sc.passed)  AS failed
FROM synthetic.model_card mc
LEFT JOIN synthetic.subgroup_check sc ON sc.model_version = mc.model_version
GROUP BY mc.model_version, mc.model_name, mc.release_status, mc.access_adjusted_flag, mc.signed_off_by, mc.cosigned_by
HAVING count(sc.check_id) > 0
ORDER BY failed DESC, mc.model_version
LIMIT 15;

-- @id CIO-S2
-- @persona rain_cio
-- @data synthetic
-- @question Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold.
SELECT sc.model_version, sc.subgroup, sc.comparison_group, sc.metric,
       sc.gap_percent, sc.threshold_percent,
       round((sc.gap_percent - sc.threshold_percent)::numeric, 4) AS over_threshold_by,
       sc.passed, sc.checked_at::timestamp AS checked_at
FROM synthetic.subgroup_check sc
WHERE sc.gap_percent > sc.threshold_percent
ORDER BY over_threshold_by DESC NULLS LAST
LIMIT 20;

-- @id CIO-S3
-- @persona rain_cio
-- @data synthetic
-- @question How fresh is each data source? Latest record per feed and lag in days.
SELECT feed, latest, (now()::date - latest::date) AS days_since_latest, rows
FROM (
    SELECT 'Claims (paid)'          AS feed, max(paid_date::date)::timestamp     AS latest, count(*) AS rows FROM synthetic.claim
    UNION ALL SELECT 'EHR encounters',       max(end_time::timestamp),          count(*) FROM synthetic.encounter
    UNION ALL SELECT 'EHR observations',     max(observed_at::timestamp),       count(*) FROM synthetic.observation
    UNION ALL SELECT 'Remote BP devices',    max(reading_time::timestamp),      count(*) FROM synthetic.remote_bp_reading
    UNION ALL SELECT 'Eligibility (270/271)',max(checked_at::timestamp),        count(*) FROM synthetic.eligibility_check
    UNION ALL SELECT 'Reminder messages',    max(sent_at::timestamp),           count(*) FROM synthetic.reminder_message
    UNION ALL SELECT 'SDOH screenings',      max(screened_at::timestamp),       count(*) FROM synthetic.sdoh_screening
) f
ORDER BY days_since_latest DESC;

-- @id CIO-S4
-- @persona rain_cio
-- @data synthetic
-- @question Show records that failed patient matching (patient_id missing or not in the patient master).
SELECT src, records, null_patient_id, unmatched_patient_id, null_patient_id + unmatched_patient_id AS failed_matching
FROM (
SELECT src, count(*) AS records, count(*) FILTER (WHERE patient_id IS NULL) AS null_patient_id,
       count(*) FILTER (WHERE patient_id IS NOT NULL AND NOT EXISTS
                        (SELECT 1 FROM synthetic.patient p WHERE p.patient_id = x.patient_id)) AS unmatched_patient_id
FROM (
    SELECT 'claim' AS src, patient_id FROM synthetic.claim
    UNION ALL SELECT 'encounter',          patient_id FROM synthetic.encounter
    UNION ALL SELECT 'observation',        patient_id FROM synthetic.observation
    UNION ALL SELECT 'care_gap',           patient_id FROM synthetic.care_gap
    UNION ALL SELECT 'appointment',        patient_id FROM synthetic.appointment
    UNION ALL SELECT 'attributed_member',  patient_id FROM synthetic.attributed_member
    UNION ALL SELECT 'sdoh_screening',     patient_id FROM synthetic.sdoh_screening
) x
GROUP BY src
) m
ORDER BY failed_matching DESC, src;

-- @id CIO-S5
-- @persona rain_cio
-- @data synthetic
-- @question Social needs coverage: how many attributed members have at least one SDOH screening?
SELECT count(DISTINCT am.patient_id)                                           AS attributed_members,
       count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NOT NULL)   AS screened,
       count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NULL)       AS missing_screening,
       round(100.0 * count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NOT NULL)
             / NULLIF(count(DISTINCT am.patient_id), 0), 1)                     AS coverage_pct
FROM synthetic.attributed_member am
LEFT JOIN synthetic.sdoh_screening s ON s.patient_id = am.patient_id;

-- @id CIO-P1
-- @persona rain_cio
-- @data public
-- @question What public data feeds the county view? Row counts and state coverage per public table.
SELECT 'cdc_places' AS dataset, count(*) AS rows, count(DISTINCT stateabbr) AS states, string_agg(DISTINCT year::text, ',') AS vintage FROM public_data.cdc_places
UNION ALL SELECT 'svi_county',          count(*), count(DISTINCT st_abbr), '2022' FROM public_data.svi_county
UNION ALL SELECT 'rucc_county',         count(*), count(DISTINCT state), '2023'   FROM public_data.rucc_county
UNION ALL SELECT 'hpsa_primary_care',   count(*), count(DISTINCT primary_state_abbreviation), 'HRSA current' FROM public_data.hpsa_primary_care
UNION ALL SELECT 'hpsa_mental_health',  count(*), count(DISTINCT primary_state_abbreviation), 'HRSA current' FROM public_data.hpsa_mental_health
UNION ALL SELECT 'health_center_sites', count(*), count(DISTINCT site_state_abbreviation), 'HRSA current' FROM public_data.health_center_sites
UNION ALL SELECT 'providers (NPPES)',   count(*), count(DISTINCT state), 'NPPES' FROM public_data.providers
UNION ALL SELECT 'zcta_centroids',      count(*), NULL, '2023 Gazetteer' FROM public_data.zcta_centroids
ORDER BY rows DESC;

-- @id CIO-P2
-- @persona rain_cio
-- @data public
-- @question CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state.
SELECT stateabbr, data_value_type,
       count(DISTINCT measureid)                                         AS measures,
       count(DISTINCT locationid)                                        AS counties,
       count(*)                                                          AS cells,
       count(*) FILTER (WHERE data_value IS NULL)                        AS missing_values,
       count(*) FILTER (WHERE high_confidence_limit - low_confidence_limit > 10) AS ci_wider_than_10pts
FROM public_data.cdc_places
GROUP BY stateabbr, data_value_type
ORDER BY stateabbr, data_value_type;

-- @id CIO-P3
-- @persona rain_cio
-- @data public
-- @question Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS?
SELECT s.fips, s.county,
       (r.fips IS NOT NULL)                                   AS in_rucc,
       EXISTS (SELECT 1 FROM public_data.cdc_places p WHERE p.locationid = s.fips) AS in_cdc_places,
       EXISTS (SELECT 1 FROM public_data.hpsa_primary_care h
               WHERE h.common_county_name = s.county || ', NV')                  AS has_any_pc_hpsa
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY s.fips;

-- @id CIO-P4
-- @persona rain_cio
-- @data public
-- @question HRSA HPSA status mix and data volume by discipline (primary care vs mental health) in Nevada.
SELECT 'primary care' AS discipline, hpsa_status, count(*) AS hpsas, count(DISTINCT common_county_name) AS counties
FROM public_data.hpsa_primary_care WHERE primary_state_abbreviation = 'NV' GROUP BY hpsa_status
UNION ALL
SELECT 'mental health', hpsa_status, count(*), count(DISTINCT common_county_name)
FROM public_data.hpsa_mental_health WHERE primary_state_abbreviation = 'NV' GROUP BY hpsa_status
ORDER BY discipline, hpsas DESC;

-- @id CIO-P5
-- @persona rain_cio
-- @data public
-- @question NPPES provider data quality: completeness and duplicate NPIs by state and entity type.
SELECT state, enumeration_type,
       count(*)                                         AS providers,
       count(DISTINCT npi)                              AS distinct_npis,
       count(*) - count(DISTINCT npi)                   AS duplicate_rows,
       count(*) FILTER (WHERE taxonomy IS NULL OR taxonomy = '') AS missing_taxonomy,
       count(*) FILTER (WHERE zip IS NULL)              AS missing_zip
FROM public_data.providers
GROUP BY state, enumeration_type
ORDER BY state, enumeration_type;


-- #####################################################################################################
-- STATE - Dr. Lauren Pike (Program Lead, Rural Health Outcomes Accelerator): county view, primary care
-- visits since January, low-value care across networks, broadband vs telehealth, funding, CMS summary
-- #####################################################################################################

-- @id STATE-S1
-- @persona rain_state
-- @data synthetic
-- @question Primary care visits by month (is volume down since January?), with telehealth share.
SELECT date_trunc('month', e.start_time::timestamp)::date               AS month,
       count(*)                                                         AS encounters,
       count(*) FILTER (WHERE e.telehealth_flag)                        AS telehealth,
       round(100.0 * count(*) FILTER (WHERE e.telehealth_flag) / count(*), 1) AS telehealth_pct
FROM synthetic.encounter e
WHERE e.start_time::timestamp >= date '2026-01-01' - interval '12 months'
GROUP BY 1
ORDER BY 1;

-- @id STATE-S2
-- @persona rain_state
-- @data synthetic
-- @question Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth.
SELECT cs.telehealth_capable,
       count(DISTINCT cs.clinic_site_id)                                          AS sites,
       count(e.encounter_id)                                                      AS encounters,
       round(100.0 * count(e.encounter_id) FILTER (WHERE e.telehealth_flag)
             / NULLIF(count(e.encounter_id), 0), 1)                               AS telehealth_pct
FROM synthetic.clinic_site cs
LEFT JOIN synthetic.encounter e ON e.clinic_site_id = cs.clinic_site_id
GROUP BY cs.telehealth_capable
ORDER BY cs.telehealth_capable DESC NULLS LAST;

-- @id STATE-S3
-- @persona rain_state
-- @data synthetic
-- @question Where does broadband block telehealth? Share of coverage records not served, by technology.
SELECT b.technology,
       count(*)                                                    AS coverage_records,
       count(*) FILTER (WHERE NOT b.served_flag)                   AS not_served,
       round(100.0 * count(*) FILTER (WHERE NOT b.served_flag) / count(*), 1) AS not_served_pct
FROM synthetic.broadband_coverage b
GROUP BY b.technology
ORDER BY not_served DESC, coverage_records DESC, b.technology NULLS LAST
LIMIT 15;

-- @id STATE-S4
-- @persona rain_state
-- @data synthetic
-- @question Rural and frontier mix of the areas in view (FORHP rural, frontier flags).
SELECT rc.forhp_rural_flag, rc.frontier_flag,
       count(*)                        AS areas,
       count(DISTINCT rc.county_fips)  AS counties
FROM synthetic.rural_classification rc
GROUP BY rc.forhp_rural_flag, rc.frontier_flag
ORDER BY rc.frontier_flag DESC NULLS LAST, rc.forhp_rural_flag DESC NULLS LAST;

-- @id STATE-S5
-- @persona rain_state
-- @data synthetic
-- @question Small-cell suppression: how many county metric cells are suppressed before the state can publish?
SELECT cm.suppressed_flag,
       count(*)                          AS cells,
       count(DISTINCT cm.county_fips)    AS counties,
       count(DISTINCT cm.metric_code)    AS metrics,
       min(cm.year)                      AS min_year,
       max(cm.year)                      AS max_year
FROM synthetic.county_metric cm
GROUP BY cm.suppressed_flag
ORDER BY cm.suppressed_flag DESC NULLS LAST;

-- @id STATE-P1
-- @persona rain_state
-- @data public
-- @question The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs.
SELECT s.county, s.fips, s.e_totpop AS population, r.value AS rucc_2023,
       round(s.rpl_themes::numeric, 3) AS svi_percentile,
       (SELECT count(*) FROM public_data.hpsa_primary_care h
         WHERE h.common_county_name = s.county || ', NV' AND h.hpsa_status = 'Designated') AS designated_pc_hpsas,
       s.fips IN (32007,32013,32015,32027,32033,32001) AS sierra_basin_county
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY r.value DESC, s.e_totpop;

-- @id STATE-P2
-- @persona rain_state
-- @data public
-- @question Metro vs rural vs frontier-like: Nevada population and county count by RUCC group.
SELECT CASE WHEN r.value::int <= 3 THEN '1-3 metro'
            WHEN r.value::int <= 7 THEN '4-7 nonmetro, urban pop >= 2,500'
            ELSE '8-9 completely rural / remote' END AS rucc_group,
       count(*)              AS counties,
       sum(s.e_totpop)       AS population,
       string_agg(s.county, ', ' ORDER BY s.county) AS counties_in_group
FROM public_data.rucc_county r
JOIN public_data.svi_county s ON s.fips = r.fips
WHERE r.state = 'NV' AND r.attribute = 'RUCC_2023'
GROUP BY 1
ORDER BY 1;

-- @id STATE-P3
-- @persona rain_state
-- @data public
-- @question Primary care shortage counties: designated primary care HPSAs by county, type and severity.
SELECT h.common_county_name, h.designation_type,
       count(*)                  AS designated_hpsas,
       max(h.hpsa_score)         AS max_score,
       round(avg(h.hpsa_score), 1) AS avg_score,
       sum(h.hpsa_designation_population) AS designation_population
FROM public_data.hpsa_primary_care h
WHERE h.primary_state_abbreviation = 'NV' AND h.hpsa_status = 'Designated'
GROUP BY h.common_county_name, h.designation_type
ORDER BY max_score DESC, designated_hpsas DESC
LIMIT 25;

-- @id STATE-P4
-- @persona rain_state
-- @data public
-- @question Where does broadband limit telehealth? Households without internet (SVI) by county, worst first.
SELECT s.county, s.fips, s.ep_noint AS pct_households_no_internet, s.e_noint AS households_no_internet,
       r.value AS rucc_2023, s.fips IN (32007,32013,32015,32027,32033,32001) AS sierra_basin_county
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY s.ep_noint DESC;

-- @id STATE-P5
-- @persona rain_state
-- @data public
-- @question Health center site coverage per 100,000 residents by Nevada county (where do Accelerator funds go first?).
SELECT s.county, s.e_totpop AS population,
       count(hc.site_name)                                             AS health_center_sites,
       round(100000.0 * count(hc.site_name) / NULLIF(s.e_totpop, 0), 1) AS sites_per_100k,
       r.value AS rucc_2023
FROM public_data.svi_county s
LEFT JOIN public_data.health_center_sites hc
       ON hc.site_state_abbreviation = 'NV' AND hc.complete_county_name = s.county
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
GROUP BY s.county, s.e_totpop, r.value
ORDER BY sites_per_100k, s.e_totpop DESC;


-- #####################################################################################################
-- CHW - Teresa Lopez, CHW (Community Health Worker and Care Coordinator): worklist, closest to BP control,
-- unanswered reminders, campaign progress, Spanish talking points
-- #####################################################################################################

-- @id CHW-S1
-- @persona rain_chw
-- @data synthetic
-- @question Open my worklist: open outreach tasks by priority, with who to call.
SELECT t.task_id, t.priority_score, t.task_type, t.status,
       p.patient_id, p.first_name || ' ' || p.last_name AS patient, p.phone,
       t.created_at::timestamp AS created_at, left(t.reason_summary, 60) AS reason
FROM synthetic.outreach_task t
JOIN synthetic.patient p ON p.patient_id = t.patient_id
WHERE t.closed_at IS NULL OR t.status IN ('pending', 'active')
ORDER BY t.priority_score DESC NULLS LAST
LIMIT 25;

-- @id CHW-S2
-- @persona rain_chw
-- @data synthetic
-- @question How is the campaign going? Members, cuffs on file and bookings per campaign.
SELECT c.campaign_id, c.campaign_name, c.status, c.target_count,
       count(cm.campaign_member_id)                         AS members,
       count(*) FILTER (WHERE cm.cuff_on_file)              AS cuff_on_file,
       count(*) FILTER (WHERE cm.booked_flag)               AS booked,
       round(100.0 * count(*) FILTER (WHERE cm.booked_flag) / NULLIF(count(cm.campaign_member_id), 0), 1) AS booked_pct
FROM synthetic.campaign c
JOIN synthetic.campaign_member cm ON cm.campaign_id = c.campaign_id
GROUP BY c.campaign_id, c.campaign_name, c.status, c.target_count
ORDER BY members DESC, booked DESC
LIMIT 15;

-- @id CHW-S3
-- @persona rain_chw
-- @data synthetic
-- @question Who has not answered reminders? Patients with reminders that got no reply or are still pending.
SELECT p.patient_id, p.first_name || ' ' || p.last_name AS patient, p.phone,
       count(*)                                                            AS reminders,
       count(*) FILTER (WHERE rm.reply IS NULL OR rm.delivery_status = 'pending') AS unanswered,
       max(rm.sent_at::timestamp)                                          AS last_sent,
       string_agg(DISTINCT rm.channel, ', ')                               AS channels
FROM synthetic.reminder_message rm
JOIN synthetic.patient p ON p.patient_id = rm.patient_id
GROUP BY p.patient_id, patient, p.phone
HAVING count(*) FILTER (WHERE rm.reply IS NULL OR rm.delivery_status = 'pending') > 0
ORDER BY unanswered DESC, last_sent DESC NULLS LAST
LIMIT 20;

-- @id CHW-S4
-- @persona rain_chw
-- @data synthetic
-- @question Who is closest to BP control? Campaign members with their latest home BP reading.
SELECT DISTINCT ON (cm.patient_id)
       cm.patient_id, p.first_name || ' ' || p.last_name AS patient, cm.outreach_rank, cm.cuff_on_file,
       b.value_systolic, b.value_diastolic, b.reading_time::timestamp AS reading_time, b.counts_for_measure
FROM synthetic.campaign_member cm
JOIN synthetic.patient p            ON p.patient_id = cm.patient_id
JOIN synthetic.remote_bp_reading b  ON b.patient_id = cm.patient_id
ORDER BY cm.patient_id, b.reading_time::timestamp DESC
LIMIT 25;

-- @id CHW-S5
-- @persona rain_chw
-- @data synthetic
-- @question How should I reach each patient? Consented contact channel and language preferences.
SELECT cp.channel, cp.consent_flag,
       count(DISTINCT cp.patient_id) AS patients,
       count(DISTINCT cp.language)   AS languages_recorded
FROM synthetic.contact_preference cp
GROUP BY cp.channel, cp.consent_flag
ORDER BY cp.consent_flag DESC NULLS LAST, patients DESC;

-- @id CHW-P1
-- @persona rain_chw
-- @data public
-- @question Where can I send patients? Health center sites in or near our counties, with hours and phone.
SELECT hc.complete_county_name, hc.site_city, hc.site_name, hc.site_address,
       hc.site_telephone_number, hc.operating_hours_per_week, hc.health_center_type_description
FROM public_data.health_center_sites hc
WHERE hc.site_state_abbreviation = 'NV'
  AND hc.complete_county_name IN ('Elko County','Humboldt County','Lander County','Pershing County',
                                  'White Pine County','Churchill County','Lyon County','Eureka County')
ORDER BY hc.complete_county_name, hc.site_city;

-- @id CHW-P2
-- @persona rain_chw
-- @data public
-- @question Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI).
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'LACKTRPT') AS transport_barrier_pct,
       max(s.ep_noveh)                                           AS pct_households_no_vehicle,
       max(s.area_sqmi)                                          AS county_area_sqmi
FROM public_data.cdc_places p
JOIN public_data.svi_county s ON s.fips = p.locationid
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY transport_barrier_pct DESC;

-- @id CHW-P3
-- @persona rain_chw
-- @data public
-- @question Talking points on social needs: food, housing, utility and food-stamp rates in our counties.
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'FOODINSECU')  AS food_insecurity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'FOODSTAMP')   AS food_stamps_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'HOUSINSECU')  AS housing_insecurity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'SHUTUTILITY') AS utility_shutoff_threat_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'EMOTIONSPT')  AS lacks_social_support_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY food_insecurity_pct DESC;

-- @id CHW-P4
-- @persona rain_chw
-- @data public
-- @question Do I need Spanish talking points? Hispanic share and limited-English households by county (SVI).
SELECT s.county, s.e_totpop AS population,
       s.ep_hisp   AS pct_hispanic,
       s.ep_limeng AS pct_limited_english,
       s.ep_age65  AS pct_age_65_plus
FROM public_data.svi_county s
WHERE s.fips IN (32007, 32013, 32015, 32027, 32033, 32001)
ORDER BY s.ep_limeng DESC;

-- @id CHW-P5
-- @persona rain_chw
-- @data public
-- @question Which primary care practices (NPPES) are in our towns: Elko, Winnemucca, Fallon, Ely, Lovelock, Battle Mountain?
SELECT pr.city, pr.taxonomy, count(*) AS providers,
       count(*) FILTER (WHERE pr.enumeration_type = 'NPI-2') AS organizations,
       count(*) FILTER (WHERE pr.enumeration_type = 'NPI-1') AS individuals
FROM public_data.providers pr
WHERE pr.state = 'NV'
  AND upper(pr.city) IN ('ELKO', 'WINNEMUCCA', 'FALLON', 'ELY', 'LOVELOCK', 'BATTLE MOUNTAIN')
GROUP BY pr.city, pr.taxonomy
ORDER BY pr.city, providers DESC;


-- #####################################################################################################
-- ACCESS - Brandon Kee (Patient Access Coordinator): bookings, unconfirmed visits, R replies, reminders,
-- long drives and telehealth, alternative slots
-- #####################################################################################################

-- @id ACCESS-S1
-- @persona rain_access
-- @data synthetic
-- @question What slots are open? Open slots by site, in-person vs telehealth.
SELECT cs.clinic_site_id, cs.site_name, sl.telehealth_flag,
       count(*)                                         AS slots,
       count(*) FILTER (WHERE sl.status IN ('active', 'pending')) AS open_slots,
       min(sl.slot_start::timestamp)                    AS first_slot
FROM synthetic.slot sl
JOIN synthetic.schedule sc    ON sc.schedule_id = sl.schedule_id
JOIN synthetic.clinic_site cs ON cs.clinic_site_id = sc.clinic_site_id
GROUP BY cs.clinic_site_id, cs.site_name, sl.telehealth_flag
ORDER BY open_slots DESC, slots DESC
LIMIT 20;

-- @id ACCESS-S2
-- @persona rain_access
-- @data synthetic
-- @question Show unconfirmed visits: pending appointments and whether eligibility was verified.
SELECT a.appointment_id, a.status, a.visit_mode, a.booked_at::timestamp AS booked_at,
       p.first_name || ' ' || p.last_name AS patient, p.phone,
       ec.coverage_status, ec.checked_at::timestamp AS eligibility_checked_at
FROM synthetic.appointment a
JOIN synthetic.patient p                ON p.patient_id = a.patient_id
LEFT JOIN synthetic.eligibility_check ec ON ec.appointment_id = a.appointment_id
WHERE a.status = 'booked'
ORDER BY ec.checked_at NULLS FIRST, a.booked_at NULLS LAST
LIMIT 25;

-- @id ACCESS-S3
-- @persona rain_access
-- @data synthetic
-- @question Handle the replies: reminder replies waiting for action, by channel and delivery status.
SELECT rm.channel, rm.delivery_status,
       count(*)                                    AS messages,
       count(*) FILTER (WHERE rm.reply IS NOT NULL) AS with_reply,
       count(DISTINCT rm.patient_id)               AS patients,
       round(avg(rm.offset_hours), 1)              AS avg_hours_before_visit
FROM synthetic.reminder_message rm
GROUP BY rm.channel, rm.delivery_status
ORDER BY with_reply DESC, messages DESC;

-- @id ACCESS-S4
-- @persona rain_access
-- @data synthetic
-- @question Why telehealth for this patient? Longest drive times and whether the site can do telehealth.
SELECT tt.patient_zcta, cs.clinic_site_id, cs.site_name, cs.telehealth_capable,
       round(tt.drive_minutes::numeric, 1) AS drive_minutes,
       CASE WHEN tt.drive_minutes > 60 AND cs.telehealth_capable THEN 'offer telehealth'
            WHEN tt.drive_minutes > 60 THEN 'long drive, no telehealth at site'
            ELSE 'in-person ok' END AS recommendation
FROM synthetic.travel_time tt
JOIN synthetic.clinic_site cs ON cs.clinic_site_id = tt.clinic_site_id
ORDER BY tt.drive_minutes DESC NULLS LAST
LIMIT 20;

-- @id ACCESS-S5
-- @persona rain_access
-- @data synthetic
-- @question Start bookings: campaign members not yet booked, highest outreach rank first, with visit mode.
SELECT cm.outreach_rank, cm.patient_id, p.first_name || ' ' || p.last_name AS patient, p.phone,
       cm.recommended_visit_mode, cm.cuff_on_file, c.campaign_name
FROM synthetic.campaign_member cm
JOIN synthetic.patient p   ON p.patient_id = cm.patient_id
JOIN synthetic.campaign c  ON c.campaign_id = cm.campaign_id
WHERE NOT cm.booked_flag
ORDER BY cm.outreach_rank NULLS LAST
LIMIT 25;

-- @id ACCESS-P1
-- @persona rain_access
-- @data public
-- @question How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx).
SELECT z.geoid AS zcta, round(z.aland_sqmi::numeric, 1) AS land_sq_mi,
       z.intptlat AS lat, z.intptlong AS lon
FROM public_data.zcta_centroids z
WHERE z.geoid BETWEEN '89400' AND '89899'
ORDER BY z.aland_sqmi DESC
LIMIT 20;

-- @id ACCESS-P2
-- @persona rain_access
-- @data public
-- @question Health center capacity: operating hours per week of sites in Nevada's rural counties.
SELECT hc.complete_county_name, count(*) AS sites,
       sum(hc.operating_hours_per_week)           AS total_hours_per_week,
       round(avg(hc.operating_hours_per_week)::numeric, 1) AS avg_hours_per_site
FROM public_data.health_center_sites hc
WHERE hc.site_state_abbreviation = 'NV'
  AND hc.complete_county_name NOT IN ('Clark County', 'Washoe County', 'Carson City')
GROUP BY hc.complete_county_name
ORDER BY total_hours_per_week DESC;

-- @id ACCESS-P3
-- @persona rain_access
-- @data public
-- @question Primary care capacity gap: HPSA FTE shortage and population affected in our counties.
SELECT h.common_county_name, h.hpsa_name, h.designation_type, h.hpsa_score,
       h.hpsa_fte, h.hpsa_shortage, h.hpsa_designation_population, h.hpsa_formal_ratio
FROM public_data.hpsa_primary_care h
WHERE h.hpsa_status = 'Designated'
  AND h.common_county_name IN ('Elko County, NV','Humboldt County, NV','Lander County, NV',
                               'Pershing County, NV','White Pine County, NV','Churchill County, NV')
ORDER BY h.hpsa_score DESC NULLS LAST, h.hpsa_designation_population DESC NULLS LAST;

-- @id ACCESS-P4
-- @persona rain_access
-- @data public
-- @question Primary care providers by town in our region (NPPES: family, internal medicine, NP, PA, clinics).
SELECT upper(pr.city) AS town, count(*) AS primary_care_providers
FROM public_data.providers pr
WHERE pr.state = 'NV'
  AND upper(pr.city) IN ('ELKO', 'WINNEMUCCA', 'FALLON', 'ELY', 'LOVELOCK', 'BATTLE MOUNTAIN', 'WELLS', 'CARLIN')
  AND (pr.taxonomy ILIKE '%family%' OR pr.taxonomy ILIKE '%internal medicine%' OR pr.taxonomy ILIKE '%nurse practitioner%'
       OR pr.taxonomy ILIKE '%physician assistant%' OR pr.taxonomy ILIKE '%clinic%' OR pr.taxonomy ILIKE '%general practice%')
GROUP BY upper(pr.city)
ORDER BY primary_care_providers DESC;

-- @id ACCESS-P5
-- @persona rain_access
-- @data public
-- @question Expect eligibility problems? Uninsured and no-checkup rates in our counties.
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'ACCESS2') AS uninsured_18_64_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'CHECKUP') AS annual_checkup_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'DENTAL')  AS dental_visit_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY uninsured_18_64_pct DESC;


-- #####################################################################################################
-- LINDA GARCIA - patient, Battle Mountain (Lander County), synthetic anchor M-40107: her appointments,
-- reminders, readings, gaps, consent; public drive time, broadband, blood pressure, shortage area, language
-- #####################################################################################################

-- @id GAR-S1
-- @persona patient_linda_garcia
-- @data synthetic
-- @question What appointments do I have?
SELECT a.appointment_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start, s.telehealth_flag
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id WHERE a.patient_id = 'M-40107';

-- @id GAR-S2
-- @persona patient_linda_garcia
-- @data synthetic
-- @question Which reminders were sent to me, and what did I reply?
SELECT channel, language, offset_hours, delivery_status, reply, sent_at
FROM synthetic.reminder_message WHERE patient_id = 'M-40107' ORDER BY sent_at;

-- @id GAR-S3
-- @persona patient_linda_garcia
-- @data synthetic
-- @question What are my home blood pressure readings?
SELECT value_systolic, value_diastolic, reading_time, device_type, counts_for_measure
FROM synthetic.remote_bp_reading WHERE patient_id = 'M-40107' ORDER BY reading_time DESC;

-- @id GAR-S4
-- @persona patient_linda_garcia
-- @data synthetic
-- @question Which care gaps are open for me?
SELECT measure_code, status, opened_at, closed_at, closed_by FROM synthetic.care_gap WHERE patient_id = 'M-40107';

-- @id GAR-S5
-- @persona patient_linda_garcia
-- @data synthetic
-- @question What are my contact preferences and consent?
SELECT channel, language, consent_flag, quiet_hours_start, quiet_hours_end, updated_at
FROM synthetic.contact_preference WHERE patient_id = 'M-40107';

-- @id GAR-P1
-- @persona patient_linda_garcia
-- @data public
-- @question How far do I drive from Battle Mountain to the nearest health center?
SELECT site_name, site_location_type, drive_minutes, drive_miles, straight_line_miles, origin_snap_meters, osm_extract_date
FROM public_data.osrm_nearest_site WHERE zcta = 89820;

-- @id GAR-P2
-- @persona patient_linda_garcia
-- @data public
-- @question What share of households in my county, Lander, have broadband?
SELECT county_name, households_internet_universe AS households, households_with_broadband_any_type, pct_households_broadband, acs_release
FROM public_data.acs_county WHERE county_fips = 32015;

-- @id GAR-P3
-- @persona patient_linda_garcia
-- @data public
-- @question What share of adults in my county, Lander, have high blood pressure?
SELECT locationname AS county, measure, data_value AS crude_prevalence_pct, low_confidence_limit, high_confidence_limit, year
FROM public_data.cdc_places WHERE locationid = 32015 AND measureid IN ('BPHIGH', 'BPMED') AND data_value_type = 'Crude prevalence';

-- @id GAR-P4
-- @persona patient_linda_garcia
-- @data public
-- @question Is my county, Lander, a primary care shortage area?
SELECT hpsa_name, designation_type, hpsa_component_type_description, hpsa_score
FROM public_data.hpsa_primary_care WHERE common_county_name = 'Lander County, NV' AND hpsa_status = 'Designated'
ORDER BY hpsa_score DESC NULLS LAST;

-- @id GAR-P5
-- @persona patient_linda_garcia
-- @data public
-- @question How many households in my county, Lander, speak Spanish with limited English?
SELECT county_name, lep_households_spanish, lep_households_total, pct_lep_households, pop_5plus_speak_spanish
FROM public_data.acs_county WHERE county_fips = 32015;
