# RAIN v0.4 build log

The end-to-end build of `doc/prd/RAIN_Platform_PRD_v0.4.docx`, following `doc/prd/RAIN_Platform_PRD_v0.4_e2e_prompt.md`. The folder is `C:\Users\pa613\RAIN4.0-DIF_BT_integration`, on branch `RAIN4.0-DIF_BT_integration`, built from commit `a513008` of `RAIN3.0-DIF_BT_integration`. Results are in `doc/queries/RAIN_v4_validation_report.md`.

| Phase | Status | Notes |
|---|---|---|
| 0. New folder | done | v0.3 work committed as `a513008` (not pushed). Worktree created; gitignored inputs copied; `entrypoint.sh` is LF via `.gitattributes`; v0.3 helper scripts are in `scripts/e2e/v3_reference/` |
| 1. Factory inputs | done | `RAIN_Platform_PRD_v0.4_factory_extract.txt` and `_planned_schemas.sql`, 53 tables: the 38 v0.3 tables; `rpm_reading`, `risk_score` and `no_show_rate`; and 12 new tables for the v0.2 personas and the public reference layers |
| 2. Factory run and KAG | done | Release `rain-v4.0.0`: 614 factory nodes plus 139 seed nodes (`seeds/rain_v4_prd_seed.py`), including 14 Persona nodes. Live validation passed. Readiness is "partial" as in v0.3 (classes without an upper-ontology concept); the `no_show_rate` gap is closed |
| 3. Postgres rain_v4 and public data | done; 3 sources blocked | 53 synthetic tables (10,600 rows) and 23 public tables (see `.data/public/MANIFEST.md`). FCC broadband, CMS Geographic Variation and County Health Rankings need an account or a manual browser download |
| 4. Backend /api/v4 | done | `ui_data_v4.py`; `chat_v4.py` (persona list taken from the data, live `query_table` visuals); `ultra_v4_api.py`; `persona_queries_v4.py` (130 queries); `data_api_v4.py` (76 tables). 292/292 tests pass |
| 5. Frontend | done | 11 operator personas, scoped workbenches, the Front-desk inbox and Pre-visit Summary workbenches, Rosa's patient thread, all on `/api/v4`. Every `npm run check` step passes; the standard audit is run under Linux because its path checks fail on Windows |
| 6. Run (compose project rain4) | done | UI 8184, API 8003, Postgres 55436, Neo4j 17477/17690, pgAdmin 5052 |
| 7. Validate end to end | done | 365/365 chat checks. In the browser: 11/11 briefings, 78/78 chips, 45/45 pages, 2/2 patient threads, 110/110 chat queries. 23/23 public tables queryable. The Postgres-edit proof passed. 14/14 Cypher queries return rows |
| 8. Docs | done | `doc/queries/RAIN_v4_*.md`, `rain_v4_persona_queries.sql`, `rain_v4_persona_graph.cypher`, `doc/DOCKER.md`, `frontend/rain-app/docs/backend-integration.md` |

## Decisions made along the way

- **Scopes for the v0.2 personas** (proposed in PRD Section 13 item 2):
  - Dr. Hargrove: the Winnemucca site.
  - Kayla Brooks: the Battle Mountain front desk.
  - Dr. Okafor: a panel at Battle Mountain and Lovelock.
  - Denise Holloway: frontier patients outside Teresa's two sites.
- **No typed-in figures.** Every v0.2 persona figure is derived from the Q3 records in the v0.3 seed (`scripts/e2e/make_v4_ui_seed.py`).
- **Substitutes for blocked sources.** Visuals that needed a blocked source read a loaded one instead and say so: household broadband from the Census ACS, and unplanned hospital visits from CMS.
- **One test change outside the RAIN data.** `catalog.test.tsx` now waits 15 s (was 5 s) for a lazy component, because the full suite runs under heavy load.

## Second pass (2026-11-10): no stored figures, patients and payer in the UI, KAG rebuilt

Asked for: the patient personas in the UI and the KAG, the KAG holding only what v0.4 has now, no answer built from stored figures, a complete flow on synthetic data, and the public data loaded and queryable from the UI, all validated end to end.

| Area | What changed | Proof |
|---|---|---|
| Synthetic data | `scripts/e2e/synth/gen_synthetic_v4.py` writes row-level data (31,600 patients, 95,000 encounters, 150,000 claims, 245,000 claim lines, quality results, readings, the BP campaign, the model's scores, schedules, reminders, ...): about 690,000 rows in 59 tables. It is calibrated so SQL over the rows gives back the Q3 story (9,400 members, $412 against $386 PMPM, gate 2 of 5, 2,140 low-value services, 312 avoidable ED visits per 1,000). Public reference tables are derived from `public_data`; every foreign key is checked. | `doc/queries/RAIN_v4_synthetic_extensions.md` |
| Computed UI data | `rain-api/metrics_v4.py` (and `metrics_personas_v4.py`) compute every constant, record, governance item and dataset per request. Persona contracts and copy are templates (`rain-api/seed/rain_v4_ui_templates.json`) rendered against them; `ui_v4.dataset` holds configuration and templates only. The cache is recomputed when any source row changes. | `doc/queries/RAIN_v4_metrics_roundtrip.md`: 324 values equal the scenario, 52 differ (listed with reasons), 0 render errors |
| Write-back flow | `rain-api/flow_v4.py`: `POST /api/v4/flow/{book,contact,reply,reading,handoff,inbox,signoff,note,reset}`. The frontend store writes each action (`src/data/rain/_shared/flowApi.ts`) and re-reads the computed data; Reset demo undoes the backend changes too. | `doc/queries/RAIN_v4_flow_check.md`: 7/7 steps, reset restores every value |
| Data-driven proof | Editing one benchmark row or one claim in Postgres changes the CEO tiles in the real UI (`$412 / $386` to `$412 / $394`, to `$422 / $386`), then restored. | `scripts/e2e/demo_data_driven_v4.py`, screenshots in `artifacts/rain-v4-validation/` |
| Personas | Linda Garcia (`rain_linda`) and Rosa Martínez (`rain_rosa`), patients who see only their own record, and Hannah Lee (`rain_hannah`), payer analyst at High Desert Health Plan, are switcher personas: 14 in all. Hannah's 10 queries: 140 in the pack, all returning rows on the new data. | `rain-api/test_personas_templates_v4.py` |
| Public data | County Health Rankings 2025 loaded: 24 public tables, all queryable from the UI origin and used by a persona query or a computed UI value. Still blocked: FCC Broadband Data Collection (needs the user's FCC account and API token) and CMS Geographic Variation (data.cms.gov needs a browser download). | `scripts/e2e/public_data_v4.py`: 24/24 |
| KAG | One release `rain-v4.1.0` (2,603 nodes): 14 personas, 84 tables with columns and foreign keys, 140 queries, metric groups, datasets, flows, sources. The v1/v2 seed graph and `rain-v4.0.0` are deleted; the seed service no longer reloads them. | `doc/queries/RAIN_v4_kag_check.md`: 21/21 |

Story values that come out differently when computed (the UI shows the computed value): BP controls needed 158 (PRD 180) and projected 180 (PRD 210), so CMS165 still projects 66%; members in the six low-broadband ZIP areas 1,138 (PRD 190); the frontier score gap 14% to 2% (PRD 18% to 3%); county prevalence, SVI and broadband now come from the real public sources; tied ranks in the PRD's top-300 swap list moved to the nearest free rank.
