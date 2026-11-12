# RAIN v0.4: demo queries, 3 synthetic-data and 3 public-data per persona

14 personas, 84 queries, taken from the verified query pack `doc/queries/rain_v4_persona_queries.sql` (140 queries, every one returning rows and rendering a live table in the browser chat). Database `rain_v4`:

- **Synthetic data** (`synthetic`, 59 tables): row-level operational data for the Q3 checkpoint, the same rows every number in the UI is computed from.
- **Public data** (`public_data`, 24 tables): real public datasets for Nevada and Tennessee (CDC PLACES, CDC/ATSDR SVI, HRSA HPSA and health center sites, Census ACS, CMS hospitals, County Health Rankings, OSRM drive times, ...).

## How to run them

| Where | How |
|---|---|
| The app (chat) | Sign in at http://localhost:8184/login/rain/?access=rain@9705, open the persona (`http://localhost:8184/ask?persona=<persona id>`), and type the question or the query id in the Ask AI box. The answer is a live table from Postgres. |
| The API | `GET http://localhost:8003/api/v4/queries/<id>` runs one read-only and returns its rows; `GET http://localhost:8003/api/v4/queries?persona=<persona id>` lists a persona's queries. |
| pgAdmin | http://localhost:5052 (`admin@rain.app` / `admin`): open `rain_v4_persona_queries.sql` from its file storage, select one query and press F5, or paste the SQL below into a Query Tool on `rain_v4`. |

Row counts are from the last run of the pack against the current data; the write-back flow (bookings, readings, replies) can move the synthetic ones.

## Personas

- [CEO - Gregory Haskins, MBA (Chief Executive Officer)](#ceo---gregory-haskins-mba-chief-executive-officer) (`rain_ceo`)
- [CMO - Dr. Naomi Castellanos (Chief Medical Officer, VBC Quality Lead)](#cmo---dr-naomi-castellanos-chief-medical-officer-vbc-quality-lead) (`rain_cmo`)
- [CIO - Raj Malhotra (CIO, Data and AI Governance Lead)](#cio---raj-malhotra-cio-data-and-ai-governance-lead) (`rain_cio`)
- [STATE - Dr. Lauren Pike (Program Lead, Rural Health Outcomes Accelerator)](#state---dr-lauren-pike-program-lead-rural-health-outcomes-accelerator) (`rain_state`)
- [CHW - Teresa Lopez, CHW (Community Health Worker and Care Coordinator)](#chw---teresa-lopez-chw-community-health-worker-and-care-coordinator) (`rain_chw`)
- [ACCESS - Brandon Kee (Patient Access Coordinator)](#access---brandon-kee-patient-access-coordinator) (`rain_access`)
- [HARGROVE - Dr. Linda Hargrove (Clinic Medical / Quality Director)](#hargrove---dr-linda-hargrove-clinic-medical--quality-director) (`rain_hargrove`)
- [BELL - Marcus Bell (State RHTP Program Manager)](#bell---marcus-bell-state-rhtp-program-manager) (`rain_bell`)
- [HOLLOWAY - Denise Holloway (Community Health Worker, field)](#holloway---denise-holloway-community-health-worker-field) (`rain_holloway`)
- [BROOKS - Kayla Brooks (Clinic Scheduler / Front Desk)](#brooks---kayla-brooks-clinic-scheduler--front-desk) (`rain_brooks`)
- [OKAFOR - Dr. Samuel Okafor (Rural Provider)](#okafor---dr-samuel-okafor-rural-provider) (`rain_okafor`)
- [LINDA GARCIA - patient, Battle Mountain (Lander County), synthetic anchor M-40107](#linda-garcia---patient-battle-mountain-lander-county-synthetic-anchor-m-40107) (`rain_linda`)
- [ROSA MARTINEZ - patient, Fallon (Churchill County), synthetic anchor R-50214](#rosa-martinez---patient-fallon-churchill-county-synthetic-anchor-r-50214) (`rain_rosa`)
- [HANNAH LEE - Payer / Medicaid MCO Analyst (High Desert Health Plan, phase 2)](#hannah-lee---payer--medicaid-mco-analyst-high-desert-health-plan-phase-2) (`rain_hannah`)

## CEO - Gregory Haskins, MBA (Chief Executive Officer)

Persona id in the app: `rain_ceo` · open: http://localhost:8184/ask?persona=rain_ceo

### Synthetic data

**CEO-S1**: What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)?

- Type in Ask AI: `What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)?` (or just `CEO-S1`)
- Reads: `synthetic.attributed_member`, `synthetic.claim`
- Returns now: 1 row; columns `attributed_members`, `claims`, `total_allowed`, `allowed_per_member`

```sql
SELECT count(DISTINCT am.patient_id)                                   AS attributed_members,
       count(c.claim_id)                                               AS claims,
       round(sum(c.allowed_amount)::numeric, 2)                        AS total_allowed,
       round((sum(c.allowed_amount) / NULLIF(count(DISTINCT am.patient_id), 0))::numeric, 2) AS allowed_per_member
FROM synthetic.attributed_member am
LEFT JOIN synthetic.claim c ON c.patient_id = am.patient_id;
```

**CEO-S2**: How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members?

- Type in Ask AI: `How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members?` (or just `CEO-S2`)
- Reads: `synthetic.attributed_member`, `synthetic.claim`
- Returns now: 1 row; columns `ed_claims`, `avoidable_ed_claims`, `admissions`, `ed_per_1000`, `avoidable_ed_per_1000`

```sql
WITH members AS (SELECT count(DISTINCT patient_id) AS n FROM synthetic.attributed_member)
SELECT count(*) FILTER (WHERE c.ed_flag)                                          AS ed_claims,
       count(*) FILTER (WHERE c.avoidable_ed_flag)                                AS avoidable_ed_claims,
       count(*) FILTER (WHERE c.admission_flag)                                   AS admissions,
       round(1000.0 * count(*) FILTER (WHERE c.ed_flag) / m.n, 1)                 AS ed_per_1000,
       round(1000.0 * count(*) FILTER (WHERE c.avoidable_ed_flag) / m.n, 1)       AS avoidable_ed_per_1000
FROM synthetic.claim c CROSS JOIN members m
GROUP BY m.n;
```

**CEO-S3**: Where is the low-value care? Top sites by low-value spend.

- Type in Ask AI: `Where is the low-value care? Top sites by low-value spend.` (or just `CEO-S3`)
- Reads: `synthetic.low_value_finding`, `synthetic.clinic_site`
- Returns now: 10 rows; columns `clinic_site_id`, `site_name`, `low_value_findings`, `low_value_allowed`

```sql
SELECT cs.clinic_site_id, cs.site_name,
       count(lf.finding_id)                       AS low_value_findings,
       round(sum(lf.allowed_amount)::numeric, 2)  AS low_value_allowed
FROM synthetic.low_value_finding lf
JOIN synthetic.clinic_site cs ON cs.clinic_site_id = lf.clinic_site_id
GROUP BY cs.clinic_site_id, cs.site_name
ORDER BY low_value_allowed DESC NULLS LAST
LIMIT 10;
```

### Public data

**CEO-P1**: Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability.

- Type in Ask AI: `Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability.` (or just `CEO-P1`)
- Reads: `public_data.svi_county`, `public_data.rucc_county`
- Returns now: 6 rows; columns `county`, `fips`, `population`, `rucc_2023`, `svi_percentile`, `pct_below_150_poverty`, `pct_uninsured`

```sql
WITH network(fips) AS (VALUES (32007),(32013),(32015),(32027),(32033),(32001))
SELECT s.county, s.fips, s.e_totpop AS population, r.value AS rucc_2023,
       round(s.rpl_themes::numeric, 3) AS svi_percentile, s.ep_pov150 AS pct_below_150_poverty, s.ep_uninsur AS pct_uninsured
FROM network n
JOIN public_data.svi_county s  ON s.fips = n.fips
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
ORDER BY s.e_totpop DESC;
```

**CEO-P2**: What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)?

- Type in Ask AI: `What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)?` (or just `CEO-P2`)
- Reads: `public_data.cdc_places`
- Returns now: 6 rows; columns `county`, `high_bp_pct`, `diabetes_pct`, `obesity_pct`, `smoking_pct`, `copd_pct`

```sql
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
```

**CEO-P3**: How do our counties compare with the Nevada county average on annual checkups and insurance gaps?

- Type in Ask AI: `How do our counties compare with the Nevada county average on annual checkups and insurance gaps?` (or just `CEO-P3`)
- Reads: `public_data.cdc_places`
- Returns now: 5 rows; columns `measureid`, `short_question_text`, `network_avg_pct`, `nv_county_avg_pct`

```sql
SELECT p.measureid, p.short_question_text,
       round(avg(p.data_value) FILTER (WHERE p.locationid IN (32007,32013,32015,32027,32033,32001))::numeric, 1) AS network_avg_pct,
       round(avg(p.data_value)::numeric, 1)                                                                      AS nv_county_avg_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.measureid IN ('CHECKUP', 'ACCESS2', 'BPMED', 'CHOLSCREEN', 'COLON_SCREEN')
GROUP BY p.measureid, p.short_question_text
ORDER BY p.measureid;
```

## CMO - Dr. Naomi Castellanos (Chief Medical Officer, VBC Quality Lead)

Persona id in the app: `rain_cmo` · open: http://localhost:8184/ask?persona=rain_cmo

### Synthetic data

**CMO-S1**: How close are we to each quality target? Performance gap per measure.

- Type in Ask AI: `How close are we to each quality target? Performance gap per measure.` (or just `CMO-S1`)
- Reads: `synthetic.quality_measure`, `synthetic.quality_measure_result`
- Returns now: 5 rows; columns `measure_code`, `measure_name`, `gate_flag`, `target_rate`, `rate`, `gap_to_target`, `patients_in_denominator`

```sql
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
```

**CMO-S2**: Which care gaps are still open, by measure?

- Type in Ask AI: `Which care gaps are still open, by measure?` (or just `CMO-S2`)
- Reads: `synthetic.care_gap`, `synthetic.quality_measure`
- Returns now: 5 rows; columns `measure_code`, `measure_name`, `gaps`, `never_closed`, `pending`, `oldest_opened`

```sql
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
```

**CMO-S3**: Which patients with an open care gap have home BP readings that count toward the measure?

- Type in Ask AI: `Which patients with an open care gap have home BP readings that count toward the measure?` (or just `CMO-S3`)
- Reads: `synthetic.patient`, `synthetic.remote_bp_reading`, `synthetic.care_gap`
- Returns now: 20 rows; columns `patient_id`, `first_name`, `last_name`, `readings_counting`, `latest_reading`, `open_gaps`

```sql
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
```

### Public data

**CMO-P1**: How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada?

- Type in Ask AI: `How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada?` (or just `CMO-P1`)
- Reads: `public_data.cdc_places`
- Returns now: 17 rows; columns `county`, `high_bp_pct`, `on_bp_medication_pct`, `grp`

```sql
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'BPHIGH') AS high_bp_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'BPMED')  AS on_bp_medication_pct,
       CASE WHEN p.locationid IN (32007,32013,32015,32027,32033,32001) THEN 'network' ELSE 'other NV' END AS grp
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence' AND p.measureid IN ('BPHIGH', 'BPMED')
GROUP BY p.locationname, p.locationid
ORDER BY grp, high_bp_pct DESC;
```

**CMO-P2**: Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context).

- Type in Ask AI: `Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context).` (or just `CMO-P2`)
- Reads: `public_data.cdc_places`
- Returns now: 17 rows; columns `county`, `diabetes_pct`, `obesity_pct`, `physical_inactivity_pct`, `is_network_county`

```sql
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'DIABETES') AS diabetes_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'OBESITY')  AS obesity_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'LPA')      AS physical_inactivity_pct,
       p.locationid IN (32007,32013,32015,32027,32033,32001)     AS is_network_county
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
GROUP BY p.locationname, p.locationid
ORDER BY diabetes_pct DESC;
```

**CMO-P3**: Preventive screening rates in our counties (colorectal, mammography, cholesterol).

- Type in Ask AI: `Preventive screening rates in our counties (colorectal, mammography, cholesterol).` (or just `CMO-P3`)
- Reads: `public_data.cdc_places`
- Returns now: 6 rows; columns `county`, `colorectal_screening_pct`, `mammography_pct`, `cholesterol_screening_pct`

```sql
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'COLON_SCREEN') AS colorectal_screening_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'MAMMOUSE')     AS mammography_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'CHOLSCREEN')   AS cholesterol_screening_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY colorectal_screening_pct;
```

## CIO - Raj Malhotra (CIO, Data and AI Governance Lead)

Persona id in the app: `rain_cio` · open: http://localhost:8184/ask?persona=rain_cio

### Synthetic data

**CIO-S1**: Show the model cards: release status, sign-off and how many subgroup checks each passed.

- Type in Ask AI: `Show the model cards: release status, sign-off and how many subgroup checks each passed.` (or just `CIO-S1`)
- Reads: `synthetic.model_card`, `synthetic.subgroup_check`
- Returns now: 2 rows; columns `model_version`, `model_name`, `release_status`, `access_adjusted_flag`, `signed_off_by`, `cosigned_by`, `subgroup_checks`, `passed` …

```sql
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
```

**CIO-S2**: Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold.

- Type in Ask AI: `Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold.` (or just `CIO-S2`)
- Reads: `synthetic.subgroup_check`
- Returns now: 6 rows; columns `model_version`, `subgroup`, `comparison_group`, `metric`, `gap_percent`, `threshold_percent`, `over_threshold_by`, `passed` …

```sql
SELECT sc.model_version, sc.subgroup, sc.comparison_group, sc.metric,
       sc.gap_percent, sc.threshold_percent,
       round((sc.gap_percent - sc.threshold_percent)::numeric, 4) AS over_threshold_by,
       sc.passed, sc.checked_at::timestamp AS checked_at
FROM synthetic.subgroup_check sc
WHERE sc.gap_percent > sc.threshold_percent
ORDER BY over_threshold_by DESC NULLS LAST
LIMIT 20;
```

**CIO-S3**: How fresh is each data source? Latest record per feed and lag in days.

- Type in Ask AI: `How fresh is each data source? Latest record per feed and lag in days.` (or just `CIO-S3`)
- Reads: `synthetic.claim`, `synthetic.encounter`, `synthetic.observation`, `synthetic.remote_bp_reading`, `synthetic.eligibility_check`, `synthetic.reminder_message`, `synthetic.sdoh_screening`
- Returns now: 7 rows; columns `feed`, `latest`, `days_since_latest`, `rows`

```sql
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
```

### Public data

**CIO-P1**: What public data feeds the county view? Row counts and state coverage per public table.

- Type in Ask AI: `What public data feeds the county view? Row counts and state coverage per public table.` (or just `CIO-P1`)
- Reads: `public_data.cdc_places`, `public_data.svi_county`, `public_data.rucc_county`, `public_data.hpsa_primary_care`, `public_data.hpsa_mental_health`, `public_data.health_center_sites`, `public_data.providers`, `public_data.zcta_centroids`
- Returns now: 8 rows; columns `dataset`, `rows`, `states`, `vintage`

```sql
SELECT 'cdc_places' AS dataset, count(*) AS rows, count(DISTINCT stateabbr) AS states, string_agg(DISTINCT year::text, ',') AS vintage FROM public_data.cdc_places
UNION ALL SELECT 'svi_county',          count(*), count(DISTINCT st_abbr), '2022' FROM public_data.svi_county
UNION ALL SELECT 'rucc_county',         count(*), count(DISTINCT state), '2023'   FROM public_data.rucc_county
UNION ALL SELECT 'hpsa_primary_care',   count(*), count(DISTINCT primary_state_abbreviation), 'HRSA current' FROM public_data.hpsa_primary_care
UNION ALL SELECT 'hpsa_mental_health',  count(*), count(DISTINCT primary_state_abbreviation), 'HRSA current' FROM public_data.hpsa_mental_health
UNION ALL SELECT 'health_center_sites', count(*), count(DISTINCT site_state_abbreviation), 'HRSA current' FROM public_data.health_center_sites
UNION ALL SELECT 'providers (NPPES)',   count(*), count(DISTINCT state), 'NPPES' FROM public_data.providers
UNION ALL SELECT 'zcta_centroids',      count(*), NULL, '2023 Gazetteer' FROM public_data.zcta_centroids
ORDER BY rows DESC;
```

**CIO-P2**: CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state.

- Type in Ask AI: `CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state.` (or just `CIO-P2`)
- Reads: `public_data.cdc_places`
- Returns now: 4 rows; columns `stateabbr`, `data_value_type`, `measures`, `counties`, `cells`, `missing_values`, `ci_wider_than_10pts`

```sql
SELECT stateabbr, data_value_type,
       count(DISTINCT measureid)                                         AS measures,
       count(DISTINCT locationid)                                        AS counties,
       count(*)                                                          AS cells,
       count(*) FILTER (WHERE data_value IS NULL)                        AS missing_values,
       count(*) FILTER (WHERE high_confidence_limit - low_confidence_limit > 10) AS ci_wider_than_10pts
FROM public_data.cdc_places
GROUP BY stateabbr, data_value_type
ORDER BY stateabbr, data_value_type;
```

**CIO-P3**: Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS?

- Type in Ask AI: `Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS?` (or just `CIO-P3`)
- Reads: `public_data.cdc_places`, `public_data.hpsa_primary_care`, `public_data.svi_county`, `public_data.rucc_county`
- Returns now: 17 rows; columns `fips`, `county`, `in_rucc`, `in_cdc_places`, `has_any_pc_hpsa`

```sql
SELECT s.fips, s.county,
       (r.fips IS NOT NULL)                                   AS in_rucc,
       EXISTS (SELECT 1 FROM public_data.cdc_places p WHERE p.locationid = s.fips) AS in_cdc_places,
       EXISTS (SELECT 1 FROM public_data.hpsa_primary_care h
               WHERE h.common_county_name = s.county || ', NV')                  AS has_any_pc_hpsa
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY s.fips;
```

## STATE - Dr. Lauren Pike (Program Lead, Rural Health Outcomes Accelerator)

Persona id in the app: `rain_state` · open: http://localhost:8184/ask?persona=rain_state

### Synthetic data

**STATE-S1**: Primary care visits by month (is volume down since January?), with telehealth share.

- Type in Ask AI: `Primary care visits by month (is volume down since January?), with telehealth share.` (or just `STATE-S1`)
- Reads: `synthetic.encounter`
- Returns now: 12 rows; columns `month`, `encounters`, `telehealth`, `telehealth_pct`

```sql
SELECT date_trunc('month', e.start_time::timestamp)::date               AS month,
       count(*)                                                         AS encounters,
       count(*) FILTER (WHERE e.telehealth_flag)                        AS telehealth,
       round(100.0 * count(*) FILTER (WHERE e.telehealth_flag) / count(*), 1) AS telehealth_pct
FROM synthetic.encounter e
WHERE e.start_time::timestamp >= date '2026-01-01' - interval '12 months'
GROUP BY 1
ORDER BY 1;
```

**STATE-S2**: Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth.

- Type in Ask AI: `Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth.` (or just `STATE-S2`)
- Reads: `synthetic.clinic_site`, `synthetic.encounter`
- Returns now: 2 rows; columns `telehealth_capable`, `sites`, `encounters`, `telehealth_pct`

```sql
SELECT cs.telehealth_capable,
       count(DISTINCT cs.clinic_site_id)                                          AS sites,
       count(e.encounter_id)                                                      AS encounters,
       round(100.0 * count(e.encounter_id) FILTER (WHERE e.telehealth_flag)
             / NULLIF(count(e.encounter_id), 0), 1)                               AS telehealth_pct
FROM synthetic.clinic_site cs
LEFT JOIN synthetic.encounter e ON e.clinic_site_id = cs.clinic_site_id
GROUP BY cs.telehealth_capable
ORDER BY cs.telehealth_capable DESC NULLS LAST;
```

**STATE-S3**: Where does broadband block telehealth? Share of coverage records not served, by technology.

- Type in Ask AI: `Where does broadband block telehealth? Share of coverage records not served, by technology.` (or just `STATE-S3`)
- Reads: `synthetic.broadband_coverage`
- Returns now: 2 rows; columns `technology`, `coverage_records`, `not_served`, `not_served_pct`

```sql
SELECT b.technology,
       count(*)                                                    AS coverage_records,
       count(*) FILTER (WHERE NOT b.served_flag)                   AS not_served,
       round(100.0 * count(*) FILTER (WHERE NOT b.served_flag) / count(*), 1) AS not_served_pct
FROM synthetic.broadband_coverage b
GROUP BY b.technology
ORDER BY not_served DESC, coverage_records DESC, b.technology NULLS LAST
LIMIT 15;
```

### Public data

**STATE-P1**: The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs.

- Type in Ask AI: `The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs.` (or just `STATE-P1`)
- Reads: `public_data.hpsa_primary_care`, `public_data.svi_county`, `public_data.rucc_county`
- Returns now: 17 rows; columns `county`, `fips`, `population`, `rucc_2023`, `svi_percentile`, `designated_pc_hpsas`, `sierra_basin_county`

```sql
SELECT s.county, s.fips, s.e_totpop AS population, r.value AS rucc_2023,
       round(s.rpl_themes::numeric, 3) AS svi_percentile,
       (SELECT count(*) FROM public_data.hpsa_primary_care h
         WHERE h.common_county_name = s.county || ', NV' AND h.hpsa_status = 'Designated') AS designated_pc_hpsas,
       s.fips IN (32007,32013,32015,32027,32033,32001) AS sierra_basin_county
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY r.value DESC, s.e_totpop;
```

**STATE-P2**: Metro vs rural vs frontier-like: Nevada population and county count by RUCC group.

- Type in Ask AI: `Metro vs rural vs frontier-like: Nevada population and county count by RUCC group.` (or just `STATE-P2`)
- Reads: `public_data.rucc_county`, `public_data.svi_county`
- Returns now: 3 rows; columns `rucc_group`, `counties`, `population`, `counties_in_group`

```sql
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
```

**STATE-P3**: Primary care shortage counties: designated primary care HPSAs by county, type and severity.

- Type in Ask AI: `Primary care shortage counties: designated primary care HPSAs by county, type and severity.` (or just `STATE-P3`)
- Reads: `public_data.hpsa_primary_care`
- Returns now: 25 rows; columns `common_county_name`, `designation_type`, `designated_hpsas`, `max_score`, `avg_score`, `designation_population`

```sql
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
```

## CHW - Teresa Lopez, CHW (Community Health Worker and Care Coordinator)

Persona id in the app: `rain_chw` · open: http://localhost:8184/ask?persona=rain_chw

### Synthetic data

**CHW-S1**: Open my worklist: open outreach tasks by priority, with who to call.

- Type in Ask AI: `Open my worklist: open outreach tasks by priority, with who to call.` (or just `CHW-S1`)
- Reads: `synthetic.outreach_task`, `synthetic.patient`
- Returns now: 25 rows; columns `task_id`, `priority_score`, `task_type`, `status`, `patient_id`, `patient`, `phone`, `created_at` …

```sql
SELECT t.task_id, t.priority_score, t.task_type, t.status,
       p.patient_id, p.first_name || ' ' || p.last_name AS patient, p.phone,
       t.created_at::timestamp AS created_at, left(t.reason_summary, 60) AS reason
FROM synthetic.outreach_task t
JOIN synthetic.patient p ON p.patient_id = t.patient_id
WHERE t.closed_at IS NULL OR t.status IN ('pending', 'active')
ORDER BY t.priority_score DESC NULLS LAST
LIMIT 25;
```

**CHW-S2**: How is the campaign going? Members, cuffs on file and bookings per campaign.

- Type in Ask AI: `How is the campaign going? Members, cuffs on file and bookings per campaign.` (or just `CHW-S2`)
- Reads: `synthetic.campaign`, `synthetic.campaign_member`
- Returns now: 2 rows; columns `campaign_id`, `campaign_name`, `status`, `target_count`, `members`, `cuff_on_file`, `booked`, `booked_pct`

```sql
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
```

**CHW-S3**: Who has not answered reminders? Patients with reminders that got no reply or are still pending.

- Type in Ask AI: `Who has not answered reminders? Patients with reminders that got no reply or are still pending.` (or just `CHW-S3`)
- Reads: `synthetic.reminder_message`, `synthetic.patient`
- Returns now: 15 rows; columns `patient_id`, `patient`, `phone`, `reminders`, `unanswered`, `last_sent`, `channels`

```sql
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
```

### Public data

**CHW-P1**: Where can I send patients? Health center sites in or near our counties, with hours and phone.

- Type in Ask AI: `Where can I send patients? Health center sites in or near our counties, with hours and phone.` (or just `CHW-P1`)
- Reads: `public_data.health_center_sites`
- Returns now: 6 rows; columns `complete_county_name`, `site_city`, `site_name`, `site_address`, `site_telephone_number`, `operating_hours_per_week`, `health_center_type_description`

```sql
SELECT hc.complete_county_name, hc.site_city, hc.site_name, hc.site_address,
       hc.site_telephone_number, hc.operating_hours_per_week, hc.health_center_type_description
FROM public_data.health_center_sites hc
WHERE hc.site_state_abbreviation = 'NV'
  AND hc.complete_county_name IN ('Elko County','Humboldt County','Lander County','Pershing County',
                                  'White Pine County','Churchill County','Lyon County','Eureka County')
ORDER BY hc.complete_county_name, hc.site_city;
```

**CHW-P2**: Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI).

- Type in Ask AI: `Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI).` (or just `CHW-P2`)
- Reads: `public_data.cdc_places`, `public_data.svi_county`
- Returns now: 6 rows; columns `county`, `transport_barrier_pct`, `pct_households_no_vehicle`, `county_area_sqmi`

```sql
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
```

**CHW-P3**: Talking points on social needs: food, housing, utility and food-stamp rates in our counties.

- Type in Ask AI: `Talking points on social needs: food, housing, utility and food-stamp rates in our counties.` (or just `CHW-P3`)
- Reads: `public_data.cdc_places`
- Returns now: 6 rows; columns `county`, `food_insecurity_pct`, `food_stamps_pct`, `housing_insecurity_pct`, `utility_shutoff_threat_pct`, `lacks_social_support_pct`

```sql
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
```

## ACCESS - Brandon Kee (Patient Access Coordinator)

Persona id in the app: `rain_access` · open: http://localhost:8184/ask?persona=rain_access

### Synthetic data

**ACCESS-S1**: What slots are open? Open slots by site, in-person vs telehealth.

- Type in Ask AI: `What slots are open? Open slots by site, in-person vs telehealth.` (or just `ACCESS-S1`)
- Reads: `synthetic.slot`, `synthetic.schedule`, `synthetic.clinic_site`
- Returns now: 15 rows; columns `clinic_site_id`, `site_name`, `telehealth_flag`, `slots`, `open_slots`, `first_slot`

```sql
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
```

**ACCESS-S2**: Show unconfirmed visits: pending appointments and whether eligibility was verified.

- Type in Ask AI: `Show unconfirmed visits: pending appointments and whether eligibility was verified.` (or just `ACCESS-S2`)
- Reads: `synthetic.appointment`, `synthetic.patient`, `synthetic.eligibility_check`
- Returns now: 15 rows; columns `appointment_id`, `status`, `visit_mode`, `booked_at`, `patient`, `phone`, `coverage_status`, `eligibility_checked_at`

```sql
SELECT a.appointment_id, a.status, a.visit_mode, a.booked_at::timestamp AS booked_at,
       p.first_name || ' ' || p.last_name AS patient, p.phone,
       ec.coverage_status, ec.checked_at::timestamp AS eligibility_checked_at
FROM synthetic.appointment a
JOIN synthetic.patient p                ON p.patient_id = a.patient_id
LEFT JOIN synthetic.eligibility_check ec ON ec.appointment_id = a.appointment_id
WHERE a.status = 'booked'
ORDER BY ec.checked_at NULLS FIRST, a.booked_at NULLS LAST
LIMIT 25;
```

**ACCESS-S3**: Handle the replies: reminder replies waiting for action, by channel and delivery status.

- Type in Ask AI: `Handle the replies: reminder replies waiting for action, by channel and delivery status.` (or just `ACCESS-S3`)
- Reads: `synthetic.reminder_message`
- Returns now: 4 rows; columns `channel`, `delivery_status`, `messages`, `with_reply`, `patients`, `avg_hours_before_visit`

```sql
SELECT rm.channel, rm.delivery_status,
       count(*)                                    AS messages,
       count(*) FILTER (WHERE rm.reply IS NOT NULL) AS with_reply,
       count(DISTINCT rm.patient_id)               AS patients,
       round(avg(rm.offset_hours), 1)              AS avg_hours_before_visit
FROM synthetic.reminder_message rm
GROUP BY rm.channel, rm.delivery_status
ORDER BY with_reply DESC, messages DESC;
```

### Public data

**ACCESS-P1**: How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx).

- Type in Ask AI: `How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx).` (or just `ACCESS-P1`)
- Reads: `public_data.zcta_centroids`
- Returns now: 20 rows; columns `zcta`, `land_sq_mi`, `lat`, `lon`

```sql
SELECT z.geoid AS zcta, round(z.aland_sqmi::numeric, 1) AS land_sq_mi,
       z.intptlat AS lat, z.intptlong AS lon
FROM public_data.zcta_centroids z
WHERE z.geoid BETWEEN '89400' AND '89899'
ORDER BY z.aland_sqmi DESC
LIMIT 20;
```

**ACCESS-P2**: Health center capacity: operating hours per week of sites in Nevada's rural counties.

- Type in Ask AI: `Health center capacity: operating hours per week of sites in Nevada's rural counties.` (or just `ACCESS-P2`)
- Reads: `public_data.health_center_sites`
- Returns now: 4 rows; columns `complete_county_name`, `sites`, `total_hours_per_week`, `avg_hours_per_site`

```sql
SELECT hc.complete_county_name, count(*) AS sites,
       sum(hc.operating_hours_per_week)           AS total_hours_per_week,
       round(avg(hc.operating_hours_per_week)::numeric, 1) AS avg_hours_per_site
FROM public_data.health_center_sites hc
WHERE hc.site_state_abbreviation = 'NV'
  AND hc.complete_county_name NOT IN ('Clark County', 'Washoe County', 'Carson City')
GROUP BY hc.complete_county_name
ORDER BY total_hours_per_week DESC;
```

**ACCESS-P3**: Primary care capacity gap: HPSA FTE shortage and population affected in our counties.

- Type in Ask AI: `Primary care capacity gap: HPSA FTE shortage and population affected in our counties.` (or just `ACCESS-P3`)
- Reads: `public_data.hpsa_primary_care`
- Returns now: 22 rows; columns `common_county_name`, `hpsa_name`, `designation_type`, `hpsa_score`, `hpsa_fte`, `hpsa_shortage`, `hpsa_designation_population`, `hpsa_formal_ratio`

```sql
SELECT h.common_county_name, h.hpsa_name, h.designation_type, h.hpsa_score,
       h.hpsa_fte, h.hpsa_shortage, h.hpsa_designation_population, h.hpsa_formal_ratio
FROM public_data.hpsa_primary_care h
WHERE h.hpsa_status = 'Designated'
  AND h.common_county_name IN ('Elko County, NV','Humboldt County, NV','Lander County, NV',
                               'Pershing County, NV','White Pine County, NV','Churchill County, NV')
ORDER BY h.hpsa_score DESC NULLS LAST, h.hpsa_designation_population DESC NULLS LAST;
```

## HARGROVE - Dr. Linda Hargrove (Clinic Medical / Quality Director)

Persona id in the app: `rain_hargrove` · open: http://localhost:8184/ask?persona=rain_hargrove

### Synthetic data

**HAR-S1**: What is the risk mix of the patients seen at my site?

- Type in Ask AI: `What is the risk mix of the patients seen at my site?` (or just `HAR-S1`)
- Reads: `synthetic.encounter`, `synthetic.impactability_score`, `synthetic.model_card`
- Returns now: 3 rows; columns `risk_segment`, `patients`, `avg_impactability`, `predicted_cost_avoided`

```sql
WITH site AS (SELECT 'winnemucca'::text AS clinic_site_id),
seen AS (SELECT DISTINCT e.patient_id FROM synthetic.encounter e JOIN site ON site.clinic_site_id = e.clinic_site_id)
SELECT i.segment AS risk_segment, count(*) AS patients, round(avg(i.score)::numeric, 2) AS avg_impactability,
       round(sum(i.predicted_cost_avoided)) AS predicted_cost_avoided
FROM synthetic.impactability_score i JOIN seen ON seen.patient_id = i.patient_id
WHERE i.model_version = (SELECT model_version FROM synthetic.model_card WHERE release_status = 'released' ORDER BY model_version DESC LIMIT 1)
GROUP BY i.segment ORDER BY patients DESC;
```

**HAR-S2**: Which care gaps are still open for patients seen at my site?

- Type in Ask AI: `Which care gaps are still open for patients seen at my site?` (or just `HAR-S2`)
- Reads: `synthetic.encounter`, `synthetic.care_gap`
- Returns now: 5 rows; columns `measure_code`, `status`, `gaps`, `oldest_opened`

```sql
WITH site AS (SELECT 'winnemucca'::text AS clinic_site_id),
seen AS (SELECT DISTINCT e.patient_id FROM synthetic.encounter e JOIN site ON site.clinic_site_id = e.clinic_site_id)
SELECT cg.measure_code, cg.status, count(*) AS gaps, min(cg.opened_at) AS oldest_opened
FROM synthetic.care_gap cg JOIN seen ON seen.patient_id = cg.patient_id
WHERE cg.status <> 'closed'
GROUP BY cg.measure_code, cg.status ORDER BY gaps DESC;
```

**HAR-S3**: How are outreach tasks closing for my site's patients, open against closed?

- Type in Ask AI: `How are outreach tasks closing for my site's patients, open against closed?` (or just `HAR-S3`)
- Reads: `synthetic.encounter`, `synthetic.outreach_task`
- Returns now: 2 rows; columns `state`, `tasks`, `avg_priority`

```sql
WITH site AS (SELECT 'winnemucca'::text AS clinic_site_id),
seen AS (SELECT DISTINCT e.patient_id FROM synthetic.encounter e JOIN site ON site.clinic_site_id = e.clinic_site_id)
SELECT CASE WHEN ot.closed_at IS NULL THEN 'Open' ELSE 'Closed' END AS state, count(*) AS tasks,
       round(avg(ot.priority_score)::numeric, 2) AS avg_priority
FROM synthetic.outreach_task ot JOIN seen ON seen.patient_id = ot.patient_id
GROUP BY 1 ORDER BY 1;
```

### Public data

**HAR-P1**: How common are high blood pressure and diabetes in Humboldt County against the other five counties?

- Type in Ask AI: `How common are high blood pressure and diabetes in Humboldt County against the other five counties?` (or just `HAR-P1`)
- Reads: `public_data.cdc_places`
- Returns now: 12 rows; columns `county`, `measureid`, `crude_prevalence_pct`, `year`

```sql
WITH six(fips, county) AS (VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill'))
SELECT six.county, p.measureid, p.data_value AS crude_prevalence_pct, p.year
FROM six JOIN public_data.cdc_places p ON p.locationid = six.fips
WHERE p.measureid IN ('BPHIGH', 'DIABETES') AND p.data_value_type = 'Crude prevalence'
ORDER BY p.measureid, p.data_value DESC;
```

**HAR-P2**: How do the hospitals in our six counties do on unplanned visits and readmissions?

- Type in Ask AI: `How do the hospitals in our six counties do on unplanned visits and readmissions?` (or just `HAR-P2`)
- Reads: `public_data.cms_unplanned_visits`
- Returns now: 22 rows; columns `facility_name`, `county`, `measure_id`, `measure_name`, `compared_to_national`, `score`, `end_date`

```sql
SELECT facility_name, county_parish AS county, measure_id, measure_name, compared_to_national, score, end_date
FROM public_data.cms_unplanned_visits
WHERE state = 'NV' AND county_parish IN ('ELKO', 'HUMBOLDT', 'LANDER', 'PERSHING', 'WHITE PINE', 'CHURCHILL') AND score NOT IN ('Not Available', '')
ORDER BY county_parish, facility_name, measure_id;
```

**HAR-P3**: How do Nevada and US health centers score on the UDS clinical quality measures?

- Type in Ask AI: `How do Nevada and US health centers score on the UDS clinical quality measures?` (or just `HAR-P3`)
- Reads: `public_data.uds_state_national_cqm`
- Returns now: 12 rows; columns `measure`, `geography`, `year`, `value`

```sql
SELECT measure, geography, year, value
FROM public_data.uds_state_national_cqm
WHERE geo_abbr IN ('NV', 'US') AND year = (SELECT max(year) FROM public_data.uds_state_national_cqm)
ORDER BY measure, geography;
```

## BELL - Marcus Bell (State RHTP Program Manager)

Persona id in the app: `rain_bell` · open: http://localhost:8184/ask?persona=rain_bell

### Synthetic data

**BEL-S1**: How many people served and services delivered does each grantee report?

- Type in Ask AI: `How many people served and services delivered does each grantee report?` (or just `BEL-S1`)
- Reads: `synthetic.grantee`, `synthetic.rhtp_report`
- Returns now: 4 rows; columns `network_name`, `program_initiative`, `report_rows`, `people_served`, `services_delivered`

```sql
SELECT g.network_name, g.program_initiative, count(r.rhtp_report_id) AS report_rows,
       sum(r.people_served) AS people_served, sum(r.services_delivered) AS services_delivered
FROM synthetic.grantee g LEFT JOIN synthetic.rhtp_report r ON r.grantee_id = g.grantee_id
GROUP BY g.network_name, g.program_initiative ORDER BY people_served DESC NULLS LAST;
```

**BEL-S2**: Which RHTP report cells must be suppressed because fewer than 11 people were served?

- Type in Ask AI: `Which RHTP report cells must be suppressed because fewer than 11 people were served?` (or just `BEL-S2`)
- Reads: `synthetic.rhtp_report`, `synthetic.grantee`, `synthetic.assumption`
- Returns now: 14 rows; columns `rhtp_report_id`, `network_name`, `county_fips`, `reporting_period`, `people_served`, `suppress_under`, `must_suppress`, `suppressed_flag`

```sql
SELECT r.rhtp_report_id, g.network_name, r.county_fips, r.reporting_period, r.people_served,
       t.threshold::int AS suppress_under, (r.people_served < t.threshold) AS must_suppress, r.suppressed_flag
FROM synthetic.rhtp_report r JOIN synthetic.grantee g ON g.grantee_id = r.grantee_id
CROSS JOIN (SELECT coalesce((SELECT value FROM synthetic.assumption WHERE assumption_code = 'suppress_under'), 11) AS threshold) t
ORDER BY (r.people_served < t.threshold OR r.suppressed_flag) DESC, r.people_served;
```

**BEL-S3**: How many clinic sites does each grantee network run, and how many are telehealth-capable?

- Type in Ask AI: `How many clinic sites does each grantee network run, and how many are telehealth-capable?` (or just `BEL-S3`)
- Reads: `synthetic.grantee`, `synthetic.clinic_site`
- Returns now: 4 rows; columns `network_name`, `sites`, `telehealth_capable`

```sql
SELECT g.network_name, count(cs.clinic_site_id) AS sites, count(*) FILTER (WHERE cs.telehealth_capable) AS telehealth_capable
FROM synthetic.grantee g LEFT JOIN synthetic.clinic_site cs ON cs.grantee_id = g.grantee_id
GROUP BY g.network_name ORDER BY sites DESC;
```

### Public data

**BEL-P1**: Which public datasets are loaded, and how many rows does each hold?

- Type in Ask AI: `Which public datasets are loaded, and how many rows does each hold?` (or just `BEL-P1`)
- Reads: 
- Returns now: 24 rows; columns `public_table`, `row_count`

```sql
SELECT t.table_name AS public_table,
       (xpath('/row/cnt/text()', query_to_xml(format('SELECT count(*) AS cnt FROM public_data.%I', t.table_name), false, true, '')))[1]::text::int AS row_count
FROM information_schema.tables t WHERE t.table_schema = 'public_data' ORDER BY t.table_name;
```

**BEL-P2**: What share of households have broadband in each of our six counties?

- Type in Ask AI: `What share of households have broadband in each of our six counties?` (or just `BEL-P2`)
- Reads: `public_data.acs_county`
- Returns now: 6 rows; columns `county`, `households`, `with_broadband`, `pct_households_broadband`, `no_internet`, `acs_release`

```sql
WITH six(fips, county) AS (VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill'))
SELECT six.county, a.households_internet_universe AS households, a.households_with_broadband_any_type AS with_broadband,
       a.pct_households_broadband, a.households_no_internet_access AS no_internet, a.acs_release
FROM six JOIN public_data.acs_county a ON a.county_fips = six.fips ORDER BY a.pct_households_broadband;
```

**BEL-P3**: How many health center sites, rural health clinics and critical access hospitals are in each of our six counties?

- Type in Ask AI: `How many health center sites, rural health clinics and critical access hospitals are in each of our six counties?` (or just `BEL-P3`)
- Reads: `public_data.health_center_sites`, `public_data.cms_pos_facilities`
- Returns now: 6 rows; columns `county`, `hrsa_health_center_sites`, `rural_health_clinics`, `critical_access_hospitals`, `fqhc_pos_records`

```sql
WITH six(fips, county) AS (VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill'))
SELECT six.county,
       (SELECT count(*) FROM public_data.health_center_sites h
         WHERE h.state_and_county_federal_information_processing_standard_code::bigint = six.fips) AS hrsa_health_center_sites,
       count(*) FILTER (WHERE f.hrsa_layer_name = 'Rural Health Clinics') AS rural_health_clinics,
       count(*) FILTER (WHERE f.hrsa_layer_name = 'Critical Access Hospitals') AS critical_access_hospitals,
       count(*) FILTER (WHERE f.hrsa_layer_name = 'Federally Qualified Health Centers') AS fqhc_pos_records
FROM six LEFT JOIN public_data.cms_pos_facilities f ON f.county_fips_derived = six.fips
GROUP BY six.fips, six.county ORDER BY six.county;
```

## HOLLOWAY - Denise Holloway (Community Health Worker, field)

Persona id in the app: `rain_holloway` · open: http://localhost:8184/ask?persona=rain_holloway

### Synthetic data

**HOL-S1**: Which open outreach tasks should I call first?

- Type in Ask AI: `Which open outreach tasks should I call first?` (or just `HOL-S1`)
- Reads: `synthetic.outreach_task`
- Returns now: 25 rows; columns `task_id`, `patient_id`, `task_type`, `priority_score`, `reason_summary`, `created_at`

```sql
SELECT ot.task_id, ot.patient_id, ot.task_type, ot.priority_score, ot.reason_summary, ot.created_at
FROM synthetic.outreach_task ot WHERE ot.closed_at IS NULL ORDER BY ot.priority_score DESC NULLS LAST LIMIT 25;
```

**HOL-S2**: Which reminders have no reply yet, and how were they sent?

- Type in Ask AI: `Which reminders have no reply yet, and how were they sent?` (or just `HOL-S2`)
- Reads: `synthetic.reminder_message`
- Returns now: 25 rows; columns `patient_id`, `channel`, `language`, `offset_hours`, `delivery_status`, `sent_at`

```sql
SELECT rm.patient_id, rm.channel, rm.language, rm.offset_hours, rm.delivery_status, rm.sent_at
FROM synthetic.reminder_message rm WHERE rm.reply IS NULL OR rm.reply = '' ORDER BY rm.sent_at DESC NULLS LAST LIMIT 25;
```

**HOL-S3**: Which patients have no SMS consent on file?

- Type in Ask AI: `Which patients have no SMS consent on file?` (or just `HOL-S3`)
- Reads: `synthetic.contact_preference`
- Returns now: 4024 rows; columns `patient_id`, `channel`, `language`, `consent_flag`, `updated_at`

```sql
SELECT cp.patient_id, cp.channel, cp.language, cp.consent_flag, cp.updated_at
FROM synthetic.contact_preference cp WHERE NOT cp.consent_flag ORDER BY cp.updated_at DESC NULLS LAST;
```

### Public data

**HOL-P1**: How many households have no vehicle or no internet in our six counties?

- Type in Ask AI: `How many households have no vehicle or no internet in our six counties?` (or just `HOL-P1`)
- Reads: `public_data.acs_county`
- Returns now: 6 rows; columns `county`, `households_no_vehicle`, `pct_households_no_vehicle`, `households_no_internet_access`, `total_population`

```sql
WITH six(fips, county) AS (VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill'))
SELECT six.county, a.households_no_vehicle, a.pct_households_no_vehicle, a.households_no_internet_access,
       a.total_population
FROM six JOIN public_data.acs_county a ON a.county_fips = six.fips ORDER BY a.pct_households_no_vehicle DESC;
```

**HOL-P2**: Which Nevada ZIP codes are more than an hour from the nearest health center?

- Type in Ask AI: `Which Nevada ZIP codes are more than an hour from the nearest health center?` (or just `HOL-P2`)
- Reads: `public_data.osrm_nearest_site`, `public_data.zcta_county`
- Returns now: 68 rows; columns `zcta`, `county`, `nearest_site`, `drive_minutes`, `drive_miles`

```sql
SELECT n.zcta, z.namelsad_county_20 AS county, n.site_name AS nearest_site, n.drive_minutes, n.drive_miles
FROM public_data.osrm_nearest_site n
LEFT JOIN public_data.zcta_county z ON z.geoid_zcta5_20 = n.zcta AND z.geoid_county_20 BETWEEN 32000 AND 32999
WHERE n.state = 'NV' AND n.drive_minutes > 60 ORDER BY n.drive_minutes DESC;
```

**HOL-P3**: How many census tracts in our six counties count as rural for FORHP?

- Type in Ask AI: `How many census tracts in our six counties count as rural for FORHP?` (or just `HOL-P3`)
- Reads: `public_data.forhp_rural_tracts`
- Returns now: 6 rows; columns `county`, `forhp_rural_tracts`, `report_year`

```sql
WITH six(fips, county) AS (VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill'))
SELECT six.county, count(t.census_tract_cd) AS forhp_rural_tracts, max(t.report_yr) AS report_year
FROM six LEFT JOIN public_data.forhp_rural_tracts t ON t.cmn_state_county_fips_cd::bigint = six.fips
GROUP BY six.county ORDER BY forhp_rural_tracts DESC;
```

## BROOKS - Kayla Brooks (Clinic Scheduler / Front Desk)

Persona id in the app: `rain_brooks` · open: http://localhost:8184/ask?persona=rain_brooks

### Synthetic data

**BRK-S1**: Which booked appointments carry the highest no-show risk?

- Type in Ask AI: `Which booked appointments carry the highest no-show risk?` (or just `BRK-S1`)
- Reads: `synthetic.appointment`, `synthetic.slot`
- Returns now: 25 rows; columns `appointment_id`, `patient_id`, `visit_mode`, `status`, `no_show_risk`, `slot_start`

```sql
SELECT a.appointment_id, a.patient_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id
ORDER BY a.no_show_risk DESC NULLS LAST LIMIT 25;
```

**BRK-S2**: What is the no-show history by visit type?

- Type in Ask AI: `What is the no-show history by visit type?` (or just `BRK-S2`)
- Reads: `synthetic.no_show_rate`
- Returns now: 1 row; columns `visit_type`, `patients`, `scheduled`, `no_shows`, `no_show_pct`

```sql
SELECT visit_type, count(*) AS patients, sum(scheduled_count) AS scheduled, sum(no_show_count) AS no_shows,
       round(100.0 * sum(no_show_count) / NULLIF(sum(scheduled_count), 0), 1) AS no_show_pct
FROM synthetic.no_show_rate GROUP BY visit_type ORDER BY no_show_pct DESC NULLS LAST;
```

**BRK-S3**: What did the eligibility checks return for upcoming appointments?

- Type in Ask AI: `What did the eligibility checks return for upcoming appointments?` (or just `BRK-S3`)
- Reads: `synthetic.eligibility_check`
- Returns now: 3 rows; columns `coverage_status`, `payer`, `checks`, `last_checked`

```sql
SELECT ec.coverage_status, ec.payer, count(*) AS checks, max(ec.checked_at) AS last_checked
FROM synthetic.eligibility_check ec GROUP BY ec.coverage_status, ec.payer ORDER BY checks DESC;
```

### Public data

**BRK-P1**: How long is the drive from Battle Mountain ZIP 89820 to the nearest health center sites?

- Type in Ask AI: `How long is the drive from Battle Mountain ZIP 89820 to the nearest health center sites?` (or just `BRK-P1`)
- Reads: `public_data.osrm_drive_times`
- Returns now: 5 rows; columns `rank`, `site_name`, `drive_minutes`, `drive_miles`, `straight_line_miles`, `osm_extract_date`

```sql
SELECT rank_by_drive_time AS rank, site_name, drive_minutes, drive_miles, straight_line_miles, osm_extract_date
FROM public_data.osrm_drive_times WHERE zcta = 89820 ORDER BY rank_by_drive_time;
```

**BRK-P2**: Which HRSA health center sites operate in our six counties, and how many hours a week?

- Type in Ask AI: `Which HRSA health center sites operate in our six counties, and how many hours a week?` (or just `BRK-P2`)
- Reads: `public_data.health_center_sites`
- Returns now: 6 rows; columns `county`, `site_name`, `site_city`, `operating_hours_per_week`, `health_center_location_type_description`

```sql
WITH six(fips, county) AS (VALUES (32007, 'Elko'), (32013, 'Humboldt'), (32015, 'Lander'), (32027, 'Pershing'), (32033, 'White Pine'), (32001, 'Churchill'))
SELECT six.county, h.site_name, h.site_city, h.operating_hours_per_week, h.health_center_location_type_description
FROM six JOIN public_data.health_center_sites h
  ON h.state_and_county_federal_information_processing_standard_code::bigint = six.fips
ORDER BY six.county, h.site_name;
```

**BRK-P3**: Which rural health clinics in Nevada are certified by CMS?

- Type in Ask AI: `Which rural health clinics in Nevada are certified by CMS?` (or just `BRK-P3`)
- Reads: `public_data.cms_pos_facilities`
- Returns now: 19 rows; columns `facility_nm`, `cms_provider_city`, `county`, `cms_provider_num`, `cms_provider_cat_sub_typ_desc`

```sql
SELECT facility_nm, cms_provider_city, county_name_derived AS county, cms_provider_num, cms_provider_cat_sub_typ_desc
FROM public_data.cms_pos_facilities
WHERE hrsa_layer_name = 'Rural Health Clinics' AND cms_provider_state_abbr = 'NV' ORDER BY county, facility_nm;
```

## OKAFOR - Dr. Samuel Okafor (Rural Provider)

Persona id in the app: `rain_okafor` · open: http://localhost:8184/ask?persona=rain_okafor

### Synthetic data

**OKA-S1**: Which appointments have a pre-visit summary, with risk tier and open gaps?

- Type in Ask AI: `Which appointments have a pre-visit summary, with risk tier and open gaps?` (or just `OKA-S1`)
- Reads: `synthetic.previsit_summary`, `synthetic.appointment`
- Returns now: 8 rows; columns `appointment_id`, `patient_id`, `risk_tier`, `top_reasons`, `open_gap_count`, `adherence_gap_flag`, `latest_bp`, `coding_recapture_flag` …

```sql
SELECT ps.appointment_id, ps.patient_id, ps.risk_tier, ps.top_reasons, ps.open_gap_count, ps.adherence_gap_flag,
       ps.latest_bp, ps.coding_recapture_flag, a.visit_mode
FROM synthetic.previsit_summary ps JOIN synthetic.appointment a ON a.appointment_id = ps.appointment_id
ORDER BY ps.open_gap_count DESC NULLS LAST LIMIT 25;
```

**OKA-S2**: Which patients take a medication with adherence under 80 percent?

- Type in Ask AI: `Which patients take a medication with adherence under 80 percent?` (or just `OKA-S2`)
- Reads: `synthetic.medication`
- Returns now: 25 rows; columns `patient_id`, `rxnorm_code`, `adherence_ratio`, `start_date`, `end_date`

```sql
SELECT patient_id, rxnorm_code, adherence_ratio, start_date, end_date
FROM synthetic.medication WHERE adherence_ratio < 0.8 ORDER BY adherence_ratio LIMIT 25;
```

**OKA-S3**: What is each patient's latest home blood pressure reading?

- Type in Ask AI: `What is each patient's latest home blood pressure reading?` (or just `OKA-S3`)
- Reads: `synthetic.remote_bp_reading`
- Returns now: 919 rows; columns `patient_id`, `value_systolic`, `value_diastolic`, `reading_time`, `device_type`, `counts_for_measure`

```sql
SELECT DISTINCT ON (patient_id) patient_id, value_systolic, value_diastolic, reading_time, device_type, counts_for_measure
FROM synthetic.remote_bp_reading ORDER BY patient_id, reading_time DESC NULLS LAST;
```

### Public data

**OKA-P1**: What does each quality gate measure count, per the CMS eCQM specification?

- Type in Ask AI: `What does each quality gate measure count, per the CMS eCQM specification?` (or just `OKA-P1`)
- Reads: `public_data.ecqm_measures`
- Returns now: 5 rows; columns `measure_family`, `ecqm_version_id`, `performance_period`, `title`, `improvement_notation`, `telehealth_eligible`, `url`

```sql
SELECT measure_family, ecqm_version_id, performance_period, title, improvement_notation, telehealth_eligible, url
FROM public_data.ecqm_measures
WHERE performance_period = (SELECT max(performance_period) FROM public_data.ecqm_measures) ORDER BY measure_family;
```

**OKA-P2**: What are the numerator and denominator of the blood pressure control measure CMS165?

- Type in Ask AI: `What are the numerator and denominator of the blood pressure control measure CMS165?` (or just `OKA-P2`)
- Reads: `public_data.ecqm_measures`
- Returns now: 2 rows; columns `ecqm_version_id`, `performance_period`, `initial_population`, `denominator`, `denominator_exclusions`, `numerator`

```sql
SELECT ecqm_version_id, performance_period, initial_population, denominator, denominator_exclusions, numerator
FROM public_data.ecqm_measures WHERE measure_family = 'CMS165' ORDER BY performance_period DESC;
```

**OKA-P3**: How have Nevada health centers trended on hypertension control and HbA1c poor control?

- Type in Ask AI: `How have Nevada health centers trended on hypertension control and HbA1c poor control?` (or just `OKA-P3`)
- Reads: `public_data.uds_state_national_cqm`
- Returns now: 10 rows; columns `measure`, `year`, `value`

```sql
SELECT measure, year, value FROM public_data.uds_state_national_cqm
WHERE geo_abbr = 'NV' AND (measure ILIKE '%blood pressure%' OR measure ILIKE '%A1c%') ORDER BY measure, year;
```

## LINDA GARCIA - patient, Battle Mountain (Lander County), synthetic anchor M-40107

Persona id in the app: `rain_linda` · open: http://localhost:8184/ask?persona=rain_linda · query pack persona: `patient_linda_garcia`

### Synthetic data

**GAR-S1**: What appointments do I have?

- Type in Ask AI: `What appointments do I have?` (or just `GAR-S1`)
- Reads: `synthetic.appointment`, `synthetic.slot`
- Returns now: 5 rows; columns `appointment_id`, `visit_mode`, `status`, `no_show_risk`, `slot_start`, `telehealth_flag`

```sql
SELECT a.appointment_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start, s.telehealth_flag
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id WHERE a.patient_id = 'M-40107';
```

**GAR-S2**: Which reminders were sent to me, and what did I reply?

- Type in Ask AI: `Which reminders were sent to me, and what did I reply?` (or just `GAR-S2`)
- Reads: `synthetic.reminder_message`
- Returns now: 3 rows; columns `channel`, `language`, `offset_hours`, `delivery_status`, `reply`, `sent_at`

```sql
SELECT channel, language, offset_hours, delivery_status, reply, sent_at
FROM synthetic.reminder_message WHERE patient_id = 'M-40107' ORDER BY sent_at;
```

**GAR-S3**: What are my home blood pressure readings?

- Type in Ask AI: `What are my home blood pressure readings?` (or just `GAR-S3`)
- Reads: `synthetic.remote_bp_reading`
- Returns now: 1 row; columns `value_systolic`, `value_diastolic`, `reading_time`, `device_type`, `counts_for_measure`

```sql
SELECT value_systolic, value_diastolic, reading_time, device_type, counts_for_measure
FROM synthetic.remote_bp_reading WHERE patient_id = 'M-40107' ORDER BY reading_time DESC;
```

### Public data

**GAR-P1**: How far do I drive from Battle Mountain to the nearest health center?

- Type in Ask AI: `How far do I drive from Battle Mountain to the nearest health center?` (or just `GAR-P1`)
- Reads: `public_data.osrm_nearest_site`
- Returns now: 1 row; columns `site_name`, `site_location_type`, `drive_minutes`, `drive_miles`, `straight_line_miles`, `origin_snap_meters`, `osm_extract_date`

```sql
SELECT site_name, site_location_type, drive_minutes, drive_miles, straight_line_miles, origin_snap_meters, osm_extract_date
FROM public_data.osrm_nearest_site WHERE zcta = 89820;
```

**GAR-P2**: What share of households in my county, Lander, have broadband?

- Type in Ask AI: `What share of households in my county, Lander, have broadband?` (or just `GAR-P2`)
- Reads: `public_data.acs_county`
- Returns now: 1 row; columns `county_name`, `households`, `households_with_broadband_any_type`, `pct_households_broadband`, `acs_release`

```sql
SELECT county_name, households_internet_universe AS households, households_with_broadband_any_type, pct_households_broadband, acs_release
FROM public_data.acs_county WHERE county_fips = 32015;
```

**GAR-P3**: What share of adults in my county, Lander, have high blood pressure?

- Type in Ask AI: `What share of adults in my county, Lander, have high blood pressure?` (or just `GAR-P3`)
- Reads: `public_data.cdc_places`
- Returns now: 2 rows; columns `county`, `measure`, `crude_prevalence_pct`, `low_confidence_limit`, `high_confidence_limit`, `year`

```sql
SELECT locationname AS county, measure, data_value AS crude_prevalence_pct, low_confidence_limit, high_confidence_limit, year
FROM public_data.cdc_places WHERE locationid = 32015 AND measureid IN ('BPHIGH', 'BPMED') AND data_value_type = 'Crude prevalence';
```

## ROSA MARTINEZ - patient, Fallon (Churchill County), synthetic anchor R-50214

Persona id in the app: `rain_rosa` · open: http://localhost:8184/ask?persona=rain_rosa · query pack persona: `patient_rosa_martinez`

### Synthetic data

**ROS-S1**: What appointments do I have, and how likely am I to miss one?

- Type in Ask AI: `What appointments do I have, and how likely am I to miss one?` (or just `ROS-S1`)
- Reads: `synthetic.appointment`, `synthetic.slot`
- Returns now: 6 rows; columns `appointment_id`, `visit_mode`, `status`, `no_show_risk`, `slot_start`, `telehealth_flag`

```sql
SELECT a.appointment_id, a.visit_mode, a.status, a.no_show_risk, s.slot_start, s.telehealth_flag
FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id WHERE a.patient_id = 'R-50214';
```

**ROS-S2**: What is my no-show history by visit type?

- Type in Ask AI: `What is my no-show history by visit type?` (or just `ROS-S2`)
- Reads: `synthetic.no_show_rate`
- Returns now: 1 row; columns `visit_type`, `window_months`, `scheduled_count`, `no_show_count`, `rate`, `computed_at`

```sql
SELECT visit_type, window_months, scheduled_count, no_show_count, rate, computed_at
FROM synthetic.no_show_rate WHERE patient_id = 'R-50214';
```

**ROS-S3**: Which reminders went to me, and by which channel?

- Type in Ask AI: `Which reminders went to me, and by which channel?` (or just `ROS-S3`)
- Reads: `synthetic.reminder_message`
- Returns now: 3 rows; columns `channel`, `language`, `offset_hours`, `delivery_status`, `reply`, `sent_at`

```sql
SELECT channel, language, offset_hours, delivery_status, reply, sent_at
FROM synthetic.reminder_message WHERE patient_id = 'R-50214' ORDER BY sent_at;
```

### Public data

**ROS-P1**: How far do I drive from Fallon to the nearest health center sites?

- Type in Ask AI: `How far do I drive from Fallon to the nearest health center sites?` (or just `ROS-P1`)
- Reads: `public_data.osrm_drive_times`
- Returns now: 5 rows; columns `rank`, `site_name`, `drive_minutes`, `drive_miles`, `osm_extract_date`

```sql
SELECT rank_by_drive_time AS rank, site_name, drive_minutes, drive_miles, osm_extract_date
FROM public_data.osrm_drive_times WHERE zcta = 89406 ORDER BY rank_by_drive_time;
```

**ROS-P2**: What share of households in my county, Churchill, have no vehicle?

- Type in Ask AI: `What share of households in my county, Churchill, have no vehicle?` (or just `ROS-P2`)
- Reads: `public_data.acs_county`
- Returns now: 1 row; columns `county_name`, `households`, `households_no_vehicle`, `pct_households_no_vehicle`, `acs_release`

```sql
SELECT county_name, households_vehicle_universe AS households, households_no_vehicle, pct_households_no_vehicle, acs_release
FROM public_data.acs_county WHERE county_fips = 32001;
```

**ROS-P3**: Is my county, Churchill, rural for FORHP, and what is its RUCC code?

- Type in Ask AI: `Is my county, Churchill, rural for FORHP, and what is its RUCC code?` (or just `ROS-P3`)
- Reads: `public_data.rucc_county`, `public_data.forhp_county_status`
- Returns now: 1 row; columns `county_nm`, `rural_status_desc`, `rucc_2023`, `rucc_description`

```sql
SELECT f.county_nm, f.rural_status_desc,
       (SELECT r.value FROM public_data.rucc_county r WHERE r.fips = 32001 AND r.attribute = 'RUCC_2023') AS rucc_2023,
       (SELECT r.value FROM public_data.rucc_county r WHERE r.fips = 32001 AND r.attribute = 'Description') AS rucc_description
FROM public_data.forhp_county_status f WHERE f.state_county_fips_cd = 32001;
```

## HANNAH LEE - Payer / Medicaid MCO Analyst (High Desert Health Plan, phase 2)

Persona id in the app: `rain_hannah` · open: http://localhost:8184/ask?persona=rain_hannah · query pack persona: `payer_hannah_lee`

### Synthetic data

**HAN-S1**: How many High Desert Health Plan members does each network carry, by Medicaid aid category?

- Type in Ask AI: `How many High Desert Health Plan members does each network carry, by Medicaid aid category?` (or just `HAN-S1`)
- Reads: `synthetic.contract_benchmark`, `synthetic.data_source`, `synthetic.attributed_member`, `synthetic.patient`, `synthetic.grantee`
- Returns now: 5 rows; columns `network_name`, `aid_category`, `members`, `pct_of_network`

```sql
WITH plan AS (
  SELECT cb.network_id, cb.expected_pmpm, cb.contract_start, cb.contract_year, cb.quality_gate_required, cb.quality_gate_total
  FROM synthetic.contract_benchmark cb
  WHERE cb.payer = 'High Desert Health Plan' AND cb.contract_year = (SELECT max(contract_year) FROM synthetic.contract_benchmark)),
thru AS (
  SELECT (date_trunc('quarter', max(ds.last_refreshed)
            - make_interval(days => (SELECT lag_days FROM synthetic.data_source WHERE data_source_id = 'SYN-claim')))
          + interval '3 months' - interval '1 day')::date AS period_end
  FROM synthetic.data_source ds),
mem AS (
  SELECT p.network_id, count(*) AS members
  FROM synthetic.attributed_member am JOIN synthetic.patient p ON p.patient_id = am.patient_id
  JOIN plan ON plan.network_id = p.network_id AND plan.contract_year = am.contract_year
  WHERE am.payer = 'High Desert Health Plan' GROUP BY p.network_id)
SELECT g.network_name, am.aid_category, count(*) AS members,
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY g.network_name), 1) AS pct_of_network
FROM synthetic.attributed_member am
JOIN synthetic.patient p ON p.patient_id = am.patient_id
JOIN plan ON plan.network_id = p.network_id AND plan.contract_year = am.contract_year
JOIN synthetic.grantee g ON g.grantee_id = p.network_id
WHERE am.payer = 'High Desert Health Plan'
GROUP BY g.network_name, am.aid_category ORDER BY g.network_name, members DESC;
```

**HAN-S2**: What does the plan pay per member per month at each network against the expected PMPM, and is each claims feed complete?

- Type in Ask AI: `What does the plan pay per member per month at each network against the expected PMPM, and is each claims feed complete?` (or just `HAN-S2`)
- Reads: `synthetic.contract_benchmark`, `synthetic.data_source`, `synthetic.attributed_member`, `synthetic.patient`, `synthetic.claim`, `synthetic.grantee`
- Returns now: 2 rows; columns `network_name`, `members`, `claims_through`, `months`, `actual_pmpm`, `expected_pmpm`, `pct_vs_expected`, `claim_types_received` …

```sql
WITH plan AS (
  SELECT cb.network_id, cb.expected_pmpm, cb.contract_start, cb.contract_year, cb.quality_gate_required, cb.quality_gate_total
  FROM synthetic.contract_benchmark cb
  WHERE cb.payer = 'High Desert Health Plan' AND cb.contract_year = (SELECT max(contract_year) FROM synthetic.contract_benchmark)),
thru AS (
  SELECT (date_trunc('quarter', max(ds.last_refreshed)
            - make_interval(days => (SELECT lag_days FROM synthetic.data_source WHERE data_source_id = 'SYN-claim')))
          + interval '3 months' - interval '1 day')::date AS period_end
  FROM synthetic.data_source ds),
mem AS (
  SELECT p.network_id, count(*) AS members
  FROM synthetic.attributed_member am JOIN synthetic.patient p ON p.patient_id = am.patient_id
  JOIN plan ON plan.network_id = p.network_id AND plan.contract_year = am.contract_year
  WHERE am.payer = 'High Desert Health Plan' GROUP BY p.network_id),
types AS (SELECT array_agg(DISTINCT claim_type ORDER BY claim_type) AS all_types FROM synthetic.claim),
cl AS (
  SELECT p.network_id, sum(c.allowed_amount) AS allowed, array_agg(DISTINCT c.claim_type ORDER BY c.claim_type) AS claim_types
  FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
  JOIN plan ON plan.network_id = p.network_id CROSS JOIN thru
  WHERE c.service_date BETWEEN plan.contract_start AND thru.period_end
  GROUP BY p.network_id)
SELECT g.network_name, mem.members, thru.period_end AS claims_through, ((extract(year FROM thru.period_end) * 12 + extract(month FROM thru.period_end)) - (extract(year FROM plan.contract_start) * 12 + extract(month FROM plan.contract_start)) + 1)::int AS months,
       round(cl.allowed / (mem.members * ((extract(year FROM thru.period_end) * 12 + extract(month FROM thru.period_end)) - (extract(year FROM plan.contract_start) * 12 + extract(month FROM plan.contract_start)) + 1)), 2) AS actual_pmpm, plan.expected_pmpm,
       round(100 * (cl.allowed / (mem.members * ((extract(year FROM thru.period_end) * 12 + extract(month FROM thru.period_end)) - (extract(year FROM plan.contract_start) * 12 + extract(month FROM plan.contract_start)) + 1)) - plan.expected_pmpm) / plan.expected_pmpm, 1) AS pct_vs_expected,
       array_to_string(cl.claim_types, ', ') AS claim_types_received,
       CASE WHEN cl.claim_types @> types.all_types THEN 'Complete'
            ELSE 'Partial: no ' || array_to_string(ARRAY(SELECT unnest(types.all_types) EXCEPT SELECT unnest(cl.claim_types)), ', ') || ' claims'
       END AS claims_feed
FROM plan JOIN mem ON mem.network_id = plan.network_id JOIN cl ON cl.network_id = plan.network_id
JOIN synthetic.grantee g ON g.grantee_id = plan.network_id CROSS JOIN thru CROSS JOIN types
ORDER BY g.network_name;
```

**HAN-S3**: How many avoidable ED visits per 1,000 plan members does each network have, annualized, against the benchmark?

- Type in Ask AI: `How many avoidable ED visits per 1,000 plan members does each network have, annualized, against the benchmark?` (or just `HAN-S3`)
- Reads: `synthetic.contract_benchmark`, `synthetic.data_source`, `synthetic.attributed_member`, `synthetic.patient`, `synthetic.claim`, `synthetic.utilization_benchmark`, `synthetic.grantee`
- Returns now: 3 rows; columns `network_name`, `members`, `avoidable_ed_visits_ytd`, `per_1000_annualized`, `benchmark_per_1000`, `visits_above_benchmark_per_year`, `avg_allowed_per_visit`

```sql
WITH plan AS (
  SELECT cb.network_id, cb.expected_pmpm, cb.contract_start, cb.contract_year, cb.quality_gate_required, cb.quality_gate_total
  FROM synthetic.contract_benchmark cb
  WHERE cb.payer = 'High Desert Health Plan' AND cb.contract_year = (SELECT max(contract_year) FROM synthetic.contract_benchmark)),
thru AS (
  SELECT (date_trunc('quarter', max(ds.last_refreshed)
            - make_interval(days => (SELECT lag_days FROM synthetic.data_source WHERE data_source_id = 'SYN-claim')))
          + interval '3 months' - interval '1 day')::date AS period_end
  FROM synthetic.data_source ds),
mem AS (
  SELECT p.network_id, count(*) AS members
  FROM synthetic.attributed_member am JOIN synthetic.patient p ON p.patient_id = am.patient_id
  JOIN plan ON plan.network_id = p.network_id AND plan.contract_year = am.contract_year
  WHERE am.payer = 'High Desert Health Plan' GROUP BY p.network_id),
ed AS (
  SELECT p.network_id, count(*) AS avoidable_ed_visits, sum(c.allowed_amount) AS allowed
  FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
  JOIN plan ON plan.network_id = p.network_id CROSS JOIN thru
  WHERE c.avoidable_ed_flag AND c.service_date BETWEEN plan.contract_start AND thru.period_end
  GROUP BY p.network_id),
bench AS (SELECT benchmark_value FROM synthetic.utilization_benchmark WHERE metric_code = 'avoidable_ed_per_1000'),
per AS (
  SELECT g.network_name, mem.members, ed.avoidable_ed_visits, ((extract(year FROM thru.period_end) * 12 + extract(month FROM thru.period_end)) - (extract(year FROM plan.contract_start) * 12 + extract(month FROM plan.contract_start)) + 1) AS months, ed.allowed
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
FROM totals t CROSS JOIN bench ORDER BY t.sort, t.network_name;
```

### Public data

**HAN-P1**: Where the plan's members live, how many preventable hospital stays and uninsured residents does each county have against Nevada?

- Type in Ask AI: `Where the plan's members live, how many preventable hospital stays and uninsured residents does each county have against Nevada?` (or just `HAN-P1`)
- Reads: `public_data.county_health_rankings`
- Returns now: 7 rows; columns `county`, `year`, `preventable_stays_per_100k_medicare`, `uninsured_pct`, `level`

```sql
SELECT county, year, v005_rawvalue AS preventable_stays_per_100k_medicare, round((100 * v085_rawvalue)::numeric, 1) AS uninsured_pct,
       CASE WHEN fipscode = 32000 THEN 'State' ELSE 'County' END AS level
FROM public_data.county_health_rankings
WHERE fipscode BETWEEN 32000 AND 32999 AND (fipscode = 32000 OR fipscode IN (32001, 32007, 32013, 32015, 32027, 32033))
ORDER BY fipscode = 32000 DESC, v005_rawvalue DESC NULLS LAST;
```

**HAN-P2**: How do the plan's counties compare with Nevada on primary care physicians, mental health providers and premature death?

- Type in Ask AI: `How do the plan's counties compare with Nevada on primary care physicians, mental health providers and premature death?` (or just `HAN-P2`)
- Reads: `public_data.county_health_rankings`
- Returns now: 7 rows; columns `county`, `year`, `primary_care_physicians_per_100k`, `mental_health_providers_per_100k`, `premature_death_ypll_per_100k`

```sql
SELECT county, year, round((100000 * v004_rawvalue)::numeric, 1) AS primary_care_physicians_per_100k,
       round((100000 * v062_rawvalue)::numeric, 1) AS mental_health_providers_per_100k,
       round(v001_rawvalue::numeric) AS premature_death_ypll_per_100k
FROM public_data.county_health_rankings
WHERE fipscode BETWEEN 32000 AND 32999 AND (fipscode = 32000 OR fipscode IN (32001, 32007, 32013, 32015, 32027, 32033))
ORDER BY fipscode = 32000 DESC, v004_rawvalue NULLS LAST;
```

**HAN-P3**: How common are COPD, asthma and coronary heart disease, the drivers of avoidable ED visits, in the plan's counties?

- Type in Ask AI: `How common are COPD, asthma and coronary heart disease, the drivers of avoidable ED visits, in the plan's counties?` (or just `HAN-P3`)
- Reads: `public_data.cdc_places`
- Returns now: 6 rows; columns `county`, `year`, `copd_pct`, `asthma_pct`, `coronary_heart_disease_pct`

```sql
SELECT locationname AS county, year,
       max(data_value) FILTER (WHERE measureid = 'COPD') AS copd_pct,
       max(data_value) FILTER (WHERE measureid = 'CASTHMA') AS asthma_pct,
       max(data_value) FILTER (WHERE measureid = 'CHD') AS coronary_heart_disease_pct
FROM public_data.cdc_places
WHERE locationid IN (32001, 32007, 32013, 32015, 32027, 32033) AND measureid IN ('COPD', 'CASTHMA', 'CHD') AND data_value_type = 'Crude prevalence'
GROUP BY locationname, year ORDER BY copd_pct DESC NULLS LAST;
```
