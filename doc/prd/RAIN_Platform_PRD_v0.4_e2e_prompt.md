# Prompt: build PRD v0.4 end to end in its own folder

Paste everything below the line into a new Claude Code session opened in `C:\Users\pa613\RAIN`.

---

Take `doc/prd/RAIN_Platform_PRD_v0.4.docx` (the merged PRD: 14 personas, use cases A and B) through the same end-to-end process the v0.3 wave went through, in a new separate folder. The result is a running stack where:
- every UI figure and every chat answer comes from the backend;
- every public source in the PRD is loaded into Postgres and can be queried;
- every persona's queries pass.

Work through all phases without stopping. Stop and ask me only if you are blocked on credentials or a licence, or before a destructive action. Keep a checklist in `doc/prd/RAIN_v0.4_build_log.md` and update it after each phase, so the work can resume if the session ends.

## Reference (read first, do not modify)

- `C:\Users\pa613\RAIN` (branch `RAIN3.0-DIF_BT_integration`) is the v0.3 wave and the template for every step below. Its stack runs as compose project `rain3` on ports 8183, 8002, 55435, 17476 and 17689. Leave that stack running and untouched.
- Read these in that repo:
  - `knowledge-gathering/README.md`: factory steps and the factory-extract grammar
  - `knowledge-gathering/seeds/rain_v3_prd_seed.py`
  - `deploy/scripts/build_data_api.py`, `load_public_data.py` and `load_ui_data.py`
  - `rain-api/ui_data_v3.py`, `chat_v3.py`, `ultra_v3_api.py`, `persona_queries_v3.py`, `data_api_v3.py` and `main.py`
  - `frontend/rain-app/docs/backend-integration.md`
  - `doc/queries/` (the v3 query packs and reports) and `doc/DOCKER.md`
- Helper scripts from the v0.3 run may still be in `C:\Users\pa613\AppData\Local\Temp\claude\59345a982d4c6517\a5aef08b-f435-4eaa-9d45-d6086d3eade8\scratchpad`:
  - `factory_v3.py`, `publish_v3_kag.py`
  - `validate_ui_v3.py`, `crawl_personas.mjs`, `chat_queries_browser.mjs`, `crawl_api_logs.mjs`, `public_ui_browser.mjs`
  - `demo_data_driven.py`, `run_sql_pack.py`, `run_cypher.py`

  Copy whatever you reuse into the new repo under `scripts/e2e/`, so v0.4 does not depend on a temp folder. If they are gone, rewrite them from the descriptions in the v3 reports.

## Phase 0: new folder

1. In `C:\Users\pa613\RAIN`, commit the uncommitted v0.3 work, the v0.4 PRD files in `doc/prd/` and this prompt on `RAIN3.0-DIF_BT_integration`. I approve this commit. Do not push.
2. Run `git worktree add C:\Users\pa613\RAIN4.0-DIF_BT_integration -b RAIN4.0-DIF_BT_integration`, then work only in that folder.
3. Copy the gitignored inputs from `C:\Users\pa613\RAIN`:
   - `rain-api/.env`
   - `apps/keys.local.yaml`
   - `deploy/initdb/`
   - `.data/public/`
   - `dif/artifacts/store.py`, which was never committed
4. Convert `deploy/backend/entrypoint.sh` to LF and add `*.sh text eol=lf` to `.gitattributes`. With `autocrlf=true` the file checks out as CRLF and the backend crash-loops.
5. Check free space on C: first. A full C: hangs Docker.

## Phase 1: factory inputs

- Read the docx. It is the human reference; the factory never reads it.
- Write `doc/prd/RAIN_Platform_PRD_v0.4_factory_extract.txt`, following the no-LLM grammar in `knowledge-gathering/README.md` exactly.
- Write `doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql`:
  - one table for each planned entity in PRD Section 9: the v0.3 tables plus `rpm_reading`, `risk_score` and `no_show_rate`, which is now modelled;
  - plus whatever Sections 6 and 7 need that v0.3 lacked, such as front-desk inbox items, RHTP reporting by county and grantees;
  - a `-- source: <feed>` comment on every table.
- Mention every table in the extract.

## Phase 2: factory run and KAG

- Run `dif-build-orchestrator` with release `rain-v4.0.0` and package `4.0.0`, the way `factory_v3.py` did. Run it in a helper container on the rain4 network with the repo mounted.
- Precheck must pass with no orphan classes, and reconciliation must leave no table unmapped.
- Copy the package to `artifacts/RAIN_Knowledge_Package_v4.0.0/`.
- Publish to the rain4 Neo4j, then run `neo4j-validate`. Neo4j Community has only the database `neo4j`, so publish there under release `rain-v4.0.0`.
- Write `knowledge-gathering/seeds/rain_v4_prd_seed.py` from the v3 seed. Cover:
  - all 14 personas, with Hannah Lee marked phase 2, and their signals, KPIs and questions;
  - all 12 workbenches and their access rules;
  - use cases A and B and the hand-off;
  - the contract checkpoint, the quality gate and its measures, and the segments.
- Run the seed. `MATCH (p:Persona) RETURN p` must return 14 nodes. Query by label: `RETURN n LIMIT 300` shows only Columns.
- Add the v0.4 row to the knowledge-gathering README.

## Phase 3: Postgres `rain_v4` with all public data

- Create database `rain_v4` in the rain4 Postgres, with schemas `synthetic`, `public_data` and `ui_v4`.
- Public data must cover every public source in PRD Section 9. `.data/public` has 7 today: CDC PLACES, SVI, HRSA HPSA, HRSA sites, NPPES, RUCC and the ZCTA gazetteer.
- Download the rest for Nevada and Tennessee:
  - FCC National Broadband Map
  - Census ACS 5-year
  - HRSA FORHP rural areas
  - Census ZCTA-county relationship and cartographic boundaries
  - CMS Hospital General Information
  - CMS Provider of Services
  - HRSA UDS
  - CMS Medicare Geographic Variation
  - the County Health Rankings archive
  - CMS eCQM specs
  - OSM-derived drive times
- Record the URL, release, download date and row count for each source in `.data/public/MANIFEST.md`.
- Extend `load_public_data.py`, then load everything into `public_data`.
- Some sources need an account, a key or a licence (ACS API key, FCC bulk API, UMLS/VSAC, CPT). Stop and ask me. Never fake or stub them.
- Synthetic data: run `build_data_api.py` with:
  - the v0.4 extract and DDL;
  - `PG_DB=rain_v4`;
  - `--api-out rain-api/data_api_v4.py --mount /api/v4/data --db-env PG_DB_V4 --db-default rain_v4 --tag data-v4`.
- Keys must join across tables, and every synthetic value must be labelled synthetic.

## Phase 4: backend (`rain-api`, under `/api/v4`)

- Build these from the v3 files:
  - `ui_data_v4.py`: `GET /api/v4/ui/data`, reading `rain-api/seed/rain_v4_ui_data.json` (loaded into `ui_v4.dataset` by `load_ui_data.py`), with the live public-data overlay
  - `chat_v4.py`: every persona's briefing and answers built per request from Postgres
  - `ultra_v4_api.py`: personas, briefing and ask
  - `persona_queries_v4.py`: `/api/v4/queries`
- Contracts:
  - the 6 v0.3 personas carry over;
  - write new ones from PRD Section 6 for Hargrove, Bell, Holloway, Brooks and Okafor, and for the Rosa Martínez SMS and voice flow;
  - base every number on the Q3 contract checkpoint. Use none of the v0.2 200-patient figures.
- Query pack `doc/queries/rain_v4_persona_queries.sql`: 5 synthetic and 5 public queries per persona, for all 13 MVP personas (patients get self-scoped queries). Each must be answerable in the chat by id or by question text.
- Mount everything in `main.py` with the proof headers: X-RAIN-Source, -Request-Id, -Data-Source, -Data-Sha256, -Turn, -Query-Id, -Rows and Server-Timing. `/api/v3` must keep working.
- Write tests that mirror the v3 ones: build equivalence, a live Postgres edit, queries in the chat, the persona queries and the UI data.

## Phase 5: frontend (`frontend/rain-app`)

- Add the 6 v0.2 personas with `scaffold-persona`, and use the persona switcher order from PRD Section 7.
- Build:
  - site-scoped workbenches
  - RHTP Reporting, fully built
  - Front-desk inbox and Pre-visit Summary, with representative content
  - Rosa's patient view
- Point Ultra http mode at `/api/v4/ui` and the boot loader at `/api/v4/ui/data`.
- No data literals in components. The console proof channel logs every API call and each page's datasets.
- `npm run check` must pass.

## Phase 6: run it

- Check the ports are free, then always run: `FRONTEND_PORT=8184 BACKEND_PORT=8003 PG_HOST_PORT=55436 NEO4J_HTTP_PORT=17477 NEO4J_BOLT_PORT=17690 docker compose -p rain4 up -d --build`. Without those variables the stack collides with the other RAIN stacks.
- Add a standalone pgAdmin for `rain_v4` on port 5052, like `rain3-pgadmin`, with its server preconfigured.

## Phase 7: validate end to end

Fix whatever fails and rerun until everything is green.

- All backend tests pass.
- Every scripted question, chip and follow-up for every persona reaches its answer through `POST /api/v4/ui/ask`.
- In a real browser (playwright-core with the installed Chrome at `C:/Program Files/Google/Chrome/Application/chrome.exe`):
  - every briefing, chip and sidebar page works for every persona;
  - every persona query typed in the chat renders a live table;
  - there are no console errors, and the console shows the backend source line for each call.
- Every `public_data` table can be queried through `/api/v4/data` and appears in at least one UI view or persona query. List any that don't.
- Data-driven proof: edit one contract answer in Postgres, see it in the UI without a restart, then restore it.
- Neo4j has 14 Persona nodes under release `rain-v4.0.0`.

## Phase 8: docs

- In `doc/queries/`:
  - `RAIN_v4_persona_queries.md` and `.sql`
  - `rain_v4_persona_graph.cypher`
  - `RAIN_v4_validation_report.md`
  - `RAIN_v4_public_data_in_ui.md`
  - `RAIN_v4_backend_data_proof.md`
  - `RAIN_v4_chat_end_to_end_check.md`
- Update `doc/DOCKER.md` and `frontend/rain-app/docs/backend-integration.md`.

## Finish

Report:
- the UI, API docs, pgAdmin and Neo4j URLs, and the login;
- the results table;
- open gaps: missing public sources and credentials still needed;
- what is still uncommitted.

Commit on `RAIN4.0-DIF_BT_integration` only when I ask. Never push.

## Known traps from the v0.3 run

- The v3 seed hard-codes Neo4j database `rain-v3`, which Community cannot create. Use `neo4j`.
- nginx must keep `resolver 127.0.0.11` and `set $backend`, or the frontend returns 502 after the backend is recreated.
- Long Python in bash heredocs breaks, and complex `$$` or `$()` quoting is blocked. Write scripts to files and run them.
- HPSA "whole county" comes from HRSA component type `Single County`, not a population ratio.
- The frontend audit allows `console` only in `core/log.ts`, and forbids wall-clock reads and hex colours in components.
- A Docs export or any PDF/DOCX render cannot be checked visually here: there is no LibreOffice, Word or poppler.
