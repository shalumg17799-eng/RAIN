# RAIN v0.3: which backend API each persona calls, plus synthetic and public data queries (verified)

Every API call, page and query below was captured from real runs against the `rain3` stack on 2026-11-06:
a browser session per persona (console logs and `window.__RAIN_API_CALLS__`), and each persona query called
through the UI's own address (http://localhost:8183) and matched by request id to the backend's log.

## Summary

| Persona | UI API calls (all HTTP 200) | Pages and their backend datasets logged | Synthetic data queries | Public data queries | Typed in the chat | Console `rainQuery()` |
|---|---|---|---|---|---|---|
| CEO: Gregory Haskins, MBA | 6/6 ✅ | 6 | **5/5** ✅ | **5/5** ✅ | **10/10** ✅ | CEO-S1 = 1 rows, CEO-P1 = 6 rows ✅ |
| CMO: Dr. Naomi Castellanos | 6/6 ✅ | 7 | **5/5** ✅ | **5/5** ✅ | **10/10** ✅ | CMO-S1 = 15 rows, CMO-P1 = 17 rows ✅ |
| CIO: Raj Malhotra | 6/6 ✅ | 4 | **5/5** ✅ | **5/5** ✅ | **10/10** ✅ | CIO-S1 = 15 rows, CIO-P1 = 8 rows ✅ |
| State: Dr. Lauren Pike | 6/6 ✅ | 5 | **5/5** ✅ | **5/5** ✅ | **10/10** ✅ | STATE-S1 = 23 rows, STATE-P1 = 17 rows ✅ |
| CHW: Teresa Lopez, CHW | 6/6 ✅ | 5 | **5/5** ✅ | **5/5** ✅ | **10/10** ✅ | CHW-S1 = 25 rows, CHW-P1 = 6 rows ✅ |
| Access: Brandon Kee | 6/6 ✅ | 5 | **5/5** ✅ | **5/5** ✅ | **10/10** ✅ | ACCESS-S1 = 20 rows, ACCESS-P1 = 20 rows ✅ |

**60/60 queries working**: each returned HTTP 200 with rows, and the backend logged it twice under the same
request id (the query line and the request line). Typed into that persona's chat in the real UI, every question
also answers with a live table (60/60). Backend tests pass 168/168, including all 60
queries through the API and through the chat.

## 1. How to see which backend API is called

### In the browser console (DevTools → Console at http://localhost:8183)

Lines look like this (captured from the State persona's run):

```
RAIN Data loaded from the backend: 83 datasets, 410 KB in 112 ms
RAIN GET /api/v3/queries?persona=rain_state → 200 in 12 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request b17311d922e1 · data query pack doc/queries/rain_v3_persona_queries.sql
RAIN rain_state: 10 backend queries (5 synthetic data, 5 public data). Run one with rainQuery('STATE-S1')
RAIN GET /api/v3/ui/briefing?clientId=rain&personaId=rain_state → 200 in 59 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request 2e5689fe260d · data postgres://rain_v3/ui_v3.dataset (contracts.state, built live) · turn st_brief
RAIN POST /api/v3/ui/ask → 200 in 86 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request ab83bc223e51 · data postgres://rain_v3/ui_v3.dataset (contracts.state, built live) · turn st_county
RAIN page /county-explorer ← backend GET http://localhost:8183/api/v3/ui/data?clientId=rain (request af4bd3c59f8e, postgres://rain_v3/ui_v3.dataset + public_data (live)): constants.COUNTIES [county public fields live from rain_v3.public_data], constants.STATE, contracts.state, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW
RAIN GET /api/v3/queries/STATE-S1 → 200 in 26 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request d5c0a6dc706e · data postgres://rain_v3/synthetic
RAIN query STATE-S1 (rain_state, synthetic data): 23 rows from rain_v3.synthetic in 10.8 ms
```

| Line | Meaning |
|---|---|
| `Data loaded from the backend …` | The one boot call `GET /api/v3/ui/data` (all UI data, from Postgres `rain_v3.ui_v3.dataset` + live `public_data`), with its request id and SHA-256 check |
| `RAIN GET/POST /api/v3/… → 200 … request … data … turn …` | One line per backend API call, with the backend's proof headers: `X-RAIN-Source`, server (container id), request id, data source, chat turn |
| `RAIN page /county-explorer ← backend GET /api/v3/ui/data …: constants.COUNTIES, geo.COUNTY_SHAPES, …` | Which backend datasets the page on screen is built from (logged once per page and dataset) |
| `RAIN rain_state: 10 backend queries …` | Printed when a persona opens: that persona's synthetic and public data queries (a table with the API of each) |
| `RAIN query STATE-S1 … rows from rain_v3.synthetic` | Output of `rainQuery('STATE-S1')`: the question, the SQL and the rows |

Console helpers: `rainQueries()` or `rainQueries('rain_cmo')` (list), `rainQuery('CMO-P1')` (run and print rows),
`window.__RAIN_API_CALLS__` (every API call with its headers), `window.__RAIN_PAGE_DATA__` (each page and its backend
datasets) and `window.__RAIN_DATA_PROOF__` (the boot data load).

### Ask the queries in the chat

Type a query's question (as written below), or just its id (e.g. `CEO-P1`), into that persona's Ask AI box. The
backend runs the query live and answers with a table of the rows, the tables it read as sources, and the persona's
other queries as follow-up chips. The console shows it, for example:

```
RAIN POST /api/v3/ui/ask → 200 in 95 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request 48cafccd6d37 · data postgres://rain_v3/public_data (query CEO-P1) · turn query:CEO-P1
```

How a typed message is matched, in order:
1. A scripted chip or recorded question keeps its scripted answer.
2. A query id, or a query question typed exactly.
3. A scripted chip typed in any case.
4. A query question in any case, or a 20+ character part of it.
5. The rest of the scripted conversation.
6. Before the generic "I can answer from the contract checkpoint…" reply: a query whose words cover most of what was typed.

One query repeats a scripted question word for word (CEO-S5, "Compare our sites on cost per member"). Type it with
the trailing period, or `CEO-S5`, to get the query.

### In the backend log (`docker logs -f rain3-backend-1`)

Every call has a line with the same request id as the browser console. For a persona query there are two lines:

```
2026-11-06 12:43:34,790 INFO    [rain.api.queries] persona query CEO-S1 (rain_ceo, synthetic data) -> 1 rows in 10 ms req=6e14511be728
2026-11-06 12:43:34,791 INFO    [rain.api] GET /api/v3/queries/CEO-S1 -> 200 (12 ms) req=6e14511be728
2026-11-06 13:23:35,203 INFO    [rain.api.ui] briefing persona=rain_access turn=acc_brief built from postgres://rain_v3/ui_v3.dataset (contracts.access, built live)
2026-11-06 13:23:35,292 INFO    [rain.api.ui] ask persona=rain_access turn=acc_start built from postgres://rain_v3/ui_v3.dataset (contracts.access, built live)
2026-11-06 13:24:24,083 INFO    [rain.api.queries] persona query list persona=rain_access data=all -> 10 queries
2026-11-06 13:24:23,367 INFO    [rain.api.ui] ui data client=rain: 83 datasets from rain_v3.ui_v3.dataset, 31 live public values, 419873 bytes in 60 ms req=474bc4e5336d
```

### From a terminal

```bash
curl -s http://localhost:8183/api/v3/queries?persona=rain_cmo          # list a persona's queries
curl -i http://localhost:8183/api/v3/queries/CMO-P1                    # run one (see X-RAIN-* headers)
```

## 2. The backend APIs

| API | What it returns | Backend source | Proof headers |
|---|---|---|---|
| `GET /api/v3/ui/data?clientId=rain` | All UI data (82 datasets), loaded once when the app starts | Postgres `rain_v3.ui_v3.dataset`; county public fields and source counts live from `rain_v3.public_data` | X-RAIN-Request-Id, X-RAIN-Server, X-RAIN-Data-Source, X-RAIN-Data-Sha256, Server-Timing |
| `GET /api/v3/ui/briefing?clientId=rain&personaId=…` | The persona's morning briefing | built live from Postgres `rain_v3.ui_v3.dataset` (`contracts.<persona>`) by `chat_v3.py` | X-RAIN-Data-Source, X-RAIN-Turn, X-RAIN-Request-Id |
| `POST /api/v3/ui/ask` | A chat answer | built live from Postgres `rain_v3.ui_v3.dataset` (contract step, datasets, records, live public data); persona queries run live SQL | X-RAIN-Data-Source, X-RAIN-Turn, X-RAIN-Request-Id |
| `GET /api/v3/queries[?persona=…&data=synthetic\|public]` | The persona queries (id, question, API) | `doc/queries/rain_v3_persona_queries.sql` | X-RAIN-Data-Source, X-RAIN-Request-Id |
| `GET /api/v3/queries/{id}` | Runs one query read-only as `rain_app`: columns, rows, SQL, timing | Postgres `rain_v3.synthetic` or `rain_v3.public_data` | X-RAIN-Query-Id, X-RAIN-Data-Source, X-RAIN-Rows, Server-Timing |

Interactive docs: http://localhost:8002/docs (tags `ui-data-v3`, `ultra-v3`, `persona-queries-v3`).

**About the data:** `synthetic` is the generated v0.3 schema. Its keys join correctly, but codes and names are filler
words and numbers are random, so synthetic results show the query logic, not the demo's figures. `public_data` holds
real CDC PLACES, CDC/ATSDR SVI, USDA RUCC, HRSA HPSA and health center sites, NPPES and Census ZCTA data for NV and TN.

## 3. Per persona

### CEO: Gregory Haskins, MBA (rain_ceo)

*Chief Executive Officer*

**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,
run one synthetic and one public query from the console):

| # | API call | For | Status | Request id | Backend source |
|---|---|---|---|---|---|
| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: True) | 200 | `f0c18d675abd` | postgres://rain_v3/ui_v3.dataset + public_data (live) |
| 2 | `GET /api/v3/queries?persona=rain_ceo` | list this persona's backend queries (printed when the persona opens) | 200 | `3217a2b8a4e1` | query pack doc/queries/rain_v3_persona_queries.sql |
| 3 | `GET /api/v3/ui/briefing?clientId=rain&personaId=rain_ceo` | morning briefing (turn `ceo_brief`) | 200 | `a695cc7d74fb` | postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live) |
| 4 | `POST /api/v3/ui/ask` | chat answer to the first briefing chip (turn `ceo_gap`) | 200 | `34e30aee2fbd` | postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live) |
| 5 | `GET /api/v3/queries/CEO-S1` | query run from the browser console with `rainQuery()` | 200 | `fcd552ff630b` | postgres://rain_v3/synthetic |
| 6 | `GET /api/v3/queries/CEO-P1` | query run from the browser console with `rainQuery()` | 200 | `fc590a3fb504` | postgres://rain_v3/public_data |

**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row
also holds what the app shell reads while it starts):

| Page | Backend datasets read (from `GET /api/v3/ui/data`) |
|---|---|
| `/ask?persona=rain_ceo` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CARE, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.LOW_VALUE, constants.LV_MEASURES, constants.MEASURES, constants.MODEL, constants.OPTIONS, constants.ORG, constants.PERSONAS, constants.PMPM_TREND, constants.SEGMENTS, constants.SITES, constants.STATE, contracts.access, contracts.ceo, contracts.chw, contracts.cio, contracts.cmo, contracts.state, datasets.lv_top5, datasets.projection_2027, geo.VIEW, personas.ceo, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |
| `/ask` | capabilities.CAPABILITY_CALLOUTS, constants.CODING, constants.COHORT, constants.CONTRACT, constants.GAP, constants.PMPM_TREND, constants.SEGMENTS |
| `/value-insights` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.MEASURES, constants.ORG, constants.PMPM_TREND, constants.SEGMENTS, constants.SITES, contracts.ceo, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW |
| `/quality-gate` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CODING, constants.COHORT, constants.CONTRACT, constants.GAP, constants.MEASURES, constants.PMPM_TREND, constants.SEGMENTS, contracts.ceo, personas.cmo, records.campaignMembers |
| `/low-value-care` | capabilities.CAPABILITY_CALLOUTS, constants.CODING, constants.COHORT, constants.CONTRACT, constants.GAP, constants.LOCUMS, constants.LOW_VALUE, constants.LV_MEASURES, constants.PMPM_TREND, constants.SEGMENTS, constants.SITES, constants.WINNEMUCCA_TREND, contracts.ceo |
| `/data-sources` | capabilities.CAPABILITY_CALLOUTS, constants.CODING, constants.COHORT, constants.CONTRACT, constants.GAP, constants.PMPM_TREND, constants.SEGMENTS, contracts.ceo, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |

**Synthetic data queries (`rain_v3.synthetic`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CEO-S1 | What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)? | `GET /api/v3/queries/CEO-S1` | ✅ 200 · 1 rows · 9.7 ms | ✅ live table, 1 rows shown | `persona query CEO-S1 (rain_ceo, synthetic data) -> 1 rows in 10 ms req=6e14511be728` |
| CEO-S2 | How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members? | `GET /api/v3/queries/CEO-S2` | ✅ 200 · 1 rows · 7.4 ms | ✅ live table, 1 rows shown | `persona query CEO-S2 (rain_ceo, synthetic data) -> 1 rows in 7 ms req=1655ae2432d6` |
| CEO-S3 | Where is the low-value care? Top sites by low-value spend. | `GET /api/v3/queries/CEO-S3` | ✅ 200 · 10 rows · 8.6 ms | ✅ live table, 10 rows shown | `persona query CEO-S3 (rain_ceo, synthetic data) -> 10 rows in 9 ms req=23b657028dc5` |
| CEO-S4 | How close are we to the quality gate? Rate vs target for every gate measure. | `GET /api/v3/queries/CEO-S4` | ✅ 200 · 15 rows · 8.1 ms | ✅ live table, 15 rows shown | `persona query CEO-S4 (rain_ceo, synthetic data) -> 15 rows in 8 ms req=3f112687b29d` |
| CEO-S5 | Compare our sites on cost per member. | `GET /api/v3/queries/CEO-S5` | ✅ 200 · 10 rows · 8.9 ms | ✅ live table, 10 rows shown | `persona query CEO-S5 (rain_ceo, synthetic data) -> 10 rows in 9 ms req=1b942b99ad42` |

<details><summary>CEO-S1: SQL and first row</summary>

```sql
SELECT count(DISTINCT am.patient_id)                                   AS attributed_members,
       count(c.claim_id)                                               AS claims,
       round(sum(c.allowed_amount)::numeric, 2)                        AS total_allowed,
       round((sum(c.allowed_amount) / NULLIF(count(DISTINCT am.patient_id), 0))::numeric, 2) AS allowed_per_member
FROM synthetic.attributed_member am
LEFT JOIN synthetic.claim c ON c.patient_id = am.patient_id;
```

Columns: attributed_members, claims, total_allowed, allowed_per_member  
First row: `{"attributed_members": 136, "claims": 225, "total_allowed": 11641519.89, "allowed_per_member": 85599.41}`

</details>

<details><summary>CEO-S2: SQL and first row</summary>

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

Columns: ed_claims, avoidable_ed_claims, admissions, ed_per_1000, avoidable_ed_per_1000  
First row: `{"ed_claims": 107, "avoidable_ed_claims": 87, "admissions": 90, "ed_per_1000": 786.8, "avoidable_ed_per_1000": 639.7}`

</details>

<details><summary>CEO-S3: SQL and first row</summary>

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

Columns: clinic_site_id, site_name, low_value_findings, low_value_allowed  
First row: `{"clinic_site_id": "CLINIC_S000189", "site_name": "Maybe", "low_value_findings": 4, "low_value_allowed": 298400.49}`

</details>

<details><summary>CEO-S4: SQL and first row</summary>

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

Columns: measure_code, measure_name, target_rate, lower_is_better, denominator, numerator, rate  
First row: `{"measure_code": "QUALITY_000004", "measure_name": "Study", "target_rate": 0.9576, "lower_is_better": true, "denominator": 3, "numerator": 0, "rate": 0.0}`

</details>

<details><summary>CEO-S5: SQL and first row</summary>

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

Columns: clinic_site_id, site_name, telehealth_capable, members_seen, allowed, allowed_per_member  
First row: `{"clinic_site_id": "CLINIC_S000006", "site_name": "Win", "telehealth_capable": false, "members_seen": 1, "allowed": 98850.79, "allowed_per_member": 98850.79}`

</details>

**Public data queries (`rain_v3.public_data`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CEO-P1 | Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability. | `GET /api/v3/queries/CEO-P1` | ✅ 200 · 6 rows · 18.0 ms | ✅ live table, 6 rows shown | `persona query CEO-P1 (rain_ceo, public data) -> 6 rows in 18 ms req=f620e5fbf464` |
| CEO-P2 | What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)? | `GET /api/v3/queries/CEO-P2` | ✅ 200 · 6 rows · 8.5 ms | ✅ live table, 6 rows shown | `persona query CEO-P2 (rain_ceo, public data) -> 6 rows in 9 ms req=da190e2eb364` |
| CEO-P3 | How do our counties compare with the Nevada county average on annual checkups and insurance gaps? | `GET /api/v3/queries/CEO-P3` | ✅ 200 · 5 rows · 8.8 ms | ✅ live table, 5 rows shown | `persona query CEO-P3 (rain_ceo, public data) -> 5 rows in 9 ms req=c9ec23b6c480` |
| CEO-P4 | Which of our counties have designated primary care shortage areas (HRSA HPSA), and how severe? | `GET /api/v3/queries/CEO-P4` | ✅ 200 · 6 rows · 8.1 ms | ✅ live table, 6 rows shown | `persona query CEO-P4 (rain_ceo, public data) -> 6 rows in 8 ms req=1ea068346bd7` |
| CEO-P5 | Where does each of our counties rank among Nevada's 17 counties for high blood pressure? | `GET /api/v3/queries/CEO-P5` | ✅ 200 · 6 rows · 8.9 ms | ✅ live table, 6 rows shown | `persona query CEO-P5 (rain_ceo, public data) -> 6 rows in 9 ms req=25fd1539a2e3` |

<details><summary>CEO-P1: SQL and first row</summary>

```sql
WITH network(fips) AS (VALUES (32007),(32013),(32015),(32027),(32033),(32001))
SELECT s.county, s.fips, s.e_totpop AS population, r.value AS rucc_2023,
       round(s.rpl_themes::numeric, 3) AS svi_percentile, s.ep_pov150 AS pct_below_150_poverty, s.ep_uninsur AS pct_uninsured
FROM network n
JOIN public_data.svi_county s  ON s.fips = n.fips
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
ORDER BY s.e_totpop DESC;
```

Columns: county, fips, population, rucc_2023, svi_percentile, pct_below_150_poverty, pct_uninsured  
First row: `{"county": "Elko County", "fips": 32007, "population": 53600, "rucc_2023": "5", "svi_percentile": 0.619, "pct_below_150_poverty": 19.2, "pct_uninsured": 8.9}`

</details>

<details><summary>CEO-P2: SQL and first row</summary>

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

Columns: county, high_bp_pct, diabetes_pct, obesity_pct, smoking_pct, copd_pct  
First row: `{"county": "White Pine", "high_bp_pct": 36.4, "diabetes_pct": 12.6, "obesity_pct": 34.4, "smoking_pct": 17.5, "copd_pct": 9.1}`

</details>

<details><summary>CEO-P3: SQL and first row</summary>

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

Columns: measureid, short_question_text, network_avg_pct, nv_county_avg_pct  
First row: `{"measureid": "ACCESS2", "short_question_text": "Health Insurance", "network_avg_pct": 13.6, "nv_county_avg_pct": 12.6}`

</details>

<details><summary>CEO-P4: SQL and first row</summary>

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

Columns: common_county_name, designated_hpsas, max_hpsa_score, designation_population, designation_types  
First row: `{"common_county_name": "Churchill County, NV", "designated_hpsas": 3, "max_hpsa_score": 19, "designation_population": 45644.0, "designation_types": "Geographic HPSA; Indian Health Service, Tribal Health, and Urban Indian Health Or…`

</details>

<details><summary>CEO-P5: SQL and first row</summary>

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

Columns: county, fips, high_bp_pct, rank_of_17  
First row: `{"county": "White Pine", "fips": 32033, "high_bp_pct": 36.4, "rank_of_17": 9}`

</details>

### CMO: Dr. Naomi Castellanos (rain_cmo)

*Chief Medical Officer and Value-Based Care Quality Lead*

**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,
run one synthetic and one public query from the console):

| # | API call | For | Status | Request id | Backend source |
|---|---|---|---|---|---|
| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: True) | 200 | `81bcc3327c03` | postgres://rain_v3/ui_v3.dataset + public_data (live) |
| 2 | `GET /api/v3/queries?persona=rain_cmo` | list this persona's backend queries (printed when the persona opens) | 200 | `75fa15561b15` | query pack doc/queries/rain_v3_persona_queries.sql |
| 3 | `GET /api/v3/ui/briefing?clientId=rain&personaId=rain_cmo` | morning briefing (turn `cmo_brief`) | 200 | `4b05214b2f5e` | postgres://rain_v3/ui_v3.dataset (contracts.cmo, built live) |
| 4 | `POST /api/v3/ui/ask` | chat answer to the first briefing chip (turn `cmo_412`) | 200 | `c9d0ad5fee11` | postgres://rain_v3/ui_v3.dataset (contracts.cmo, built live) |
| 5 | `GET /api/v3/queries/CMO-S1` | query run from the browser console with `rainQuery()` | 200 | `44ad5732aef2` | postgres://rain_v3/synthetic |
| 6 | `GET /api/v3/queries/CMO-P1` | query run from the browser console with `rainQuery()` | 200 | `2446d6282d32` | postgres://rain_v3/public_data |

**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row
also holds what the app shell reads while it starts):

| Page | Backend datasets read (from `GET /api/v3/ui/data`) |
|---|---|
| `/ask?persona=rain_cmo` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CARE, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.LOW_VALUE, constants.LV_MEASURES, constants.MEASURES, constants.MODEL, constants.OPTIONS, constants.ORG, constants.PERSONAS, constants.SEGMENTS, constants.SITES, constants.STATE, contracts.access, contracts.ceo, contracts.chw, contracts.cio, contracts.cmo, contracts.state, datasets.campaign_top10, datasets.lv_top5, datasets.measure_projection, datasets.mode_split, datasets.site_imaging, datasets.site_lowvalue, geo.VIEW, governance.FEATURES, personas.cmo, records.campaignMembers, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |
| `/ask` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CONTRACT, constants.MEASURES |
| `/quality-gate` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CONTRACT, constants.MEASURES, contracts.cmo, records.campaignMembers |
| `/low-value-care` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CONTRACT, constants.LOCUMS, constants.LOW_VALUE, constants.LV_MEASURES, constants.MEASURES, constants.SITES, constants.WINNEMUCCA_TREND, contracts.cmo |
| `/value-insights` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.MEASURES, constants.ORG, constants.PMPM_TREND, constants.SEGMENTS, constants.SITES, contracts.cmo, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW |
| `/model-governance` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CONTRACT, **constants.COUNTIES** (live public), constants.MEASURES, constants.MODEL, contracts.cmo, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.FRONTIER_POINTS, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW, governance.FEATURES, governance.SUBGROUP, governance.accessPoints |
| `/worklist` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CARE, constants.CONTRACT, constants.LINDA, constants.MEASURES, contracts.cmo, personas.cmo, records.campaignMembers |

**Synthetic data queries (`rain_v3.synthetic`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CMO-S1 | How close are we to each quality target? Performance gap per measure. | `GET /api/v3/queries/CMO-S1` | ✅ 200 · 15 rows · 7.9 ms | ✅ live table, 15 rows shown | `persona query CMO-S1 (rain_cmo, synthetic data) -> 15 rows in 8 ms req=ca584e8e4fa2` |
| CMO-S2 | Which care gaps are still open, by measure? | `GET /api/v3/queries/CMO-S2` | ✅ 200 · 15 rows · 8.9 ms | ✅ live table, 15 rows shown | `persona query CMO-S2 (rain_cmo, synthetic data) -> 15 rows in 9 ms req=740e6b4d33ad` |
| CMO-S3 | Which patients with an open care gap have home BP readings that count toward the measure? | `GET /api/v3/queries/CMO-S3` | ✅ 200 · 3 rows · 7.9 ms | ✅ live table, 3 rows shown | `persona query CMO-S3 (rain_cmo, synthetic data) -> 3 rows in 8 ms req=f5ccdc13fae4` |
| CMO-S4 | Which providers order the most low-value services (the Winnemucca imaging question), and are they locums? | `GET /api/v3/queries/CMO-S4` | ✅ 200 · 10 rows · 7.7 ms | ✅ live table, 10 rows shown | `persona query CMO-S4 (rain_cmo, synthetic data) -> 10 rows in 8 ms req=241477f6f14a` |
| CMO-S5 | Which members need risk-coding recapture (documented condition not recaptured)? | `GET /api/v3/queries/CMO-S5` | ✅ 200 · 20 rows · 7.1 ms | ✅ live table, 20 rows shown | `persona query CMO-S5 (rain_cmo, synthetic data) -> 20 rows in 7 ms req=cb0a4a9acd64` |

<details><summary>CMO-S1: SQL and first row</summary>

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

Columns: measure_code, measure_name, gate_flag, target_rate, rate, gap_to_target, patients_in_denominator  
First row: `{"measure_code": "QUALITY_000050", "measure_name": "Quite", "gate_flag": null, "target_rate": 0.7146, "rate": 0.333, "gap_to_target": -0.381, "patients_in_denominator": 3}`

</details>

<details><summary>CMO-S2: SQL and first row</summary>

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

Columns: measure_code, measure_name, gaps, never_closed, pending, oldest_opened  
First row: `{"measure_code": "QUALITY_000041", "measure_name": "Strong", "gaps": 4, "never_closed": 0, "pending": 1, "oldest_opened": "2024-06-07"}`

</details>

<details><summary>CMO-S3: SQL and first row</summary>

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

Columns: patient_id, first_name, last_name, readings_counting, latest_reading, open_gaps  
First row: `{"patient_id": "PATIENT000189", "first_name": "Denise", "last_name": "Garcia", "readings_counting": 1, "latest_reading": "2025-10-05T04:11:56", "open_gaps": 1}`

</details>

<details><summary>CMO-S4: SQL and first row</summary>

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

Columns: provider_id, provider, locum_flag, site_name, low_value_findings, low_value_allowed  
First row: `{"provider_id": "PROVIDER000106", "provider": "Latoya Baldwin", "locum_flag": true, "site_name": "Investment", "low_value_findings": 1, "low_value_allowed": 99330.76}`

</details>

<details><summary>CMO-S5: SQL and first row</summary>

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

Columns: patient_id, first_name, last_name, conditions, not_recaptured  
First row: `{"patient_id": "PATIENT000081", "first_name": "Leonard", "last_name": "Ramirez", "conditions": 4, "not_recaptured": 3}`

</details>

**Public data queries (`rain_v3.public_data`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CMO-P1 | How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada? | `GET /api/v3/queries/CMO-P1` | ✅ 200 · 17 rows · 9.1 ms | ✅ live table, 17 rows shown | `persona query CMO-P1 (rain_cmo, public data) -> 17 rows in 9 ms req=9f629e4a8703` |
| CMO-P2 | Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context). | `GET /api/v3/queries/CMO-P2` | ✅ 200 · 17 rows · 8.4 ms | ✅ live table, 17 rows shown | `persona query CMO-P2 (rain_cmo, public data) -> 17 rows in 8 ms req=c24fa5cbfae3` |
| CMO-P3 | Preventive screening rates in our counties (colorectal, mammography, cholesterol). | `GET /api/v3/queries/CMO-P3` | ✅ 200 · 6 rows · 8.1 ms | ✅ live table, 6 rows shown | `persona query CMO-P3 (rain_cmo, public data) -> 6 rows in 8 ms req=05e972b4420f` |
| CMO-P4 | Social needs that block BP control in our counties (food, housing, transport, utilities, loneliness). | `GET /api/v3/queries/CMO-P4` | ✅ 200 · 6 rows · 8.8 ms | ✅ live table, 6 rows shown | `persona query CMO-P4 (rain_cmo, public data) -> 6 rows in 9 ms req=fb9390fa3106` |
| CMO-P5 | Mental health burden and designated mental health shortage areas in our counties. | `GET /api/v3/queries/CMO-P5` | ✅ 200 · 6 rows · 9.6 ms | ✅ live table, 6 rows shown | `persona query CMO-P5 (rain_cmo, public data) -> 6 rows in 10 ms req=f64edba6b35c` |

<details><summary>CMO-P1: SQL and first row</summary>

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

Columns: county, high_bp_pct, on_bp_medication_pct, grp  
First row: `{"county": "White Pine", "high_bp_pct": 36.4, "on_bp_medication_pct": 74.7, "grp": "network"}`

</details>

<details><summary>CMO-P2: SQL and first row</summary>

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

Columns: county, diabetes_pct, obesity_pct, physical_inactivity_pct, is_network_county  
First row: `{"county": "Esmeralda", "diabetes_pct": 17.7, "obesity_pct": 36.1, "physical_inactivity_pct": 32.3, "is_network_county": false}`

</details>

<details><summary>CMO-P3: SQL and first row</summary>

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

Columns: county, colorectal_screening_pct, mammography_pct, cholesterol_screening_pct  
First row: `{"county": "Pershing", "colorectal_screening_pct": 56.1, "mammography_pct": 72.4, "cholesterol_screening_pct": 83.4}`

</details>

<details><summary>CMO-P4: SQL and first row</summary>

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

Columns: county, food_insecurity_pct, housing_insecurity_pct, transport_barrier_pct, utility_threat_pct, loneliness_pct  
First row: `{"county": "Lander", "food_insecurity_pct": 18.9, "housing_insecurity_pct": 15.0, "transport_barrier_pct": 10.4, "utility_threat_pct": 10.1, "loneliness_pct": 35.3}`

</details>

<details><summary>CMO-P5: SQL and first row</summary>

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

Columns: county, frequent_mental_distress_pct, depression_pct, designated_mh_hpsas, max_mh_hpsa_score  
First row: `{"county": "Lander", "frequent_mental_distress_pct": 19.1, "depression_pct": 22.8, "designated_mh_hpsas": 4, "max_mh_hpsa_score": 17}`

</details>

### CIO: Raj Malhotra (rain_cio)

*Chief Information Officer and Data and AI Governance Lead*

**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,
run one synthetic and one public query from the console):

| # | API call | For | Status | Request id | Backend source |
|---|---|---|---|---|---|
| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: True) | 200 | `72756a6e4774` | postgres://rain_v3/ui_v3.dataset + public_data (live) |
| 2 | `GET /api/v3/queries?persona=rain_cio` | list this persona's backend queries (printed when the persona opens) | 200 | `d5ce2b115f5c` | query pack doc/queries/rain_v3_persona_queries.sql |
| 3 | `GET /api/v3/ui/briefing?clientId=rain&personaId=rain_cio` | morning briefing (turn `cio_brief`) | 200 | `28fda7065822` | postgres://rain_v3/ui_v3.dataset (contracts.cio, built live) |
| 4 | `POST /api/v3/ui/ask` | chat answer to the first briefing chip (turn `cio_subgroup`) | 200 | `3420bae66a21` | postgres://rain_v3/ui_v3.dataset (contracts.cio, built live) |
| 5 | `GET /api/v3/queries/CIO-S1` | query run from the browser console with `rainQuery()` | 200 | `e4f362158366` | postgres://rain_v3/synthetic |
| 6 | `GET /api/v3/queries/CIO-P1` | query run from the browser console with `rainQuery()` | 200 | `23332f6b0597` | postgres://rain_v3/public_data |

**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row
also holds what the app shell reads while it starts):

| Page | Backend datasets read (from `GET /api/v3/ui/data`) |
|---|---|
| `/ask?persona=rain_cio` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CARE, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.LOW_VALUE, constants.MODEL, constants.OPTIONS, constants.ORG, constants.PERSONAS, constants.STATE, contracts.access, contracts.ceo, contracts.chw, contracts.cio, contracts.cmo, contracts.state, datasets.before_after, datasets.features, datasets.site_social, datasets.subgroup, datasets.swaps, datasets.swaps_in, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.FRONTIER_POINTS, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW, governance.FEATURES, governance.accessPoints, personas.cio, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |
| `/ask` | capabilities.CAPABILITY_CALLOUTS, constants.CONTRACT, **constants.COUNTIES** (live public), constants.MODEL, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.FRONTIER_POINTS, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW, governance.accessPoints |
| `/model-governance` | capabilities.CAPABILITY_CALLOUTS, constants.CONTRACT, **constants.COUNTIES** (live public), constants.MODEL, contracts.cio, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.FRONTIER_POINTS, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW, governance.FEATURES, governance.SUBGROUP, governance.accessPoints |
| `/data-sources` | capabilities.CAPABILITY_CALLOUTS, constants.CONTRACT, **constants.COUNTIES** (live public), constants.MODEL, contracts.cio, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.FRONTIER_POINTS, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW, governance.accessPoints, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |

**Synthetic data queries (`rain_v3.synthetic`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CIO-S1 | Show the model cards: release status, sign-off and how many subgroup checks each passed. | `GET /api/v3/queries/CIO-S1` | ✅ 200 · 15 rows · 7.5 ms | ✅ live table, 15 rows shown | `persona query CIO-S1 (rain_cio, synthetic data) -> 15 rows in 7 ms req=1d2a5181baa3` |
| CIO-S2 | Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold. | `GET /api/v3/queries/CIO-S2` | ✅ 200 · 20 rows · 7.2 ms | ✅ live table, 20 rows shown | `persona query CIO-S2 (rain_cio, synthetic data) -> 20 rows in 7 ms req=b2b0d3b8c80c` |
| CIO-S3 | How fresh is each data source? Latest record per feed and lag in days. | `GET /api/v3/queries/CIO-S3` | ✅ 200 · 7 rows · 8.7 ms | ✅ live table, 7 rows shown | `persona query CIO-S3 (rain_cio, synthetic data) -> 7 rows in 9 ms req=5b41882f705d` |
| CIO-S4 | Show records that failed patient matching (patient_id missing or not in the patient master). | `GET /api/v3/queries/CIO-S4` | ✅ 200 · 7 rows · 9.8 ms | ✅ live table, 7 rows shown | `persona query CIO-S4 (rain_cio, synthetic data) -> 7 rows in 10 ms req=a5e2f1150312` |
| CIO-S5 | Social needs coverage: how many attributed members have at least one SDOH screening? | `GET /api/v3/queries/CIO-S5` | ✅ 200 · 1 rows · 7.4 ms | ✅ live table, 1 rows shown | `persona query CIO-S5 (rain_cio, synthetic data) -> 1 rows in 7 ms req=11cbb071449b` |

<details><summary>CIO-S1: SQL and first row</summary>

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

Columns: model_version, model_name, release_status, access_adjusted_flag, signed_off_by, cosigned_by, subgroup_checks, passed, failed  
First row: `{"model_version": "MODEL_CA000002", "model_name": "Whether", "release_status": "active", "access_adjusted_flag": false, "signed_off_by": "always", "cosigned_by": "magazine", "subgroup_checks": 3, "passed": 0, "failed": 3}`

</details>

<details><summary>CIO-S2: SQL and first row</summary>

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

Columns: model_version, subgroup, comparison_group, metric, gap_percent, threshold_percent, over_threshold_by, passed, checked_at  
First row: `{"model_version": "MODEL_CA000002", "subgroup": "whether", "comparison_group": "series", "metric": "situation", "gap_percent": 0.9121, "threshold_percent": 0.017, "over_threshold_by": 0.8951, "passed": false, "checked_at": "2026-0…`

</details>

<details><summary>CIO-S3: SQL and first row</summary>

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

Columns: feed, latest, days_since_latest, rows  
First row: `{"feed": "Eligibility (270/271)", "latest": "2026-10-28T07:40:49", "days_since_latest": 9, "rows": 200}`

</details>

<details><summary>CIO-S4: SQL and first row</summary>

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

Columns: src, records, null_patient_id, unmatched_patient_id, failed_matching  
First row: `{"src": "appointment", "records": 200, "null_patient_id": 0, "unmatched_patient_id": 0, "failed_matching": 0}`

</details>

<details><summary>CIO-S5: SQL and first row</summary>

```sql
SELECT count(DISTINCT am.patient_id)                                           AS attributed_members,
       count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NOT NULL)   AS screened,
       count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NULL)       AS missing_screening,
       round(100.0 * count(DISTINCT am.patient_id) FILTER (WHERE s.patient_id IS NOT NULL)
             / NULLIF(count(DISTINCT am.patient_id), 0), 1)                     AS coverage_pct
FROM synthetic.attributed_member am
LEFT JOIN synthetic.sdoh_screening s ON s.patient_id = am.patient_id;
```

Columns: attributed_members, screened, missing_screening, coverage_pct  
First row: `{"attributed_members": 136, "screened": 94, "missing_screening": 42, "coverage_pct": 69.1}`

</details>

**Public data queries (`rain_v3.public_data`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CIO-P1 | What public data feeds the county view? Row counts and state coverage per public table. | `GET /api/v3/queries/CIO-P1` | ✅ 200 · 8 rows · 16.2 ms | ✅ live table, 8 rows shown | `persona query CIO-P1 (rain_cio, public data) -> 8 rows in 16 ms req=b254c3bca216` |
| CIO-P2 | CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state. | `GET /api/v3/queries/CIO-P2` | ✅ 200 · 4 rows · 16.6 ms | ✅ live table, 4 rows shown | `persona query CIO-P2 (rain_cio, public data) -> 4 rows in 17 ms req=f3968f113eeb` |
| CIO-P3 | Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS? | `GET /api/v3/queries/CIO-P3` | ✅ 200 · 17 rows · 13.9 ms | ✅ live table, 17 rows shown | `persona query CIO-P3 (rain_cio, public data) -> 17 rows in 14 ms req=52600d8539cd` |
| CIO-P4 | HRSA HPSA status mix and data volume by discipline (primary care vs mental health) in Nevada. | `GET /api/v3/queries/CIO-P4` | ✅ 200 · 6 rows · 12.0 ms | ✅ live table, 6 rows shown | `persona query CIO-P4 (rain_cio, public data) -> 6 rows in 12 ms req=a7dc0e902551` |
| CIO-P5 | NPPES provider data quality: completeness and duplicate NPIs by state and entity type. | `GET /api/v3/queries/CIO-P5` | ✅ 200 · 4 rows · 40.2 ms | ✅ live table, 4 rows shown | `persona query CIO-P5 (rain_cio, public data) -> 4 rows in 40 ms req=18c61f21fd22` |

<details><summary>CIO-P1: SQL and first row</summary>

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

Columns: dataset, rows, states, vintage  
First row: `{"dataset": "zcta_centroids", "rows": 33791, "states": null, "vintage": "2023 Gazetteer"}`

</details>

<details><summary>CIO-P2: SQL and first row</summary>

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

Columns: stateabbr, data_value_type, measures, counties, cells, missing_values, ci_wider_than_10pts  
First row: `{"stateabbr": "NV", "data_value_type": "Age-adjusted prevalence", "measures": 40, "counties": 17, "cells": 680, "missing_values": 0, "ci_wider_than_10pts": 99}`

</details>

<details><summary>CIO-P3: SQL and first row</summary>

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

Columns: fips, county, in_rucc, in_cdc_places, has_any_pc_hpsa  
First row: `{"fips": 32001, "county": "Churchill County", "in_rucc": true, "in_cdc_places": true, "has_any_pc_hpsa": true}`

</details>

<details><summary>CIO-P4: SQL and first row</summary>

```sql
SELECT 'primary care' AS discipline, hpsa_status, count(*) AS hpsas, count(DISTINCT common_county_name) AS counties
FROM public_data.hpsa_primary_care WHERE primary_state_abbreviation = 'NV' GROUP BY hpsa_status
UNION ALL
SELECT 'mental health', hpsa_status, count(*), count(DISTINCT common_county_name)
FROM public_data.hpsa_mental_health WHERE primary_state_abbreviation = 'NV' GROUP BY hpsa_status
ORDER BY discipline, hpsas DESC;
```

Columns: discipline, hpsa_status, hpsas, counties  
First row: `{"discipline": "mental health", "hpsa_status": "Withdrawn", "hpsas": 1093, "counties": 18}`

</details>

<details><summary>CIO-P5: SQL and first row</summary>

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

Columns: state, enumeration_type, providers, distinct_npis, duplicate_rows, missing_taxonomy, missing_zip  
First row: `{"state": "NV", "enumeration_type": "NPI-1", "providers": 6571, "distinct_npis": 6571, "duplicate_rows": 0, "missing_taxonomy": 11, "missing_zip": 0}`

</details>

### State: Dr. Lauren Pike (rain_state)

*Program Lead, Rural Health Outcomes Accelerator*

**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,
run one synthetic and one public query from the console):

| # | API call | For | Status | Request id | Backend source |
|---|---|---|---|---|---|
| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: True) | 200 | `af4bd3c59f8e` | postgres://rain_v3/ui_v3.dataset + public_data (live) |
| 2 | `GET /api/v3/queries?persona=rain_state` | list this persona's backend queries (printed when the persona opens) | 200 | `b17311d922e1` | query pack doc/queries/rain_v3_persona_queries.sql |
| 3 | `GET /api/v3/ui/briefing?clientId=rain&personaId=rain_state` | morning briefing (turn `st_brief`) | 200 | `2e5689fe260d` | postgres://rain_v3/ui_v3.dataset (contracts.state, built live) |
| 4 | `POST /api/v3/ui/ask` | chat answer to the first briefing chip (turn `st_county`) | 200 | `ab83bc223e51` | postgres://rain_v3/ui_v3.dataset (contracts.state, built live) |
| 5 | `GET /api/v3/queries/STATE-S1` | query run from the browser console with `rainQuery()` | 200 | `d5c0a6dc706e` | postgres://rain_v3/synthetic |
| 6 | `GET /api/v3/queries/STATE-P1` | query run from the browser console with `rainQuery()` | 200 | `8d7cad9745f6` | postgres://rain_v3/public_data |

**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row
also holds what the app shell reads while it starts):

| Page | Backend datasets read (from `GET /api/v3/ui/data`) |
|---|---|
| `/ask?persona=rain_state` | capabilities.CAPABILITY_CALLOUTS, constants.BP, constants.CARE, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.LOW_VALUE, constants.MODEL, constants.OPTIONS, constants.ORG, constants.PERSONAS, constants.STATE, contracts.access, contracts.ceo, contracts.chw, contracts.cio, contracts.cmo, contracts.state, datasets.county_lowvalue, datasets.ed_projection, datasets.networks, datasets.options, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW, personas.state, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |
| `/ask` | capabilities.CAPABILITY_CALLOUTS, **constants.COUNTIES** (live public), constants.STATE, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW |
| `/county-explorer` | capabilities.CAPABILITY_CALLOUTS, **constants.COUNTIES** (live public), constants.STATE, contracts.state, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW |
| `/value-insights` | capabilities.CAPABILITY_CALLOUTS, **constants.COUNTIES** (live public), constants.GAP, constants.SITES, constants.STATE, contracts.state, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW |
| `/rhtp-reporting` | capabilities.CAPABILITY_CALLOUTS, **constants.COUNTIES** (live public), constants.OPTIONS, constants.STATE, contracts.state, geo.COUNTY_LABEL, geo.COUNTY_SHAPES, geo.OTHER_COUNTIES, geo.SITE_POINTS, geo.STATE_OUTLINE, geo.VIEW |

**Synthetic data queries (`rain_v3.synthetic`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| STATE-S1 | Primary care visits by month (is volume down since January?), with telehealth share. | `GET /api/v3/queries/STATE-S1` | ✅ 200 · 23 rows · 10.5 ms | ✅ live table, 23 rows shown | `persona query STATE-S1 (rain_state, synthetic data) -> 23 rows in 10 ms req=422b4b3aefa8` |
| STATE-S2 | Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth. | `GET /api/v3/queries/STATE-S2` | ✅ 200 · 3 rows · 13.9 ms | ✅ live table, 3 rows shown | `persona query STATE-S2 (rain_state, synthetic data) -> 3 rows in 14 ms req=0e5521e4a864` |
| STATE-S3 | Where does broadband block telehealth? Share of coverage records not served, by technology. | `GET /api/v3/queries/STATE-S3` | ✅ 200 · 15 rows · 13.5 ms | ✅ live table, 15 rows shown | `persona query STATE-S3 (rain_state, synthetic data) -> 15 rows in 14 ms req=f63f45c9982f` |
| STATE-S4 | Rural and frontier mix of the areas in view (FORHP rural, frontier flags). | `GET /api/v3/queries/STATE-S4` | ✅ 200 · 9 rows · 14.4 ms | ✅ live table, 9 rows shown | `persona query STATE-S4 (rain_state, synthetic data) -> 9 rows in 14 ms req=5937681108a6` |
| STATE-S5 | Small-cell suppression: how many county metric cells are suppressed before the state can publish? | `GET /api/v3/queries/STATE-S5` | ✅ 200 · 3 rows · 13.6 ms | ✅ live table, 3 rows shown | `persona query STATE-S5 (rain_state, synthetic data) -> 3 rows in 14 ms req=398855e5c7fb` |

<details><summary>STATE-S1: SQL and first row</summary>

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

Columns: month, encounters, telehealth, telehealth_pct  
First row: `{"month": "2025-01-01", "encounters": 8, "telehealth": 4, "telehealth_pct": 50.0}`

</details>

<details><summary>STATE-S2: SQL and first row</summary>

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

Columns: telehealth_capable, sites, encounters, telehealth_pct  
First row: `{"telehealth_capable": true, "sites": 106, "encounters": 98, "telehealth_pct": 50.0}`

</details>

<details><summary>STATE-S3: SQL and first row</summary>

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

Columns: technology, coverage_records, not_served, not_served_pct  
First row: `{"technology": null, "coverage_records": 7, "not_served": 4, "not_served_pct": 57.1}`

</details>

<details><summary>STATE-S4: SQL and first row</summary>

```sql
SELECT rc.forhp_rural_flag, rc.frontier_flag,
       count(*)                        AS areas,
       count(DISTINCT rc.county_fips)  AS counties
FROM synthetic.rural_classification rc
GROUP BY rc.forhp_rural_flag, rc.frontier_flag
ORDER BY rc.frontier_flag DESC NULLS LAST, rc.forhp_rural_flag DESC NULLS LAST;
```

Columns: forhp_rural_flag, frontier_flag, areas, counties  
First row: `{"forhp_rural_flag": true, "frontier_flag": true, "areas": 45, "counties": 43}`

</details>

<details><summary>STATE-S5: SQL and first row</summary>

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

Columns: suppressed_flag, cells, counties, metrics, min_year, max_year  
First row: `{"suppressed_flag": true, "cells": 92, "counties": 86, "metrics": 84, "min_year": 61, "max_year": 988}`

</details>

**Public data queries (`rain_v3.public_data`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| STATE-P1 | The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs. | `GET /api/v3/queries/STATE-P1` | ✅ 200 · 17 rows · 29.6 ms | ✅ live table, 17 rows shown | `persona query STATE-P1 (rain_state, public data) -> 17 rows in 30 ms req=7254cecdbb83` |
| STATE-P2 | Metro vs rural vs frontier-like: Nevada population and county count by RUCC group. | `GET /api/v3/queries/STATE-P2` | ✅ 200 · 3 rows · 14.5 ms | ✅ live table, 3 rows shown | `persona query STATE-P2 (rain_state, public data) -> 3 rows in 14 ms req=2f057236218a` |
| STATE-P3 | Primary care shortage counties: designated primary care HPSAs by county, type and severity. | `GET /api/v3/queries/STATE-P3` | ✅ 200 · 25 rows · 15.4 ms | ✅ live table, 25 rows shown | `persona query STATE-P3 (rain_state, public data) -> 25 rows in 15 ms req=4df936f84048` |
| STATE-P4 | Where does broadband limit telehealth? Households without internet (SVI) by county, worst first. | `GET /api/v3/queries/STATE-P4` | ✅ 200 · 17 rows · 16.2 ms | ✅ live table, 17 rows shown | `persona query STATE-P4 (rain_state, public data) -> 17 rows in 16 ms req=ebd1e15e0f51` |
| STATE-P5 | Health center site coverage per 100,000 residents by Nevada county (where do Accelerator funds go first?). | `GET /api/v3/queries/STATE-P5` | ✅ 200 · 17 rows · 14.8 ms | ✅ live table, 17 rows shown | `persona query STATE-P5 (rain_state, public data) -> 17 rows in 15 ms req=6b33bbae76c5` |

<details><summary>STATE-P1: SQL and first row</summary>

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

Columns: county, fips, population, rucc_2023, svi_percentile, designated_pc_hpsas, sierra_basin_county  
First row: `{"county": "Esmeralda County", "fips": 32009, "population": 980, "rucc_2023": "9", "svi_percentile": 0.908, "designated_pc_hpsas": 1, "sierra_basin_county": false}`

</details>

<details><summary>STATE-P2: SQL and first row</summary>

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

Columns: rucc_group, counties, population, counties_in_group  
First row: `{"rucc_group": "1-3 metro", "counties": 5, "population": 2874379, "counties_in_group": "Carson City, Clark County, Lyon County, Storey County, Washoe County"}`

</details>

<details><summary>STATE-P3: SQL and first row</summary>

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

Columns: common_county_name, designation_type, designated_hpsas, max_score, avg_score, designation_population  
First row: `{"common_county_name": "Clark County, NV", "designation_type": "Federally Qualified Health Center", "designated_hpsas": 4, "max_score": 22, "avg_score": 20.0, "designation_population": 1538488.0}`

</details>

<details><summary>STATE-P4: SQL and first row</summary>

```sql
SELECT s.county, s.fips, s.ep_noint AS pct_households_no_internet, s.e_noint AS households_no_internet,
       r.value AS rucc_2023, s.fips IN (32007,32013,32015,32027,32033,32001) AS sierra_basin_county
FROM public_data.svi_county s
LEFT JOIN public_data.rucc_county r ON r.fips = s.fips AND r.attribute = 'RUCC_2023'
WHERE s.st_abbr = 'NV'
ORDER BY s.ep_noint DESC;
```

Columns: county, fips, pct_households_no_internet, households_no_internet, rucc_2023, sierra_basin_county  
First row: `{"county": "Nye County", "fips": 32023, "pct_households_no_internet": 22.4, "households_no_internet": 4884, "rucc_2023": "4", "sierra_basin_county": false}`

</details>

<details><summary>STATE-P5: SQL and first row</summary>

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

Columns: county, population, health_center_sites, sites_per_100k, rucc_2023  
First row: `{"county": "Lyon County", "population": 59435, "health_center_sites": 0, "sites_per_100k": 0.0, "rucc_2023": "2"}`

</details>

### CHW: Teresa Lopez, CHW (rain_chw)

*Community Health Worker and Care Coordinator*

**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,
run one synthetic and one public query from the console):

| # | API call | For | Status | Request id | Backend source |
|---|---|---|---|---|---|
| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: True) | 200 | `63b9dc4deb3c` | postgres://rain_v3/ui_v3.dataset + public_data (live) |
| 2 | `GET /api/v3/queries?persona=rain_chw` | list this persona's backend queries (printed when the persona opens) | 200 | `f501d91c5e20` | query pack doc/queries/rain_v3_persona_queries.sql |
| 3 | `GET /api/v3/ui/briefing?clientId=rain&personaId=rain_chw` | morning briefing (turn `chw_brief`) | 200 | `2f1c65ca9eef` | postgres://rain_v3/ui_v3.dataset (contracts.chw, built live) |
| 4 | `POST /api/v3/ui/ask` | chat answer to the first briefing chip (turn `chw_open`) | 200 | `ca6423e181e4` | postgres://rain_v3/ui_v3.dataset (contracts.chw, built live) |
| 5 | `GET /api/v3/queries/CHW-S1` | query run from the browser console with `rainQuery()` | 200 | `2bfdd2b2300b` | postgres://rain_v3/synthetic |
| 6 | `GET /api/v3/queries/CHW-P1` | query run from the browser console with `rainQuery()` | 200 | `4fa8f141727c` | postgres://rain_v3/public_data |

**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row
also holds what the app shell reads while it starts):

| Page | Backend datasets read (from `GET /api/v3/ui/data`) |
|---|---|
| `/ask?persona=rain_chw` | constants.BP, constants.CARE, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.LINDA, constants.LOW_VALUE, constants.MODEL, constants.OPTIONS, constants.ORG, constants.PERSONAS, constants.SITES, constants.STATE, constants.TERESA_SITES, contracts.access, contracts.ceo, contracts.chw, contracts.cio, contracts.cmo, contracts.state, datasets.reminders_unconfirmed, datasets.teresa_noreply, datasets.teresa_top5, geo.VIEW, personas.chw, records.campaignMembers, records.slots, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |
| `/worklist?filter=teresa46` | constants.BP, constants.CARE, constants.LINDA, constants.SITES, constants.TERESA_SITES, contracts.chw, personas.cmo, records.campaignMembers |
| `/ask` | constants.BP, constants.CARE, constants.SITES, constants.TERESA_SITES, records.campaignMembers |
| `/worklist` | constants.BP, constants.CARE, constants.LINDA, constants.SITES, constants.TERESA_SITES, contracts.chw, personas.cmo, records.campaignMembers |
| `/scheduling` | constants.BP, constants.CARE, constants.LINDA, constants.ORG, constants.SITES, constants.TERESA_SITES, contracts.chw, records.campaignMembers, records.pendingBookings, records.slots |

**Synthetic data queries (`rain_v3.synthetic`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CHW-S1 | Open my worklist: open outreach tasks by priority, with who to call. | `GET /api/v3/queries/CHW-S1` | ✅ 200 · 25 rows · 12.9 ms | ✅ live table, 25 rows shown | `persona query CHW-S1 (rain_chw, synthetic data) -> 25 rows in 13 ms req=0bb736f64b7f` |
| CHW-S2 | How is the campaign going? Members, cuffs on file and bookings per campaign. | `GET /api/v3/queries/CHW-S2` | ✅ 200 · 15 rows · 12.7 ms | ✅ live table, 15 rows shown | `persona query CHW-S2 (rain_chw, synthetic data) -> 15 rows in 13 ms req=ac69005fe361` |
| CHW-S3 | Who has not answered reminders? Patients with reminders that got no reply or are still pending. | `GET /api/v3/queries/CHW-S3` | ✅ 200 · 20 rows · 16.0 ms | ✅ live table, 20 rows shown | `persona query CHW-S3 (rain_chw, synthetic data) -> 20 rows in 16 ms req=8d6e748b73dc` |
| CHW-S4 | Who is closest to BP control? Campaign members with their latest home BP reading. | `GET /api/v3/queries/CHW-S4` | ✅ 200 · 25 rows · 14.4 ms | ✅ live table, 25 rows shown | `persona query CHW-S4 (rain_chw, synthetic data) -> 25 rows in 14 ms req=4bbbd6e00dfc` |
| CHW-S5 | How should I reach each patient? Consented contact channel and language preferences. | `GET /api/v3/queries/CHW-S5` | ✅ 200 · 18 rows · 14.2 ms | ✅ live table, 18 rows shown | `persona query CHW-S5 (rain_chw, synthetic data) -> 18 rows in 14 ms req=7a2b021b59ab` |

<details><summary>CHW-S1: SQL and first row</summary>

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

Columns: task_id, priority_score, task_type, status, patient_id, patient, phone, created_at, reason  
First row: `{"task_id": "OUTREACH000160", "priority_score": 0.9965, "task_type": "standard", "status": "active", "patient_id": "PATIENT000062", "patient": "Eric Collins", "phone": "367.697.6438x156", "created_at": "2025-11-20T03:21:04", "reas…`

</details>

<details><summary>CHW-S2: SQL and first row</summary>

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

Columns: campaign_id, campaign_name, status, target_count, members, cuff_on_file, booked, booked_pct  
First row: `{"campaign_id": "CAMPAIGN000031", "campaign_name": "Method", "status": "rejected", "target_count": 252, "members": 4, "cuff_on_file": 2, "booked": 3, "booked_pct": 75.0}`

</details>

<details><summary>CHW-S3: SQL and first row</summary>

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

Columns: patient_id, patient, phone, reminders, unanswered, last_sent, channels  
First row: `{"patient_id": "PATIENT000096", "patient": "Elizabeth Schmidt", "phone": "(708)626-7734", "reminders": 5, "unanswered": 2, "last_sent": "2026-10-29T03:17:01", "channels": "enterprise, premium, standard"}`

</details>

<details><summary>CHW-S4: SQL and first row</summary>

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

Columns: patient_id, patient, outreach_rank, cuff_on_file, value_systolic, value_diastolic, reading_time, counts_for_measure  
First row: `{"patient_id": "PATIENT000002", "patient": "Jeffrey Lawrence", "outreach_rank": 661, "cuff_on_file": true, "value_systolic": 41774.8, "value_diastolic": 23075.02, "reading_time": "2026-06-05T15:03:28", "counts_for_measure": false}`

</details>

<details><summary>CHW-S5: SQL and first row</summary>

```sql
SELECT cp.channel, cp.consent_flag,
       count(DISTINCT cp.patient_id) AS patients,
       count(DISTINCT cp.language)   AS languages_recorded
FROM synthetic.contact_preference cp
GROUP BY cp.channel, cp.consent_flag
ORDER BY cp.consent_flag DESC NULLS LAST, patients DESC;
```

Columns: channel, consent_flag, patients, languages_recorded  
First row: `{"channel": "premium", "consent_flag": true, "patients": 19, "languages_recorded": 19}`

</details>

**Public data queries (`rain_v3.public_data`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| CHW-P1 | Where can I send patients? Health center sites in or near our counties, with hours and phone. | `GET /api/v3/queries/CHW-P1` | ✅ 200 · 6 rows · 13.3 ms | ✅ live table, 6 rows shown | `persona query CHW-P1 (rain_chw, public data) -> 6 rows in 13 ms req=3564d07216a7` |
| CHW-P2 | Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI). | `GET /api/v3/queries/CHW-P2` | ✅ 200 · 6 rows · 18.7 ms | ✅ live table, 6 rows shown | `persona query CHW-P2 (rain_chw, public data) -> 6 rows in 19 ms req=c4e53d8a9a76` |
| CHW-P3 | Talking points on social needs: food, housing, utility and food-stamp rates in our counties. | `GET /api/v3/queries/CHW-P3` | ✅ 200 · 6 rows · 17.1 ms | ✅ live table, 6 rows shown | `persona query CHW-P3 (rain_chw, public data) -> 6 rows in 17 ms req=ac975b32716a` |
| CHW-P4 | Do I need Spanish talking points? Hispanic share and limited-English households by county (SVI). | `GET /api/v3/queries/CHW-P4` | ✅ 200 · 6 rows · 15.1 ms | ✅ live table, 6 rows shown | `persona query CHW-P4 (rain_chw, public data) -> 6 rows in 15 ms req=80338318b2c7` |
| CHW-P5 | Which primary care practices (NPPES) are in our towns: Elko, Winnemucca, Fallon, Ely, Lovelock, Battle Mountain? | `GET /api/v3/queries/CHW-P5` | ✅ 200 · 97 rows · 21.2 ms | ✅ live table, 25 rows shown | `persona query CHW-P5 (rain_chw, public data) -> 97 rows in 21 ms req=9ff0a3ed2b2b` |

<details><summary>CHW-P1: SQL and first row</summary>

```sql
SELECT hc.complete_county_name, hc.site_city, hc.site_name, hc.site_address,
       hc.site_telephone_number, hc.operating_hours_per_week, hc.health_center_type_description
FROM public_data.health_center_sites hc
WHERE hc.site_state_abbreviation = 'NV'
  AND hc.complete_county_name IN ('Elko County','Humboldt County','Lander County','Pershing County',
                                  'White Pine County','Churchill County','Lyon County','Eureka County')
ORDER BY hc.complete_county_name, hc.site_city;
```

Columns: complete_county_name, site_city, site_name, site_address, site_telephone_number, operating_hours_per_week, health_center_type_description  
First row: `{"complete_county_name": "Elko County", "site_city": "Carlin", "site_name": "Carlin Community Health Center", "site_address": "310 Memory Ln", "site_telephone_number": "775-754-2666", "operating_hours_per_week": 40.0, "health_cent…`

</details>

<details><summary>CHW-P2: SQL and first row</summary>

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

Columns: county, transport_barrier_pct, pct_households_no_vehicle, county_area_sqmi  
First row: `{"county": "Lander", "transport_barrier_pct": 10.4, "pct_households_no_vehicle": 2.4, "county_area_sqmi": 5519.24436764232}`

</details>

<details><summary>CHW-P3: SQL and first row</summary>

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

Columns: county, food_insecurity_pct, food_stamps_pct, housing_insecurity_pct, utility_shutoff_threat_pct, lacks_social_support_pct  
First row: `{"county": "Lander", "food_insecurity_pct": 18.9, "food_stamps_pct": 17.2, "housing_insecurity_pct": 15.0, "utility_shutoff_threat_pct": 10.1, "lacks_social_support_pct": 25.6}`

</details>

<details><summary>CHW-P4: SQL and first row</summary>

```sql
SELECT s.county, s.e_totpop AS population,
       s.ep_hisp   AS pct_hispanic,
       s.ep_limeng AS pct_limited_english,
       s.ep_age65  AS pct_age_65_plus
FROM public_data.svi_county s
WHERE s.fips IN (32007, 32013, 32015, 32027, 32033, 32001)
ORDER BY s.ep_limeng DESC;
```

Columns: county, population, pct_hispanic, pct_limited_english, pct_age_65_plus  
First row: `{"county": "Humboldt County", "population": 17266, "pct_hispanic": 27.9, "pct_limited_english": 3.6, "pct_age_65_plus": 15.4}`

</details>

<details><summary>CHW-P5: SQL and first row</summary>

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

Columns: city, taxonomy, providers, organizations, individuals  
First row: `{"city": "BATTLE MOUNTAIN", "taxonomy": "Ambulance, Land Transport", "providers": 2, "organizations": 2, "individuals": 0}`

</details>

### Access: Brandon Kee (rain_access)

*Patient Access Coordinator*

**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,
run one synthetic and one public query from the console):

| # | API call | For | Status | Request id | Backend source |
|---|---|---|---|---|---|
| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: True) | 200 | `813b86aa3ac9` | postgres://rain_v3/ui_v3.dataset + public_data (live) |
| 2 | `GET /api/v3/queries?persona=rain_access` | list this persona's backend queries (printed when the persona opens) | 200 | `cbcdc7fd264c` | query pack doc/queries/rain_v3_persona_queries.sql |
| 3 | `GET /api/v3/ui/briefing?clientId=rain&personaId=rain_access` | morning briefing (turn `acc_brief`) | 200 | `6ae0e76aefb7` | postgres://rain_v3/ui_v3.dataset (contracts.access, built live) |
| 4 | `POST /api/v3/ui/ask` | chat answer to the first briefing chip (turn `acc_start`) | 200 | `cca88f51feec` | postgres://rain_v3/ui_v3.dataset (contracts.access, built live) |
| 5 | `GET /api/v3/queries/ACCESS-S1` | query run from the browser console with `rainQuery()` | 200 | `2d89749dc54d` | postgres://rain_v3/synthetic |
| 6 | `GET /api/v3/queries/ACCESS-P1` | query run from the browser console with `rainQuery()` | 200 | `b69a2c93500c` | postgres://rain_v3/public_data |

**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row
also holds what the app shell reads while it starts):

| Page | Backend datasets read (from `GET /api/v3/ui/data`) |
|---|---|
| `/ask?persona=rain_access` | constants.BP, constants.CARE, constants.CODING, constants.COHORT, constants.CONTRACT, **constants.COUNTIES** (live public), constants.GAP, constants.LINDA, constants.LOW_VALUE, constants.MODEL, constants.OPTIONS, constants.ORG, constants.PERSONAS, constants.STATE, contracts.access, contracts.ceo, contracts.chw, contracts.cio, contracts.cmo, contracts.state, datasets.reminders_r, datasets.reminders_unconfirmed, geo.VIEW, personas.access, records.campaignMembers, records.slots, sources.ENGINES, **sources.PUBLIC_SOURCES** (live public), sources.SYNTHETIC_SOURCES |
| `/scheduling?filter=next` | constants.CARE, constants.LINDA, constants.ORG, contracts.access, records.campaignMembers, records.pendingBookings, records.slots |
| `/ask` | constants.CARE, constants.LINDA |
| `/scheduling` | constants.CARE, constants.LINDA, constants.ORG, contracts.access, records.campaignMembers, records.pendingBookings, records.slots |
| `/reminders` | constants.CARE, constants.LINDA, contracts.access, records.reminders |

**Synthetic data queries (`rain_v3.synthetic`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| ACCESS-S1 | What slots are open? Open slots by site, in-person vs telehealth. | `GET /api/v3/queries/ACCESS-S1` | ✅ 200 · 20 rows · 20.7 ms | ✅ live table, 20 rows shown | `persona query ACCESS-S1 (rain_access, synthetic data) -> 20 rows in 21 ms req=9d19497241f7` |
| ACCESS-S2 | Show unconfirmed visits: pending appointments and whether eligibility was verified. | `GET /api/v3/queries/ACCESS-S2` | ✅ 200 · 25 rows · 16.3 ms | ✅ live table, 25 rows shown | `persona query ACCESS-S2 (rain_access, synthetic data) -> 25 rows in 16 ms req=5b4040568978` |
| ACCESS-S3 | Handle the replies: reminder replies waiting for action, by channel and delivery status. | `GET /api/v3/queries/ACCESS-S3` | ✅ 200 · 33 rows · 14.3 ms | ✅ live table, 25 rows shown | `persona query ACCESS-S3 (rain_access, synthetic data) -> 33 rows in 14 ms req=561292806aa4` |
| ACCESS-S4 | Why telehealth for this patient? Longest drive times and whether the site can do telehealth. | `GET /api/v3/queries/ACCESS-S4` | ✅ 200 · 20 rows · 17.7 ms | ✅ live table, 20 rows shown | `persona query ACCESS-S4 (rain_access, synthetic data) -> 20 rows in 18 ms req=0eee05c473c1` |
| ACCESS-S5 | Start bookings: campaign members not yet booked, highest outreach rank first, with visit mode. | `GET /api/v3/queries/ACCESS-S5` | ✅ 200 · 25 rows · 20.6 ms | ✅ live table, 25 rows shown | `persona query ACCESS-S5 (rain_access, synthetic data) -> 25 rows in 21 ms req=4e4a3d397414` |

<details><summary>ACCESS-S1: SQL and first row</summary>

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

Columns: clinic_site_id, site_name, telehealth_flag, slots, open_slots, first_slot  
First row: `{"clinic_site_id": "CLINIC_S000109", "site_name": "Only", "telehealth_flag": true, "slots": 6, "open_slots": 3, "first_slot": "2024-01-13T05:13:08"}`

</details>

<details><summary>ACCESS-S2: SQL and first row</summary>

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

Columns: appointment_id, status, visit_mode, booked_at, patient, phone, coverage_status, eligibility_checked_at  
First row: `{"appointment_id": "APPOINTM000178", "status": "pending", "visit_mode": "recently", "booked_at": "2023-12-24T03:51:38", "patient": "Julia Tapia", "phone": "001-689-241-3435x24082", "coverage_status": null, "eligibility_checked_at"…`

</details>

<details><summary>ACCESS-S3: SQL and first row</summary>

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

Columns: channel, delivery_status, messages, with_reply, patients, avg_hours_before_visit  
First row: `{"channel": "basic", "delivery_status": "approved", "messages": 12, "with_reply": 12, "patients": 12, "avg_hours_before_visit": 520.7}`

</details>

<details><summary>ACCESS-S4: SQL and first row</summary>

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

Columns: patient_zcta, clinic_site_id, site_name, telehealth_capable, drive_minutes, recommendation  
First row: `{"patient_zcta": "religious", "clinic_site_id": "CLINIC_S000097", "site_name": "Year", "telehealth_capable": true, "drive_minutes": 99938.4, "recommendation": "offer telehealth"}`

</details>

<details><summary>ACCESS-S5: SQL and first row</summary>

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

Columns: outreach_rank, patient_id, patient, phone, recommended_visit_mode, cuff_on_file, campaign_name  
First row: `{"outreach_rank": 3, "patient_id": "PATIENT000197", "patient": "Roy Hawkins", "phone": null, "recommended_visit_mode": "newspaper", "cuff_on_file": true, "campaign_name": "Parent"}`

</details>

**Public data queries (`rain_v3.public_data`)**

| Query | Question | API | Result | Typed in the chat | Backend log (request id) |
|---|---|---|---|---|---|
| ACCESS-P1 | How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx). | `GET /api/v3/queries/ACCESS-P1` | ✅ 200 · 20 rows · 28.9 ms | ✅ live table, 20 rows shown | `persona query ACCESS-P1 (rain_access, public data) -> 20 rows in 29 ms req=6d7e71f16a1a` |
| ACCESS-P2 | Health center capacity: operating hours per week of sites in Nevada's rural counties. | `GET /api/v3/queries/ACCESS-P2` | ✅ 200 · 4 rows · 18.6 ms | ✅ live table, 4 rows shown | `persona query ACCESS-P2 (rain_access, public data) -> 4 rows in 19 ms req=5fd9ac140a61` |
| ACCESS-P3 | Primary care capacity gap: HPSA FTE shortage and population affected in our counties. | `GET /api/v3/queries/ACCESS-P3` | ✅ 200 · 22 rows · 22.2 ms | ✅ live table, 22 rows shown | `persona query ACCESS-P3 (rain_access, public data) -> 22 rows in 22 ms req=0422fbefefdc` |
| ACCESS-P4 | Primary care providers by town in our region (NPPES: family, internal medicine, NP, PA, clinics). | `GET /api/v3/queries/ACCESS-P4` | ✅ 200 · 7 rows · 39.2 ms | ✅ live table, 7 rows shown | `persona query ACCESS-P4 (rain_access, public data) -> 7 rows in 39 ms req=194044772d2a` |
| ACCESS-P5 | Expect eligibility problems? Uninsured and no-checkup rates in our counties. | `GET /api/v3/queries/ACCESS-P5` | ✅ 200 · 6 rows · 22.4 ms | ✅ live table, 6 rows shown | `persona query ACCESS-P5 (rain_access, public data) -> 6 rows in 22 ms req=72688034ec56` |

<details><summary>ACCESS-P1: SQL and first row</summary>

```sql
SELECT z.geoid AS zcta, round(z.aland_sqmi::numeric, 1) AS land_sq_mi,
       z.intptlat AS lat, z.intptlong AS lon
FROM public_data.zcta_centroids z
WHERE z.geoid BETWEEN '89400' AND '89899'
ORDER BY z.aland_sqmi DESC
LIMIT 20;
```

Columns: zcta, land_sq_mi, lat, lon  
First row: `{"zcta": "89412", "land_sq_mi": 3084.5, "lat": 41.121163, "lon": -119.704982}`

</details>

<details><summary>ACCESS-P2: SQL and first row</summary>

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

Columns: complete_county_name, sites, total_hours_per_week, avg_hours_per_site  
First row: `{"complete_county_name": "Elko County", "sites": 5, "total_hours_per_week": 197.0, "avg_hours_per_site": 39.4}`

</details>

<details><summary>ACCESS-P3: SQL and first row</summary>

```sql
SELECT h.common_county_name, h.hpsa_name, h.designation_type, h.hpsa_score,
       h.hpsa_fte, h.hpsa_shortage, h.hpsa_designation_population, h.hpsa_formal_ratio
FROM public_data.hpsa_primary_care h
WHERE h.hpsa_status = 'Designated'
  AND h.common_county_name IN ('Elko County, NV','Humboldt County, NV','Lander County, NV',
                               'Pershing County, NV','White Pine County, NV','Churchill County, NV')
ORDER BY h.hpsa_score DESC NULLS LAST, h.hpsa_designation_population DESC NULLS LAST;
```

Columns: common_county_name, hpsa_name, designation_type, hpsa_score, hpsa_fte, hpsa_shortage, hpsa_designation_population, hpsa_formal_ratio  
First row: `{"common_county_name": "Churchill County, NV", "hpsa_name": "FALLON TRIBAL HEALTH CENTER", "designation_type": "Indian Health Service, Tribal Health, and Urban Indian Health Organizations", "hpsa_score": 19, "hpsa_fte": null, "hps…`

</details>

<details><summary>ACCESS-P4: SQL and first row</summary>

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

Columns: town, primary_care_providers  
First row: `{"town": "ELKO", "primary_care_providers": 42}`

</details>

<details><summary>ACCESS-P5: SQL and first row</summary>

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

Columns: county, uninsured_18_64_pct, annual_checkup_pct, dental_visit_pct  
First row: `{"county": "Pershing", "uninsured_18_64_pct": 15.0, "annual_checkup_pct": 70.9, "dental_visit_pct": 56.4}`

</details>

## 4. Re-run the checks

```bash
# all 60 queries through the API, with the backend tests (inside the backend container)
docker exec -w /app/rain-api -e PG_HOST=postgres rain3-backend-1 python -m pytest -q test_persona_queries_v3.py
# one query from the browser console
rainQuery('CEO-S1')
```
