# RAIN v0.4: persona queries (synthetic and public), served by the backend

Checked on 2026-11-10 against the `rain4` stack (UI http://localhost:8184, API http://localhost:8003). The pack `doc/queries/rain_v4_persona_queries.sql` holds **70 queries**: 5 synthetic and 5 public for each of the 7 personas (6 operators and the patient Linda Garcia).

| Check | Result |
|---|---|
| Every query runs read-only as the backend login `rain_app` and returns rows | **70/70** |
| Every query typed into its persona's chat in a real browser renders a live table | **70/70** |
| The patient's queries run through `GET /api/v4/queries/{id}` (her chat finds only her own queries) | **10/10** |

Each query is also an endpoint: `GET /api/v4/queries?persona=<id>` lists them, `GET /api/v4/queries/<ID>` runs one. In the chat, type the question or its id (for example `CMO-P3`). Synthetic tables hold row-level synthetic data calibrated to the Q3 checkpoint (the UI computes its figures from the same rows); public tables are the real NV and TN datasets listed in `.data/public/MANIFEST.md`. The patient keeps her pack id (`patient_linda_garcia`); her app id (`rain_linda`) lists the same queries.

## Gregory Haskins, MBA (rain_ceo)

*Chief Executive Officer*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `CEO-P1` | public | Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability. | 6 | live table |
| `CEO-P2` | public | What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)? | 6 | live table |
| `CEO-P3` | public | How do our counties compare with the Nevada county average on annual checkups and insurance gaps? | 5 | live table |
| `CEO-P4` | public | Which of our counties have designated primary care shortage areas (HRSA HPSA), and how severe? | 6 | live table |
| `CEO-P5` | public | Where does each of our counties rank among Nevada's 17 counties for high blood pressure? | 6 | live table |
| `CEO-S1` | synthetic | What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)? | 1 | live table |
| `CEO-S2` | synthetic | How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members? | 1 | live table |
| `CEO-S3` | synthetic | Where is the low-value care? Top sites by low-value spend. | 10 | live table |
| `CEO-S4` | synthetic | How close are we to the quality gate? Rate vs target for every gate measure. | 5 | live table |
| `CEO-S5` | synthetic | Compare our sites on cost per member. | 10 | live table |

## Dr. Naomi Castellanos (rain_cmo)

*Chief Medical Officer and Value-Based Care Quality Lead*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `CMO-P1` | public | How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada? | 17 | live table |
| `CMO-P2` | public | Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context). | 17 | live table |
| `CMO-P3` | public | Preventive screening rates in our counties (colorectal, mammography, cholesterol). | 6 | live table |
| `CMO-P4` | public | Social needs that block BP control in our counties (food, housing, transport, utilities, loneliness). | 6 | live table |
| `CMO-P5` | public | Mental health burden and designated mental health shortage areas in our counties. | 6 | live table |
| `CMO-S1` | synthetic | How close are we to each quality target? Performance gap per measure. | 5 | live table |
| `CMO-S2` | synthetic | Which care gaps are still open, by measure? | 5 | live table |
| `CMO-S3` | synthetic | Which patients with an open care gap have home BP readings that count toward the measure? | 20 | live table |
| `CMO-S4` | synthetic | Which providers order the most low-value services (the Winnemucca imaging question), and are they locums? | 10 | live table |
| `CMO-S5` | synthetic | Which members need risk-coding recapture (documented condition not recaptured)? | 20 | live table |

## Raj Malhotra (rain_cio)

*Chief Information Officer and Data and AI Governance Lead*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `CIO-P1` | public | What public data feeds the county view? Row counts and state coverage per public table. | 8 | live table |
| `CIO-P2` | public | CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state. | 4 | live table |
| `CIO-P3` | public | Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS? | 17 | live table |
| `CIO-P4` | public | HRSA HPSA status mix and data volume by discipline (primary care vs mental health) in Nevada. | 6 | live table |
| `CIO-P5` | public | NPPES provider data quality: completeness and duplicate NPIs by state and entity type. | 4 | live table |
| `CIO-S1` | synthetic | Show the model cards: release status, sign-off and how many subgroup checks each passed. | 2 | live table |
| `CIO-S2` | synthetic | Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold. | 6 | live table |
| `CIO-S3` | synthetic | How fresh is each data source? Latest record per feed and lag in days. | 7 | live table |
| `CIO-S4` | synthetic | Show records that failed patient matching (patient_id missing or not in the patient master). | 7 | live table |
| `CIO-S5` | synthetic | Social needs coverage: how many attributed members have at least one SDOH screening? | 1 | live table |

## Dr. Lauren Pike (rain_state)

*Program Lead, Rural Health Outcomes Accelerator*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `STATE-P1` | public | The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs. | 17 | live table |
| `STATE-P2` | public | Metro vs rural vs frontier-like: Nevada population and county count by RUCC group. | 3 | live table |
| `STATE-P3` | public | Primary care shortage counties: designated primary care HPSAs by county, type and severity. | 25 | live table |
| `STATE-P4` | public | Where does broadband limit telehealth? Households without internet (SVI) by county, worst first. | 17 | live table |
| `STATE-P5` | public | Health center site coverage per 100,000 residents by Nevada county (where do Accelerator funds go first?). | 17 | live table |
| `STATE-S1` | synthetic | Primary care visits by month (is volume down since January?), with telehealth share. | 12 | live table |
| `STATE-S2` | synthetic | Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth. | 2 | live table |
| `STATE-S3` | synthetic | Where does broadband block telehealth? Share of coverage records not served, by technology. | 2 | live table |
| `STATE-S4` | synthetic | Rural and frontier mix of the areas in view (FORHP rural, frontier flags). | 3 | live table |
| `STATE-S5` | synthetic | Small-cell suppression: how many county metric cells are suppressed before the state can publish? | 1 | live table |

## Teresa Lopez, CHW (rain_chw)

*Community Health Worker and Care Coordinator*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `CHW-P1` | public | Where can I send patients? Health center sites in or near our counties, with hours and phone. | 6 | live table |
| `CHW-P2` | public | Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI). | 6 | live table |
| `CHW-P3` | public | Talking points on social needs: food, housing, utility and food-stamp rates in our counties. | 6 | live table |
| `CHW-P4` | public | Do I need Spanish talking points? Hispanic share and limited-English households by county (SVI). | 6 | live table |
| `CHW-P5` | public | Which primary care practices (NPPES) are in our towns: Elko, Winnemucca, Fallon, Ely, Lovelock, Battle Mountain? | 97 | live table |
| `CHW-S1` | synthetic | Open my worklist: open outreach tasks by priority, with who to call. | 25 | live table |
| `CHW-S2` | synthetic | How is the campaign going? Members, cuffs on file and bookings per campaign. | 2 | live table |
| `CHW-S3` | synthetic | Who has not answered reminders? Patients with reminders that got no reply or are still pending. | 15 | live table |
| `CHW-S4` | synthetic | Who is closest to BP control? Campaign members with their latest home BP reading. | 25 | live table |
| `CHW-S5` | synthetic | How should I reach each patient? Consented contact channel and language preferences. | 3 | live table |

## Brandon Kee (rain_access)

*Patient Access Coordinator*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `ACCESS-P1` | public | How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx). | 20 | live table |
| `ACCESS-P2` | public | Health center capacity: operating hours per week of sites in Nevada's rural counties. | 4 | live table |
| `ACCESS-P3` | public | Primary care capacity gap: HPSA FTE shortage and population affected in our counties. | 22 | live table |
| `ACCESS-P4` | public | Primary care providers by town in our region (NPPES: family, internal medicine, NP, PA, clinics). | 7 | live table |
| `ACCESS-P5` | public | Expect eligibility problems? Uninsured and no-checkup rates in our counties. | 6 | live table |
| `ACCESS-S1` | synthetic | What slots are open? Open slots by site, in-person vs telehealth. | 15 | live table |
| `ACCESS-S2` | synthetic | Show unconfirmed visits: pending appointments and whether eligibility was verified. | 15 | live table |
| `ACCESS-S3` | synthetic | Handle the replies: reminder replies waiting for action, by channel and delivery status. | 4 | live table |
| `ACCESS-S4` | synthetic | Why telehealth for this patient? Longest drive times and whether the site can do telehealth. | 20 | live table |
| `ACCESS-S5` | synthetic | Start bookings: campaign members not yet booked, highest outreach rank first, with visit mode. | 25 | live table |

## Linda Garcia (patient) (patient_linda_garcia)

*Patient, Battle Mountain (SMS); app persona rain_linda*

| ID | Data | Question | Rows | In the chat |
|---|---|---|---|---|
| `GAR-P1` | public | How far do I drive from Battle Mountain to the nearest health center? | 1 | live table |
| `GAR-P2` | public | What share of households in my county, Lander, have broadband? | 1 | live table |
| `GAR-P3` | public | What share of adults in my county, Lander, have high blood pressure? | 2 | live table |
| `GAR-P4` | public | Is my county, Lander, a primary care shortage area? | 3 | live table |
| `GAR-P5` | public | How many households in my county, Lander, speak Spanish with limited English? | 1 | live table |
| `GAR-S1` | synthetic | What appointments do I have? | 5 | live table |
| `GAR-S2` | synthetic | Which reminders were sent to me, and what did I reply? | 3 | live table |
| `GAR-S3` | synthetic | What are my home blood pressure readings? | 1 | live table |
| `GAR-S4` | synthetic | Which care gaps are open for me? | 4 | live table |
| `GAR-S5` | synthetic | What are my contact preferences and consent? | 1 | live table |

## Re-run

```bash
# every query, read-only, in a container on the rain4 network
docker run --rm --network container:rain4-postgres-1 -v <repo>:/app -w /app -e PG_HOST=127.0.0.1 \
  --entrypoint python rain4-backend scripts/e2e/run_v4_pack.py
# every query typed into its persona's chat in Chrome
node scripts/e2e/chat_queries_v4.mjs
```
