# RAIN v0.4: validation report

PRD v0.4 (`doc/prd/RAIN_Platform_PRD_v0.4.docx`, 14 personas) built end to end in `C:\Users\pa613\RAIN4.0-DIF_BT_integration` (branch `RAIN4.0-DIF_BT_integration`) and run as compose project `rain4`. Checked on 2026-11-10.

| Stage | Check | Result |
|---|---|---|
| Factory inputs | `RAIN_Platform_PRD_v0.4_factory_extract.txt` + `_planned_schemas.sql` | 53 planned tables, every one in the extract |
| Factory run | `dif-build-orchestrator`, release `rain-v4.0.0`, package `4.0.0` | succeeded; 53 entities, 53 classes, no orphans; precheck passed; readiness partial (27 classes without an upper-ontology concept, 1 unmapped attribute; `no_show_rate` now modelled) |
| KAG | Release `rain-v4.1.0` from `scripts/e2e/kag_v4_refresh.py` (the factory ontology + PRD v0.4 seed + rain_v4 + query pack + UI contracts + flows) in Neo4j `neo4j`, nothing else in the database | 2,603 nodes, 3,930 relationships, **14 Persona nodes**; 21/21 checks pass (`RAIN_v4_kag_check.md`) |
| KAG | Cypher pack `rain_v4_persona_graph.cypher` | **24/24** queries return rows |
| Postgres | `rain_v4.synthetic` | 59 tables, 689,446 rows of calibrated row-level data (`scripts/e2e/synth/`) |
| Postgres | `rain_v4.public_data` | 24 tables loaded (NV and TN); 2 sources blocked, see `RAIN_v4_public_data_in_ui.md` |
| Postgres | `rain_v4.ui_v4.dataset` | configuration and persona templates only: no stored figures |
| Computed UI data | `metrics_v4.py` against the scenario targets | values equal **324**, differ 52, render errors **0** (`RAIN_v4_metrics_roundtrip.md`) |
| Data API | `/api/v4/data` | 83 table endpoints (59 synthetic, 24 public); 24/24 public tables answer through the UI origin |
| Query pack | `/api/v4/queries`, 14 personas x 10 | **140/140** return rows |
| Backend tests | every `test_*v4*.py` in rain4-backend-1 (UI data, chat, queries, flow, persona templates) | **388/388** |
| Frontend gate | typecheck, 516 vitest tests | all pass |
| Chat through the UI origin | every scripted question, chip, follow-up, variant, off-topic | **436/436** |
| Real browser | briefings, chips, pages, patients | **14/14**, **98/98**, **51/51**, **2/2**, no console errors |
| Real browser | every persona query typed in the chat | **140/140** live tables |
| Write-back flow | book, contact, reply, reading, inbox, sign-off, then reset | **7/7** steps, reset restores every value (`RAIN_v4_flow_check.md`) |
| Data-driven | edit a benchmark row and a claim in Postgres; the CEO tiles in the real UI change; restore | passed (`scripts/e2e/demo_data_driven_v4.py`) |

## Known limits

- **Blocked public sources:** FCC broadband needs the user's FCC account and API token; CMS Geographic Variation needs a browser download from data.cms.gov; VSAC value sets need a UMLS licence.
- **Computed against the PRD story:** the generator is calibrated to the PRD's Q3 checkpoint, so most figures match it; the ones that come out differently (BP controls needed 158 vs 180, low-broadband members, the frontier score gap, county public figures) are listed in `RAIN_v4_metrics_roundtrip.md`, and the UI shows the computed value.
- **Proposed scopes:** Dr. Hargrove at Winnemucca, Kayla Brooks at Battle Mountain, Dr. Okafor's panel at Battle Mountain and Lovelock, Denise Holloway's frontier list: proposed in PRD v0.4 Section 13 item 2, not yet confirmed.
- **Hannah Lee** (payer analyst, phase 2 in the PRD) is in the UI now; Ruby Valley's claims feed has no pharmacy claims, so its PMPM is labelled a partial feed.
- **`/api/v3`** routes are still mounted in the rain4 backend but read `rain_v3`, which only the rain3 stack holds.

## Reports

- [RAIN_v4_persona_queries.md](RAIN_v4_persona_queries.md): the 140 queries and their results
- [RAIN_v4_public_data_in_ui.md](RAIN_v4_public_data_in_ui.md): every public table, where it is used, what is blocked
- [RAIN_v4_backend_data_proof.md](RAIN_v4_backend_data_proof.md): console proof, live values, the Postgres-edit proof
- [RAIN_v4_chat_end_to_end_check.md](RAIN_v4_chat_end_to_end_check.md): every persona's answers and what each draws
- Raw results: `artifacts/rain-v4-validation/` (screenshots in `crawl/`)
