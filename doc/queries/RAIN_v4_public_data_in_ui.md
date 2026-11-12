# RAIN v0.4: every public dataset, loaded and queryable

24 public tables are loaded in `rain_v4.public_data` (NV and TN rows). **24/24** answer `GET /api/v4/data/public_data/<table>` through the UI's own origin, and **24/24** are read by a persona query or a live UI view. The one that is not, `acs_variables`, is the column dictionary for `acs_county`.

| Table | API rows (limit 5) | Persona queries reading it | Live UI views reading it |
|---|---|---|---|
| `acs_county` | 5 | BEL-P2, GAR-P2, GAR-P5, HOL-P1, HOL-P4, ROS-P2 | bell.v_fcc, holloway.v_acs, GET /api/v4/ui/data (live overlay / KPI) |
| `acs_variables` | 5 | - | GET /api/v4/ui/data (live overlay / KPI) |
| `cdc_places` | 5 | ACCESS-P5, CEO-P2, CEO-P3, CEO-P5, CHW-P2, CHW-P3, CIO-P1, CIO-P2, CIO-P3, CMO-P1, CMO-P2, CMO-P3, CMO-P4, CMO-P5, GAR-P3, HAN-P3, HAN-P5, HAR-P1, HOL-P5, OKA-P5, ROS-P4 | GET /api/v4/ui/data (live overlay / KPI) |
| `cms_hospitals` | 5 | BRK-P4 | GET /api/v4/ui/data (live overlay / KPI) |
| `cms_pos_facilities` | 5 | BEL-P3, BRK-P3 | bell.v_sites, GET /api/v4/ui/data (live overlay / KPI) |
| `cms_unplanned_visits` | 5 | HAN-P4, HAR-P2 | hargrove.v_ed_public, GET /api/v4/ui/data (live overlay / KPI) |
| `county_boundaries` | 5 | - | GET /api/v4/ui/data (live overlay / KPI) |
| `county_health_rankings` | 5 | HAN-P1, HAN-P2 | hannah.v_chr, hannah.v_chr_pcp, GET /api/v4/ui/data (live overlay / KPI) |
| `ecqm_measures` | 5 | OKA-P1, OKA-P2, ROS-P5 | okafor.v_ecqm, GET /api/v4/ui/data (live overlay / KPI) |
| `forhp_county_status` | 5 | BEL-P4, ROS-P3 | GET /api/v4/ui/data (live overlay / KPI) |
| `forhp_rural_tracts` | 5 | HOL-P3 | GET /api/v4/ui/data (live overlay / KPI) |
| `health_center_sites` | 5 | ACCESS-P2, BEL-P3, BRK-P2, CHW-P1, CIO-P1, STATE-P5 | bell.v_sites, GET /api/v4/ui/data (live overlay / KPI) |
| `hpsa_mental_health` | 5 | CIO-P1, CIO-P4, CMO-P5 | GET /api/v4/ui/data (live overlay / KPI) |
| `hpsa_primary_care` | 5 | ACCESS-P3, BRK-P5, CEO-P4, CIO-P1, CIO-P3, CIO-P4, GAR-P4, HAR-P5, STATE-P1, STATE-P3 | GET /api/v4/ui/data (live overlay / KPI) |
| `osrm_drive_times` | 5 | BRK-P1, ROS-P1 | brooks.v_drive, GET /api/v4/ui/data (live overlay / KPI) |
| `osrm_nearest_site` | 5 | BEL-P5, GAR-P1, HOL-P2 | GET /api/v4/ui/data (live overlay / KPI) |
| `providers` | 5 | ACCESS-P4, CHW-P5, CIO-P1, CIO-P5, OKA-P4 | GET /api/v4/ui/data (live overlay / KPI) |
| `rucc_county` | 5 | BEL-P4, CEO-P1, CIO-P1, CIO-P3, ROS-P3, STATE-P1, STATE-P2, STATE-P4, STATE-P5 | GET /api/v4/ui/data (live overlay / KPI) |
| `svi_county` | 5 | BEL-P4, CEO-P1, CHW-P2, CHW-P4, CIO-P1, CIO-P3, HAR-P5, STATE-P1, STATE-P2, STATE-P4, STATE-P5 | GET /api/v4/ui/data (live overlay / KPI) |
| `uds_health_center_cqm` | 5 | HAR-P4 | GET /api/v4/ui/data (live overlay / KPI) |
| `uds_state_national_cqm` | 5 | HAR-P3, OKA-P3 | hargrove.v_uds, GET /api/v4/ui/data (live overlay / KPI) |
| `uds_state_national_summary` | 5 | - | GET /api/v4/ui/data (live overlay / KPI) |
| `zcta_centroids` | 5 | ACCESS-P1, CIO-P1 | GET /api/v4/ui/data (live overlay / KPI), drive-time inputs (osrm tables) |
| `zcta_county` | 5 | BEL-P5, HOL-P2 | GET /api/v4/ui/data (live overlay / KPI) |

## Sources the PRD names that are not loaded yet

These stay visible in the Data Sources workbench as **Not loaded yet** with 0 records, instead of the seed's illustrative counts. Nothing was invented for them. Dropping the file in its folder and re-running `deploy/scripts/load_public_data.py` loads it (the loader already lists the expected file names).

| Source | Why it is not loaded | What unblocks it |
|---|---|---|
| FCC National Broadband Map | The download page refuses scripts; the API needs an account | A free FCC account and API token, or a browser download of the county summary CSV into `.data/public/fcc_broadband/` |
| CMS Medicare Geographic Variation | data.cms.gov refuses scripted downloads | A browser download of the 2014-2024 public use file into `.data/public/cms_geo_variation/` |
| County Health Rankings 2025 | The site serves a browser challenge to scripts | A browser download of `analytic_data2025.csv` into `.data/public/county_health_rankings/` |
| CMS Provider of Services (official file) | Same data.cms.gov block | Loaded instead from HRSA's republished CMS POS layers (`cms_pos_facilities`, 1,862 NV+TN rows) |
| HRSA FORHP Excel workbooks | hrsa.gov refuses scripts | Loaded instead from HRSA's rural map service (`forhp_rural_tracts`, `forhp_county_status`) |
| VSAC value sets for the eCQMs | Need a UMLS licence | A UMLS (NLM) account; the eCQM specifications themselves are loaded (`ecqm_measures`) |
| Synthea | A generator, not a dataset | The factory's synthetic generator fills the same role (53 tables, 10,600 rows) |

Where a visual needed a blocked source, it now reads a loaded one and says so: household broadband from the Census ACS (not the FCC map) and hospital unplanned visits from CMS (not Geographic Variation).
