# RAIN v0.3 persona queries

Every query below was run against the `rain3` stack on 2026-11-06 and returned rows without errors (SQL as the backend login `rain_app`, read-only). Each one shows the row count and first row from that run.

**Totals:** 60 SQL queries (6 personas x 5 synthetic + 5 public) and 10 Cypher queries.

## How to run them

| Where | How |
|---|---|
| **pgAdmin** http://localhost:5051 (`admin@rain.app` / `admin`) | Servers → RAIN v3 → **RAIN v3 - postgres (admin)** → Databases → **rain_v3** → right-click → Query Tool. Paste a query and press **F5**. The same queries are in pgAdmin's file store as `rain_v3_persona_queries.sql` (Query Tool → Open File). |
| **Any SQL client** | `localhost:55435`, database `rain_v3`, user `postgres` / `root` (or `rain_app` / `rain_dev_pw`) |
| **Neo4j Browser** http://localhost:17476/browser/ | Connect URL `bolt://localhost:17689`, user `neo4j` / `password`, database `neo4j` |

## The data behind the queries

- **`synthetic` schema:** 38 tables generated from the v0.3 planned schema, 200 rows each. IDs join correctly across tables (patients, claims, providers, sites, campaigns, measures), and yes/no flags, statuses and dates are usable. Codes and names are generator filler words and numbers are random, so these queries show the **logic** each persona needs, not the demo's figures (the UI's $412 PMPM and 9,400 members come from data bundled in the frontend).
- **`public_data` schema:** real public data for Nevada and Tennessee: CDC PLACES (2022/2023), CDC/ATSDR SVI 2022, USDA RUCC 2023, HRSA shortage areas (primary care, mental health), HRSA health center sites, NPPES providers, Census ZCTAs.
- **The network's six counties:** Elko 32007 · Humboldt 32013 (Winnemucca) · Lander 32015 · Pershing 32027 · White Pine 32033 · Churchill 32001.

## Contents

- [CEO: Gregory Haskins, MBA](#ceo-gregory-haskins-mba)
- [CMO: Dr. Naomi Castellanos](#cmo-dr-naomi-castellanos)
- [CIO: Raj Malhotra](#cio-raj-malhotra)
- [State: Dr. Lauren Pike](#state-dr-lauren-pike)
- [CHW: Teresa Lopez, CHW](#chw-teresa-lopez-chw)
- [Access: Brandon Kee](#access-brandon-kee)
- [Neo4j: persona graph queries](#neo4j-persona-graph-queries)

## CEO Gregory Haskins, MBA

*Chief Executive Officer.* Focus: cost vs expected, quality gate, low-value care, sites, board brief.

### Synthetic data (`synthetic` schema)

#### CEO-S1: What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)?

```sql
SELECT count(DISTINCT am.patient_id)                                   AS attributed_members,
       count(c.claim_id)                                               AS claims,
       round(sum(c.allowed_amount)::numeric, 2)                        AS total_allowed,
       round((sum(c.allowed_amount) / NULLIF(count(DISTINCT am.patient_id), 0))::numeric, 2) AS allowed_per_member
FROM synthetic.attributed_member am
LEFT JOIN synthetic.claim c ON c.patient_id = am.patient_id;
```

Result: **1 row**. First row: `attributed_members = 136, claims = 225, total_allowed = 11641519.89, allowed_per_member = 85599.41`

#### CEO-S2: How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members?

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

Result: **1 row**. First row: `ed_claims = 107, avoidable_ed_claims = 87, admissions = 90, ed_per_1000 = 786.8, avoidable_ed_per_1000 = 639.7`

#### CEO-S3: Where is the low-value care? Top sites by low-value spend.

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

Result: **10 rows**. First row: `clinic_site_id = "CLINIC_S000189", site_name = "Maybe", low_value_findings = 4, low_value_allowed = 298400.49`

#### CEO-S4: How close are we to the quality gate? Rate vs target for every gate measure.

```sql
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
```

Result: **15 rows**. First row: `measure_code = "QUALITY_000004", measure_name = "Study", target_rate = 0.9576, lower_is_better = true, denominator = 3, numerator = 0, rate = 0.0`

#### CEO-S5: Compare our sites on cost per member.

```sql
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
```

Result: **10 rows**. First row: `clinic_site_id = "CLINIC_S000006", site_name = "Win", telehealth_capable = false, members_seen = 1, allowed = 98850.79, allowed_per_member = 98850.79`

### Public data (`public_data` schema)

#### CEO-P1: Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability.

```sql
WITH network(fips) AS (VALUES (32007),(32013),(32015),(32027),(32033),(32001))
SELECT s.county, s.fips, s.e_totpop AS population, r.value AS rucc_2023,
       round(s.rpl_themes::numeric, 3) AS svi_percentile, s.ep_pov150 AS pct_below_150_poverty, s.ep_uninsur AS pct_uninsured
FROM network n
JOIN public_data.svi_county s  ON s.fips = n.fips
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
ORDER BY s.e_totpop DESC;
```

Result: **6 rows**. First row: `county = "Elko County", fips = 32007, population = 53600, rucc_2023 = "5", svi_percentile = 0.619, pct_below_150_poverty = 19.2, pct_uninsured = 8.9`

#### CEO-P2: What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)?

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

Result: **6 rows**. First row: `county = "White Pine", high_bp_pct = 36.4, diabetes_pct = 12.6, obesity_pct = 34.4, smoking_pct = 17.5, copd_pct = 9.1`

#### CEO-P3: How do our counties compare with the Nevada county average on annual checkups and insurance gaps?

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

Result: **5 rows**. First row: `measureid = "ACCESS2", short_question_text = "Health Insurance", network_avg_pct = 13.6, nv_county_avg_pct = 12.6`

#### CEO-P4: Which of our counties have designated primary care shortage areas (HRSA HPSA), and how severe?

```sql
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
```

Result: **6 rows**. First row: `common_county_name = "Churchill County, NV", designated_hpsas = 3, max_hpsa_score = 19, designation_population = 45644.0, designation_types = "Geographic HPSA; Indian Health Service, Tribal Health, and Urban Indian Health Organizations; Rural Health Clinic"`

#### CEO-P5: Where does each of our counties rank among Nevada's 17 counties for high blood pressure?

```sql
SELECT * FROM (
    SELECT p.locationname AS county, p.locationid AS fips, p.data_value AS high_bp_pct,
           rank() OVER (ORDER BY p.data_value DESC) AS rank_of_17
    FROM public_data.cdc_places p
    WHERE p.stateabbr = 'NV' AND p.measureid = 'BPHIGH' AND p.data_value_type = 'Crude prevalence'
) ranked
WHERE fips IN (32007, 32013, 32015, 32027, 32033, 32001)
ORDER BY rank_of_17;
```

Result: **6 rows**. First row: `county = "White Pine", fips = 32033, high_bp_pct = 36.4, rank_of_17 = 9`

## CMO Dr. Naomi Castellanos

*Chief Medical Officer and Value-Based Care Quality Lead.* Focus: BP control, HbA1c, screening, Winnemucca low-value imaging, coding recapture.

### Synthetic data (`synthetic` schema)

#### CMO-S1: How close are we to each quality target? Performance gap per measure.

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

Result: **15 rows**. First row: `measure_code = "QUALITY_000050", measure_name = "Quite", gate_flag = null, target_rate = 0.7146, rate = 0.333, gap_to_target = -0.381, patients_in_denominator = 3`

#### CMO-S2: Which care gaps are still open, by measure?

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

Result: **15 rows**. First row: `measure_code = "QUALITY_000041", measure_name = "Strong", gaps = 4, never_closed = 0, pending = 1, oldest_opened = "2024-06-07"`

#### CMO-S3: Which patients with an open care gap have home BP readings that count toward the measure?

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

Result: **3 rows**. First row: `patient_id = "PATIENT000189", first_name = "Denise", last_name = "Garcia", readings_counting = 1, latest_reading = "2025-10-05T04:11:56", open_gaps = 1`

#### CMO-S4: Which providers order the most low-value services (the Winnemucca imaging question), and are they locums?

```sql
SELECT pr.provider_id, pr.first_name || ' ' || pr.last_name AS provider, pr.locum_flag, cs.site_name,
       count(lf.finding_id)                      AS low_value_findings,
       round(sum(lf.allowed_amount)::numeric, 2) AS low_value_allowed
FROM synthetic.low_value_finding lf
JOIN synthetic.provider pr         ON pr.provider_id = lf.ordering_provider_id
LEFT JOIN synthetic.clinic_site cs ON cs.clinic_site_id = lf.clinic_site_id
GROUP BY pr.provider_id, provider, pr.locum_flag, cs.site_name
ORDER BY low_value_findings DESC, low_value_allowed DESC NULLS LAST
LIMIT 10;
```

Result: **10 rows**. First row: `provider_id = "PROVIDER000106", provider = "Latoya Baldwin", locum_flag = true, site_name = "Investment", low_value_findings = 1, low_value_allowed = 99330.76`

#### CMO-S5: Which members need risk-coding recapture (documented condition not recaptured)?

```sql
SELECT c.patient_id, p.first_name, p.last_name,
       count(*)                                                                      AS conditions,
       count(*) FILTER (WHERE c.recaptured_year IS NULL OR c.recaptured_year < c.documented_year) AS not_recaptured
FROM synthetic.condition c
JOIN synthetic.patient p ON p.patient_id = c.patient_id
GROUP BY c.patient_id, p.first_name, p.last_name
HAVING count(*) FILTER (WHERE c.recaptured_year IS NULL OR c.recaptured_year < c.documented_year) > 0
ORDER BY not_recaptured DESC, conditions DESC
LIMIT 20;
```

Result: **20 rows**. First row: `patient_id = "PATIENT000081", first_name = "Leonard", last_name = "Ramirez", conditions = 4, not_recaptured = 3`

### Public data (`public_data` schema)

#### CMO-P1: How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada?

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

Result: **17 rows**. First row: `county = "White Pine", high_bp_pct = 36.4, on_bp_medication_pct = 74.7, grp = "network"`

#### CMO-P2: Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context).

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

Result: **17 rows**. First row: `county = "Esmeralda", diabetes_pct = 17.7, obesity_pct = 36.1, physical_inactivity_pct = 32.3, is_network_county = false`

#### CMO-P3: Preventive screening rates in our counties (colorectal, mammography, cholesterol).

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

Result: **6 rows**. First row: `county = "Pershing", colorectal_screening_pct = 56.1, mammography_pct = 72.4, cholesterol_screening_pct = 83.4`

#### CMO-P4: Social needs that block BP control in our counties (food, housing, transport, utilities, loneliness).

```sql
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
```

Result: **6 rows**. First row: `county = "Lander", food_insecurity_pct = 18.9, housing_insecurity_pct = 15.0, transport_barrier_pct = 10.4, utility_threat_pct = 10.1, loneliness_pct = 35.3`

#### CMO-P5: Mental health burden and designated mental health shortage areas in our counties.

```sql
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
```

Result: **6 rows**. First row: `county = "Lander", frequent_mental_distress_pct = 19.1, depression_pct = 22.8, designated_mh_hpsas = 4, max_mh_hpsa_score = 17`

## CIO Raj Malhotra

*Chief Information Officer and Data and AI Governance Lead.* Focus: model subgroup check, model card, data freshness, social needs coverage, patient matching, public data feeds.

### Synthetic data (`synthetic` schema)

#### CIO-S1: Show the model cards: release status, sign-off and how many subgroup checks each passed.

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

Result: **15 rows**. First row: `model_version = "MODEL_CA000002", model_name = "Whether", release_status = "active", access_adjusted_flag = false, signed_off_by = "always", cosigned_by = "magazine", subgroup_checks = 3, passed = 0, failed = 3`

#### CIO-S2: Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold.

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

Result: **20 rows**. First row: `model_version = "MODEL_CA000002", subgroup = "whether", comparison_group = "series", metric = "situation", gap_percent = 0.9121, threshold_percent = 0.017, over_threshold_by = 0.8951, passed = false, checked_at = "2026-09-01T21:59:00"`

#### CIO-S3: How fresh is each data source? Latest record per feed and lag in days.

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

Result: **7 rows**. First row: `feed = "Eligibility (270/271)", latest = "2026-10-28T07:40:49", days_since_latest = 9, rows = 200`

#### CIO-S4: Show records that failed patient matching (patient_id missing or not in the patient master).

```sql
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
```

Result: **7 rows**. First row: `src = "appointment", records = 200, null_patient_id = 0, unmatched_patient_id = 0, failed_matching = 0`

#### CIO-S5: Social needs coverage: how many attributed members have at least one SDOH screening?

```sql
SELECT count(DISTINCT am.patient_id)                                           AS attributed_members,
       count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NOT NULL)   AS screened,
       count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NULL)       AS missing_screening,
       round(100.0 * count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NOT NULL)
             / NULLIF(count(DISTINCT am.patient_id), 0), 1)                     AS coverage_pct
FROM synthetic.attributed_member am
LEFT JOIN synthetic.sdoh_screening s ON s.patient_id = am.patient_id;
```

Result: **1 row**. First row: `attributed_members = 136, screened = 94, missing_screening = 42, coverage_pct = 69.1`

### Public data (`public_data` schema)

#### CIO-P1: What public data feeds the county view? Row counts and state coverage per public table.

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

Result: **8 rows**. First row: `dataset = "zcta_centroids", rows = 33791, states = null, vintage = "2023 Gazetteer"`

#### CIO-P2: CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state.

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

Result: **4 rows**. First row: `stateabbr = "NV", data_value_type = "Age-adjusted prevalence", measures = 40, counties = 17, cells = 680, missing_values = 0, ci_wider_than_10pts = 99`

#### CIO-P3: Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS?

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

Result: **17 rows**. First row: `fips = 32001, county = "Churchill County", in_rucc = true, in_cdc_places = true, has_any_pc_hpsa = true`

#### CIO-P4: HRSA HPSA status mix and data volume by discipline (primary care vs mental health) in Nevada.

```sql
SELECT 'primary care' AS discipline, hpsa_status, count(*) AS hpsas, count(DISTINCT common_county_name) AS counties
FROM public_data.hpsa_primary_care WHERE primary_state_abbreviation = 'NV' GROUP BY hpsa_status
UNION ALL
SELECT 'mental health', hpsa_status, count(*), count(DISTINCT common_county_name)
FROM public_data.hpsa_mental_health WHERE primary_state_abbreviation = 'NV' GROUP BY hpsa_status
ORDER BY discipline, hpsas DESC;
```

Result: **6 rows**. First row: `discipline = "mental health", hpsa_status = "Withdrawn", hpsas = 1093, counties = 18`

#### CIO-P5: NPPES provider data quality: completeness and duplicate NPIs by state and entity type.

```sql
SELECT state, enumeration_type,
       count(*)                                         AS providers,
       count(DISTINCT npi)                              AS distinct_npis,
       count(*) - count(DISTINCT npi)                   AS duplicate_rows,
       count(*) FILTER (WHERE taxonomy IS NULL OR taxonomy = '') AS missing_taxonomy,
       count(*) FILTER (WHERE zip IS NULL)              AS missing_zip
FROM public_data.providers
GROUP BY state, enumeration_type
ORDER BY state, enumeration_type;
```

Result: **4 rows**. First row: `state = "NV", enumeration_type = "NPI-1", providers = 6571, distinct_npis = 6571, duplicate_rows = 0, missing_taxonomy = 11, missing_zip = 0`

## State Dr. Lauren Pike

*Program Lead, Rural Health Outcomes Accelerator.* Focus: county view, primary care visits, low-value care across networks, broadband vs telehealth, funding.

### Synthetic data (`synthetic` schema)

#### STATE-S1: Primary care visits by month (is volume down since January?), with telehealth share.

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

Result: **23 rows**. First row: `month = "2025-01-01", encounters = 8, telehealth = 4, telehealth_pct = 50.0`

#### STATE-S2: Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth.

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

Result: **3 rows**. First row: `telehealth_capable = true, sites = 106, encounters = 98, telehealth_pct = 50.0`

#### STATE-S3: Where does broadband block telehealth? Share of coverage records not served, by technology.

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

Result: **15 rows**. First row: `technology = null, coverage_records = 7, not_served = 4, not_served_pct = 57.1`

#### STATE-S4: Rural and frontier mix of the areas in view (FORHP rural, frontier flags).

```sql
SELECT rc.forhp_rural_flag, rc.frontier_flag,
       count(*)                        AS areas,
       count(DISTINCT rc.county_fips)  AS counties
FROM synthetic.rural_classification rc
GROUP BY rc.forhp_rural_flag, rc.frontier_flag
ORDER BY rc.frontier_flag DESC NULLS LAST, rc.forhp_rural_flag DESC NULLS LAST;
```

Result: **9 rows**. First row: `forhp_rural_flag = true, frontier_flag = true, areas = 45, counties = 43`

#### STATE-S5: Small-cell suppression: how many county metric cells are suppressed before the state can publish?

```sql
SELECT cm.suppressed_flag,
       count(*)                          AS cells,
       count(DISTINCT cm.county_fips)    AS counties,
       count(DISTINCT cm.metric_code)    AS metrics,
       min(cm.year)                      AS min_year,
       max(cm.year)                      AS max_year
FROM synthetic.county_metric cm
GROUP BY cm.suppressed_flag
ORDER BY cm.suppressed_flag DESC NULLS LAST;
```

Result: **3 rows**. First row: `suppressed_flag = true, cells = 92, counties = 86, metrics = 84, min_year = 61, max_year = 988`

### Public data (`public_data` schema)

#### STATE-P1: The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs.

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

Result: **17 rows**. First row: `county = "Esmeralda County", fips = 32009, population = 980, rucc_2023 = "9", svi_percentile = 0.908, designated_pc_hpsas = 1, sierra_basin_county = false`

#### STATE-P2: Metro vs rural vs frontier-like: Nevada population and county count by RUCC group.

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

Result: **3 rows**. First row: `rucc_group = "1-3 metro", counties = 5, population = 2874379.0, counties_in_group = "Carson City, Clark County, Lyon County, Storey County, Washoe County"`

#### STATE-P3: Primary care shortage counties: designated primary care HPSAs by county, type and severity.

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

Result: **25 rows**. First row: `common_county_name = "Clark County, NV", designation_type = "Federally Qualified Health Center", designated_hpsas = 4, max_score = 22, avg_score = 20.0, designation_population = 1538488.0`

#### STATE-P4: Where does broadband limit telehealth? Households without internet (SVI) by county, worst first.

```sql
SELECT s.county, s.fips, s.ep_noint AS pct_households_no_internet, s.e_noint AS households_no_internet,
       r.value AS rucc_2023, s.fips IN (32007,32013,32015,32027,32033,32001) AS sierra_basin_county
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY s.ep_noint DESC;
```

Result: **17 rows**. First row: `county = "Nye County", fips = 32023, pct_households_no_internet = 22.4, households_no_internet = 4884, rucc_2023 = "4", sierra_basin_county = false`

#### STATE-P5: Health center site coverage per 100,000 residents by Nevada county (where do Accelerator funds go first?).

```sql
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
```

Result: **17 rows**. First row: `county = "Lyon County", population = 59435, health_center_sites = 0, sites_per_100k = 0.0, rucc_2023 = "2"`

## CHW Teresa Lopez, CHW

*Community Health Worker and Care Coordinator.* Focus: worklist, closest to BP control, unanswered reminders, campaign progress, Spanish outreach.

### Synthetic data (`synthetic` schema)

#### CHW-S1: Open my worklist: open outreach tasks by priority, with who to call.

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

Result: **25 rows**. First row: `task_id = "OUTREACH000160", priority_score = 0.9965, task_type = "standard", status = "active", patient_id = "PATIENT000062", patient = "Eric Collins", phone = "367.697.6438x156", created_at = "2025-11-20T03:21:04", reason = "Race position where detail."`

#### CHW-S2: How is the campaign going? Members, cuffs on file and bookings per campaign.

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

Result: **15 rows**. First row: `campaign_id = "CAMPAIGN000031", campaign_name = "Method", status = "rejected", target_count = 252, members = 4, cuff_on_file = 2, booked = 3, booked_pct = 75.0`

#### CHW-S3: Who has not answered reminders? Patients with reminders that got no reply or are still pending.

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

Result: **20 rows**. First row: `patient_id = "PATIENT000096", patient = "Elizabeth Schmidt", phone = "(708)626-7734", reminders = 5, unanswered = 2, last_sent = "2026-10-29T03:17:01", channels = "enterprise, premium, standard"`

#### CHW-S4: Who is closest to BP control? Campaign members with their latest home BP reading.

```sql
SELECT DISTINCT ON (cm.patient_id)
       cm.patient_id, p.first_name || ' ' || p.last_name AS patient, cm.outreach_rank, cm.cuff_on_file,
       b.value_systolic, b.value_diastolic, b.reading_time::timestamp AS reading_time, b.counts_for_measure
FROM synthetic.campaign_member cm
JOIN synthetic.patient p            ON p.patient_id = cm.patient_id
JOIN synthetic.remote_bp_reading b  ON b.patient_id = cm.patient_id
ORDER BY cm.patient_id, b.reading_time::timestamp DESC
LIMIT 25;
```

Result: **25 rows**. First row: `patient_id = "PATIENT000002", patient = "Jeffrey Lawrence", outreach_rank = 661, cuff_on_file = true, value_systolic = 41774.8, value_diastolic = 23075.02, reading_time = "2026-06-05T15:03:28", counts_for_measure = false`

#### CHW-S5: How should I reach each patient? Consented contact channel and language preferences.

```sql
SELECT cp.channel, cp.consent_flag,
       count(DISTINCT cp.patient_id) AS patients,
       count(DISTINCT cp.language)   AS languages_recorded
FROM synthetic.contact_preference cp
GROUP BY cp.channel, cp.consent_flag
ORDER BY cp.consent_flag DESC NULLS LAST, patients DESC;
```

Result: **18 rows**. First row: `channel = "premium", consent_flag = true, patients = 19, languages_recorded = 19`

### Public data (`public_data` schema)

#### CHW-P1: Where can I send patients? Health center sites in or near our counties, with hours and phone.

```sql
SELECT hc.complete_county_name, hc.site_city, hc.site_name, hc.site_address,
       hc.site_telephone_number, hc.operating_hours_per_week, hc.health_center_type_description
FROM public_data.health_center_sites hc
WHERE hc.site_state_abbreviation = 'NV'
  AND hc.complete_county_name IN ('Elko County','Humboldt County','Lander County','Pershing County',
                                  'White Pine County','Churchill County','Lyon County','Eureka County')
ORDER BY hc.complete_county_name, hc.site_city;
```

Result: **6 rows**. First row: `complete_county_name = "Elko County", site_city = "Carlin", site_name = "Carlin Community Health Center", site_address = "310 Memory Ln", site_telephone_number = "775-754-2666", operating_hours_per_week = 40.0, health_center_type_description = "Service Delivery Site"`

#### CHW-P2: Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI).

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

Result: **6 rows**. First row: `county = "Lander", transport_barrier_pct = 10.4, pct_households_no_vehicle = 2.4, county_area_sqmi = 5519.24436764232`

#### CHW-P3: Talking points on social needs: food, housing, utility and food-stamp rates in our counties.

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

Result: **6 rows**. First row: `county = "Lander", food_insecurity_pct = 18.9, food_stamps_pct = 17.2, housing_insecurity_pct = 15.0, utility_shutoff_threat_pct = 10.1, lacks_social_support_pct = 25.6`

#### CHW-P4: Do I need Spanish talking points? Hispanic share and limited-English households by county (SVI).

```sql
SELECT s.county, s.e_totpop AS population,
       s.ep_hisp   AS pct_hispanic,
       s.ep_limeng AS pct_limited_english,
       s.ep_age65  AS pct_age_65_plus
FROM public_data.svi_county s
WHERE s.fips IN (32007, 32013, 32015, 32027, 32033, 32001)
ORDER BY s.ep_limeng DESC;
```

Result: **6 rows**. First row: `county = "Humboldt County", population = 17266, pct_hispanic = 27.9, pct_limited_english = 3.6, pct_age_65_plus = 15.4`

#### CHW-P5: Which primary care practices (NPPES) are in our towns: Elko, Winnemucca, Fallon, Ely, Lovelock, Battle Mountain?

```sql
SELECT pr.city, pr.taxonomy, count(*) AS providers,
       count(*) FILTER (WHERE pr.enumeration_type = 'NPI-2') AS organizations,
       count(*) FILTER (WHERE pr.enumeration_type = 'NPI-1') AS individuals
FROM public_data.providers pr
WHERE pr.state = 'NV'
  AND upper(pr.city) IN ('ELKO', 'WINNEMUCCA', 'FALLON', 'ELY', 'LOVELOCK', 'BATTLE MOUNTAIN')
GROUP BY pr.city, pr.taxonomy
ORDER BY pr.city, providers DESC;
```

Result: **97 rows**. First row: `city = "BATTLE MOUNTAIN", taxonomy = "Ambulance, Land Transport", providers = 2, organizations = 2, individuals = 0`

## Access Brandon Kee

*Patient Access Coordinator.* Focus: bookings, unconfirmed visits, reminder replies, long drives and telehealth, open slots.

### Synthetic data (`synthetic` schema)

#### ACCESS-S1: What slots are open? Open slots by site, in-person vs telehealth.

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

Result: **20 rows**. First row: `clinic_site_id = "CLINIC_S000109", site_name = "Only", telehealth_flag = true, slots = 6, open_slots = 3, first_slot = "2024-01-13T05:13:08"`

#### ACCESS-S2: Show unconfirmed visits: pending appointments and whether eligibility was verified.

```sql
SELECT a.appointment_id, a.status, a.visit_mode, a.booked_at::timestamp AS booked_at,
       p.first_name || ' ' || p.last_name AS patient, p.phone,
       ec.coverage_status, ec.checked_at::timestamp AS eligibility_checked_at
FROM synthetic.appointment a
JOIN synthetic.patient p                ON p.patient_id = a.patient_id
LEFT JOIN synthetic.eligibility_check ec ON ec.appointment_id = a.appointment_id
WHERE a.status = 'pending' OR a.status IS NULL
ORDER BY ec.checked_at NULLS FIRST, a.booked_at NULLS LAST
LIMIT 25;
```

Result: **25 rows**. First row: `appointment_id = "APPOINTM000178", status = "pending", visit_mode = "recently", booked_at = "2023-12-24T03:51:38", patient = "Julia Tapia", phone = "001-689-241-3435x24082", coverage_status = null, eligibility_checked_at = null`

#### ACCESS-S3: Handle the replies: reminder replies waiting for action, by channel and delivery status.

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

Result: **33 rows**. First row: `channel = "basic", delivery_status = "approved", messages = 12, with_reply = 12, patients = 12, avg_hours_before_visit = 520.7`

#### ACCESS-S4: Why telehealth for this patient? Longest drive times and whether the site can do telehealth.

```sql
SELECT tt.patient_zcta, cs.clinic_site_id, cs.site_name, cs.telehealth_capable,
       round(tt.drive_minutes::numeric, 1) AS drive_minutes,
       CASE WHEN tt.drive_minutes > 60 AND cs.telehealth_capable THEN 'offer telehealth'
            WHEN tt.drive_minutes > 60 THEN 'long drive, no telehealth at site'
            ELSE 'in-person ok' END AS recommendation
FROM synthetic.travel_time tt
JOIN synthetic.clinic_site cs ON cs.clinic_site_id = tt.clinic_site_id
ORDER BY tt.drive_minutes DESC NULLS LAST
LIMIT 20;
```

Result: **20 rows**. First row: `patient_zcta = "religious", clinic_site_id = "CLINIC_S000097", site_name = "Year", telehealth_capable = true, drive_minutes = 99938.4, recommendation = "offer telehealth"`

#### ACCESS-S5: Start bookings: campaign members not yet booked, highest outreach rank first, with visit mode.

```sql
SELECT cm.outreach_rank, cm.patient_id, p.first_name || ' ' || p.last_name AS patient, p.phone,
       cm.recommended_visit_mode, cm.cuff_on_file, c.campaign_name
FROM synthetic.campaign_member cm
JOIN synthetic.patient p   ON p.patient_id = cm.patient_id
JOIN synthetic.campaign c  ON c.campaign_id = cm.campaign_id
WHERE NOT cm.booked_flag
ORDER BY cm.outreach_rank NULLS LAST
LIMIT 25;
```

Result: **25 rows**. First row: `outreach_rank = 3, patient_id = "PATIENT000197", patient = "Roy Hawkins", phone = null, recommended_visit_mode = "newspaper", cuff_on_file = true, campaign_name = "Parent"`

### Public data (`public_data` schema)

#### ACCESS-P1: How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx).

```sql
SELECT z.geoid AS zcta, round(z.aland_sqmi::numeric, 1) AS land_sq_mi,
       z.intptlat AS lat, z.intptlong AS lon
FROM public_data.zcta_centroids z
WHERE z.geoid BETWEEN '89400' AND '89899'
ORDER BY z.aland_sqmi DESC
LIMIT 20;
```

Result: **20 rows**. First row: `zcta = "89412", land_sq_mi = 3084.5, lat = 41.121163, lon = -119.704982`

#### ACCESS-P2: Health center capacity: operating hours per week of sites in Nevada's rural counties.

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

Result: **4 rows**. First row: `complete_county_name = "Elko County", sites = 5, total_hours_per_week = 197.0, avg_hours_per_site = 39.4`

#### ACCESS-P3: Primary care capacity gap: HPSA FTE shortage and population affected in our counties.

```sql
SELECT h.common_county_name, h.hpsa_name, h.designation_type, h.hpsa_score,
       h.hpsa_fte, h.hpsa_shortage, h.hpsa_designation_population, h.hpsa_formal_ratio
FROM public_data.hpsa_primary_care h
WHERE h.hpsa_status = 'Designated'
  AND h.common_county_name IN ('Elko County, NV','Humboldt County, NV','Lander County, NV',
                               'Pershing County, NV','White Pine County, NV','Churchill County, NV')
ORDER BY h.hpsa_score DESC NULLS LAST, h.hpsa_designation_population DESC NULLS LAST;
```

Result: **22 rows**. First row: `common_county_name = "Churchill County, NV", hpsa_name = "FALLON TRIBAL HEALTH CENTER", designation_type = "Indian Health Service, Tribal Health, and Urban Indian Health Organizations", hpsa_score = 19, hpsa_fte = null, hpsa_shortage = null, hpsa_designation_population = 3172.0, hpsa_formal_ratio = `

#### ACCESS-P4: Primary care providers by town in our region (NPPES: family, internal medicine, NP, PA, clinics).

```sql
SELECT upper(pr.city) AS town, count(*) AS primary_care_providers
FROM public_data.providers pr
WHERE pr.state = 'NV'
  AND upper(pr.city) IN ('ELKO', 'WINNEMUCCA', 'FALLON', 'ELY', 'LOVELOCK', 'BATTLE MOUNTAIN', 'WELLS', 'CARLIN')
  AND (pr.taxonomy ILIKE '%family%' OR pr.taxonomy ILIKE '%internal medicine%' OR pr.taxonomy ILIKE '%nurse practitioner%'
       OR pr.taxonomy ILIKE '%physician assistant%' OR pr.taxonomy ILIKE '%clinic%' OR pr.taxonomy ILIKE '%general practice%')
GROUP BY upper(pr.city)
ORDER BY primary_care_providers DESC;
```

Result: **7 rows**. First row: `town = "ELKO", primary_care_providers = 42`

#### ACCESS-P5: Expect eligibility problems? Uninsured and no-checkup rates in our counties.

```sql
SELECT p.locationname AS county,
       max(p.data_value) FILTER (WHERE p.measureid = 'ACCESS2') AS uninsured_18_64_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'CHECKUP') AS annual_checkup_pct,
       max(p.data_value) FILTER (WHERE p.measureid = 'DENTAL')  AS dental_visit_pct
FROM public_data.cdc_places p
WHERE p.stateabbr = 'NV' AND p.data_value_type = 'Crude prevalence'
  AND p.locationid IN (32007, 32013, 32015, 32027, 32033, 32001)
GROUP BY p.locationname
ORDER BY uninsured_18_64_pct DESC;
```

Result: **6 rows**. First row: `county = "Pershing", uninsured_18_64_pct = 15.0, annual_checkup_pct = 70.9, dental_visit_pct = 56.4`

## Neo4j: persona graph queries

The v0.3 release is scoped by `release = 'rain-v3.0.0'`. Query personas by label: a plain `MATCH (n {release:'rain-v3.0.0'}) RETURN n LIMIT 300` returns only columns, classes and tables (295 of the 523 nodes are columns) and never reaches the 7 Persona nodes. The same database also holds 11 older v0.2 Persona nodes, which have no `release` property.

#### KAG-1: The seven v0.3 personas (table view)

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})
RETURN p.order AS order, p.name AS name, p.role AS role, p.key AS key,
       size(coalesce(p.suggested_queries, [])) AS suggested_queries
ORDER BY p.order;
```

Result: **7 rows**.

#### KAG-2: Every v0.3 persona with everything it links to (graph view)

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})-[r]->(x)
RETURN p, r, x;
```

Result: **84 rows**.

#### KAG-3: One persona's neighbourhood (swap the key: GregoryHaskins, NaomiCastellanos, RajMalhotra, LaurenPike, TeresaLopez, BrandonKee, LindaGarcia)

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0', key: 'persona:GregoryHaskins'})-[r]-(x)
RETURN p, r, x;
```

Result: **18 rows**.

#### KAG-4: Priority signals per persona

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:HAS_SIGNAL]->(s:Signal)
RETURN p.name AS persona, s.name AS signal, s.severity AS severity, s.detail AS detail
ORDER BY p.order, s.severity;
```

Result: **12 rows**.

#### KAG-5: The PRD's suggested questions per persona (each one is answered by that persona's UI)

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})
UNWIND coalesce(p.suggested_queries, []) AS question
RETURN p.name AS persona, question
ORDER BY p.order;
```

Result: **28 rows**.

#### KAG-6: Guided conversation steps per persona, in order

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:HAS_STEP]->(s:Step)
RETURN p.name AS persona, s.step AS step, s.user_prompt AS user_prompt,
       s.visualization AS visualization, s.data_sources AS data_sources
ORDER BY p.order, s.step;
```

Result: **16 rows**.

#### KAG-7: What data each persona's workbenches read: Persona -> Workbench -> Class -> Table (planned schema)

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:USES]->(w:Workbench)-[:READS]->(c:Class)-[:MAPS_TO]->(t:Table)
RETURN p.name AS persona, w.name AS workbench,
       collect(DISTINCT c.name) AS classes, collect(DISTINCT t.name) AS tables
ORDER BY persona, workbench;
```

Result: **16 rows**.

#### KAG-8: Same lineage as a graph (one persona; swap the key)

```cypher
MATCH path = (p:Persona {release: 'rain-v3.0.0', key: 'persona:NaomiCastellanos'})-[:USES]->(:Workbench)
             -[:READS]->(:Class)-[:MAPS_TO]->(:Table)
RETURN path;
```

Result: **23 rows**.

#### KAG-9: The v0.3 release without column detail (228 nodes; personas included)

```cypher
MATCH (n {release: 'rain-v3.0.0'})
WHERE NOT n:Column
OPTIONAL MATCH (n)-[r]->(m {release: 'rain-v3.0.0'})
WHERE NOT m:Column
RETURN n, r, m;
```

Result: **481 rows**.

#### KAG-10: Contract checkpoint the operator personas view

```cypher
MATCH (p:Persona {release: 'rain-v3.0.0'})-[:VIEWS]->(c:Checkpoint)
RETURN c.name AS checkpoint, c.actual_pmpm AS actual_pmpm, c.expected_pmpm AS expected_pmpm,
       c.pct_above_expected AS pct_above_expected, c.annualized_gap_usd AS annualized_gap_usd,
       c.days_left AS days_left, collect(p.name) AS viewed_by;
```

Result: **1 rows**.
