# Is the public data queryable in the RAIN v0.3 UI?

Checked on 2026-11-06 against the `rain3` stack (UI http://localhost:8183). Raw results: `artifacts/rain-v3-validation/public_data_in_ui.json`.

## Answer

**No. None of the 8 public datasets in `rain_v3.public_data` can be queried from the UI.**

- The UI never reads the database. Across every test it called only `GET /api/v3/ui/briefing` and `POST /api/v3/ui/ask`, which return pre-recorded answers. The frontend code has no call to the data API (`/api/v3/data`).
- Typed questions about public data almost always get the persona's generic reply: **123 of 144** (8 datasets x 2-4 questions x 6 personas). 16 match an unrelated scripted answer. 5 reach an answer that cites the dataset, but none returns the value asked for.
- Where the UI shows figures labelled with public sources (the six-county table and County Explorer layers), the values are **illustrative**, hard-coded in `frontend/rain-app/src/data/rain/_shared/constants.ts`. The table says so in its footer ("Prevalence and SVI values are illustrative"). Some differ from the real data; see below.
- The data **is** queryable outside the chat: every public table answers through the backend data API on the UI's own address, and in pgAdmin. Links are at the end.

## Per dataset

| Public table (`rain_v3`) | Rows loaded | UI source name | Answers citing it | Typed questions: cites dataset / other answer / default | Returns the queried value? | Data API |
|---|---|---|---|---|---|---|
| `cdc_places` | 7,630 | CDC PLACES (2025 release) | 9 | 0 / 3 / 21 (of 24) | No. E.g. "hypertension rate in Elko County?" → default (CEO) or the CMS summary (State). Real: 32.1% | 200 OK |
| `svi_county` | 112 | CDC/ATSDR SVI (2022) | 1 | 1 / 1 / 16 (of 18) | No. State gets the illustrative table: Pershing **0.71**, real **0.68** | 200 OK |
| `rucc_county` | 336 | USDA RUCC (2023) | 3 | 0 / 3 / 15 (of 18) | No. Answers never give a RUCC code (Lander is 9) | 200 OK |
| `hpsa_primary_care` | 3,179 | HRSA HPSA | 6 | 1 / 3 / 14 (of 18) | Partly. The State table says Lander is a "Whole county" shortage area, which matches HRSA (5,710 of 5,728 residents) | 200 OK |
| `hpsa_mental_health` | 2,881 | HRSA HPSA | 6 | 0 / 2 / 10 (of 12) | No. Matched the CEO opening briefing or the broadband answer | 200 OK |
| `health_center_sites` | 338 | HRSA health center sites | 2 | 0 / 2 / 16 (of 18) | No. "Where are the health center sites?" → default (82 NV sites exist) | 200 OK |
| `providers` | 21,527 | NPPES NPI Registry | 3 | 1 / 0 / 17 (of 18) | No. "Providers in Winnemucca?" → imaging rates of 3 locums. Real: 25 NPPES providers | 200 OK |
| `zcta_centroids` | 33,791 | Census ZCTA gazetteer | 2 | 2 / 2 / 14 (of 18) | No. "Most remote ZIP codes?" → the six low-broadband ZIPs (FCC, not loaded), not land area | 200 OK |

"Answers citing it" counts the recorded chat answers whose source chips name the dataset. The figures in those answers are scripted, not read from the table.

### Every typed question and what came back

| Dataset | Question | Persona | Result | Answer |
|---|---|---|---|---|
| `cdc_places` | What is the hypertension rate in Elko County? | rain_state | other scripted answer | `st_summary`: Here is the RHTP progress summary: people served, services and outcomes by county, sourced |
| `cdc_places` | Which county has the highest obesity rate? | rain_state | other scripted answer | `st_summary`: Here is the RHTP progress summary: people served, services and outcomes by county, sourced |
| `cdc_places` | Show me CDC PLACES data for Nevada | rain_cio | other scripted answer | `cio_public`: Six public sources feed the county view: PLACES, SVI, HRSA shortage areas, FCC broadband,  |
| `svi_county` | What is the social vulnerability index for Pershing County? | rain_state | answered, cites dataset | `st_county`: Here is each county side by side; Lander and Pershing stand out. |
| `svi_county` | Show SVI by county | rain_cio | other scripted answer | `cio_public`: Six public sources feed the county view: PLACES, SVI, HRSA shortage areas, FCC broadband,  |
| `rucc_county` | What is the RUCC code for Lander County? | rain_cio | other scripted answer | `cio_public`: Six public sources feed the county view: PLACES, SVI, HRSA shortage areas, FCC broadband,  |
| `rucc_county` | What is the RUCC code for Lander County? | rain_state | other scripted answer | `st_county`: Here is each county side by side; Lander and Pershing stand out. |
| `rucc_county` | Show rural urban classification by county | rain_cio | other scripted answer | `cio_public`: Six public sources feed the county view: PLACES, SVI, HRSA shortage areas, FCC broadband,  |
| `hpsa_primary_care` | Which counties are primary care shortage areas? | rain_cio | other scripted answer | `cio_features`: Prior-year cost and primary care visits carry 41 percent of the weight, and both read thin |
| `hpsa_primary_care` | Which counties are primary care shortage areas? | rain_state | other scripted answer | `st_trend`: Lander and Pershing lost 14 percent of primary care visits since January, while the other  |
| `hpsa_primary_care` | Is Lander County a health professional shortage area? | rain_cio | other scripted answer | `cio_public`: Six public sources feed the county view: PLACES, SVI, HRSA shortage areas, FCC broadband,  |
| `hpsa_primary_care` | Is Lander County a health professional shortage area? | rain_state | answered, cites dataset | `st_county`: Here is each county side by side; Lander and Pershing stand out. |
| `hpsa_mental_health` | Which counties have a mental health shortage? | rain_ceo | other scripted answer | `ceo_brief`: Good morning, Gregory. Your Q3 reconciliation from High Desert Health Plan is in, and I ha |
| `hpsa_mental_health` | Which counties have a mental health shortage? | rain_state | other scripted answer | `st_bb`: Six frontier ZIP codes have under 40% video-ready broadband, so rechecks there need a phon |
| `health_center_sites` | List FQHC sites in Elko County | rain_state | other scripted answer | `st_ctx_elko`: Elko County lost 3 percent of primary care visits since January, and avoidable ED sits at  |
| `health_center_sites` | What are the opening hours of the health centers? | rain_access | other scripted answer | `acc_start`: Opening Scheduling at your first booking, Linda Garcia's telehealth BP recheck, so you can |
| `providers` | How many providers are in Winnemucca? | rain_cmo | answered, cites dataset | `cmo_providers`: The three rotating clinicians at Winnemucca order imaging at 26 to 28%, against 9% network |
| `zcta_centroids` | Which ZIP codes are the most remote? | rain_cio | other scripted answer | `cio_card`: The impactability score ranks rising-risk members for outreach, and version 1.3 failed its |
| `zcta_centroids` | Which ZIP codes are the most remote? | rain_state | answered, cites dataset | `st_bb`: Six frontier ZIP codes have under 40% video-ready broadband, so rechecks there need a phon |
| `zcta_centroids` | Show ZIP code areas in our region | rain_cio | other scripted answer | `cio_card`: The impactability score ranks rising-risk members for outreach, and version 1.3 failed its |
| `zcta_centroids` | Show ZIP code areas in our region | rain_state | answered, cites dataset | `st_bb`: Six frontier ZIP codes have under 40% video-ready broadband, so rechecks there need a phon |

All other combinations (123) returned the persona's default reply.

## What the UI shows vs the real data

The six-county table (State persona: "Show me the county view" / County Explorer):

| County | Hypertension % UI / CDC PLACES | Diabetes % UI / CDC PLACES | SVI UI / SVI 2022 |
|---|---|---|---|
| Elko | 29 / 32.1 | 10 / 11.0 | 0.41 / 0.62 |
| Humboldt | 31 / 32.0 | 11 / 11.5 | 0.55 / 0.62 |
| Lander | 34 / 36.0 | 13 / 13.0 | 0.62 / 0.58 |
| Pershing | 35 / 35.4 | 13 / 12.1 | 0.71 / 0.68 |
| White Pine | 33 / 36.4 | 12 / 12.6 | 0.48 / 0.25 |
| Churchill | 32 / 35.4 | 12 / 11.7 | 0.52 / 0.63 |

The Data Sources page record counts are illustrative too (the source file says so). For example, CDC PLACES is listed as 1,240 records against 7,630 rows loaded, and NPPES as 9,870 against 21,527 (9,694 in NV).

## The 19 public sources the UI lists

| UI source | Loaded in `rain_v3`? | Chat answers citing it |
|---|---|---|
| CDC PLACES | yes: `cdc_places` | 9 |
| CDC/ATSDR SVI | yes: `svi_county` | 1 |
| HRSA HPSA | yes: `hpsa_primary_care`, `hpsa_mental_health` | 6 |
| County Health Rankings | no | 0 |
| USDA RUCC | yes: `rucc_county` | 3 |
| HRSA FORHP rural areas | no | 1 |
| Census ZCTA | yes: `zcta_centroids` (gazetteer only, no ZIP-to-county file) | 2 |
| Census boundary files | no (the map uses simplified shapes in the frontend) | 1 |
| Census ACS 5-year | no (SVI includes some ACS-derived fields) | 1 |
| FCC National Broadband Map | no | 8 |
| HRSA health center sites | yes: `health_center_sites` | 2 |
| CMS Hospital General Information | no | 0 |
| CMS Provider of Services | no | 0 |
| NPPES NPI Registry | yes: `providers` | 3 |
| HRSA UDS | no | 0 |
| CMS Medicare Geographic Variation | no | 1 |
| CMS eCQMs | no (measure specifications, not a data table) | 0 (the "eCQM Engine" chip is cited 13 times) |
| Synthea | no (`synthetic` is generator output, not Synthea) | 0 |
| OpenStreetMap road network | no | 8 ("Travel Time") |

7 of the 19 are loaded (as 8 tables). The rest, including FCC Broadband and OpenStreetMap travel time, which answers cite 8 times each, exist only as labels.

## Where the public data IS queryable

**Data API through the UI's address.** These are GET links, so they open in a browser:

- High blood pressure, all NV counties: http://localhost:8183/api/v3/data/public_data/cdc_places?stateabbr=NV&measureid=BPHIGH&data_value_type=Crude%20prevalence
- County overview: CDC PLACES + SVI + RUCC joined (any `measureid`): http://localhost:8183/api/v3/data/views/county-overview?state=NV&measureid=BPHIGH
- SVI, NV counties: http://localhost:8183/api/v3/data/public_data/svi_county?st_abbr=NV
- RUCC 2023, NV counties: http://localhost:8183/api/v3/data/public_data/rucc_county?state=NV&attribute=RUCC_2023
- Designated primary care HPSAs, NV: http://localhost:8183/api/v3/data/public_data/hpsa_primary_care?primary_state_abbreviation=NV&hpsa_status=Designated&limit=500
- Designated mental health HPSAs, NV: http://localhost:8183/api/v3/data/public_data/hpsa_mental_health?primary_state_abbreviation=NV&hpsa_status=Designated&limit=500
- Health center sites, NV: http://localhost:8183/api/v3/data/public_data/health_center_sites?site_state_abbreviation=NV&limit=100
- NPPES providers in Winnemucca: http://localhost:8183/api/v3/data/public_data/providers?state=NV&city=WINNEMUCCA
- ZCTA 89412 (largest in the region): http://localhost:8183/api/v3/data/public_data/zcta_centroids?geoid=89412

Any column can be used as an exact-match filter; `limit` (max 500), `offset` and `order_by` are also supported. All tables are listed at http://localhost:8183/api/v3/data/tables, and the interactive docs are at http://localhost:8002/docs (tag `data-v3`).

**pgAdmin** (http://localhost:5051): the 30 public queries in [RAIN_v3_persona_queries.md](RAIN_v3_persona_queries.md) (the `-P` IDs).

## What it would take to make it queryable in the UI

1. **Show real values in the workbenches:** point the county getters in `src/data/rain/_shared` (`COUNTIES`, the County Explorer layers) at `/api/v3/data/views/county-overview` and the SVI/RUCC/HPSA endpoints, instead of the illustrative constants. This is the smallest change, and `docs/backend-integration.md` names these getters as the swap point.
2. **Answer typed questions from data:** `/api/v3/ui/ask` only matches recorded turns. Free-text questions about public data need a live path, such as the governed NLQ agent in `insights/` (`/api/v2/ask`), pointed at `rain_v3.public_data` and returning the Ultra answer format.
3. **Load the cited-but-missing sources** (FCC Broadband, OpenStreetMap travel time, ACS, FORHP, CMS Geographic Variation), or stop citing them.