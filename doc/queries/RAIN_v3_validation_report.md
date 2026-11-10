# RAIN v0.3 validation report

Run on 2026-11-06 against the `rain3` Docker stack (frontend :8183, backend :8002, Postgres :55435 `rain_v3`, Neo4j :17689).
Raw results: `artifacts/rain-v3-validation/*.json`.

## Summary

| Check | Result |
|---|---|
| UI conversation API: every scripted question, chip, follow-up, typed variant and an off-topic question, per persona, through nginx | **487/487 pass** (JSON Schema, expected answer, known components, no dead-end chips) |
| Browser: briefing per persona | **6/6** render |
| Browser: every briefing chip clicked, expected answer appears | **46/46 pass**, 0 console errors |
| Browser: every sidebar page per persona | **24/24 render**, 0 console errors |
| Frontend unit tests (vitest) + typecheck | **358/358 pass**, typecheck clean |
| Backend fixtures regenerated from current frontend source | **identical** to committed `rain-api/fixtures/ultra_v3` |
| Backend Ultra v3 API tests | **38/38 pass** |
| PRD suggested questions stored on KAG Persona nodes, asked in that persona's UI | **28/28** reach their dedicated answer |
| SQL persona pack (`rain_v3_persona_queries.sql`), run as `rain_app`, read-only | **60/60 return rows**, no errors |
| Cypher persona pack (`rain_v3_persona_graph.cypher`) | **10/10 return rows** |

## Findings

1. **Neo4j: Persona nodes exist (7 for v0.3).** They were invisible because `MATCH (n {release:'rain-v3.0.0'}) RETURN n LIMIT 300` stops before them (295 of the 523 nodes are Columns). Use KAG-1/KAG-2 in the Cypher pack.
2. **UI county figures cited to public sources are illustrative, not the real data.** `frontend/rain-app/src/data/rain/_shared/constants.ts` marks them illustrative, but the county view cites CDC PLACES / SVI:

| County | UI hypertension % | CDC PLACES BPHIGH % | UI diabetes % | CDC PLACES % | UI SVI | SVI 2022 RPL |
|---|---|---|---|---|---|---|
| Churchill | 32 | 35.4 | 12 | 11.7 | 0.52 | 0.63 |
| Elko | 29 | 32.1 | 10 | 11.0 | 0.41 | 0.62 |
| Humboldt | 31 | 32.0 | 11 | 11.5 | 0.55 | 0.62 |
| Lander | 34 | 36.0 | 13 | 13.0 | 0.62 | 0.58 |
| Pershing | 35 | 35.4 | 13 | 12.1 | 0.71 | 0.68 |
| White Pine | 33 | 36.4 | 12 | 12.6 | 0.48 | 0.25 |

3. **`rain_v3.synthetic` is structurally valid but not scenario data.** Keys join (CIO-S4: 0 unmatched patient references across 7 tables), flags/dates/statuses are usable, but codes and names are generator filler words and numbers are random magnitudes. The UI's own figures ($412 PMPM, 9,400 members) come from the frontend's seeded data, not this database.
4. The UI chat answers from recorded turns (strict matching): scripted questions, chips and sentences containing them resolve; any other free-text question gets the persona's default answer. It does not run SQL or Cypher.

## Gregory Haskins, MBA - Chief Executive Officer

UI: 101/101 API questions pass; 23 distinct answers reached. Browser: chips 9/9, pages 5/5 (Ask AI, Value Insights, Quality Gate and Campaigns, Low-Value Care, Data Sources).

| Query | Data | Question | Rows | First row |
|---|---|---|---|---|
| CEO-S1 | synthetic | What are our attributed members, claims and allowed cost per member (the PMPM gap inputs)? | 1 | `[136, 225, 11641519.89, 85599.41]` |
| CEO-S2 | synthetic | How many ED visits, avoidable ED visits and admissions do we have per 1,000 attributed members? | 1 | `[107, 87, 90, 786.8, 639.7]` |
| CEO-S3 | synthetic | Where is the low-value care? Top sites by low-value spend. | 10 | `["CLINIC_S000189", "Maybe", 4, 298400.49]` |
| CEO-S4 | synthetic | How close are we to the quality gate? Rate vs target for every gate measure. | 15 | `["QUALITY_000004", "Study", 0.9576, true, 3, 0, 0.0]` |
| CEO-S5 | synthetic | Compare our sites on cost per member. | 10 | `["CLINIC_S000006", "Win", false, 1, 98850.79, 98850.79]` |
| CEO-P1 | public | Profile of the six counties we serve: population, rurality (RUCC 2023) and social vulnerability. | 6 | `["Elko County", 32007, 53600, "5", 0.619, 19.2, 8.9]` |
| CEO-P2 | public | What chronic disease burden drives cost in our counties (CDC PLACES crude prevalence)? | 6 | `["White Pine", 36.4, 12.6, 34.4, 17.5, 9.1]` |
| CEO-P3 | public | How do our counties compare with the Nevada county average on annual checkups and insurance gaps? | 5 | `["ACCESS2", "Health Insurance", 13.6, 12.6]` |
| CEO-P4 | public | Which of our counties have designated primary care shortage areas (HRSA HPSA), and how severe? | 6 | `["Churchill County, NV", 3, 19, 45644.0, "Geographic HPSA; Indian Health Service, Tribal Health, and Urban Ind` |
| CEO-P5 | public | Where does each of our counties rank among Nevada's 17 counties for high blood pressure? | 6 | `["White Pine", 32033, 36.4, 9]` |

## Dr. Naomi Castellanos - Chief Medical Officer and Value-Based Care Quality Lead

UI: 105/105 API questions pass; 21 distinct answers reached. Browser: chips 10/10, pages 6/6 (Ask AI, Quality Gate and Campaigns, Low-Value Care, Value Insights, Model Governance, Worklist).

| Query | Data | Question | Rows | First row |
|---|---|---|---|---|
| CMO-S1 | synthetic | How close are we to each quality target? Performance gap per measure. | 15 | `["QUALITY_000050", "Quite", null, 0.7146, 0.333, -0.381, 3]` |
| CMO-S2 | synthetic | Which care gaps are still open, by measure? | 15 | `["QUALITY_000041", "Strong", 4, 0, 1, "2024-06-07"]` |
| CMO-S3 | synthetic | Which patients with an open care gap have home BP readings that count toward the measure? | 3 | `["PATIENT000189", "Denise", "Garcia", 1, "2025-10-05T04:11:56", 1]` |
| CMO-S4 | synthetic | Which providers order the most low-value services (the Winnemucca imaging question), and are they locums? | 10 | `["PROVIDER000106", "Latoya Baldwin", true, "Investment", 1, 99330.76]` |
| CMO-S5 | synthetic | Which members need risk-coding recapture (documented condition not recaptured)? | 20 | `["PATIENT000081", "Leonard", "Ramirez", 4, 3]` |
| CMO-P1 | public | How prevalent is high blood pressure, and how many adults take BP medication, in our counties vs Nevada? | 17 | `["White Pine", 36.4, 74.7, "network"]` |
| CMO-P2 | public | Diabetes and obesity prevalence across Nevada counties, with our counties flagged (the HbA1c context). | 17 | `["Esmeralda", 17.7, 36.1, 32.3, false]` |
| CMO-P3 | public | Preventive screening rates in our counties (colorectal, mammography, cholesterol). | 6 | `["Pershing", 56.1, 72.4, 83.4]` |
| CMO-P4 | public | Social needs that block BP control in our counties (food, housing, transport, utilities, loneliness). | 6 | `["Lander", 18.9, 15.0, 10.4, 10.1, 35.3]` |
| CMO-P5 | public | Mental health burden and designated mental health shortage areas in our counties. | 6 | `["Lander", 19.1, 22.8, 4, 17]` |

## Raj Malhotra - Chief Information Officer and Data and AI Governance Lead

UI: 88/88 API questions pass; 17 distinct answers reached. Browser: chips 10/10, pages 3/3 (Ask AI, Model Governance, Data Sources).

| Query | Data | Question | Rows | First row |
|---|---|---|---|---|
| CIO-S1 | synthetic | Show the model cards: release status, sign-off and how many subgroup checks each passed. | 15 | `["MODEL_CA000002", "Whether", "active", false, "always", "magazine", 3, 0, 3]` |
| CIO-S2 | synthetic | Did the risk model pass its subgroup check? Checks where the gap exceeds the threshold. | 20 | `["MODEL_CA000002", "whether", "series", "situation", 0.9121, 0.017, 0.8951, false, "2026-09-01T21:59:00"]` |
| CIO-S3 | synthetic | How fresh is each data source? Latest record per feed and lag in days. | 7 | `["Eligibility (270/271)", "2026-10-28T07:40:49", 9, 200]` |
| CIO-S4 | synthetic | Show records that failed patient matching (patient_id missing or not in the patient master). | 7 | `["appointment", 200, 0, 0, 0]` |
| CIO-S5 | synthetic | Social needs coverage: how many attributed members have at least one SDOH screening? | 1 | `[136, 94, 42, 69.1]` |
| CIO-P1 | public | What public data feeds the county view? Row counts and state coverage per public table. | 8 | `["zcta_centroids", 33791, null, "2023 Gazetteer"]` |
| CIO-P2 | public | CDC PLACES completeness: measures, counties, missing values and wide confidence intervals per state. | 4 | `["NV", "Age-adjusted prevalence", 40, 17, 680, 0, 99]` |
| CIO-P3 | public | Join-key quality: does every Nevada county match across SVI, RUCC and CDC PLACES by FIPS? | 17 | `[32001, "Churchill County", true, true, true]` |
| CIO-P4 | public | HRSA HPSA status mix and data volume by discipline (primary care vs mental health) in Nevada. | 6 | `["mental health", "Withdrawn", 1093, 18]` |
| CIO-P5 | public | NPPES provider data quality: completeness and duplicate NPIs by state and entity type. | 4 | `["NV", "NPI-1", 6571, 6571, 0, 11, 0]` |

## Dr. Lauren Pike - Program Lead, Rural Health Outcomes Accelerator

UI: 92/92 API questions pass; 17 distinct answers reached. Browser: chips 9/9, pages 4/4 (Ask AI, County Explorer, Value Insights, RHTP Reporting).

| Query | Data | Question | Rows | First row |
|---|---|---|---|---|
| STATE-S1 | synthetic | Primary care visits by month (is volume down since January?), with telehealth share. | 23 | `["2025-01-01", 8, 4, 50.0]` |
| STATE-S2 | synthetic | Telehealth readiness by site: telehealth-capable sites vs the share of their visits done by telehealth. | 3 | `[true, 106, 98, 50.0]` |
| STATE-S3 | synthetic | Where does broadband block telehealth? Share of coverage records not served, by technology. | 15 | `[null, 7, 4, 57.1]` |
| STATE-S4 | synthetic | Rural and frontier mix of the areas in view (FORHP rural, frontier flags). | 9 | `[true, true, 45, 43]` |
| STATE-S5 | synthetic | Small-cell suppression: how many county metric cells are suppressed before the state can publish? | 3 | `[true, 92, 86, 84, 61, 988]` |
| STATE-P1 | public | The county view: all 17 Nevada counties with rurality, vulnerability, population and primary care HPSAs. | 17 | `["Esmeralda County", 32009, 980, "9", 0.908, 1, false]` |
| STATE-P2 | public | Metro vs rural vs frontier-like: Nevada population and county count by RUCC group. | 3 | `["1-3 metro", 5, 2874379.0, "Carson City, Clark County, Lyon County, Storey County, Washoe County"]` |
| STATE-P3 | public | Primary care shortage counties: designated primary care HPSAs by county, type and severity. | 25 | `["Clark County, NV", "Federally Qualified Health Center", 4, 22, 20.0, 1538488.0]` |
| STATE-P4 | public | Where does broadband limit telehealth? Households without internet (SVI) by county, worst first. | 17 | `["Nye County", 32023, 22.4, 4884, "4", false]` |
| STATE-P5 | public | Health center site coverage per 100,000 residents by Nevada county (where do Accelerator funds go first?). | 17 | `["Lyon County", 59435, 0, 0.0, "2"]` |

## Teresa Lopez, CHW - Community Health Worker and Care Coordinator

UI: 62/62 API questions pass; 10 distinct answers reached. Browser: chips 4/4, pages 3/3 (Ask AI, Worklist, Scheduling).

| Query | Data | Question | Rows | First row |
|---|---|---|---|---|
| CHW-S1 | synthetic | Open my worklist: open outreach tasks by priority, with who to call. | 25 | `["OUTREACH000160", 0.9965, "standard", "active", "PATIENT000062", "Eric Collins", "367.697.6438x156", "2025-11` |
| CHW-S2 | synthetic | How is the campaign going? Members, cuffs on file and bookings per campaign. | 15 | `["CAMPAIGN000031", "Method", "rejected", 252, 4, 2, 3, 75.0]` |
| CHW-S3 | synthetic | Who has not answered reminders? Patients with reminders that got no reply or are still pending. | 20 | `["PATIENT000096", "Elizabeth Schmidt", "(708)626-7734", 5, 2, "2026-10-29T03:17:01", "enterprise, premium, sta` |
| CHW-S4 | synthetic | Who is closest to BP control? Campaign members with their latest home BP reading. | 25 | `["PATIENT000002", "Jeffrey Lawrence", 661, true, 41774.8, 23075.02, "2026-06-05T15:03:28", false]` |
| CHW-S5 | synthetic | How should I reach each patient? Consented contact channel and language preferences. | 18 | `["premium", true, 19, 19]` |
| CHW-P1 | public | Where can I send patients? Health center sites in or near our counties, with hours and phone. | 6 | `["Elko County", "Carlin", "Carlin Community Health Center", "310 Memory Ln", "775-754-2666", 40.0, "Service De` |
| CHW-P2 | public | Transportation barriers in our counties (CDC PLACES) vs households with no vehicle (SVI). | 6 | `["Lander", 10.4, 2.4, 5519.24436764232]` |
| CHW-P3 | public | Talking points on social needs: food, housing, utility and food-stamp rates in our counties. | 6 | `["Lander", 18.9, 17.2, 15.0, 10.1, 25.6]` |
| CHW-P4 | public | Do I need Spanish talking points? Hispanic share and limited-English households by county (SVI). | 6 | `["Humboldt County", 17266, 27.9, 3.6, 15.4]` |
| CHW-P5 | public | Which primary care practices (NPPES) are in our towns: Elko, Winnemucca, Fallon, Ely, Lovelock, Battle Mountain? | 97 | `["BATTLE MOUNTAIN", "Ambulance, Land Transport", 2, 2, 0]` |

## Brandon Kee - Patient Access Coordinator

UI: 39/39 API questions pass; 7 distinct answers reached. Browser: chips 4/4, pages 3/3 (Ask AI, Scheduling, Reminders).

| Query | Data | Question | Rows | First row |
|---|---|---|---|---|
| ACCESS-S1 | synthetic | What slots are open? Open slots by site, in-person vs telehealth. | 20 | `["CLINIC_S000109", "Only", true, 6, 3, "2024-01-13T05:13:08"]` |
| ACCESS-S2 | synthetic | Show unconfirmed visits: pending appointments and whether eligibility was verified. | 25 | `["APPOINTM000178", "pending", "recently", "2023-12-24T03:51:38", "Julia Tapia", "001-689-241-3435x24082", null` |
| ACCESS-S3 | synthetic | Handle the replies: reminder replies waiting for action, by channel and delivery status. | 33 | `["basic", "approved", 12, 12, 12, 520.7]` |
| ACCESS-S4 | synthetic | Why telehealth for this patient? Longest drive times and whether the site can do telehealth. | 20 | `["religious", "CLINIC_S000097", "Year", true, 99938.4, "offer telehealth"]` |
| ACCESS-S5 | synthetic | Start bookings: campaign members not yet booked, highest outreach rank first, with visit mode. | 25 | `[3, "PATIENT000197", "Roy Hawkins", null, "newspaper", true, "Parent"]` |
| ACCESS-P1 | public | How remote are the ZIP areas in our region? Largest ZCTAs (sq mi) in northern/eastern Nevada (894xx-898xx). | 20 | `["89412", 3084.5, 41.121163, -119.704982]` |
| ACCESS-P2 | public | Health center capacity: operating hours per week of sites in Nevada's rural counties. | 4 | `["Elko County", 5, 197.0, 39.4]` |
| ACCESS-P3 | public | Primary care capacity gap: HPSA FTE shortage and population affected in our counties. | 22 | `["Churchill County, NV", "FALLON TRIBAL HEALTH CENTER", "Indian Health Service, Tribal Health, and Urban India` |
| ACCESS-P4 | public | Primary care providers by town in our region (NPPES: family, internal medicine, NP, PA, clinics). | 7 | `["ELKO", 42]` |
| ACCESS-P5 | public | Expect eligibility problems? Uninsured and no-checkup rates in our counties. | 6 | `["Pershing", 15.0, 70.9, 56.4]` |
